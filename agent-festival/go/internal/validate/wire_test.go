package validate

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// Test-only schema loading: the package init() probes the CWD and under
// `go test` that is one level too deep — loading here lets wire-level tests
// drive the full production path (schema layer included).
func init() {
	for _, root := range []string{"../../../schema", "../../../../schema"} {
		if cs, err := LoadSchema(filepath.Join(root, "capability-contract.schema.json")); err == nil {
			ContractSchema = cs
			EnvelopeSchema, _ = LoadSchema(filepath.Join(root, "contract-envelope.schema.json"))
			ExamplesDir = filepath.Join(root, "examples")
			return
		}
	}
}

// TestKeyOpsWireShapePinned locks the WIRE DIALECT LEDGER entry (V11 F2): JWK
// key_ops is an ARRAY (JWA §4.3). The frozen oracle's `in`-on-dict quirk accepts
// {"verify": true} and an int value crashes it outright; Go enforces the
// array/str shape. The divergence is unshareable (opposite verdicts on the same
// document), so the Go side is pinned here programmatically — reverting Go
// toward "parity" with the quirk must turn this test red.
func TestKeyOpsWireShapePinned(t *testing.T) {
	compileLibraries() // independent of sibling tests' save/restore ordering
	for _, ops := range []any{map[string]any{"verify": true}, 5} {
		jwk := map[string]any{
			"kty": "EC", "crv": "P-256", "x": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
			"y": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "kid": "wire-2026",
			"use": "sig", "alg": "ES256", "key_ops": ops,
		}
		ts := &TrustStore{
			Keys:      map[string]map[string]any{"wire-2026": jwk},
			SubjectOf: map[string]map[string]bool{"wire-2026": {"doc-extractor": true}},
		}
		fx, err := LoadFixture(filepath.Join(ExamplesDir, "valid", "doc-extractor.json"))
		if err != nil {
			t.Fatal(err)
		}
		hash, err := ContractHash(fx.Doc)
		if err != nil {
			t.Fatal(err)
		}
		hdr, _ := json.Marshal(map[string]any{"alg": "ES256", "typ": "JOSE", "kid": "wire-2026"})
		errs, _ := EnvelopeErrors(map[string]any{
			"envelope_version": "0.1.0",
			"contract":         fx.Doc,
			"contract_hash":    hash,
			"signatures":       []any{map[string]any{"protected": B64url(hdr), "signature": "AA"}},
		}, ts, false)
		found := false
		for _, e := range errs {
			if strings.Contains(e, "key_ops") {
				found = true
			}
		}
		if !found {
			t.Fatalf("key_ops wire shape %v was not rejected: %v", ops, errs)
		}
	}
}

// TestBase64AlphabetPinned locks the Go-strict side of the b64 wire-form
// FORCED DIVERGENCE (V12→V14): Go rejects every non-alphabet byte; the oracle
// accepts whenever the non-alphabet-stripped residue still decodes (so some
// live shapes pass verification there and fail here — opposite verdicts by
// design, strict side wins per the JOSE-anchored wire ledger).
func TestBase64AlphabetPinned(t *testing.T) {
	if _, err := B64urlDecode("e30\n"); err == nil {
		t.Fatal("B64urlDecode accepted a trailing newline")
	}
	if _, err := B64urlDecode("e=30"); err == nil {
		t.Fatal("B64urlDecode accepted a stray '=' inside the payload")
	}
	if b, err := B64urlDecode("e30"); err != nil || string(b) != "{}" {
		t.Fatalf("B64urlDecode rejected canonical input: %v %q", err, b)
	}

	// the STRING shape of key_ops is deliberately lenient (substring "verify"),
	// mirroring the oracle's `in`-on-str quirk — pinned so a strict-side-wins
	// "cleanup" cannot silently flip it into an unrecorded divergence (V19 F2)
	if !keyOpsStringAccepted() {
		t.Fatal("key_ops string containing 'verify' no longer passes the shape gate")
	}
	// padding is NOT part of the raw wire form: B64urlDecode("e30=") must err
	// (the oracle accepts it — same forced-divergence family)
	if _, err := B64urlDecode("e30="); err == nil {
		t.Fatal("B64urlDecode accepted padded input")
	}
	// through the production path: a protected header with a trailing newline
	// must be rejected as "not base64url-encoded JSON", not verified. Note
	// "e30\n" is a BOTH-REJECT shape (residue 3 chars, no padding, undecodable
	// on the oracle too); the live divergence family is 0-mod-4 carriers with
	// a single trailing newline, where the oracle decodes and counts the kid
	compileLibraries()
	fx, err := LoadFixture(filepath.Join(ExamplesDir, "valid", "doc-extractor.json"))
	if err != nil {
		t.Fatal(err)
	}
	hash, _ := ContractHash(fx.Doc)
	errs, _ := EnvelopeErrors(map[string]any{
		"envelope_version": "0.1.0",
		"contract":         fx.Doc,
		"contract_hash":    hash,
		"signatures":       []any{map[string]any{"protected": "e30\n", "signature": "AA"}},
	}, &TrustStore{}, false)
	if !hasSubstr(errs, "not a base64url-encoded JSON object") {
		t.Fatalf("newline-bearing protected header not rejected: %v", errs)
	}
}

// TestJWKCoordinateAlphabetPinned locks the V13 F1 wire entry: a JWK whose
// coordinate carries non-alphabet characters (accepted by pyjwt's lenient
// decode, an opposite-verdict divergence) must be refused at store load.
func TestJWKCoordinateAlphabetPinned(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "lenient.jwks.json")
	coords := "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
	store := map[string]any{
		"keys": []any{map[string]any{
			"kty": "EC", "crv": "P-256", "x": coords + "    ", "y": coords,
			"kid": "lenient-2026", "use": "sig", "alg": "ES256",
		}},
	}
	raw, _ := json.Marshal(store)
	if err := os.WriteFile(p, raw, 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := LoadTrustStore(p); err == nil || !hasSubstr([]string{err.Error()}, "canonical base64url") {
		t.Fatalf("lenient JWK coordinate was not refused at load: %v", err)
	}
	// canonical twin loads fine
	store["keys"].([]any)[0].(map[string]any)["x"] = coords
	raw, _ = json.Marshal(store)
	if err := os.WriteFile(p, raw, 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := LoadTrustStore(p); err != nil {
		t.Fatalf("canonical store refused: %v", err)
	}
}

// TestKidTypePinned locks the kid wire entry (V15 4-lens M-1): an int kid
// files and fully verifies on the oracle but must be refused at load here.
func TestKidTypePinned(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "intkid.jwks.json")
	store := map[string]any{
		"keys": []any{map[string]any{
			"kty": "EC", "crv": "P-256",
			"x":   "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
			"y":   "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
			"kid": 5, "use": "sig", "alg": "ES256",
		}},
	}
	raw, _ := json.Marshal(store)
	if err := os.WriteFile(p, raw, 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := LoadTrustStore(p); err == nil || !hasSubstr([]string{err.Error()}, "has no kid") {
		t.Fatalf("int kid was not refused at load: %v", err)
	}
}

func keyOpsStringAccepted() bool {
	jwk := map[string]any{
		"kty": "EC", "crv": "P-256", "x": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
		"y": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "kid": "ops-str-2026",
		"use": "sig", "alg": "ES256", "key_ops": "myverifytool",
	}
	ts := &TrustStore{
		Keys:      map[string]map[string]any{"ops-str-2026": jwk},
		SubjectOf: map[string]map[string]bool{"ops-str-2026": {"doc-extractor": true}},
	}
	fx, err := LoadFixture(filepath.Join(ExamplesDir, "valid", "doc-extractor.json"))
	if err != nil {
		return false
	}
	hash, err := ContractHash(fx.Doc)
	if err != nil {
		return false
	}
	hdr, _ := json.Marshal(map[string]any{"alg": "ES256", "typ": "JOSE", "kid": "ops-str-2026"})
	errs, _ := EnvelopeErrors(map[string]any{
		"envelope_version": "0.1.0",
		"contract":         fx.Doc,
		"contract_hash":    hash,
		"signatures":       []any{map[string]any{"protected": B64url(hdr), "signature": "AA"}},
	}, ts, false)
	for _, e := range errs {
		if strings.Contains(e, "key_ops") {
			return false // shape gate fired — the pinned leniency regressed
		}
	}
	return true
}
