"""Merge a train_r3.py checkpoint (LoRA-only .pt, from --stop-after or a completed run) into a plain HF directory.

    python3 -P merge_r3.py --run-dir <out dir used by train_r3.py> --ckpt <path or 'latest'> [--out <dir>]

Rebuilds the LoRA model exactly as train_r3.py does (same seed, same manifest.json args), loads the checkpoint's LoRA
tensors, and calls train_r3.fold_and_save (weight-space folding + its three checks).
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import train_r3 as T


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--ckpt", default="latest")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    manifest = json.load(open(os.path.join(a.run_dir, "manifest.json")))
    margs = manifest["args"]
    argv = []
    for k, v in margs.items():
        if k in ("out",):
            continue
        flag = "--" + k.replace("_", "-")
        if isinstance(v, bool):
            if v:
                argv.append(flag)
        elif v is not None:
            argv += [flag, str(v)]
    args = T.parse_args(["--out", a.run_dir] + argv)

    import torch
    import torch_npu  # noqa: F401
    import transformers

    tok = transformers.AutoTokenizer.from_pretrained(args.model_path)
    pm, trainable, n_pairs = T.build_model(args, torch)
    pm.to(args.device)

    ckpt = T.latest_ckpt(a.run_dir) if a.ckpt == "latest" else a.ckpt
    st = torch.load(ckpt, map_location="cpu", weights_only=False)
    with torch.no_grad():
        for n, p in trainable:
            p.copy_(st["lora"][n].to(p.device, p.dtype))
    print(f"loaded {ckpt} (step {st['step']})", flush=True)

    data = T.Data(args)
    probe_units = data.step_units(0)[1][:4]
    probe = []
    for u in probe_units:
        p, resp = T.encode_example(tok, u[0], args.max_len, {})
        probe.append(p + resp)

    out_dir = a.out or os.path.join(a.run_dir, "export_fp32")
    check = T.fold_and_save(torch, pm, args, tok, out_dir, probe, args.device)
    print("merge check:", json.dumps(check))
    json.dump({"source_step": st["step"], "source_ckpt": ckpt, "check": check},
              open(os.path.join(out_dir, "r3_merge_manifest.json"), "w"), indent=2)
    print(f"merged HF model at {out_dir}")


if __name__ == "__main__":
    main()
