#!/usr/bin/env python3
"""Move stale root wiki/experiment process documents into a local dated archive.

The tracked surface intentionally retains current conclusions, machine indexes and task code.
Run this from the repository root every milestone; the default retention window is three days.
The archive is ignored by git and is for bounded historical lookup only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import shutil
from pathlib import Path

KEEP_WIKI = {"CURRENT-CONCLUSIONS.md", "README.md"}
KEEP_EXPERIMENTS = {
    "README.md",
    "manifest.json",
    "build_tasks.py",
    "REFERENCE-BASELINE-MATRIX-2026-10-31.json",
    "REFERENCE-BASELINE-INCREMENT-2026-10-31.json",
}


def candidates(root: Path, name: str, keep: set[str], cutoff: float):
    directory = root / name
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.name in keep:
            continue
        if path.stat().st_mtime < cutoff:
            yield path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--older-than-days", type=float, default=3.0)
    parser.add_argument("--date", default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.older_than_days)).timestamp()
    archive = args.root / ".local" / "archive" / args.date
    moves = list(candidates(args.root, "wiki", KEEP_WIKI, cutoff))
    moves += list(candidates(args.root, "experiments", KEEP_EXPERIMENTS, cutoff))
    for source in moves:
        target_dir = archive / source.parent.name
        target = target_dir / source.name
        print(f"{source} -> {target}")
        if not args.dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
