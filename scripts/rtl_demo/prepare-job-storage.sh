#!/usr/bin/env bash
set -euo pipefail
# Fixed, separate filesystem; never repartition or format an existing volume.
dry_run=false
case "${1:-}" in --dry-run) dry_run=true;; "") ;; *) echo 'Usage: prepare-job-storage.sh [--dry-run]' >&2; exit 2;; esac
image=/var/lib/rtl-demo-jobs.ext4
mount_dir=/var/lib/rtl-demo/jobs
if $dry_run; then
    echo 'Prepare 8192MiB dedicated ext4 image and mount only /var/lib/rtl-demo/jobs; preserve existing evidence. No changes made.'
    exit 0
fi
if [[ $(id -u) != 0 ]]; then echo 'Root required for the reviewed job volume setup.' >&2; exit 5; fi
if mountpoint -q "$mount_dir"; then echo 'Job volume already mounted; verify capacity before use.'; exit 0; fi
if [[ -e "$image" || -L "$mount_dir" || -L "$image" ]]; then echo 'Existing/unapproved volume; refusing to overwrite.' >&2; exit 3; fi
if [[ -d "$mount_dir" && -n $(find "$mount_dir" -mindepth 1 -maxdepth 1 -print -quit) ]]; then echo 'Job directory is not empty; manual migration required.' >&2; exit 3; fi
available_kib=$(df -Pk /var/lib | awk 'NR==2 {print $4}')
if (( available_kib < 13631488 )); then echo 'Need 8GiB allocation plus 5GiB host free space.' >&2; exit 4; fi
install -d -m 0700 /var/lib/rtl-demo "$mount_dir"
fallocate -l 8192M "$image"
chmod 0600 "$image"
mkfs.ext4 -q -F "$image"
mount -o loop,nosuid,nodev "$image" "$mount_dir"
chown rtl-demo:rtl-demo "$mount_dir"
chmod 0700 "$mount_dir"
echo 'Job volume prepared. Install the reviewed mount unit for boot persistence.'
