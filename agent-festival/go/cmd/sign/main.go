// sign regenerates the envelope example suite with fresh ephemeral keys.
// It is the Go successor of schema/sign.py: every run creates new EC P-256 key
// pairs (publisher bound to the two example agents, tester as unbound endorser,
// three bound keys that each fail exactly one JWK check, another publisher bound
// to a different agent, and a rogue key that is deliberately NOT trusted),
// signs the valid contracts, writes the trusted store and the three must-reject
// key stores, and derives every must-reject envelope by programmatic mutation
// of a valid one — so the invalid examples can never drift out of sync with the
// signatures. Private keys never touch disk. Re-running rewrites all envelope
// examples and the key store together; commit them as one change.
//
// Usage: go run ./cmd/sign            # regenerate schema/examples/** under the discovered schema dir
package main

import (
	"bytes"
	"crypto"
	"crypto/ecdsa"
	"crypto/ed25519"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/rsa"
	"encoding/json"
	"fmt"
	"math/big"
	"os"
	"path/filepath"
	"strings"

	"github.com/go-jose/go-jose/v4"

	"festival-dev/go/internal/rfc8785"
	"festival-dev/go/internal/validate"
)

type keyPair struct {
	priv crypto.Signer
	alg  jose.SignatureAlgorithm
	pub  map[string]any
}

func newKey(kid string) (keyPair, error) {
	priv, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		return keyPair{}, err
	}
	pub := map[string]any{
		"kty": "EC",
		"crv": "P-256",
		"x":   validate.B64url(fixedWidth(priv.X, 32)),
		"y":   validate.B64url(fixedWidth(priv.Y, 32)),
		"kid": kid,
		"use": "sig",
		"alg": "ES256",
	}
	return keyPair{priv: priv, alg: jose.ES256, pub: pub}, nil
}

// newRSAKey / newEdKey exist so the suite exercises every allowed algorithm's
// signing AND verification path positively (V3 m5: RS256/EdDSA had zero
// positive examples — a wiring mistake there would leave both suites green).
func newRSAKey(kid string) (keyPair, error) {
	priv, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		return keyPair{}, err
	}
	pub := map[string]any{
		"kty": "RSA",
		"n":   validate.B64url(priv.N.Bytes()),
		"e":   validate.B64url(big.NewInt(int64(priv.E)).Bytes()),
		"kid": kid,
		"use": "sig",
		"alg": "RS256",
	}
	return keyPair{priv: priv, alg: jose.RS256, pub: pub}, nil
}

func newEdKey(kid string) (keyPair, error) {
	pubKey, priv, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		return keyPair{}, err
	}
	pub := map[string]any{
		"kty": "OKP",
		"crv": "Ed25519",
		"x":   validate.B64url(pubKey),
		"kid": kid,
		"use": "sig",
		"alg": "EdDSA",
	}
	return keyPair{priv: priv, alg: jose.EdDSA, pub: pub}, nil
}

// fixedWidth left-pads a big-endian integer to n bytes (JWA §6.2.1 coordinates).
func fixedWidth(v *big.Int, n int) []byte {
	b := v.Bytes()
	out := make([]byte, n)
	copy(out[n-len(b):], b)
	return out
}

// sign produces one envelope signature over JCS(contract) with the RFC 7515
// signing input "protected.payload". The protected header is built by go-jose
// (alg, typ, kid and any extras); both verifiers re-read it from the wire bytes,
// so field order never affects verification.
func sign(contract map[string]any, kp keyPair, kid, typ string, extra map[string]any) (map[string]any, error) {
	priv, alg := kp.priv, kp.alg
	canonical, err := rfc8785.Canonicalize(contract)
	if err != nil {
		return nil, err
	}
	opts := (&jose.SignerOptions{}).WithHeader("typ", typ).WithHeader("kid", kid)
	for k, v := range extra {
		opts = opts.WithHeader(jose.HeaderKey(k), v)
	}
	signer, err := jose.NewSigner(jose.SigningKey{Algorithm: alg, Key: priv}, opts)
	if err != nil {
		return nil, err
	}
	obj, err := signer.Sign(canonical)
	if err != nil {
		return nil, err
	}
	compact, err := obj.CompactSerialize()
	if err != nil {
		return nil, err
	}
	parts := strings.Split(compact, ".")
	return map[string]any{"protected": parts[0], "signature": parts[2]}, nil
}

type signerRef struct {
	kid string
	kp  keyPair
}

func envelope(contract map[string]any, signers []signerRef) (map[string]any, error) {
	sigs := make([]any, 0, len(signers))
	kids := make([]any, 0, len(signers))
	for _, s := range signers {
		sig, err := sign(contract, s.kp, s.kid, "JOSE", nil)
		if err != nil {
			return nil, err
		}
		sigs = append(sigs, sig)
		kids = append(kids, s.kid)
	}
	hash, err := validate.ContractHash(contract)
	if err != nil {
		return nil, err
	}
	return map[string]any{
		"_expect_verified_kids": kids,
		"envelope_version":      "0.1.0",
		"contract":              contract,
		"contract_hash":         hash,
		"signatures":            sigs,
	}, nil
}

func loadContract(examplesDir, name string) (map[string]any, error) {
	fx, err := validate.LoadFixture(filepath.Join(examplesDir, name))
	if err != nil {
		return nil, err
	}
	if fx.ParseError != "" {
		return nil, fmt.Errorf("%s: %s", name, fx.ParseError) // loud: a rejected parse must not flow into signing (V29 F-5)
	}
	return fx.Doc, nil
}

func writeJSON(path string, v any) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	enc.SetIndent("", "  ")
	if err := enc.Encode(v); err != nil {
		return err
	}
	return os.WriteFile(path, buf.Bytes(), 0o644)
}

// loneSurrogateMarker stands in for a lone \ud800 escape: Go strings cannot hold
// one, so the escape text is spliced into the serialized JSON afterwards.
const loneSurrogateMarker = "@@LONE-SURROGATE@@"

func clone(m map[string]any) map[string]any { return validate.CloneDoc(m) } // single source (V23 4-lens n3)

func flipFirstChar(s string) string {
	if len(s) == 0 {
		return s
	}
	if s[0] == 'A' {
		return "B" + s[1:]
	}
	return "A" + s[1:]
}

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, "sign:", err)
		os.Exit(1)
	}
}

func run() error {
	ex := validate.ExamplesDir
	if ex == "" {
		return fmt.Errorf("schema examples dir not found")
	}

	pub, err := newKey("publisher-2026-09")
	if err != nil {
		return err
	}
	test, err := newKey("tester-2026-09")
	if err != nil {
		return err
	}
	rogue, err := newKey("rogue-2026-09") // never enters the trusted store
	if err != nil {
		return err
	}
	encK, err := newKey("enc-only-2026-09") // trusted, but published as an encryption key
	if err != nil {
		return err
	}
	encK.pub["use"] = "enc"
	other, err := newKey("other-publisher-2026-09") // trusted owner of a different agent
	if err != nil {
		return err
	}
	ops, err := newKey("ops-enc-2026-09") // trusted, bound, use=sig, but key_ops says encrypt only
	if err != nil {
		return err
	}
	ops.pub["key_ops"] = []any{"encrypt"}
	algRS, err := newKey("alg-rs-2026-09") // trusted, bound, but published for RS256
	if err != nil {
		return err
	}
	algRS.pub["alg"] = "RS256"
	rsTester, err := newRSAKey("rs-tester-2026-09") // unbound endorser exercising the RS256 path
	if err != nil {
		return err
	}
	edTester, err := newEdKey("ed-tester-2026-09") // unbound endorser exercising the EdDSA path
	if err != nil {
		return err
	}
	fffdOwner, err := newKey("fffd-probe-2026") // signs the literal-U+FFFD probe envelope
	if err != nil {
		return err
	}

	if err := writeJSON(filepath.Join(ex, "keys", "trusted.jwks.json"), map[string]any{
		"keys": []any{pub.pub, test.pub, encK.pub, other.pub, ops.pub, algRS.pub, rsTester.pub, edTester.pub, fffdOwner.pub},
		"subject_of": map[string]any{ // owner binding; kids absent here are endorsers
			"publisher-2026-09":       []any{"doc-extractor", "compliance-filer"},
			"enc-only-2026-09":        []any{"doc-extractor"},
			"ops-enc-2026-09":         []any{"doc-extractor"},
			"alg-rs-2026-09":          []any{"doc-extractor"},
			"other-publisher-2026-09": []any{"ledger-poster"},
			"fffd-probe-2026":         []any{"doc-extractor"},
		},
	}); err != nil {
		return err
	}

	noKid := clone(test.pub)
	delete(noKid, "kid")
	if err := writeJSON(filepath.Join(ex, "keys", "invalid", "duplicate-kid.jwks.json"), map[string]any{
		"_expect":       "REJECT at load: two entries share a kid; last-wins would let the second appender sign as the first",
		"_expect_match": "duplicate kid",
		"keys":          []any{pub.pub, withKid(test.pub, "publisher-2026-09")},
	}); err != nil {
		return err
	}
	if err := writeJSON(filepath.Join(ex, "keys", "invalid", "missing-kid.jwks.json"), map[string]any{
		"_expect":       "REJECT at load: an entry without kid would be silently dropped and its signer indistinguishable from an impostor",
		"_expect_match": "has no kid",
		"keys":          []any{pub.pub, noKid},
	}); err != nil {
		return err
	}
	if err := writeJSON(filepath.Join(ex, "keys", "invalid", "binding-unknown-kid.jwks.json"), map[string]any{
		"_expect":       "REJECT at load: subject_of names a kid that has no key; a dangling binding is a typo, not a policy",
		"_expect_match": "unknown kid",
		"keys":          []any{pub.pub},
		"subject_of":    map[string]any{"publsher-2026-09": []any{"doc-extractor"}},
	}); err != nil {
		return err
	}

	docExtractor, err := loadContract(ex, "valid/doc-extractor.json")
	if err != nil {
		return err
	}
	complianceFiler, err := loadContract(ex, "valid/compliance-filer.json")
	if err != nil {
		return err
	}
	twoSigners, err := envelope(docExtractor, []signerRef{{"publisher-2026-09", pub}, {"tester-2026-09", test}})
	if err != nil {
		return err
	}
	// every allowed algorithm signs this one valid envelope (positive path coverage, V3 m5)
	fourSigners, err := envelope(docExtractor, []signerRef{
		{"publisher-2026-09", pub}, {"tester-2026-09", test},
		{"rs-tester-2026-09", rsTester}, {"ed-tester-2026-09", edTester},
	})
	if err != nil {
		return err
	}
	if err := writeJSON(filepath.Join(ex, "envelopes", "valid", "doc-extractor.envelope.json"), fourSigners); err != nil {
		return err
	}
	// literal U+FFFD inside the SIGNED contract is legal (only lone-surrogate
	// ESCAPES are not canonicalizable) — pins that distinction forever (V2 M3)
	fffdContract := clone(docExtractor)
	fffdContract["notes"] = "legal literal replacement char � here"
	fffdEnv, err := envelope(fffdContract, []signerRef{{"fffd-probe-2026", fffdOwner}})
	if err != nil {
		return err
	}
	if err := writeJSON(filepath.Join(ex, "envelopes", "valid", "literal-fffd.envelope.json"), fffdEnv); err != nil {
		return err
	}
	// a lone-surrogate ESCAPE in the unsigned header region is accepted by the
	// oracle (canonicalization only ever touches the contract) — pinning that
	// boundary forever (V4 MAJOR-1 regression fixture)
	headerSurrogate := clone(fffdEnv)
	if sigs, ok := headerSurrogate["signatures"].([]any); ok && len(sigs) > 0 {
		s0, _ := sigs[0].(map[string]any)
		s0["header"] = map[string]any{"note": "see " + loneSurrogateMarker + " here"}
	}
	if err := writeSpliced(filepath.Join(ex, "envelopes", "valid", "literal-fffd-header-surrogate.envelope.json"), headerSurrogate, loneSurrogateMarker, `ud800`); err != nil {
		return err
	}
	filerEnv, err := envelope(complianceFiler, []signerRef{{"publisher-2026-09", pub}})
	if err != nil {
		return err
	}
	if err := writeJSON(filepath.Join(ex, "envelopes", "valid", "compliance-filer.envelope.json"), filerEnv); err != nil {
		return err
	}

	validEnvelopeCount := 0
	for _, name := range []string{"doc-extractor.envelope.json", "literal-fffd.envelope.json", "literal-fffd-header-surrogate.envelope.json", "compliance-filer.envelope.json"} {
		if _, err := os.Stat(filepath.Join(ex, "envelopes", "valid", name)); err == nil {
			validEnvelopeCount++
		}
	}

	inv := filepath.Join(ex, "envelopes", "invalid")
	stale, _ := filepath.Glob(filepath.Join(inv, "*.json"))
	for _, f := range stale {
		if err := os.Remove(f); err != nil {
			return err
		}
	}

	base := clone(twoSigners)
	delete(base, "_expect_verified_kids")
	mutant := func() map[string]any { return clone(base) }

	type caseDef struct {
		name, expect, match string
		edit                func(map[string]any) (map[string]any, error)
	}
	cases := []caseDef{
		{"tampered-contract", "REJECT: contract edited after signing (hash recomputed so only JWS verification catches it)", "does not verify",
			func(m map[string]any) (map[string]any, error) {
				c := m["contract"].(map[string]any)
				b := c["bounds"].(map[string]any)
				mc := b["max_cost"].(map[string]any)
				mc["amount"] = mc["amount"].(float64) + 7
				h, err := validate.ContractHash(c)
				if err != nil {
					return nil, err
				}
				m["contract_hash"] = h
				return m, nil
			}},
		{"hash-mismatch", "REJECT: contract_hash does not match JCS(contract)", "contract_hash",
			func(m map[string]any) (map[string]any, error) {
				h := m["contract_hash"].(string)
				last := "0"
				if h[len(h)-1] == '0' {
					last = "1"
				}
				m["contract_hash"] = h[:len(h)-1] + last
				return m, nil
			}},
		{"alg-none", "REJECT: alg 'none' is never acceptable", "alg 'none'",
			func(m map[string]any) (map[string]any, error) {
				hdr, _ := json.Marshal(map[string]any{"alg": "none", "typ": "JOSE", "kid": "publisher-2026-09"})
				m["signatures"] = []any{map[string]any{"protected": validate.B64url(hdr), "signature": "AA"}}
				return m, nil
			}},
		{"bad-typ", "REJECT: protected header typ must be 'JOSE' (A2A §8.4.2)", "typ must be",
			func(m map[string]any) (map[string]any, error) {
				sig, err := sign(m["contract"].(map[string]any), pub, "publisher-2026-09", "JWT", nil)
				if err != nil {
					return nil, err
				}
				m["signatures"] = []any{sig}
				return m, nil
			}},
		{"enc-key", "REJECT: the kid resolves to a key published with use=enc; encryption keys never verify signatures (RFC 7517 §4.3)", "not a signing key",
			func(m map[string]any) (map[string]any, error) {
				sig, err := sign(m["contract"].(map[string]any), encK, "enc-only-2026-09", "JOSE", nil)
				if err != nil {
					return nil, err
				}
				m["signatures"] = []any{sig}
				return m, nil
			}},
		{"unknown-kid", "REJECT: valid signature but kid is not in the trusted key store", "not in trusted key store",
			func(m map[string]any) (map[string]any, error) {
				sig, err := sign(m["contract"].(map[string]any), rogue, "rogue-2026-09", "JOSE", nil)
				if err != nil {
					return nil, err
				}
				m["signatures"] = []any{sig}
				return m, nil
			}},
		{"key-ops-no-verify", "REJECT: the kid's JWK has key_ops without 'verify' (RFC 7517 §4.3)", "without 'verify'",
			func(m map[string]any) (map[string]any, error) {
				sig, err := sign(m["contract"].(map[string]any), ops, "ops-enc-2026-09", "JOSE", nil)
				if err != nil {
					return nil, err
				}
				m["signatures"] = []any{sig}
				return m, nil
			}},
		{"alg-mismatch", "REJECT: the kid's JWK is published for RS256, the protected header says ES256 (RFC 7517 §4.4)", "is published for alg",
			func(m map[string]any) (map[string]any, error) {
				sig, err := sign(m["contract"].(map[string]any), algRS, "alg-rs-2026-09", "JOSE", nil)
				if err != nil {
					return nil, err
				}
				m["signatures"] = []any{sig}
				return m, nil
			}},
		{"crit-header", "REJECT: a critical header parameter this verifier does not implement (RFC 7515 §4.1.11)", "critical header",
			func(m map[string]any) (map[string]any, error) {
				sig, err := sign(m["contract"].(map[string]any), pub, "publisher-2026-09", "JOSE", map[string]any{"crit": []any{"exp"}, "exp": 0})
				if err != nil {
					return nil, err
				}
				m["signatures"] = []any{sig}
				return m, nil
			}},
		{"duplicate-signer", "REJECT: one key, two signatures; endorsements are counted per key", "already signed",
			func(m map[string]any) (map[string]any, error) {
				sig, err := sign(m["contract"].(map[string]any), pub, "publisher-2026-09", "JOSE", nil)
				if err != nil {
					return nil, err
				}
				m["signatures"] = []any{sig, clone(sig)}
				return m, nil
			}},
		{"endorser-only", "REJECT: only an endorser (kid with no subject binding) signed; the owner's self-declaration is missing", "no signature from a key bound to subject",
			func(m map[string]any) (map[string]any, error) {
				sig, err := sign(m["contract"].(map[string]any), test, "tester-2026-09", "JOSE", nil)
				if err != nil {
					return nil, err
				}
				m["signatures"] = []any{sig}
				return m, nil
			}},
		{"wrong-owner", "REJECT: the signing kid is bound to a different agent; any trusted key could otherwise 'self-declare' for anyone", "is bound to",
			func(m map[string]any) (map[string]any, error) {
				sig, err := sign(m["contract"].(map[string]any), other, "other-publisher-2026-09", "JOSE", nil)
				if err != nil {
					return nil, err
				}
				m["signatures"] = []any{sig}
				return m, nil
			}},
		{"one-of-two-bad", "REJECT: every signature present must verify; a broken second signature is a forgery signal, not noise", "signatures/1",
			func(m map[string]any) (map[string]any, error) {
				sigs := m["signatures"].([]any)
				s1 := sigs[1].(map[string]any)
				s1["signature"] = flipFirstChar(s1["signature"].(string))
				return m, nil
			}},
		{"no-signatures", "REJECT: an envelope with no endorser is not an envelope", "non-empty",
			func(m map[string]any) (map[string]any, error) {
				m["signatures"] = []any{}
				return m, nil
			}},
		{"lone-surrogate", "REJECT (not crash): contract text contains a lone UTF-16 surrogate; RFC 8785 output must be UTF-8", "lone surrogate",
			func(m map[string]any) (map[string]any, error) {
				m["contract"].(map[string]any)["notes"] = "see " + loneSurrogateMarker + " appendix"
				return m, nil // hash left as-is; canonicalization fails before comparison
			}},
		{"signed-but-invalid-contract", "REJECT: a valid signature never relaxes the contract gate (D8 wildcard selector)", "selector",
			func(m map[string]any) (map[string]any, error) {
				bad, err := loadContract(ex, "invalid/wildcard-selector.json")
				if err != nil {
					return nil, err
				}
				h, err := validate.ContractHash(bad)
				if err != nil {
					return nil, err
				}
				sig, err := sign(bad, pub, "publisher-2026-09", "JOSE", nil)
				if err != nil {
					return nil, err
				}
				m["contract"], m["contract_hash"], m["signatures"] = bad, h, []any{sig}
				return m, nil
			}},
	}

	for _, c := range cases {
		m := mutant()
		if _, err := c.edit(m); err != nil {
			return err
		}
		out := map[string]any{"_expect": c.expect, "_expect_match": c.match}
		for k, v := range m {
			out[k] = v
		}
		if c.name == "lone-surrogate" {
			if err := writeSpliced(filepath.Join(inv, c.name+".json"), out, loneSurrogateMarker, `ud800`); err != nil {
				return err
			}
			continue
		}
		if err := writeJSON(filepath.Join(inv, c.name+".json"), out); err != nil {
			return err
		}
	}

	fmt.Printf("wrote 1 key store + 3 invalid key stores, %d valid envelopes, %d invalid envelopes under %s\n", validEnvelopeCount, len(cases), ex)
	return nil
}

func withKid(jwk map[string]any, kid string) map[string]any {
	out := clone(jwk)
	out["kid"] = kid
	return out
}

// writeSpliced serializes the doc, then replaces marker text with raw JSON
// escape source (backslash included) — used only for the lone-surrogate mutant.
func writeSpliced(path string, v any, marker, escapeSrc string) error {
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	enc.SetIndent("", "  ")
	if err := enc.Encode(v); err != nil {
		return err
	}
	data := bytes.ReplaceAll(buf.Bytes(), []byte(marker), []byte(`\`+escapeSrc))
	return os.WriteFile(path, data, 0o644)
}
