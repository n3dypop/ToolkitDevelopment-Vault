#!/usr/bin/env python3
"""Check portable Markdown structure, links, and public path hygiene."""

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

LINK = re.compile(r"!?(?<!\\)\[[^\]]*\]\(([^)]+)\)")
ABSOLUTE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:\\|/(?:Users|home|private|Volumes|mnt|tmp|var)/")


def inspect_markdown(root):
    errors, graph, active = [], {}, set()
    files = sorted(path for path in root.rglob("*.md") if ".git" not in path.relative_to(root).parts)
    for path in files:
        relative = path.relative_to(root)
        try:
            content = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as error:
            errors.append(f"{relative}: unreadable UTF-8 Markdown ({type(error).__name__})")
            continue
        lines = content.splitlines()
        if content.startswith("---\n") and re.search(r"^status: active$", content.split("---", 2)[1], re.M):
            active.add(path)
        h1, fence, visible = 0, None, []
        for number, line in enumerate(lines, 1):
            if re.search(r"[ \t]+$", line):
                errors.append(f"{relative}:{number}: trailing whitespace")
            if ABSOLUTE.search(line):
                errors.append(f"{relative}:{number}: machine-specific absolute path")
            marker = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
            if marker:
                token, suffix = marker.groups()
                if fence is None:
                    fence = token
                elif token[0] == fence[0] and len(token) >= len(fence) and not suffix.strip():
                    fence = None
                continue
            if fence is None:
                h1 += line.startswith("# ")
                visible.append(line)
        if fence is not None:
            errors.append(f"{relative}: unclosed code fence")
        if h1 != 1:
            errors.append(f"{relative}: expected exactly one H1, found {h1}")
        graph[path] = set()
        for match in LINK.finditer("\n".join(visible)):
            target = match.group(1).strip().strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or not parsed.path:
                continue
            resolved = (path.parent / unquote(parsed.path)).resolve()
            if not resolved.is_relative_to(root):
                errors.append(f"{relative}: link escapes vault")
            elif not resolved.exists():
                errors.append(f"{relative}: broken link '{target}'")
            elif resolved.suffix.lower() == ".md":
                graph[path].add(resolved)
    reached, pending = set(), [root / "HOME.md"]
    while pending:
        path = pending.pop()
        if path not in reached:
            reached.add(path)
            pending.extend(graph.get(path, ()))
    for path in sorted(active - reached):
        errors.append(f"{path.relative_to(root)}: active document is unreachable from HOME.md")
    return files, errors


def main():
    if sys.version_info < (3, 11):
        print("error: Python 3.11 or later is required.", file=sys.stderr)
        return 1
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", "-WorkspaceRoot")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    files, errors = inspect_markdown(root)
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        return 1
    workspace = args.workspace_root
    if workspace is None and root.parent.name.casefold() == "toolkit" and (root.parent / "AGENTS.md").exists():
        workspace = str(root.parent)
    if workspace:
        command = (["pwsh", "-NoProfile", "-File", str(root / "scripts/sync-agents.ps1")] if os.name == "nt" else
                   ["sh", str(root / "scripts/sync-agents.sh")])
        if workspace:
            command.extend(["-WorkspaceRoot", workspace])
        result = subprocess.run(command, check=False)
        if result.returncode:
            return result.returncode
    print(f"Vault check passed: {len(files)} Markdown files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
