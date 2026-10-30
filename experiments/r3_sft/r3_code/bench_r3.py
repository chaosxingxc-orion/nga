"""Throughput / memory sweep for train_r3.py on ONE chip: each configuration runs in a fresh process (clean peak memory).

    python3 -P bench_r3.py <out_root> [--steps 8]

Configurations: micro-chunk size (padded tokens per forward/backward), gradient checkpointing on/off, gathered vs full-logits
LM head. Reports per config: ok/OOM, steady-state s/step (steps after the first 2), tokens/s/chip, questions/s/chip, peak
reserved GiB (max_memory_reserved, whole run).
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIGS = [
    # name, micro_tokens, grad_ckpt, full_logits
    ("g_mt2048_nockpt", 2048, False, False),
    ("g_mt4096_nockpt", 4096, False, False),
    ("g_mt8192_nockpt", 8192, False, False),
    ("g_mt4096_ckpt", 4096, True, False),
    ("g_mt12000_ckpt", 12000, True, False),
    ("f_mt2048_nockpt", 2048, False, True),
    ("f_mt4096_ckpt", 4096, True, True),
]


def main():
    root = sys.argv[1]
    steps = 8
    if "--steps" in sys.argv:
        steps = int(sys.argv[sys.argv.index("--steps") + 1])
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1].split(",")
    os.makedirs(root, exist_ok=True)
    summary = []
    for name, mt, ck, fl in CONFIGS:
        if only and name not in only:
            continue
        out = os.path.join(root, name)
        os.makedirs(out, exist_ok=True)
        for f in ("losses.jsonl", "progress.log"):
            if os.path.exists(os.path.join(out, f)):
                os.remove(os.path.join(out, f))
        ckdir = os.path.join(out, "ckpt")
        if os.path.isdir(ckdir):
            import shutil
            shutil.rmtree(ckdir)
        cmd = [sys.executable, "-P", os.path.join(HERE, "train_r3.py"), "--out", out, "--seed", "2", "--arm", "k1",
               "--stop-after", str(steps), "--micro-tokens", str(mt), "--save-every", "0"]
        if ck:
            cmd.append("--grad-ckpt")
        if fl:
            cmd.append("--full-logits")
        print("RUN", name, flush=True)
        p = subprocess.run(cmd, capture_output=True, text=True)
        row = {"name": name, "micro_tokens": mt, "grad_ckpt": ck, "full_logits": fl, "rc": p.returncode}
        if p.returncode == 0:
            L = [json.loads(l) for l in open(os.path.join(out, "losses.jsonl"))]
            st = L[2:]
            row.update({"s_per_step": sum(r["step_s"] for r in st) / len(st),
                        "tok_s_chip": sum(r["tokens"] for r in st) / sum(r["step_s"] for r in st),
                        "q_s_chip": sum(r["base_questions"] for r in st) / sum(r["step_s"] for r in st),
                        "examples_per_step": sum(r["examples"] for r in st) / len(st),
                        "loss_first": L[0]["loss"], "loss_last": L[-1]["loss"]})
            last = [l for l in open(os.path.join(out, "progress.log"))][-1]
            row["peak_reserved_gib"] = float(last.split("reserved_gib")[1])
        else:
            tail = (p.stdout + p.stderr)[-400:]
            row["error"] = "OOM" if "out of memory" in (p.stdout + p.stderr) else tail
        print(json.dumps(row), flush=True)
        summary.append(row)
        json.dump(summary, open(os.path.join(root, "summary.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
