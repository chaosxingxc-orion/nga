# E40 bounded results — actual Astra PASS

Actual child/runner/EXIT all rc0 and six output hashes independently verified. This verdict covers one input, two repetitions per mode and frozen resource evidence only.

**PASS — bounded E40 diagnostic review.**

- Membership and hashes verified: `MANIFEST.json` SHA256 is `7726e8b2…e75a3`; all 315 manifest entries match size/SHA256. Plan SHA256 is `90721d65…c3d9`. All 233 `SOURCE_MAP` mappings resolve to bundled dependency entries; five large external inputs are correctly listed in `OMITTED.json`.
- Eight items and eight attempts form the exact fixed-prefix schedule. Attempt hashes, generation identity, input shape `[15,186]`, token/mask row identities, and all 18 core identities bind consistently.
- Independent reconstruction confirms the same serialized prediction across all repetitions and modes, including logits/probabilities, temperature scaling, wire probabilities, confidence, candidate order, and consumed-token hashes. All 10 controls are true; `exact_outputs=true`; `candidate_batch_admission=false`. This suspicious exact success was independently reconstructed rather than dismissed.
- Memory claims are numerically correct: original/L2 peak allocated `3.8616762161254883 GiB`; L1/L1L2 `3.8067426681518555 GiB`; saving `56.251953125 MiB` / `1.4225311729720558%` for this one input. Reserved memory remains `4.142578125 GiB` for every mode.
- Timing is recorded as claimed: original `1.1337145201 s`, `0.3344910201 s`; candidates `0.34238789999–0.35552342003 s`. The files and claims preserve the cold-first distinction and make no general speedup claim. Safety limits hold (`free_before` about `56.29 GiB`, reserved below `48 GiB`).
- CPU request, receipt, report, terminal, `EXIT`, and `CPU_EXIT_BINDING` are internally consistent, with `devices=[]`. The recorded NPU binding is to `a4c560…f30df`, started at `06:13:18.64908503Z`, finished at `06:14:21.58421406Z`; CPU binding is `eb0532…e554`, exited at `06:15:34.94236611Z`. These are file bindings; the parent’s supplied live exit observations are separately acknowledged.
- Release evidence is complete and bounded: trusted anchor `7c6c5638…5fb64`, approved plan/CPU/NPU bindings, release review, committed intent, and `RELEASED.json` all match. The allocation transition removes only chip 1, adds it to `free`, and leaves other owners unchanged. The release-tool hash matches the reviewed code hash; prior code PASS is treated as supporting review evidence, not live release proof.

No blocker found for the requested diagnostic numerical, memory, timing, or frozen resource-evidence claims. This does not establish stage liveness, large-shape behavior, general performance, full JEVal admission, or independent live Docker observation.
