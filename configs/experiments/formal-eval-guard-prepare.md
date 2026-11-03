# Formal DEV-to-DEV successor preparation

`tools/r3_formal_eval_guard_prepare.py` prepares new packages for the frozen
`primary_s2_dev_release → samechip_s2_dev` and
`primary_s3_dev_release → diffchip_s2_dev` edges. It never starts a service,
claims a device, writes an activation, or grants scientific eligibility.

The exact configuration schema is `r3-formal-eval-guard-prepare-v1`. Pins
`prepared`, `execution`, `cpu_queue`, `template_config`, `previous_execution`,
`previous_original_spec`, `previous_derivation`, `guard_controller`, and `schedule`
each contain `{path, sha256}`. `root` is a fresh CephFS run directory and
`container` a fresh retained-container stem. No role/chip override is accepted;
they are derived from the frozen specifications and schedule.

```bash
python3 -B -P tools/r3_formal_eval_guard_prepare.py verify --config /absolute/config.json --sha256 EXACT_SHA
python3 -B -P tools/r3_formal_eval_guard_prepare.py prepare --config /absolute/config.json --sha256 EXACT_SHA
```

The template launcher/resource/training-evidence/CPU-wake tools are copied
unchanged. The explicitly pinned `r3_formal_dev_successor.py` adds the evaluation
predecessor mode. Old frozen packages are unchanged. Both exact configuration
and changed source require independent review before activation.

The guard binds the actual predecessor execution and its derivation to the
original handoff specification and schedule. It allows only source-copy paths
and the two results/identity output operands to differ; model, adapter, population,
scoring and numerical arguments must remain identical. An attempt other than 1,
a synthetic or unsuccessful terminal, missing completion/release, changed claim
hash, live supervisor, altered Docker configuration or reassigned resource
lineage cannot authorize launch. The resource adapter replays the evidence under
its allocation lock. Events wake the watcher; polling fallback is 600 seconds.

A prepared package includes exact CONFIG/execution/CPU queue and derivation pins.
Partial output is retained and never adopted or overwritten. A launch needs a
separate exact independent review and authenticated activation. Observation
uncertainty and an existing start intent require reconciliation, not replay.
