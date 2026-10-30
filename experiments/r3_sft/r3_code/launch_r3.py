"""Detached single-chip launcher for R3 jobs (CLAUDE.md §7). Runs on the host.

    python3 -P launch_r3.py --name nga-r3-<job> --chip 6 --out <run dir> [--env K=V ...] -- <command inside the container>

`docker run -d` with a fixed container name and no --rm (via the proven launch.sh), the command wrapped in
speedup/code/run_cell.py (heartbeat.log, DONE/FAILED marker with the exit code, RELAUNCH.txt). The run directory gets
LAUNCH.txt with this script's own relaunch line. One chip per job: the container sees it as device 0 (npu:0).
Refuses chips outside 6,7 unless --allow-chip is given (the other chips belong to other agents).
"""
import argparse
import os
import subprocess
import sys

R = "/mnt/cephfs/xingchao/docker/verl_v030_20261029"
S = R + "/speedup"


def main():
    argv = sys.argv[1:]
    if "--" not in argv:
        raise SystemExit("usage: launch_r3.py --name N --chip C --out DIR [--env K=V ...] -- command ...")
    i = argv.index("--")
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--chip", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--image", default="nga-verl-qwen35-v030:20261029")
    ap.add_argument("--allow-chip", action="store_true", help="chips 0-5 (the orchestrator assigned 2-7 for round 1, 0-1 when the scorer agent frees them)")
    ap.add_argument("--watch-tier", default="fast", choices=("fast", "medium", "slow"), help="written to WATCH.json for tools/watchdog.py")
    ap.add_argument("--watch-total", type=int, default=0, help="declared total progress count (training steps) for WATCH.json")
    a = ap.parse_args(argv[:i])
    cmd = argv[i + 1:]
    if not a.allow_chip and any(c not in ("6", "7") for c in a.chip.split(",")):
        raise SystemExit("only chips 6 and 7 may be used by this task")
    os.makedirs(a.out, exist_ok=True)
    import json
    w = {"tier": a.watch_tier}
    if a.watch_total:
        w["total"] = a.watch_total
    with open(os.path.join(a.out, "WATCH.json"), "w") as f:
        json.dump(w, f)
    env = dict(os.environ, DETACH="1", NAME=a.name, NPUS=a.chip, IMAGE=a.image,
               EXTRA=" ".join(f"-e {e}" for e in a.env))
    full = ["bash", f"{R}/launch.sh", "python3", "-P", f"{S}/code/run_cell.py", a.out, "--"] + cmd
    with open(os.path.join(a.out, "LAUNCH.txt"), "w") as f:
        f.write("# remove a stale container of the same name first: docker rm " + a.name + "\n")
        f.write(" ".join(f"{e}" for e in [f"NAME={a.name}", f"NPUS={a.chip}", "DETACH=1"] + ([f'EXTRA="{env["EXTRA"]}"'] if env["EXTRA"] else [])) + " ")
        f.write(" ".join(full) + "\n")
    subprocess.run(full, env=env, check=True)
    print(f"launched {a.name} on chip {a.chip}; marker {a.out}/DONE or FAILED; progress {a.out}/progress.log, heartbeat {a.out}/heartbeat.log")


if __name__ == "__main__":
    main()
