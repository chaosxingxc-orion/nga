# E23 — Exact original Open-Jev release-v2 data restoration

Preregistered 2026-10-30 before execution. CPU data restoration only; no inference or training.

## Purpose and counterpart

Defect 12: measurement validity. Restore the missing Wikispeedia records so a future reference
evaluation can use the original 10,532-row test and 15,920-row OOD denominators. A generator
can produce plausible but different records; acceptance therefore requires every original
split SHA256, not approximate counts or similar task names. The public projection remains
a separately named dataset. This does not establish model quality or generalization.

## Frozen setup

Use the export's own source snapshot, verifying every `source_code_sha256` entry. Pinned
Wikispeedia archive SHA256 `97697096f5d2dcb77aa69e3992305c6c561de89edb9fb10b5ad9feaf8ba534d5`.
Generator settings: 300 targets, 12 pairs per target, 12 maximum candidates, seed 42.
All generated Wiki split hashes must match the original Wiki manifest. The published restore
script inserts records at recorded original positions and checks original mixture hashes.
No original mirrors or current inference inputs are changed. TLS verification stays enabled.

## Execution and acceptance

175, retained detached CPU container `nga-openjev-original-restore`, existing immutable image.
Output `reference_inference/openjev_original_restore_20261030/`. Freeze driver, source snapshot,
export/original manifests, public compressed data, CA bundle, registration and launch scripts.
CephFS log, heartbeat, atomic terminal, wrapper exit and exact launch survive SSH loss.
Verified archive and complete generation stages may be reused; partial mixture writes fail
closed and need reviewed fresh output. No arbitrary existing files are trusted.

Acceptance: original split counts and hashes, missing-public-row IDs and original positions,
terminal/report hash binding, wrapper and actual container exit zero. Missing 176 test and
219 OOD rows are exported for future separately preregistered supplementary inference; this
restoration does not authorize silently joining predictions or reporting an old-full score.

## Results and verdict

2026-10-30 16:23:03 UTC: all five release-v2 splits restored successfully. Retained container
`5f628a369ac4181d89dd0ac0ce6f94848a331336a821c7308445d4da81181e74` exited 0; structured
terminal and wrapper agree. The 9,901,821-byte upstream archive matches its pinned hash.
All 62 frozen files and terminal/config/report binding were independently rechecked.

| Split | Rows | Hard / soft | Missing public rows |
| --- | ---: | ---: | ---: |
| train | 80,816 | 76,754 / 4,062 | 1,700 |
| calibration | 4,761 | 4,480 / 281 | 89 |
| validation | 3,792 | 3,511 / 281 | 69 |
| test | 10,532 | 10,046 / 486 | 176 |
| ood | 15,920 | 15,446 / 474 | 219 |

Independent audit verified each original mixture SHA, unique IDs, counts, and exact byte equality
between the existing public projection and the restored rows after removing the recorded Wiki
positions. `INDEPENDENT_RESTORATION_AUDIT.json` records `VERIFIED_EXACT_DATA`. This is data
identity evidence only. Neither original-full test/OOD inference nor prediction joining occurred.

Stage reuse exists for a verified archive and complete original generation. No crash/restart test
was performed; a partial mixture intentionally fails instead of being silently reused.
