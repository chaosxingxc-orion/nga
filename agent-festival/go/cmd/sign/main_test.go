package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/go-jose/go-jose/v4"

	"festival-dev/go/internal/rfc8785"
	"festival-dev/go/internal/validate"
)

// TestSignEnvelopeRoundTrip pins cmd/sign's core path (V23 S3): a signed
// envelope object must carry a JOSE-typed protected header and a signature
// that verifies against JCS(contract) with the same key — the round trip the
// corpus regeneration depends on.
func TestSignEnvelopeRoundTrip(t *testing.T) {
	for _, root := range []string{"../../schema", "../../../schema"} {
		p := filepath.Join(root, "examples", "valid", "doc-extractor.json")
		if _, err := os.Stat(p); err != nil {
			continue
		}
		fx, err := validate.LoadFixture(p)
		if err != nil {
			t.Fatal(err)
		}
		kp, err := newKey("sign-roundtrip-2026")
		if err != nil {
			t.Fatal(err)
		}
		// typ deliberately NOT "JOSE": passing the same value as the assertion
		// made the param self-asserting — an ignored-param mutation was green (V24 F4)
		sig, err := sign(fx.Doc, kp, "sign-roundtrip-2026", "JWT", nil)
		if err != nil {
			t.Fatal(err)
		}
		hdrB64, _ := sig["protected"].(string)
		hdrRaw, err := validate.B64urlDecode(hdrB64)
		if err != nil {
			t.Fatal(err)
		}
		var hdr map[string]any
		if err := json.Unmarshal(hdrRaw, &hdr); err != nil {
			t.Fatal(err)
		}
		if hdr["typ"] != "JWT" || hdr["kid"] != "sign-roundtrip-2026" || hdr["alg"] != "ES256" {
			t.Fatalf("protected header wrong: %v", hdr)
		}
		// verify: go-jose over the exact RFC 7515 signing input
		payload, err := rfc8785.Canonicalize(fx.Doc)
		if err != nil {
			t.Fatal(err)
		}
		line := hdrB64 + "." + validate.B64url(payload) + "." + sig["signature"].(string)
		obj, err := jose.ParseSigned(line, []jose.SignatureAlgorithm{jose.ES256})
		if err != nil {
			t.Fatal(err)
		}
		var key jose.JSONWebKey
		jwkJSON, _ := json.Marshal(kp.pub)
		if err := key.UnmarshalJSON(jwkJSON); err != nil {
			t.Fatal(err)
		}
		if _, err := obj.Verify(&key); err != nil {
			t.Fatalf("round-trip signature did not verify: %v", err)
		}
		return
	}
	t.Fatal("schema examples not found")
}

// TestLoadContractParseError pins the loud rejection (V29 F-5, evidenced
// now — V30 F-2): a fixture whose parse fails must NOT flow into signing.
func TestLoadContractParseError(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "bad.json")
	if err := os.WriteFile(p, []byte(`{"contract_version": "0.1.0", "_expect_match": 5}`), 0o644); err != nil {
		t.Fatal(err)
	}
	_, err := loadContract(dir, "bad.json")
	if err == nil {
		t.Fatal("loadContract accepted a fixture with a parse error — it would sign a malformed document")
	}
	if !strings.Contains(err.Error(), "must be a string") {
		t.Fatalf("the parse reason is missing from the error (message face unpinned — V32 NIT): %v", err)
	}
}
