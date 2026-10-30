"""Mirror Git branches and tags, with leased updates and post-push verification."""

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


def push_arguments(source, target):
    """Guard every changed ref against changes since the destination was read."""
    leases, refspecs = [], []
    for ref in sorted(source.keys() | target.keys()):
        if source.get(ref) == target.get(ref):
            continue
        leases.append(f"--force-with-lease={ref}:{target.get(ref, '')}")
        refspecs.append(f"{source.get(ref, '')}:{ref}")
    return leases, refspecs


def sync_once(source_url, target_url):
    # A fresh fetch avoids replaying the triggering event's possibly stale commit.
    with tempfile.TemporaryDirectory(prefix="nga-mirror-") as directory:
        repo = Path(directory) / "repository.git"
        git("init", "--bare", str(repo))
        print("Fetching the current GitHub branches and tags...", flush=True)
        git("fetch", "--atomic", "--no-tags", source_url,
            "+refs/heads/*:refs/heads/*", "+refs/tags/*:refs/tags/*", cwd=repo)
        source = parse_refs(git(
            "for-each-ref", "--format=%(objectname) %(refname)",
            "refs/heads/", "refs/tags/", cwd=repo))
        if "refs/heads/main" not in source:
            raise RuntimeError("Source main is missing; refusing to modify the mirror.")
        print("Reading the GitCode branch and tag tips...", flush=True)
        target = remote_refs(target_url)
        leases, refspecs = push_arguments(source, target)
        if refspecs:
            # Atomic pushes fail closed if the server cannot support them. No PR,
            # backup, remote-tracking or provider-internal refs are mirrored.
            print(f"Pushing {len(refspecs)} ref updates to GitCode...", flush=True)
            git("push", "--atomic", *leases, target_url, *refspecs, cwd=repo)
        print("Verifying both repositories...", flush=True)
        if remote_refs(target_url) != source:
            raise RuntimeError("Destination refs differ from the fetched source snapshot.")
        if remote_refs(source_url) != source:
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
