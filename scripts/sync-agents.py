#!/usr/bin/env python3
"""Explicit, byte-preserving synchronization of the canonical AGENTS.md."""

import argparse
import hashlib
import os
from pathlib import Path
import stat
import sys
import tempfile
import uuid

MODES = ("Check", "RepoToWorkspace", "WorkspaceToRepo")


def read_agents(path, missing_ok=False):
    try:
        info = path.lstat()
    except FileNotFoundError:
        if missing_ok:
            return None
        raise ValueError(f"AGENTS.md is missing: {path}") from None
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError(f"Expected a regular, unlinked file: {path}")
    data = path.read_bytes()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError(f"Expected UTF-8 text: {path}") from None
    if not text.strip() or "\x00" in text:
        raise ValueError(f"Expected nonempty instruction text: {path}")
    return data


def fingerprint(data):
    return "missing" if data is None else hashlib.sha256(data).hexdigest()


def target_file(root):
    root = Path(root).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"Target root is not a directory: {root}")
    return root / "AGENTS.md"


def replace_file(path, data, expected):
    """Back up old bytes, then atomically replace the destination."""
    if read_agents(path, missing_ok=True) != expected:
        raise ValueError(f"File changed during synchronization: {path}")
    mode = stat.S_IMODE(path.stat().st_mode) if expected is not None else 0o644
    backup = None
    if expected is not None:
        backup = path.with_name(f"AGENTS.md.sync-{uuid.uuid4().hex}.bak")
        with backup.open("xb") as output:
            output.write(expected)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(backup, mode)
    fd, name = tempfile.mkstemp(prefix=".AGENTS.md.sync-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, mode)
        if read_agents(path, missing_ok=True) != expected:
            raise ValueError(f"File changed during synchronization: {path}")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    if path.read_bytes() != data:
        raise ValueError(f"Post-write verification failed: {path}")
    return backup


def synchronize(repo_root, mode, workspace_root=None, dry_run=False):
    repo = target_file(repo_root)
    if workspace_root is None:
        candidate = repo.parent.parent
        if candidate.name.casefold() != "toolkit":
            raise ValueError("Repository is not directly under Toolkit; specify --workspace-root.")
        workspace_root = candidate
    workspace = target_file(workspace_root)
    if repo == workspace:
        raise ValueError("Repository and workspace targets must be distinct.")
    states = {path: read_agents(path, missing_ok=True) for path in (repo, workspace)}
    if mode == "Check":
        source = read_agents(repo)
        same = states[workspace] == source
        print(f"workspace: {'in-sync' if same else 'out-of-sync'} SHA256={fingerprint(states[workspace])}")
        if not same:
            raise ValueError("AGENTS.md drift detected; choose a synchronization direction explicitly.")
        return
    source_path, destination = ((workspace, repo) if mode == "WorkspaceToRepo" else (repo, workspace))
    data = read_agents(source_path)
    if states[destination] == data:
        print(f"unchanged: {destination}")
        return
    if dry_run:
        print(f"would copy: {source_path} -> {destination}; previous SHA256={fingerprint(states[destination])}")
        return
    if read_agents(source_path) != data:
        raise ValueError(f"Source changed during synchronization: {source_path}")
    backup = replace_file(destination, data, states[destination])
    print(f"copied: {source_path} -> {destination}; SHA256={fingerprint(data)}")
    if backup is not None:
        print(f"backup: {backup}")


def main():
    if sys.version_info < (3, 11):
        print("error: Python 3.11 or later is required.", file=sys.stderr)
        return 1
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", "-Mode", choices=MODES, default="Check")
    parser.add_argument("--workspace-root", "-WorkspaceRoot")
    parser.add_argument("--dry-run", "-DryRun", action="store_true")
    args = parser.parse_args()
    try:
        synchronize(Path(__file__).resolve().parent.parent, args.mode,
                    args.workspace_root, args.dry_run)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
