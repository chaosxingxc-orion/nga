# Formal DEV package preparation

`tools/r3_formal_dev_prepare.py` prepares a new execution package from a formal
wave handoff receipt. Normal role instances differ only in configuration; the
source closure, evaluation semantics and scoring tools remain pinned.

The configuration schema is `r3-formal-dev-prepare-v1` and has exactly these
fields:

| Field | Meaning |
| --- | --- |
| `prepared` | `{path, sha256}` of the handoff's `PREPARED.json` |
| `spec` | `{path, sha256}` of that receipt's exact evaluation plan |
| `schedule` | `{path, sha256}` of the formal role schedule |
| `closure` | `{path, sha256}` of the original source closure manifest |
| `cpu_template` | `{path, sha256}` of an existing CPU report queue |
| `tools` | Four named `{path, sha256}` references: `r3_posttrain_eval_launcher.py`, `r3_resource_adapter.py`, `r3_cpu_report_queue.py`, `r3_selection_report.py` |
| `root` | Fresh absolute directory under CephFS `jev/r3_runs` |
| `role`, `chip`, `container` | Frozen formal role and chip, plus a unique retained-container stem |

Run with the exact config hash:

```bash
python3 -B -P tools/r3_formal_dev_prepare.py verify --config /absolute/config.json --sha256 EXACT_SHA
python3 -B -P tools/r3_formal_dev_prepare.py prepare --config /absolute/config.json --sha256 EXACT_SHA
```

Preparation copies source bytes unchanged, rewrites only source-mount and
results/identity output paths, calls the actual frozen launcher binder/verifier,
and verifies the derived CPU queue. It writes `DERIVATION.json` and
`PREPARATION.json`; it neither launches a service nor claims an NPU. A partially
written output is retained and cannot be overwritten by rerunning preparation.

The resulting generic execution requires a separate exact execution review and
a successful-predecessor guard before launch. The primary_s3 DEV predecessor is
diffchip_s2 training release. The samechip_s2 and diffchip_s2 DEV predecessors are
primary_s2 DEV and primary_s3 DEV release respectively; a training-only guard
does not implement these evaluation edges. A ready CPU package is not launch
authorization, scientific acceptance or trained-candidate TEST eligibility.

Inputs, thresholds, original role identity and source snapshots remain normative.
Future builder changes create new packages; never modify a running frozen one.
