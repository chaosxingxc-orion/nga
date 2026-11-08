# Independent R1–R6 review

Source: `25ab91e18a11dca44b511f74ae5d62f7e8ad9000`; Ubuntu 24.04,
Go 1.24.13. The original `go test ./... -count=1 -race` passes on exact LF blobs.
Export from Windows with `git -c core.autocrlf=false archive`, since the scan
fixture is compared byte-for-byte. No real model or external business API ran.

Run `python3 agent-festival/review/2026-11-08/run_probes.py /path/to/go`.
The runner uses a temporary Go overlay. It returns the actual test exit code;
**nonzero currently means known system acceptance gaps remain**, not a successful
production acceptance. Future fixes must update this evidence table.

| External probe | Actual result | Scope |
| --- | --- | --- |
| RecentShortOverdueMustNotPassUpperGrant | PASS | Original counterexample 1, typed deterministic fixture |
| SupersededDecisionMustNotDispatch | FAIL | Host lacks authoritative replacement/admission contract; not a claim that arbitrary two Adopt calls must revoke each other |
| UnadoptedResultMustNotBecomeCurrent | FAIL | Stored high revision is selected without adoption |
| VerifierRefusalNeedsDurableEvidence | FAIL | E1 refusal has no durable control fact; a qualified host audit store is also acceptable after adapting this assertion |
| OriginalLowBandRule | PASS | Original owner rule is present in code; limited integer input domain |
| RequiredWindowCannotDisappear | FAIL | Missing configuration validation provider; deliberately outside the valid fixture's preconditions, not an in-domain computation counterexample |
| ExpectedEpochIsNotDecisionAuthority | PASS | Logical contrast includes Current(bound revision); not production CAS evidence |

P0-A's three top-level tests (including eight matrix subtests) and X-S2's two
tests pass. The coverage subtest calls a source-name helper; it does not prove
the full runtime evidence-routing path. X-S2 proves a deliberately weak
parameter-only comparison is insufficient, not that all APIs with an epoch
parameter violate the original full Commit contract.

The preserved external tests were adapted only for the new durationMonths /
monthsAgo fields. They remain outside the standard test package until a full
system contract is implemented; their failures are explicitly tracked rather
than hidden by changing expectations to current broken behavior.

Current authoritative conclusions: [acceptance and open items](../../../achitecture%20design/08-r1-r6-acceptance-and-open-items.md).
