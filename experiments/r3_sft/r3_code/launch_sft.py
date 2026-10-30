"""R3 SFT launcher: constructs and runs one `docker run -d` training cell (CLAUDE.md section 7).

Run on the host (not inside a container): `python3 -P launch_sft.py <arm> --out <dir> [options]`.
Reuses the proven launcher (/mnt/cephfs/xingchao/docker/verl_v030_20261029/launch.sh) and in-container
driver (speedup/code/run_cell.py, heartbeat/DONE/FAILED/RELAUNCH.txt) unchanged; writes no shell
script. The command actually run is printed before launch and also lands in <out>/RELAUNCH.txt
(written by run_cell.py itself).

Arms (R3-SFT-PREREG §7.2-§7.4):
  k1      Kev-recipe replication, LoRA, full prompt (default data under --data-dir, train.e<epoch>.jsonl)
  k1-qo   same, but the dataset was built with --drop-state (question-only arm, open point 13.13)
  k1-pt   K1 with Kev's training-time augmentation applied (--augment kev when building the data;
          exploratory, open point 13.12; NOT the frozen K1)
  k2      option-restricted loss (R3 §7.3): NOT wired into this launcher yet; the loss function and
          its correctness test live in k2_loss.py and are validated standalone (see README note in
          the task report). Passing --arm k2 here raises, by design, rather than silently training
          with the wrong (K1) loss.

Fixed by the prereg, not exposed as flags: LoRA r=16, alpha=32, dropout=0.05, the hybrid target
module list, AdamW wd=0.01, OneCycleLR(max_lr, pct_start=0.1), grad-norm clip 1.0, batch 8
questions/step global, bf16 compute, no EOS in the loss (R3RawCompletionDataset).
"""
import argparse
import os
import subprocess
import sys

R = "/mnt/cephfs/xingchao/docker/verl_v030_20261029"
S = R + "/speedup"
HERE = os.path.dirname(os.path.abspath(__file__))

# The image's own baked-in PYTHONPATH (Dockerfile ENV; `docker image inspect
# nga-verl-qwen35-v030:20261029 --format '{{json .Config.Env}}'`, 2026-10-30), reproduced here so
# that passing -e PYTHONPATH=... to `docker run` APPENDS r3_code rather than REPLACING the CANN tbe
# path (CLAUDE.md section 6: dropping it breaks the first dynamic op compilation). run_cell.py then
# appends its own speedup/site/src/verl dirs on top of this, as it does for every other run.
IMAGE_PYTHONPATH = ("/opt/verl:/usr/local/Ascend/ascend-toolkit/latest/python/site-packages:"
                     "/usr/local/Ascend/ascend-toolkit/latest/opp/built-in/op_impl/ai_core/tbe:"
                     "/usr/local/Ascend/cann-9.2.0/python/site-packages:"
                     "/usr/local/Ascend/cann-9.2.0/opp/built-in/op_impl/ai_core/tbe:")

LORA_TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj",
                "in_proj_qkv", "in_proj_z", "in_proj_a", "in_proj_b", "out_proj"]


def build_cmd(a):
    n = len(a.npus.split(","))
    global_bs = a.batch
    per_dp = global_bs // n
    assert per_dp * n == global_bs, f"batch {global_bs} must divide evenly over {n} chips"
    micro = a.micro_bs or per_dp
    assert micro <= per_dp, f"micro_bs {micro} must be <= per-rank batch {per_dp}"
    # One train file for the whole run: verl's SFTTrainer already reshuffles the same dataset object
    # every epoch (DistributedSampler.set_epoch), which is sufficient for K1/K1-QO (prereg sec 3.3c:
    # no augmentation, so every epoch's content is identical anyway, only shuffle order differs, and
    # verl's own shuffle already varies by epoch). K1-PT (open point 13.12, not a frozen arm) uses
    # build_kev_sft.py --augment kev's epoch-0 file for every epoch of this launcher: Kev's exact
    # per-epoch regeneration (a fresh augmentation draw each epoch) is NOT reproduced here, because
    # verl's Dataset has no per-epoch hook; this is a known, reported scope limitation of the
    # exploratory K1-PT arm only, not of K1/K1-QO/K2.
    train_file = os.path.join(a.data_dir, "train.e0.jsonl")
    steps = a.steps if a.steps else None
    target_modules = "[" + ",".join(LORA_TARGETS) + "]"
    overrides = [
        f"data.train_files={train_file}",
        f"data.val_files={a.val_file}" if a.val_file else "data.val_files=null",
        f"data.train_batch_size={global_bs}",
        f"data.micro_batch_size_per_gpu={micro}",
        f"data.max_length={a.max_length}",
        "data.truncation=right",  # value unused: R3RawCompletionDataset does its own left-truncation
        "data.use_dynamic_bsz=False",
        f"data.custom_cls.path={HERE}/r3_sft_dataset.py",
        "data.custom_cls.name=R3RawCompletionDataset",
        f"model.path={a.model_path}",
        "model.use_remove_padding=False",
        "model.enable_gradient_checkpointing=True",
        "+model.override_config.attn_implementation=sdpa",
        f"model.lora_rank={a.lora_rank}",
        f"model.lora_alpha={a.lora_alpha}",
        f"model.target_modules={target_modules}",
        "optim.lr=" + str(a.lr),
        "optim.weight_decay=0.01",
        "optim.lr_scheduler_type=cosine",  # placeholder: nga_onecycle_patch overrides it unconditionally (NGA_ONECYCLE=1)
        "optim.lr_warmup_steps_ratio=0.1",
        "optim.clip_grad=1.0",
        "trainer.logger=console",
        "trainer.project_name=nga-r3",
        f"trainer.experiment_name={a.arm}-seed{a.seed}",
        f"trainer.default_local_dir={a.out}/ckpt",
        f"trainer.total_epochs={a.epochs}",
        f"trainer.n_gpus_per_node={n}",
        "trainer.save_freq=-1",
        "trainer.test_freq=-1",
        f"trainer.seed={a.seed}",
    ]
    if steps:
        overrides.append(f"trainer.total_training_steps={steps}")
    if a.extra:
        overrides += a.extra
    torchrun = ["torchrun", "--standalone", "--nnodes=1", f"--nproc_per_node={n}",
                "-m", "verl.trainer.sft_trainer"] + overrides
    return torchrun, n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("arm", choices=("k1", "k1-qo", "k1-pt", "k2"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--data-dir", required=True, help="dir with train.e<epoch>.jsonl from build_kev_sft.py")
    ap.add_argument("--val-file", default=None)
    ap.add_argument("--model-path", default="/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B-Base")
    ap.add_argument("--seed", type=int, default=2)
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--steps", type=int, default=0, help="0 = full epochs; >0 caps total optimizer steps (smoke)")
    ap.add_argument("--batch", type=int, default=8, help="global questions per optimizer step (prereg sec 7.2)")
    ap.add_argument("--micro-bs", type=int, default=0, help="0 = no internal accumulation (= batch/n_chips)")
    ap.add_argument("--max-length", type=int, default=2048)
    ap.add_argument("--lora-rank", type=int, default=16)
    ap.add_argument("--lora-alpha", type=int, default=32)
    ap.add_argument("--lora-dropout", type=float, default=0.05)
    ap.add_argument("--lr", default="1e-4")
    ap.add_argument("--onecycle", type=int, choices=(0, 1), default=1)
    ap.add_argument("--npus", default="6,7")
    ap.add_argument("--image", default="nga-verl-qwen35-v030:20261029")
    ap.add_argument("--kernel", choices=("ref", "fla"), default="ref",
                     help="ref = ran R3-SFT-PREREG sec 11.3's default (no fast kernel); fla needs its own "
                          "per-run tracking-loss-curve check before use (prereg sec 11.3c), not done by this script")
    ap.add_argument("--extra", nargs="*", default=[], help="extra raw hydra overrides")
    ap.add_argument("--name", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.arm == "k2":
        raise SystemExit("k2 needs the option-restricted loss, not wired into this launcher; see k2_loss.py")

    torchrun_cmd, n = build_cmd(a)
    name = a.name or f"nga-r3-{a.arm}-seed{a.seed}"
    os.makedirs(a.out, exist_ok=True)
    child_env = {"VERL_USE_EXTERNAL_MODULES": "nga_lora_dropout_patch,nga_onecycle_patch" + (",nga_gdn_patch" if a.kernel == "fla" else ""),
                 "NGA_LORA_DROPOUT": str(a.lora_dropout),
                 "NGA_ONECYCLE": "1" if a.onecycle else "0",
                 "NGA_TIME_DATALOADER": "1", "NGA_MEM_WARMUP_STEPS": "3",
                 "PYTHONPATH": IMAGE_PYTHONPATH + HERE}
    if a.kernel == "fla":
        child_env["NGA_GDN_KERNEL"] = "fla"
    env = dict(os.environ, DETACH="1", NAME=name, NPUS=a.npus, IMAGE=a.image,
               EXTRA=" ".join(f"-e {k}={v}" for k, v in child_env.items()),
               CODE_DIR=HERE)
    cmd = ["bash", f"{R}/launch.sh", "python3", "-P", f"{S}/code/run_cell.py", a.out, "--"] + torchrun_cmd
    print("container:", name)
    print("cmd:", " ".join(cmd))
    print("docker EXTRA:", env["EXTRA"])
    if a.dry_run:
        return
    subprocess.run(cmd, env=env, check=True)
    print(f"launched {name}; poll {a.out}/DONE or {a.out}/FAILED; heartbeat at {a.out}/heartbeat.log")


if __name__ == "__main__":
    main()
