"""Design-only static publishing. Test roots are explicit, never inferred."""

from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def validate_evidence_zip(path, root):
    """Only reviewed case-addressed archives; verify without extracting to disk."""
    import zipfile
    import stat
    from pathlib import PurePosixPath
    path,root=Path(path),Path(root)
    rel=path.relative_to(root).as_posix()
    match=re.fullmatch(r'cases/(e203|aes_cipher_system_hard|aes_inv_cipher_top_system|sdc_controller_system)/evidence/([a-f0-9]{64})\.zip',rel)
    if not match or path.stat().st_size>64*1024**2 or digest(path)!=match[2]:raise ValueError('Invalid evidence archive path/hash')
    cid=match[1]
    bundle=json.loads((root/'cases'/cid/'manifest.json').read_text())
    index=bundle.get('evidence_packages',{})
    if any(k!=v.get('validation_id') or v.get('kind')!='single' or v.get('before_validation_id') for k,v in index.get('single',{}).items()):raise ValueError('Evidence single index mismatch')
    if any(v.get('kind')!='comparison' or not v.get('before_validation_id') or v['before_validation_id']==v.get('validation_id') for v in index.get('comparisons',[])):raise ValueError('Evidence comparison index mismatch')
    descriptors=list(index.get('single',{}).values())+index.get('comparisons',[])
    descriptor=next((d for d in descriptors if d.get('url')=='/'+rel),None)
    if not descriptor or descriptor.get('sha256')!=match[2] or descriptor.get('size_bytes')!=path.stat().st_size:raise ValueError('Evidence index mismatch')
    try:
        with zipfile.ZipFile(path) as archive:
            infos=archive.infolist();names=[i.filename for i in infos]
            if len(infos)>128 or len(set(names))!=len(names) or sum(i.file_size for i in infos)>64*1024**2:raise ValueError('Evidence archive budget/duplicates')
            for i in infos:
                n=i.filename
                if n.startswith('/') or '\\' in n or ':' in n or any(p in {'','..','.'} for p in n.split('/')) or stat.S_ISLNK(i.external_attr>>16) or i.flag_bits&1:raise ValueError('Unsafe evidence entry')
                if Path(n).suffix not in {'.json','.txt','.md','.v','.sv','.vh','.svh'}:raise ValueError('Private evidence file type')
            if 'manifest.json' not in names or archive.getinfo('manifest.json').file_size>1024**2:raise ValueError('Missing/oversized evidence manifest')
            m=json.loads(archive.read('manifest.json'))
            if m.get('schema_version')!='rtl-demo-evidence-v1' or any(m.get(k)!=bundle.get(k) for k in ['case_id','bundle_id','source_fingerprint']):raise ValueError('Evidence source mismatch')
            if m.get('selection')!={k:descriptor[k] for k in ['kind','validation_id','before_validation_id'] if k in descriptor}:raise ValueError('Evidence selection mismatch')
            files=m['files'];by_name={f['archive_path']:f for f in files}
            if len(by_name)!=len(files) or set(by_name)!=set(names)-{'manifest.json'}:raise ValueError('Evidence file list mismatch')
            vals={v['validation_id']:v for v in bundle['validations']};versions={v['version_id']:v for v in bundle['versions']}
            for v in m['validations']:
                original=vals.get(v['validation_id'])
                if not original or any(v.get(k)!=original.get(k) for k in ['run_id','version_id','kind','verdict','waveform_sha256','total_samples','mismatched_samples']):raise ValueError('Evidence validation mismatch')
            expected_ids={descriptor['validation_id']}|({descriptor['before_validation_id']} if descriptor.get('before_validation_id') else set())
            if {v['validation_id'] for v in m['validations']}!=expected_ids:raise ValueError('Evidence validations not selected')
            for v in m['versions']:
                original=versions.get(v['version_id'])
                if not original or any(v.get(k)!=original.get(k) for k in ['run_id','tree_sha256','file_manifest']):raise ValueError('Evidence version mismatch')
                for f in v['file_manifest']:
                    entry=by_name.get('versions/'+v['version_id']+'/rtl/'+f['path'])
                    if not entry or entry['archive_sha256']!=f['sha256']:raise ValueError('Incomplete tested RTL')
            selected_versions={v['version_id'] for v in m['validations']}
            if len(m['validations'])!=len(expected_ids) or {v['version_id'] for v in m['versions']}!=selected_versions:raise ValueError('Unexpected evidence entities')
            public_artifacts={a['artifact_id']:a for a in bundle.get('artifacts',[]) if a.get('exposure')=='display'}
            for name,f in by_name.items():
                role=f.get('role')
                if name=='README.txt':
                    if role!='readme':raise ValueError('Invalid README role')
                    continue
                source=public_artifacts.get(f.get('artifact_id'))
                if not source or source.get('kind')!=role or source['sha256']!=f.get('source_artifact_sha256'):raise ValueError('Unreviewed evidence source')
                if role=='spec':valid=name=='spec/specification.md' and f['artifact_id']==bundle['spec_artifact_id']
                elif role=='planning':valid=name=='planning/repo_skeleton.json' and f['artifact_id']==bundle['planner_artifact_id']
                elif role=='rtl':valid=name in {'versions/'+v['version_id']+'/rtl/'+x['path'] for v in m['versions'] for x in v['file_manifest']}
                elif role=='report':valid=any(name=='validations/'+v['validation_id']+'/report.txt' and f['artifact_id']==vals[v['validation_id']]['report_artifact_id'] for v in m['validations'])
                elif role=='waveform':valid=any(name=='validations/'+v['validation_id']+'/waveform/index.json' and f['artifact_id'] in {vals[v['validation_id']].get('waveform_index_artifact_id'),vals[v['validation_id']].get('waveform_artifact_id')} for v in m['validations'])
                elif role=='waveform_tile':valid=any(re.fullmatch(r'validations/'+re.escape(v['validation_id'])+r'/waveform/tiles/[0-9]{4}\.json',name) and f['artifact_id'] in vals[v['validation_id']].get('waveform_tile_artifact_ids',[]) for v in m['validations'])
                else:valid=False
                if not valid:raise ValueError('Unapproved evidence entry layout')
                if role in {'rtl','report','spec','planning'} and f['archive_sha256']!=source['sha256']:raise ValueError('Evidence bytes differ from public source')
            for i in infos:
                h=hashlib.sha256();tail=b''
                with archive.open(i) as source:
                    for block in iter(lambda:source.read(65536),b''):
                        h.update(block);data=tail+block
                        if re.search(rb'sk-[A-Za-z0-9_-]{16,}|-----BEGIN .*PRIVATE KEY-----|/(?:home|tmp|etc|srv|opt|run/user|var)/[^\s"<>]+',data):raise ValueError('Private content in evidence archive')
                        tail=data[-512:]
                if i.filename in by_name and (h.hexdigest()!=by_name[i.filename]['archive_sha256'] or i.file_size!=by_name[i.filename]['size_bytes']):raise ValueError('Evidence entry hash mismatch')
    except (zipfile.BadZipFile,KeyError,TypeError,json.JSONDecodeError):raise ValueError('Invalid evidence archive') from None


def files(root):
    result = []
    for p in sorted(root.rglob("*")):
        if p.is_symlink():
            raise ValueError("Symlink in release")
        if p.is_file():
            name = p.relative_to(root).as_posix()
            if name == "release.json":
                continue
            if any(
                x.startswith(".") or x in {"codex_private", "node_modules"}
                for x in p.relative_to(root).parts
            ):
                raise ValueError("Private or development file in release")
            if p.suffix == ".zip":
                validate_evidence_zip(p,root)
            elif p.suffix not in {
                ".html",
                ".js",
                ".css",
                ".json",
                ".svg",
                ".png",
                ".ico",
                ".woff2",
                ".txt",
            }:
                raise ValueError("Unexpected release file")
            result.append({"path": name, "sha256": digest(p)})
    return result


def stage(dist, staging, release_id, dry_run=False):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", release_id):
        raise ValueError("Invalid release ID")
    dist = dist.resolve()
    target = staging / release_id / "design"
    if target.exists():
        raise ValueError("Release already exists")
    manifest = files(dist)
    if (
        not (dist / "index.html").is_file()
        or not (dist / "cases/e203/manifest.json").is_file()
    ):
        raise ValueError("Full dist and E203 bundle required")
    bundles = {}
    index = dist / "cases/index.json"
    if index.is_file():
        for case in json.loads(index.read_text())["cases"]:
            cid = case["case_id"]
            if not re.fullmatch(r"[a-z0-9_]+", cid):
                raise ValueError("Invalid case ID")
            entry = dist / "cases" / cid / "manifest.json"
            if not entry.is_file():
                raise ValueError("Missing case manifest: " + cid)
            bundles[cid] = json.loads(entry.read_text())["bundle_id"]
    repo = Path(__file__).resolve().parents[2]
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    package_lock = repo / "web/rtl-demo/package-lock.json"
    meta = {
        "release_id": release_id,
        "source_revision": revision,
        "source_dirty": bool(
            subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=normal"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            ).stdout
        ),
        "package_lock_sha256": digest(package_lock),
        "bundle_id": json.loads((dist / "cases/e203/manifest.json").read_text())[
            "bundle_id"
        ],
        "bundle_ids": bundles,
        "files": manifest,
    }
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(dist, target)
        (target / "release.json").write_text(json.dumps(meta, indent=2) + "\n")
    return {
        "action": "stage",
        "release_id": release_id,
        "target": str(target),
        "file_count": len(manifest),
        "dry_run": dry_run,
    }


def checked(root):
    if root.is_symlink():
        raise ValueError("Symlink release root")
    data = json.loads((root / "release.json").read_text())
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", data.get("release_id", "")):
        raise ValueError("Invalid release ID")
    if data["files"] != files(root):
        raise ValueError("Release manifest mismatch")
    return data


def atomic_copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".release-", dir=dst.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(src.read_bytes())
        os.chmod(tmp, 0o644)
        os.replace(tmp, dst)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def install(
    source,
    *,
    base=Path("/srv/deepvalleychip"),
    dry_run=False,
    rollback=False,
    test_root=False,
):
    if not test_root and base != Path("/srv/deepvalleychip"):
        raise ValueError("Only approved design root is supported")
    if not test_root and os.geteuid() != 0:
        raise ValueError("Root required for production static install")
    # Every ancestor is checked before resolving. Never follow a design/assets symlink.
    for parent in [base, *base.parents]:
        if parent.is_symlink():
            raise ValueError("Symlink service path")
    dest = base / "design"
    if dest.is_symlink():
        raise ValueError("Symlink design root")
    if dest.exists():
        for p in dest.rglob("*"):
            if p.is_symlink():
                raise ValueError("Symlink in existing design")
    meta = checked(source)
    backup = (
        base / "rtl-demo-backups" / (str(time.time_ns()) + "-" + meta["release_id"])
    )
    changed = {"index.html", "cases/index.json", "release.json"}
    changed.update(
        f["path"]
        for f in meta["files"]
        if re.fullmatch(r"cases/[a-z0-9_]+/manifest\.json", f["path"])
    )
    for entry in meta["files"]:
        name = entry["path"]
        p = dest / name
        if name not in changed and p.is_file() and digest(p) != entry["sha256"]:
            raise ValueError("Immutable asset collision: " + name)
    if not dry_run:
        if dest.exists():
            backup.mkdir(parents=True, exist_ok=False)
            shutil.copytree(dest, backup / "design")
            prior = backup / "design" / "release.json"
            previous = (
                json.loads(prior.read_text())
                if prior.is_file()
                else {"release_id": "legacy"}
            )
            previous["files"] = files(backup / "design")
            prior.write_text(json.dumps(previous, indent=2) + "\n")
        dest.mkdir(parents=True, exist_ok=True)
        # Immutable content first; current bundle pointer, then index are atomic file replacements.
        ordered = sorted(
            meta["files"],
            key=lambda f: (
                (2 if f["path"] == "index.html" else 1 if f["path"] in changed else 0),
                f["path"],
            ),
        )
        for entry in ordered:
            atomic_copy(source / entry["path"], dest / entry["path"])
        atomic_copy(source / "release.json", dest / "release.json")
    return {
        "action": "rollback" if rollback else "install",
        "release_id": meta["release_id"],
        "target": str(dest),
        "backup": str(backup / "design"),
        "dry_run": dry_run,
    }


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("stage")
    a.add_argument("dist", type=Path)
    a.add_argument("staging", type=Path)
    a.add_argument("release_id")
    a.add_argument("--dry-run", action="store_true")
    a = sub.add_parser("install")
    a.add_argument("release", type=Path, nargs="?")
    a.add_argument("--rollback", type=Path)
    a.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    try:
        if args.command == "stage":
            result = stage(args.dist, args.staging, args.release_id, args.dry_run)
        else:
            source = args.rollback or args.release
            if not source:
                raise ValueError("Specify release or backup design directory")
            result = install(source, dry_run=args.dry_run, rollback=bool(args.rollback))
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError, KeyError) as error:
        p.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
