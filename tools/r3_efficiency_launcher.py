#!/usr/bin/env python3
"""Detached R3 efficiency-validation launcher on host 175.

This is a host adapter, not a trainer. It verifies an externally pinned plan,
claims the chip through r3_resource_adapter, creates a retained container with
the exact driver/device mapping, records its launch receipt, and returns.
Release is a separate short operation after actual Docker exit.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
LAUNCH = Path("/mnt/cephfs/xingchao/docker/verl_v030_20261029/launch.sh")
CELL = Path("/mnt/cephfs/xingchao/docker/verl_v030_20261029/speedup/code/run_cell.py")
ADAPTER = HERE / "r3_resource_adapter.py"
IMAGE = "nga-verl-qwen35-v030:20261029"
IMAGE_SHA = "sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7"

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_bytes())
def atomic(p, x):
    p = Path(p); tmp = p.with_name(p.name + ".pending")
    tmp.write_text(json.dumps(x, indent=2, sort_keys=True) + "\n"); os.replace(tmp, p)

def verify(plan_path, pin):
    if sha(plan_path) != pin: raise RuntimeError("plan hash differs")
    p = load(plan_path)
    if p["schema"] not in ("r3-efficiency-plan-v1", "r3-efficiency-plan-v2") or p["image"] != IMAGE or p["image_sha256"] != IMAGE_SHA: raise RuntimeError("plan identity")
    if sha(ADAPTER) != p["adapter_sha256"]: raise RuntimeError("adapter changed")
    if sha(Path(p["launcher"])) != p["launcher_sha256"]: raise RuntimeError("launcher changed")
    if sha(Path(p["verifier"])) != p["verifier_sha256"]: raise RuntimeError("verifier changed")
    if sha(Path(p["launch_script"])) != p["launch_script_sha256"]: raise RuntimeError("launch script changed")
    if sha(Path(p["cell_driver"])) != p["cell_driver_sha256"]: raise RuntimeError("cell driver changed")
    if not Path(p["code_dir"]).is_dir() or Path(p["code_dir"]).is_symlink(): raise RuntimeError("code directory is not a regular frozen directory")
    for f, h in p["files"].items():
        if sha(f) != h: raise RuntimeError("frozen dependency changed: " + f)
    review = load(p["review_path"])
    if review["approved"] is not True or review["approved_plan_sha256"] != pin or sha(p["review_path"]) != p["review_sha256"]: raise RuntimeError("exact review missing")
    return p

def launch(plan_path, pin):
    p = verify(plan_path, pin); out = Path(p["out"]); out.mkdir(parents=True, exist_ok=True)
    if any((out / marker).exists() for marker in ("LAUNCH_INTENT.json", "LAUNCH_RECEIPT.json", "ALLOCATION_CLAIM.json", "DONE", "FAILED")):
        raise RuntimeError("run output already contains launch state")
    atomic(out / "LAUNCH_INTENT.json", {"plan_sha256": pin, "container": p["container"], "chip": p["chip"]})
    adapter = ["python3", "-P", str(ADAPTER)]
    subprocess.run(adapter + ["claim", "--alloc", p["allocation"], "--run", p["run"], "--chip", str(p["chip"]), "--owner", p["owner"], "--purpose", p["purpose"], "--proof", str(out / "ALLOCATION_CLAIM.json")], check=True)
    env = dict(os.environ, NAME=p["container"], NPUS=str(p["chip"]), IMAGE=IMAGE, DETACH="1", CODE_DIR=str(Path(p["code_dir"])), EXTRA=p["extra_env"])
    cmd = ["bash", str(LAUNCH), "python3", "-P", str(CELL), str(out), "--"] + p["command"]
    atomic(out / "LAUNCH_SPEC.json", {"image": IMAGE, "image_sha256": IMAGE_SHA, "container": p["container"], "chip": p["chip"], "command": cmd, "env": {k: env[k] for k in ["NAME", "NPUS", "IMAGE", "DETACH", "CODE_DIR", "EXTRA"]}})
    (out / "LAUNCH_COMMAND.txt").write_text(" ".join(cmd) + "\n")
    subprocess.run(cmd, env=env, check=True)
    d = json.loads(subprocess.check_output(["docker", "inspect", p["container"]]))[0]
    if d["HostConfig"].get("AutoRemove") or d["Config"].get("Image") != IMAGE: raise RuntimeError("container binding")
    atomic(out / "LAUNCH_RECEIPT.json", {"container_id": d["Id"], "image": d["Config"]["Image"], "plan_sha256": pin, "started_at": d["State"]["StartedAt"], "command": d["Config"]["Cmd"], "devices": d["HostConfig"].get("Devices")})
    print(json.dumps({"status": "STARTED", "container": p["container"], "out": str(out)}))

def release(plan_path, pin):
    p = verify(plan_path, pin); out = Path(p["out"])
    subprocess.run(["python3", "-P", str(ADAPTER), "release", "--alloc", p["allocation"], "--run", p["run"], "--chip", str(p["chip"]), "--container", p["container"], "--claim", str(out / "ALLOCATION_CLAIM.json"), "--proof", str(out / "RELEASED.json")], check=True)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("op", choices=("launch", "release")); ap.add_argument("--plan", required=True); ap.add_argument("--sha256", required=True); a = ap.parse_args()
    return launch(Path(a.plan), a.sha256) if a.op == "launch" else release(Path(a.plan), a.sha256)
if __name__ == "__main__": main()
