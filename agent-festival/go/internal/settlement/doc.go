// Package settlement machine-enforces the settlement-proof protocol
// (docs/minor-ledger.md header; legislated R55, mechanized R57 C2'):
// from R56 on, every BLOCKER/MAJOR settlement entry in the ledger must
// carry a re-runnable mutation-proof token, and every active token must
// re-run to its declared outcome (→ FAIL: exit non-zero — the mutation
// turns the test red; → OK: exit zero — the verifying script asserts the
// redness itself). Tokens execute inside a throwaway copy of the working
// tree, so a mutated source never touches the real tree. Text claims are
// views; exit codes are the trust root. The audit's own tamper battery
// lives at tools/settlement-audit-tamper.py.
package settlement
