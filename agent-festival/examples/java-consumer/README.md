# Java consumer spike — the "run it once" entry point

A minimal Maven project (Java 21 + Jackson 2.17.2 + networknt 2.0.0) that consumes the
growth-family fixture corpus (ledger / adoption / judgment / release — 81 fixtures) through
the conformance interface defined in [docs/conformance-fixture-format.md](../../docs/conformance-fixture-format.md):

- `load(path)` — shared loader semantics (UseNumber-equivalent via `BigDecimal` parsing, `_expect*` pin popping, loud wrong-typed-pin)
- `check(doc)` — json-schema validation through networknt
- `suite(dirs)` — two-phase discipline: must-accept / must-reject with wrong-reason pins

## Run it

```sh
cd examples/java-consumer
./run.sh          # incremental rebuild + full corpus, rc=0 on all-green
```

## Status (2026-11-01)

81/81 fixtures green in both arms (default-double and exact-BigDecimal), 64/64
wrong-reason pins hit, loader hardening self-checks pass. Zero Go dependencies —
this is the Java ecosystem consuming the corpus with industry libraries only.

**Honest boundary** (per the collision report): this spike was written by the
fixture authors against their own format document — it proves the corpus is
 consumable by the Java ecosystem in a day, not anything about the quality of
the NGA-side Java implementation. The known contract gaps it surfaced (networknt
2.x/3.x API break, pattern-match mode divergence, float-syntax integer domain,
the former stale counts in the format doc) are registered and driving 0.2.0.
