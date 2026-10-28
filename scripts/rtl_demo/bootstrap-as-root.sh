#!/usr/bin/env bash
# Install only the reviewed, sealed RTL toolchain. Never modifies Caddy/CAD.
set -euo pipefail
release_dir=
dry_run=false
while (($#)); do
    case "$1" in
        --release) release_dir=${2:?Missing release directory}; shift 2;;
        --dry-run) dry_run=true; shift;;
        *) echo 'Usage: bootstrap-as-root.sh --release SEALED_RELEASE [--dry-run]' >&2; exit 2;;
    esac
done
[[ -n "$release_dir" ]] || { echo 'Missing --release' >&2; exit 2; }
lock_file="$release_dir/ops/deploy/rtl_demo/toolchain.lock.json"
[[ -f "$lock_file" && ! -L "$lock_file" ]] || { echo 'Missing reviewed toolchain lock' >&2; exit 3; }
if $dry_run; then
    echo 'Install pinned tools under /opt/rtl-agent/toolchain, using checksum-verified official archives and signed, version-pinned distribution packages.'
    echo 'No download, installation, service or configuration changes made.'
    exit 0
fi
[[ $(id -u) == 0 ]] || { echo 'Root required; hand the sealed candidate and preview to the maintainer.' >&2; exit 5; }
release_id=$(basename -- "$release_dir")
[[ "$release_id" =~ ^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$ && "$release_dir" == "/opt/rtl-agent/candidates/$release_id" ]] || { echo 'Use a plain release ID under /opt/rtl-agent/candidates' >&2; exit 3; }
for ancestor in /opt /opt/rtl-agent /opt/rtl-agent/candidates "$release_dir"; do
    [[ ! -L "$ancestor" && $(stat -c %u "$ancestor") == 0 ]] || { echo 'Untrusted candidate ancestor' >&2; exit 3; }
    ancestor_mode=$(stat -c %a "$ancestor")
    (( (8#$ancestor_mode & 8#022) == 0 )) || { echo 'Writable candidate ancestor' >&2; exit 3; }
done
[[ ! -L "$release_dir" ]] || { echo 'Symlink candidate rejected' >&2; exit 3; }
if [[ -n $(find "$release_dir" -type l -print -quit) || -n $(find "$release_dir" ! -user root -print -quit) || -n $(find "$release_dir" -perm /022 -print -quit) ]]; then
    echo 'Candidate must be root-owned, immutable to dev, and contain no symlinks.' >&2; exit 3
fi
install -d -m 0755 /opt/rtl-agent/toolchain /opt/rtl-agent/toolchain/bin
install -d -m 0700 /opt/rtl-agent/toolchain/downloads
# System Python is used ONLY for this 3.6-compatible JSON manifest reader.
manifest_list=$(mktemp)
package_list=$(mktemp)
trap 'rm -f "$manifest_list" "$package_list"' EXIT
python3 - "$lock_file" "$manifest_list" "$package_list" <<'PY'
import hashlib,json,os,re,stat,sys
from pathlib import Path,PurePosixPath
lock_path=Path(sys.argv[1]);release=lock_path.parents[3]
manifest=json.loads((release/'deployment.json').read_text())
listed=set()
for entry in manifest['files']:
    package=entry['package'];name=entry['target_relative_path']
    if package not in {'design','runtime','seed','verifier','ops'} or PurePosixPath(name).is_absolute() or any(p in {'','.','..'} for p in name.split('/')) or '\\' in name:
        raise ValueError('Unsafe manifest path')
    path=release/package/name
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink!=1:raise ValueError('Unsafe release entry')
    if path.stat().st_size!=entry['size_bytes'] or hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('Release digest mismatch')
    key=package+'/'+name
    if key in listed:raise ValueError('Duplicate manifest entry')
    listed.add(key)
actual={p.relative_to(release).as_posix() for p in release.rglob('*') if p.is_file() and p!=release/'deployment.json'}
if actual!=listed:raise ValueError('Release inventory mismatch')
lock=json.load(open(sys.argv[1]))
with open(sys.argv[2],'w') as out:
    for a in lock['artifacts']:
        if not re.match(r'^[a-z]+$',a['name']) or not re.match(r'^[A-Za-z0-9_.+-]{1,80}$',a['version']) or not a['url'].startswith('https://') or not re.match(r'^[0-9a-f]{64}$',a['sha256']):
            raise ValueError('Invalid locked tool')
        out.write('\t'.join([a['name'],a['version'],a['url'],a['sha256']])+'\n')
with open(sys.argv[3],'w') as out:
    for name,version in sorted(lock['system_packages'].items()):
        if not re.match(r'^[a-zA-Z0-9+_.-]+$',name) or not re.match(r'^[a-zA-Z0-9+_.:-]+$',version):raise ValueError('Invalid RPM lock')
        out.write(name+'-'+version+'\n')
PY
mapfile -t rpm_packages < "$package_list"
dnf -y --setopt=gpgcheck=1 install "${rpm_packages[@]}"
while IFS=$'\t' read -r artifact_name artifact_version artifact_url artifact_hash; do
    archive="/opt/rtl-agent/toolchain/downloads/$artifact_name-$artifact_version.archive"
    if [[ ! -f "$archive" ]]; then
        curl --fail --location --proto '=https' --tlsv1.2 "$artifact_url" -o "$archive.part"
        mv "$archive.part" "$archive"
    fi
    printf '%s  %s\n' "$artifact_hash" "$archive" | sha256sum -c -
    case "$artifact_name" in
        uv) destination=/opt/rtl-agent/toolchain/uv;;
        python) destination=/opt/rtl-agent/toolchain/python;;
        jre) destination=/opt/rtl-agent/toolchain/jre;;
        neo4j) destination=/opt/rtl-agent/toolchain/neo4j;;
        verilator) destination=/opt/rtl-agent/toolchain/verilator-source;;
        codex) destination=/opt/rtl-agent/toolchain/codex;;
        *) echo 'Unapproved tool component' >&2; exit 3;;
    esac
    if [[ -d "$destination" ]]; then
        [[ -f "$destination/.rtl-artifact-sha256" && $(cat "$destination/.rtl-artifact-sha256") == "$artifact_hash" ]] || { echo 'Tool directory has a different or incomplete version; review before replacement.' >&2; exit 3; }
    else
        temporary_dir=$(mktemp -d /opt/rtl-agent/toolchain/.extract-XXXXXX)
        if [[ "$artifact_name" == codex ]]; then
            tar --extract --gzip --no-same-owner --no-same-permissions --file "$archive" --directory "$temporary_dir"
        else
            tar --extract --gzip --no-same-owner --no-same-permissions --strip-components=1 --file "$archive" --directory "$temporary_dir"
        fi
        printf '%s\n' "$artifact_hash" > "$temporary_dir/.rtl-artifact-sha256"
        chmod 0755 "$temporary_dir"
        mv "$temporary_dir" "$destination"
    fi
done < "$manifest_list"
ln -sfn /opt/rtl-agent/toolchain/python/bin/python3.13 /opt/rtl-agent/toolchain/bin/python3.13
ln -sfn /opt/rtl-agent/toolchain/uv/uv /opt/rtl-agent/toolchain/bin/uv
install -m 0755 /opt/rtl-agent/toolchain/codex/codex-x86_64-unknown-linux-musl /opt/rtl-agent/toolchain/bin/codex
if [[ ! -x /opt/rtl-agent/toolchain/bin/verilator_bin ]]; then
    cd /opt/rtl-agent/toolchain/verilator-source
    autoconf
    ./configure --prefix=/opt/rtl-agent/toolchain
    make -j1
    make install
fi
/opt/rtl-agent/toolchain/bin/python3.13 --version
/opt/rtl-agent/toolchain/bin/verilator --version
/opt/rtl-agent/toolchain/bin/codex --version
/opt/rtl-agent/toolchain/jre/bin/java -version
