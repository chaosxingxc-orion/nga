"""Fast-forward owned refs only; never delete or overwrite team contributions."""

import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import time


SOURCE = "https://github.com/chaosxingxc-orion/nga.git"
TARGET = "https://gitcode.com/xingchao_ml/nga.git"


def git(*args, cwd=None, timeout=180):
    # Never invoke an interactive credential prompt or persist a supplied token.
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    return subprocess.run(
        ["git", "-c", "credential.helper=", "-c", "http.lowSpeedLimit=1024",
         "-c", "http.lowSpeedTime=60", *args],
        cwd=cwd, env=env, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
    ).stdout.strip()


def parse_refs(output):
    refs = {}
    for line in output.splitlines():
        oid, ref = line.split()
        if ref.startswith(("refs/heads/", "refs/tags/")):
            refs[ref] = oid
    return refs


def remote_refs(url):
    return parse_refs(git("ls-remote", "--refs", url, "refs/heads/*", "refs/tags/*", timeout=60))


def owned(ref):
    return ref == 'refs/heads/main' or ref.startswith(('refs/heads/github/', 'refs/tags/v'))


def push_arguments(source, target):
    """Git enforces fast-forward branches and immutable existing tags."""
    refspecs = []
    for ref in sorted(r for r in source if owned(r)):
        if source.get(ref) == target.get(ref):
            continue
        refspecs.append(f"{source[ref]}:{ref}")
    return [], refspecs


def sync_once(source_url, target_url):
    # A fresh fetch avoids replaying the triggering event's possibly stale commit.
    with tempfile.TemporaryDirectory(prefix="nga-mirror-") as directory:
        repo = Path(directory) / "repository.git"
        git("init", "--bare", str(repo))
        print("Fetching the current GitHub branches and tags...", flush=True)
        git("fetch", "--atomic", "--no-tags", source_url,
            "+refs/heads/*:refs/heads/*", "+refs/tags/*:refs/tags/*", cwd=repo)
        source = {r: s for r, s in parse_refs(git(
            "for-each-ref", "--format=%(objectname) %(refname)",
            "refs/heads/", "refs/tags/", cwd=repo)).items() if owned(r)}
        if "refs/heads/main" not in source:
            raise RuntimeError("Source main is missing; refusing to modify the mirror.")
        print("Reading the GitCode branch and tag tips...", flush=True)
        target = remote_refs(target_url)
        leases, refspecs = push_arguments(source, target)
        if refspecs:
            # Atomic ordinary pushes fail closed on divergence or moved tags.
            # Unowned destination refs are never overwritten or deleted.
            print(f"Pushing {len(refspecs)} ref updates to GitCode...", flush=True)
            git("push", "--atomic", *leases, target_url, *refspecs, cwd=repo)
        print("Verifying both repositories...", flush=True)
        target_after = remote_refs(target_url)
        if any(target_after.get(r) != s for r, s in source.items()):
            raise RuntimeError("Destination refs differ from the fetched source snapshot.")
        if {r:s for r,s in remote_refs(source_url).items() if owned(r)} != source:
            raise RuntimeError("Source advanced during synchronization; retry with a fresh snapshot.")
        return source, len(refspecs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=SOURCE)
    parser.add_argument("--target", default=TARGET)
    args = parser.parse_args()
    for attempt in range(1, 4):
        try:
            refs, changes = sync_once(args.source, args.target)
            message = (
                f"Verified {len(refs)} branches/tags; {changes} ref updates. "
                f"main = {refs['refs/heads/main']}"
            )
            print(message)
            summary = os.environ.get("GITHUB_STEP_SUMMARY")
            if summary:
                with open(summary, "a", encoding="utf-8") as stream:
                    stream.write(f"### GitCode mirror verified\n\n{message}\n")
            return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, RuntimeError) as exc:
            if isinstance(exc, subprocess.TimeoutExpired):
                detail = f"Git operation exceeded its {exc.timeout}-second timeout."
            else:
                detail = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) else str(exc)
            print(f"Attempt {attempt}/3 failed: {detail}", flush=True)
            if attempt == 3:
                raise SystemExit(1) from exc
            time.sleep(attempt * 5)


if __name__ == "__main__":
    main()
