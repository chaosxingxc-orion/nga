# Formal training-to-DEV guarded packaging

`tools/r3_formal_dev_guard_prepare.py` turns a prepared generic formal DEV
execution into a new frozen package using an existing reviewed guard template.
It copies the template's execution tools byte-for-byte and changes only output
paths and the registered training-predecessor edge. It never starts a service,
claims a device, creates approval evidence or grants scientific qualification.

Configuration schema `r3-formal-dev-guard-prepare-v1` has exactly these fields:
`prepared`, `execution`, `cpu_queue`, `template_config`, `previous_training`,
`schedule` are `{path, sha256}` references; `root` is a fresh CephFS run directory;
`container` is a unique retained-container stem. Every input is pinned. The formal
role, chip, predecessor and dependency edge are derived and cross-checked against
the frozen specification and schedule, not accepted as user-supplied overrides.

```bash
python3 -B -P tools/r3_formal_dev_guard_prepare.py verify --config /absolute/config.json --sha256 EXACT_SHA
python3 -B -P tools/r3_formal_dev_guard_prepare.py prepare --config /absolute/config.json --sha256 EXACT_SHA
```

The generated package includes `CONFIG.json`, `CONFIG-PIN.json`, execution/spec,
CPU queue, derivation and preparation receipts. The real frozen guard and CPU
consumer verifiers run before the receipt is written. Existing or partial output
roots are rejected; an interrupted preparation needs explicit inspection and a
new destination, never overwrite/adoption. Existing packages remain unchanged.

Only registered successful **training** predecessors are supported. Evaluation
predecessor edges are rejected and need their separately validated implementation.
A prepared package still requires exact independent review, externally authenticated
activation and live claim-time predecessor/resource validation. No activation or
NPU/CPU service start is part of this preparation tool.
