#!/bin/sh
# Synchronize the canonical AGENTS.md using standard macOS/Linux utilities.
set -eu

fail() { printf '%s\n' "error: $*" >&2; exit 1; }
usage() {
    printf '%s\n' 'Usage: sync-agents.sh [--mode Check|RepoToWorkspace|WorkspaceToRepo]' \
        '                      [--workspace-root DIRECTORY] [--dry-run]'
}

sync_mode=Check
sync_workspace=
sync_dry_run=false
while [ "$#" -gt 0 ]; do
    case $1 in
        --mode|-Mode)
            [ "$#" -ge 2 ] || fail 'Missing mode.'
            sync_mode=$2; shift 2 ;;
        --workspace-root|-WorkspaceRoot)
            [ "$#" -ge 2 ] && [ -n "$2" ] || fail 'Missing workspace directory.'
            sync_workspace=$2; shift 2 ;;
        --dry-run|-DryRun) sync_dry_run=true; shift ;;
        --help|-h) usage; exit 0 ;;
        *) fail "Unknown argument: $1" ;;
    esac
done
case $sync_mode in Check|RepoToWorkspace|WorkspaceToRepo) ;; *) fail 'Invalid synchronization mode.' ;; esac

for sync_required in cmp cp mv mktemp stat iconv grep sed tr uname dirname basename cat rm; do
    command -v "$sync_required" >/dev/null 2>&1 || fail "Required system command is unavailable: $sync_required"
done

sync_script_dir=$(CDPATH= cd -P -- "$(dirname -- "$0")" && pwd)
sync_repo_root=$(CDPATH= cd -P -- "$sync_script_dir/.." && pwd)
if [ -z "$sync_workspace" ]; then
    sync_workspace=$(dirname -- "$sync_repo_root")
    sync_parent_name=$(basename -- "$sync_workspace" | LC_ALL=C tr '[:upper:]' '[:lower:]')
    [ "$sync_parent_name" = toolkit ] || fail 'Repository is not directly under Toolkit; specify --workspace-root.'
fi
[ -d "$sync_workspace" ] || fail 'Workspace directory does not exist.'
sync_workspace=$(CDPATH= cd -P -- "$sync_workspace" && pwd)
[ "$sync_repo_root" != "$sync_workspace" ] || fail 'Repository and workspace targets must be distinct.'
sync_repo=$sync_repo_root/AGENTS.md
sync_copy=$sync_workspace/AGENTS.md
case $(uname -s) in
    Darwin) sync_stat_format=bsd ;;
    Linux) sync_stat_format=gnu ;;
    *) fail 'Use sync-agents.ps1 on Windows; this script supports macOS and Linux.' ;;
esac

validate_file() {
    [ ! -L "$1" ] || fail "Symbolic links are not supported: $1"
    if [ ! -e "$1" ]; then
        [ "$2" = optional ] || fail "AGENTS.md is missing: $1"
        return
    fi
    [ -f "$1" ] && [ -s "$1" ] || fail "Expected a nonempty regular file: $1"
    if [ "$sync_stat_format" = bsd ]; then
        sync_links=$(stat -f '%l' "$1")
    else
        sync_links=$(stat -c '%h' "$1")
    fi
    [ "$sync_links" = 1 ] || fail "Hard links are not supported: $1"
    iconv -f UTF-8 -t UTF-8 "$1" >/dev/null 2>&1 || fail "Expected UTF-8 text: $1"
    LC_ALL=C tr -d '\000' < "$1" | cmp -s - "$1" || fail "NUL bytes are not supported: $1"
    sync_bom=$(printf '\357\273\277')
    sed "1s/^$sync_bom//" "$1" | LC_ALL=C grep -q '[^[:space:]]' || fail "Expected nonempty instruction text: $1"
}

validate_file "$sync_repo" optional
validate_file "$sync_copy" optional
if [ "$sync_mode" = Check ]; then
    validate_file "$sync_repo" required
    validate_file "$sync_copy" required
    cmp -s "$sync_repo" "$sync_copy" || fail 'AGENTS.md drift detected; choose a direction explicitly.'
    printf '%s\n' 'AGENTS.md is synchronized (byte-identical).'
    exit 0
fi
if [ "$sync_mode" = RepoToWorkspace ]; then
    sync_source=$sync_repo; sync_destination=$sync_copy
else
    sync_source=$sync_copy; sync_destination=$sync_repo
fi
validate_file "$sync_source" required
if [ -f "$sync_destination" ] && cmp -s "$sync_source" "$sync_destination"; then
    printf 'unchanged: %s\n' "$sync_destination"
    exit 0
fi
if [ "$sync_dry_run" = true ]; then
    printf 'would copy: %s -> %s\n' "$sync_source" "$sync_destination"
    exit 0
fi

# Keep temporary files on the destination filesystem for a rename-based replacement.
sync_temp=$(mktemp -d "$(dirname -- "$sync_destination")/.agents-sync.XXXXXXXX")
trap 'rm -rf -- "$sync_temp"' 0
trap 'exit 130' INT
trap 'exit 143' HUP TERM
cp -p -- "$sync_source" "$sync_temp/source"
validate_file "$sync_temp/source" required
sync_had_destination=false
if [ -e "$sync_destination" ]; then
    sync_had_destination=true
    cp -p -- "$sync_destination" "$sync_temp/previous"
    cp -p -- "$sync_temp/previous" "$sync_temp/replacement"
    cat "$sync_temp/source" > "$sync_temp/replacement"
else
    cp -p -- "$sync_temp/source" "$sync_temp/replacement"
fi
validate_file "$sync_source" required
cmp -s "$sync_source" "$sync_temp/source" || fail 'Source changed during synchronization.'
validate_file "$sync_destination" optional
if [ "$sync_had_destination" = true ]; then
    [ -f "$sync_destination" ] && cmp -s "$sync_destination" "$sync_temp/previous" || fail 'Destination changed during synchronization.'
    sync_backup=$sync_destination.sync-${sync_temp##*.}.bak
    (umask 077; set -C; cat "$sync_temp/previous" > "$sync_backup") || fail 'Could not create the backup.'
    cmp -s "$sync_backup" "$sync_temp/previous" || fail 'Backup verification failed.'
    cmp -s "$sync_destination" "$sync_temp/previous" || fail 'Destination changed during synchronization.'
else
    [ ! -e "$sync_destination" ] && [ ! -L "$sync_destination" ] || fail 'Destination appeared during synchronization.'
fi
mv -f -- "$sync_temp/replacement" "$sync_destination"
cmp -s "$sync_temp/source" "$sync_destination" || fail 'Post-write verification failed.'
printf 'copied: %s -> %s\n' "$sync_source" "$sync_destination"
if [ "$sync_had_destination" = true ]; then printf 'backup: %s\n' "$sync_backup"; fi
