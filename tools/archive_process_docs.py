#!/usr/bin/env python3
"""Archive untracked process documents older than three days; never recurse into runs."""
from __future__ import annotations
import argparse
import datetime as dt
import fcntl
import json
import math
import os
from pathlib import Path
import subprocess

SCOPES = ("wiki", "experiments", ".local/reports")
KEEP = {"readme.md", "current-conclusions.md", "status-latest.md", "template.md"}


def tracked_files(root):
    result = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                            check=True, capture_output=True)
    return {os.fsdecode(p) for p in result.stdout.split(b"\0") if p}


def candidates(root, cutoff, tracked):
    for scope in SCOPES:
        directory = root / scope
        if not directory.is_dir() or any(p.is_symlink() for p in (directory, *directory.parents)):
            continue
        for path in sorted(directory.iterdir()):
            name = path.name.lower()
            if path.is_symlink() or not path.is_file() or name in KEEP:
                continue
            if "latest" in name or "current" in name or "prereg" in name:
                continue
            if str(path.relative_to(root)) in tracked:
                continue
            # JSON may be an executable dependency: only dated monitoring
            # snapshots in the local report directory are automatically eligible.
            eligible = path.suffix.lower() in (".md", ".txt")
            if scope == ".local/reports" and path.suffix == ".json":
                eligible = path.name.startswith(("training-status-", "npu-batched-status-"))
            if eligible and path.stat().st_mtime < cutoff:
                yield path


def archive(root, days=3, date=None, dry_run=False):
    root = root.resolve()
    if not math.isfinite(days) or days < 3:
        raise ValueError("retention must be at least three days")
    today = dt.date.fromisoformat(date) if date else dt.datetime.now(dt.timezone.utc).date()
    cutoff = dt.datetime.now(dt.timezone.utc).timestamp() - days * 86400
    local = root / ".local"
    local.mkdir(exist_ok=True)
    if local.is_symlink():
        raise ValueError("symlink local root")
    result = {"utc": dt.datetime.now(dt.timezone.utc).isoformat(), "dry_run": dry_run,
              "retention_days": days, "moved": [], "collisions": []}
    with (local / "archive.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        tracked = tracked_files(root)
        for source in candidates(root, cutoff, tracked):
            relative = source.relative_to(root)
            target = local / "archive" / today.isoformat() / relative
            if any(p.is_symlink() for p in (target, *target.parents)):
                raise ValueError("symlink archive destination")
            entry = {"source": str(relative), "target": str(target.relative_to(root))}
            if target.exists():
                result["collisions"].append(entry)
                continue
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                # Exclusive hard link prevents collision overwrites; a crash
                # before unlink leaves both copies, never loses the document.
                os.link(source, target, follow_symlinks=False)
                source.unlink()
            result["moved"].append(entry)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--older-than-days", type=float, default=3)
    parser.add_argument("--date")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--status", type=Path)
    args = parser.parse_args()
    result = archive(args.root, args.older_than_days, args.date, args.dry_run)
    text = json.dumps(result, indent=2) + "\n"
    if args.status:
        args.status.parent.mkdir(parents=True, exist_ok=True)
        pending = args.status.with_suffix(".pending")
        pending.write_text(text)
        pending.replace(args.status)
    print(text, end="")


if __name__ == "__main__":
    main()
