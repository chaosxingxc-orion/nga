# PT R0 execution preparation

`tools/r3_pt_r0_execution_prepare.py` derives a new PT/R0 scoring execution from
an exact PT DEV specification and the original R0 scientific closure. It does
not start inference, reserve a chip, start CPU consumption or grant acceptance.

Configuration schema `r3-pt-r0-execution-prepare-v1` has exactly these fields:
`source_spec`, `closure`, `launcher`, `resource_adapter` are `{path, sha256}`;
`root` is a fresh CephFS `jev/r3_runs` directory; `chip` and `container` describe
a prospective execution. Launcher and resource adapter must be pinned siblings.

```bash
python3 -B -P tools/r3_pt_r0_execution_prepare.py verify --config /absolute/CONFIG.json --sha256 EXACT_SHA
python3 -B -P tools/r3_pt_r0_execution_prepare.py prepare --config /absolute/CONFIG.json --sha256 EXACT_SHA
```

The source specification must pass its actual frozen launcher verifier. Only
K1-PT seed2/3 is accepted. The derived spec preserves training, model and
unmerged adapter identity, substitutes the exact full R0 data/code closure,
and uses the launcher's canonical `track_t_pt_r0` command. The original R0 plan,
source closure and new spec are verified before output is created. Output
includes plan, execution, execution pin and a pending-review preparation receipt.
An existing or partial output cannot be overwritten by another prepare call.

The existing `r3_pt_r0_consumer.py` performs separate B-4 reconstruction against
the admitted untuned Instruct R0 baseline; CPU queue/configuration must pin the
exact consumer and execution. Formal training plans encode their objective in
canonical argv, which the report checks against seed, model and manifest.
Unknown, duplicate or abbreviated flags are rejected. Preparation is not proof
that future scoring receipts or complete population reconstruction will pass.

Before launch, independently review the precise new package and consumer,
register the experiment, and verify live host resources and predecessor release.
Keep historical runtime packages unchanged. B-4 remains a separate registered
comparison; this preparation does not introduce a universal first-K1 gate.
