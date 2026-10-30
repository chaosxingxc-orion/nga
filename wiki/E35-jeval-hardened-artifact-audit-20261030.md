# E35 — independent hardened JEVal artifact audit

> Status: probe-only audit done; full-inference supplement pending · Round: reference engineering · Date: 2026-10-30 UTC
> Pre-registration: [JEVal adversarial review and supplement](../experiments/JEVAL-ADVERSARIAL-REVIEW-2026-10-30.md)

## 1. Purpose

Defects 12/16: independently reject incomplete eligibility, malformed probe
predictions, omitted execution dependencies and misleading aggregate successes.
This audit consumes immutable E33 artifacts; it does not rerun a model or alter
the original metric protocol. It feeds reference-result acceptance, not a training gate.

## 2. Hypothesis

The complete E33 artifacts should satisfy the extra schema, arithmetic, token and
actual-container checks. A malformed record with unchanged aggregate score must
be rejected. The degenerate optimum of trusting a success flag is opposed by
missing-field, changed-token, wrong-resource and forged-output negative cases.
Exact rates, identical cells and small samples remain review flags, not evidence
that a model is either perfect or broken.

## 3. Setup

`tools/audit_jeval_inference_hardened.py`, frozen outside each E33 run; exact
11,257-row JEVal data and all native E33 configurations remain unchanged.
The existing immutable image on 175 runs CPU-only, no NPU mapping, with CephFS
and Docker inspect access. The outer wrapper must provide detached retained
containers, persistent logs/heartbeat/terminal and exact relaunch commands.
The tool authenticates the original frozen verifier and runs its full-population
metric check before supplemental acceptance. `--probe-only` independently checks
completed probes before full inference finishes. Neither mode overwrites E33 evidence.

Full acceptance requires actual inference/probe/finisher exit 0, terminal and
config/output hashes, complete execution closure, exact eligibility schemas,
strict native probe outputs and independent CPU retokenization of four requests.
Grouping is by type and source×type; minimum n=30 is frozen before the audit.
Original and supplemental flags are preserved with JSON pointers and a bounded digest.

## 4. Results

Implementation tests: 16 focused CPU tests pass. The existing E33 27 tests had
passed despite the independently demonstrated omissions; test counts are not
model performance evidence.

## 6. Probe-only result, 2026-10-30 19:31 UTC

Six completed probes were audited in one detached CPU-only retained container
`fe25173fe530f4f09d94901b93679ac52f2b863382c5f188d80162bba07c4a66`; actual
Docker exit and wrapper were 0, plan SHA256
`c075623528ac89920b089ebff702575d8a1489a7256f634821cc73d41a72b096`, and
the terminal reported `rc=0`, 6/6. Every entry returned
`VERIFIED_HARDENED_PROBE_SCOPED` with no supplemental flags:

| probe | config SHA256 | hardened report SHA256 |
| --- | --- | --- |
| Kev-0.8B | `83406e1479fb2c932e63809644cec02a1409a4421f6f3cbee9b530a905c6e652` | `5bbdc88372961bba5c1cae85147f2cbfa009620a5a6b3eb75d203661bf2452d2` |
| Kev-4B v2 | `d42acbeef917c5d736a84b70cb6d23efa67e4b9aeec9fbc9de17b7c237095776` | `701ae44f09bff509b26bdcbf640ae911e535da0fe566cf7b6efab19a89329161` |
| Kev-9B v2 | `aefba9ec015691d03125e3b75d117fda6ad2a7b7a9cc180285227e3a0742624d` | `104731e8b7841223a437ae6a2d6f4124b25e85212da9ad3dc21bea805e6ed3db` |
| Open-Jev-2B | `81113da7d23f9de4f6aff27b4d06a277a177fced4efedf33a9d278e59800551e` | `1719e0eef6e699f07d50bee2b4bbd3aea3a04a0101a22608d54d32a408e88954` |
| Open-Jev-9B | `d1e953ca97c89ce0880116a5e48f4eebe733e2d1fe5ce87027c1cfe3a21f6c85` | `05a5416bee8470eec424db1c5f487cd74e2887080f86624ac83760266d4ecf49` |
| Nimble | `9cc49322c7a515e1e6fec56b4f34d4d1b1b404c089166589ee142ebe3ed17997` | `8135c1ee516445b95681499d6bc1d68c02b4d93467c577dd3dc5f4634b95a448` |

Each audit independently retokenized the three synthetic requests and the
metadata-selected boundary request, checked eight native forwards, output
schema, logits/probability arithmetic, token identity, actual retained probe
exit, and the complete frozen execution closure. This result is bounded to the
four probe inputs. It does not produce JEVal scores, certify Open-Jev's maximum
candidate-batch memory envelope, or constitute Astra approval.

## 5. Verdict

Initial verdict before execution: actual artifact audits pending. The substantive review was performed by a Codex
agent, not Astra. Full-test token provenance is not independent retokenization;
only four probe requests are retokenized. Open-Jev candidate-batch memory
admission is a separate unresolved engineering requirement, not certified here.

Artifact directory: `/mnt/cephfs/xingchao/experiments/jev/reference_inference/jeval_hardened_probe_audit_20261030/`.
Frozen auditor SHA256 `04ecdebe1ea117c24fe1f0a66c6adb077902ef599606703a008cb902d8865b44`.
The six config hashes, exact launch/relaunch commands, persistent heartbeat,
per-entry results and overall terminal remain there; no NPU device was mapped.
