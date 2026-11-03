// Package validate validates L3 capability contracts and signed contract envelopes.
// It is the Go successor of schema/validate.py (frozen oracle): same examples,
// same _expect_match / _expect_verified_kids pins, same cross-field rules.
package validate

import (
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"unicode/utf8"

	"github.com/go-jose/go-jose/v4"

	"github.com/openjiuwen/agent-festival/go/internal/rfc8785"
)

// ---------- schema loading ----------

type Schema map[string]any

func LoadSchema(path string) (Schema, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var s Schema
	if err := json.Unmarshal(raw, &s); err != nil {
		return nil, err
	}
	return s, nil
}

var (
	ContractSchema Schema
	EnvelopeSchema Schema
	ExamplesDir    string
)

func init() {
	// run from the go/ module directory (go run ./cmd/validate)
	for _, root := range []string{".", "..", "../..", "../../.."} { // last root: go test runs from cmd/<x>/
		d := filepath.Join(root, "schema")
		if _, err := os.Stat(filepath.Join(d, "capability-contract.schema.json")); err == nil {
			ExamplesDir = filepath.Join(d, "examples")
			ContractSchema, _ = LoadSchema(filepath.Join(d, "capability-contract.schema.json"))
			EnvelopeSchema, _ = LoadSchema(filepath.Join(d, "contract-envelope.schema.json"))
			return
		}
	}
}

// ---------- JSON Schema message rendering (minimal 2020-12 subset) ----------
// The schemas use: type, properties, additionalProperties, required, items,
// enum, const, pattern, minLength, maxLength, minimum, maximum, exclusiveMinimum,
// oneOf, $ref/$defs/$id, minItems, maxItems, uniqueItems, description.
// SEMANTIC verdicts come from the industry library (schemalib.go); this engine
// renders the frozen oracle's Python-jsonschema message phrasings, which the
// fixture pins lock. Any semantic drift between the two engines trips the
// fail-closed disagreement alarm; fixtures alone only pin the phrasings.

var escapeRe = regexp.MustCompile(`%([0-9A-F]{2})`)

// selectorPattern is the single schema pattern using lookaheads (Python re supports
// them, Go RE2 does not). It must match this exact string; anything else that fails
// RE2 compilation is a schema this engine cannot enforce and is reported, not skipped.
const selectorPattern = `^(?!\*$)(?!.*%2[aA])[\x21-\x7E]+$`

// percentHasBadEscape reports a '%' not followed by two uppercase hex digits
// (Go regexp lacks lookahead; manual scan emulates Python's %(?![0-9A-F]{2})).
func percentHasBadEscape(s string) bool {
	for i := 0; i < len(s); i++ {
		if s[i] != '%' {
			continue
		}
		if i+2 >= len(s) || !isUpperHex(s[i+1]) || !isUpperHex(s[i+2]) {
			return true
		}
	}
	return false
}

func isUpperHex(c byte) bool {
	return (c >= '0' && c <= '9') || (c >= 'A' && c <= 'F')
}

const unreserved = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"

var rootSchema Schema

func SchemaErrors(doc any, schema Schema, path string, errs *[]string) {
	// $ref resolution: same-document $defs (rootSchema is the document currently being
	// validated against — set by ContractErrors / EnvelopeErrors / compose) and
	// cross-document URL refs into the contract schema. Both fail closed: an
	// unresolvable ref is an error, never a silent pass.
	if ref, ok := schema["$ref"].(string); ok {
		if strings.HasPrefix(ref, "#/$defs/") {
			name := strings.TrimPrefix(ref, "#/$defs/")
			if rootSchema != nil {
				if defs, ok := rootSchema["$defs"].(map[string]any); ok {
					if def, ok := defs[name].(map[string]any); ok {
						SchemaErrors(doc, def, path, errs)
						return
					}
				}
			}
			*errs = append(*errs, fmt.Sprintf("%s: unresolved $ref %s (not in $defs)", path, ref))
			return
		}
		if strings.HasPrefix(ref, "https://agent-festival.local/schema/") {
			// cross-schema refs only ever target the contract schema (by its $id,
			// optionally with a JSON pointer). While validating inside it, #/$defs
			// refs resolve against the contract schema's own defs, not the caller's.
			var target Schema = ContractSchema
			ok := true
			if i := strings.Index(ref, "#/"); i >= 0 {
				target, ok = resolvePointer(ContractSchema, ref[i:])
			} else if ref != ContractSchema["$id"] {
				ok = false
			}
			if !ok {
				*errs = append(*errs, fmt.Sprintf("%s: unresolvable cross-schema $ref %s", path, ref))
				return
			}
			savedRoot := rootSchema
			rootSchema = ContractSchema
			SchemaErrors(doc, target, path, errs)
			rootSchema = savedRoot
			return
		}
		*errs = append(*errs, fmt.Sprintf("%s: unsupported $ref %s", path, ref))
		return
	}
	// type
	if t, ok := schema["type"].(string); ok && !typeMatches(doc, t) {
		*errs = append(*errs, fmt.Sprintf("%s: %s is not of type '%s'", path, typeName(doc), t))
		return
	}
	// enum
	if ev, ok := schema["enum"].([]any); ok { // an EMPTY enum rejects everything, like python-jsonschema (V27 n1, landed V28)
		found := false
		for _, e := range ev {
			if jsonEqual(doc, e) {
				found = true
				break
			}
		}
		if !found {
			*errs = append(*errs, fmt.Sprintf("%s: %v is not one of %v", path, doc, ev))
		}
	}
	// const
	if cv, ok := schema["const"]; ok && !jsonEqual(doc, cv) {
		*errs = append(*errs, fmt.Sprintf("%s: '%v' was expected", path, cv))
	}
	// pattern (string only). The selector pattern is the one lookahead pattern our schemas
	// use; Go's RE2 cannot compile lookaheads, so it is matched by the equivalent semantic
	// gate (D39/D40). Any other pattern RE2 cannot compile is an error, never a skip: a
	// skipped pattern would silently admit everything it was meant to reject.
	if p, ok := schema["pattern"].(string); ok {
		if s, isStr := doc.(string); isStr {
			if p == selectorPattern {
				if !selectorGateOK(s) {
					*errs = append(*errs, fmt.Sprintf("%s: %q does not match '%s'", path, s, p))
				}
			} else if re, err := regexp.Compile(p); err != nil {
				*errs = append(*errs, fmt.Sprintf("%s: schema pattern %q cannot be enforced by this engine (fail closed)", path, p))
			} else if !patternMatches(re, p, s) {
				*errs = append(*errs, fmt.Sprintf("%s: %q does not match '%s'", path, s, p))
			}
		}
	}
	if s, isStr := doc.(string); isStr {
		if ml, ok := schema["minLength"].(float64); ok && float64(len([]rune(s))) < ml {
			if ml == 1 && len(s) == 0 {
				*errs = append(*errs, fmt.Sprintf("%s: %q should be non-empty", path, s))
			} else {
				// python-jsonschema wording: "'a' is too short" — no counts
				*errs = append(*errs, fmt.Sprintf("%s: %q is too short", path, s))
			}
		}
		if ml, ok := schema["maxLength"].(float64); ok && float64(len([]rune(s))) > ml {
			// python-jsonschema wording: "'ab' is too long" — no counts
			*errs = append(*errs, fmt.Sprintf("%s: %q is too long", path, s))
		}
	}
	n, isNum := numericValue(doc)
	if isNum {
		if mn, ok := schema["minimum"].(float64); ok && n < mn {
			*errs = append(*errs, fmt.Sprintf("%s: %s is less than the minimum of %s", path, fmtNum(n), fmtNum(mn)))
		}
		if mx, ok := schema["maximum"].(float64); ok && n > mx {
			*errs = append(*errs, fmt.Sprintf("%s: %s is greater than the maximum of %s", path, fmtNum(n), fmtNum(mx)))
		}
		if em, ok := schema["exclusiveMinimum"].(float64); ok && n <= em {
			*errs = append(*errs, fmt.Sprintf("%s: %s is less than or equal to the minimum of %s", path, fmtNum(n), fmtNum(em)))
		}
	}
	// object
	if m, isMap := doc.(map[string]any); isMap {
		if req, ok := schema["required"].([]any); ok {
			for _, r := range req {
				if rs, _ := r.(string); rs != "" {
					if _, present := m[rs]; !present {
						*errs = append(*errs, fmt.Sprintf("%s: '%s' is a required property", path, rs))
					}
				}
			}
		}
		props, _ := schema["properties"].(map[string]any)
		addlSchema, hasAddlSchema := schema["additionalProperties"].(map[string]any)
		addl, addlIsBool := schema["additionalProperties"].(bool)
		addlFalse := addlIsBool && !addl
		// sorted iteration: map order randomization made errs[0] flap between
		// runs of the same binary (V22 4-lens m2) — verdicts were always stable
		// (anyContains), but first-line output must not be a coin flip
		sortedKeys := make([]string, 0, len(m))
		for k := range m {
			sortedKeys = append(sortedKeys, k)
		}
		sort.Strings(sortedKeys)
		for _, k := range sortedKeys {
			v := m[k]
			if ps, ok := props[k].(map[string]any); ok {
				SchemaErrors(v, ps, path+"/"+k, errs)
			} else if hasAddlSchema {
				// additionalProperties as a SCHEMA (the graph schema maps every
				// node key to the contract schema this way) — the differential
				// library caught this gap (V2 differential round, node-fails-contract-gate)
				SchemaErrors(v, addlSchema, path+"/"+k, errs)
			} else if addlFalse {
				*errs = append(*errs, fmt.Sprintf("%s: Additional properties are not allowed ('%s' was unexpected)", path, k))
			}
		}
	}
	// array
	if arr, isArr := doc.([]any); isArr {
		if mi, ok := schema["minItems"].(float64); ok && float64(len(arr)) < mi {
			// full path AND the actual instance, matching the oracle's two
			// phrasings: "requires/0/actions: [] should be non-empty" for the
			// empty case, "edges/0: ['a'] is too short" for minItems>=2 —
			// the lastSegment truncation was never landed in V25 (V29 M-1)
			if mi == 1 && len(arr) == 0 {
				*errs = append(*errs, fmt.Sprintf("%s: %v should be non-empty", path, arr))
			} else {
				*errs = append(*errs, fmt.Sprintf("%s: %v is too short", path, arr))
			}
		}
		if ma, ok := schema["maxItems"].(float64); ok && float64(len(arr)) > ma {
			*errs = append(*errs, fmt.Sprintf("%s: %v is too long", path, arr))
		}
		if uu, ok := schema["uniqueItems"].(bool); ok && uu && !uniqueArr(arr) {
			*errs = append(*errs, fmt.Sprintf("%s: %v has non-unique elements", path, arr))
		}
		if items, ok := schema["items"].(map[string]any); ok {
			for i, e := range arr {
				SchemaErrors(e, items, fmt.Sprintf("%s/%d", path, i), errs)
			}
		}
	}
	// contains (array containment: at least one item matching the subschema)
	if contains, ok := schema["contains"].(map[string]any); ok {
		if arr, isArr := doc.([]any); isArr {
			matched := false
			for _, e := range arr {
				var e2 []string
				SchemaErrors(e, contains, path, &e2)
				if len(e2) == 0 {
					matched = true
					break
				}
			}
			if !matched {
				*errs = append(*errs, fmt.Sprintf("%s: no items match the contains subschema", path))
			}
		}
	}
	// propertyNames
	if pn, ok := schema["propertyNames"].(map[string]any); ok {
		if m, isMap := doc.(map[string]any); isMap {
			if pat, ok := pn["pattern"].(string); ok {
				// lookahead patterns fail RE2 compilation and fall into the
				// fail-closed branch below — including the selector pattern,
				// which no schema currently uses in propertyNames
				if re2, err := regexp.Compile(pat); err != nil {
					*errs = append(*errs, fmt.Sprintf("%s: schema propertyNames pattern %q cannot be enforced by this engine (fail closed)", path, pat))
				} else {
					pnKeys := make([]string, 0, len(m))
					for k := range m {
						pnKeys = append(pnKeys, k)
					}
					sort.Strings(pnKeys) // deterministic error order (V23 4-lens M-1 sibling)
					for _, k := range pnKeys {
						if !patternMatches(re2, pat, k) {
							*errs = append(*errs, fmt.Sprintf("%s: property name %q does not match '%s'", path, k, pat))
						}
					}
				}
			}
		}
	}
	// minProperties / maxProperties. minProperties:1 on an empty object gets
	// the oracle's "should be non-empty" phrasing (V24 4-lens m1, probed)
	if mp, ok := schema["minProperties"].(float64); ok {
		if m, isMap := doc.(map[string]any); isMap && float64(len(m)) < mp {
			if mp == 1 && len(m) == 0 {
				*errs = append(*errs, fmt.Sprintf("%s: {} should be non-empty", path))
			} else {
				*errs = append(*errs, fmt.Sprintf("%s: fewer than %d properties", path, int(mp)))
			}
		}
	}
	if mp, ok := schema["maxProperties"].(float64); ok {
		if m, isMap := doc.(map[string]any); isMap && float64(len(m)) > mp {
			*errs = append(*errs, fmt.Sprintf("%s: has too many properties (%d, maximum is %d)", path, len(m), int(mp)))
		}
	}
	// allOf with if/then (the grant def's conditional constraints)
	if allOf, ok := schema["allOf"].([]any); ok {
		for _, sub := range allOf {
			sm, ok := sub.(map[string]any)
			if !ok {
				continue
			}
			ifCond, hasIf := sm["if"].(map[string]any)
			thenS, hasThen := sm["then"].(map[string]any)
			if !hasIf || !hasThen {
				continue
			}
			var ifErrs []string
			SchemaErrors(doc, ifCond, path, &ifErrs)
			if len(ifErrs) == 0 {
				SchemaErrors(doc, thenS, path, errs)
			}
		}
	}
	// oneOf
	if oneOf, ok := schema["oneOf"].([]any); ok {
		matched := 0
		var oneErrs []string
		for _, sub := range oneOf {
			if sm, ok := sub.(map[string]any); ok {
				var e []string
				SchemaErrors(doc, sm, path, &e)
				if len(e) == 0 {
					matched++
				} else {
					oneErrs = e
				}
			}
		}
		if matched != 1 {
			if len(oneErrs) > 0 {
				*errs = append(*errs, oneErrs...)
			} else {
				*errs = append(*errs, fmt.Sprintf("%s: matched %d oneOf branches, need exactly 1", path, matched))
			}
		}
		return // oneOf consumes
	}
}

func uniqueArr(arr []any) bool {
	seen := map[string]bool{}
	for _, e := range arr {
		b, _ := json.Marshal(e)
		if seen[string(b)] {
			return false
		}
		seen[string(b)] = true
	}
	return true
}

func selectorGateOK(s string) bool {
	// Python re '$' matches before a single trailing newline (V3 MAJOR-1): the
	// oracle accepts selectors like "data:x\n", so the gate must too.
	if strings.HasSuffix(s, "\n") {
		s = s[:len(s)-1]
	}
	if s == "*" {
		return false
	}
	if strings.Contains(s, "%2a") || strings.Contains(s, "%2A") {
		return false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < 0x21 || s[i] > 0x7E {
			return false
		}
	}
	return len(s) > 0
}

// patternMatches applies a compiled RE2 pattern with Python's '$' semantics:
// Python re matches before a single trailing newline; RE2's '$' is absolute.
func patternMatches(re *regexp.Regexp, pattern, s string) bool {
	if re.MatchString(s) {
		return true
	}
	if strings.HasSuffix(pattern, "$") && strings.HasSuffix(s, "\n") {
		return re.MatchString(s[:len(s)-1])
	}
	return false
}

func typeMatches(doc any, t string) bool {
	switch t {
	case "object":
		_, ok := doc.(map[string]any)
		return ok
	case "array":
		_, ok := doc.([]any)
		return ok
	case "string":
		_, ok := doc.(string)
		return ok
	case "boolean":
		_, ok := doc.(bool)
		return ok
	case "number":
		switch doc.(type) {
		case float64, int64, int:
			return true // int64/int from programmatic callers (guards suite rationale)
		}
		return false
	case "integer":
		switch v := doc.(type) {
		case int64, int:
			return true
		case float64:
			if math.IsInf(v, 0) || math.IsNaN(v) {
				return false // Python float.is_integer() is False for non-finite values
			}
			// any non-fractional value is an integer; the maximum keyword rejects oversized ones
			return v == float64(int64(v)) || v >= 9223372036854775808.0 || v <= -9223372036854775808.0
		}
		return false
	case "null":
		return doc == nil
	}
	return true
}

func typeName(doc any) string {
	switch doc.(type) {
	case map[string]any:
		return "object"
	case []any:
		return "array"
	case string:
		return "string"
	case bool:
		return "boolean"
	case float64:
		f, _ := doc.(float64)
		// beyond int64 the bare conversion is implementation-defined (arm64
		// saturates, amd64 wraps) — same boundary clause as typeMatches keeps
		// the name architecture-stable (V29 F-4, text-family sibling)
		if f == float64(int64(f)) || f >= 9223372036854775808.0 || f <= -9223372036854775808.0 {
			return "integer"
		}
		return "number"
	case int64, int:
		return "integer"
	}
	return "null"
}

// numericValue widens programmatic int64/int to float64 so the numeric
// keyword checks treat them exactly like parsed numbers (V9 m1: relying on the
// disagreement alarm for these degraded the message; parity should not need it).
func numericValue(doc any) (float64, bool) {
	switch v := doc.(type) {
	case float64:
		return v, true
	case int64:
		return float64(v), true
	case int:
		return float64(v), true
	}
	return 0, false
}

// fmtNum prints a schema number without an implementation-defined int64 cast:
// floats outside int64 range (legal JSON integers up to 2^53 by schema, but a
// programmatic guard can hand us anything) fall back to %v.
func fmtNum(n float64) string {
	// 2^63 itself is outside int64 (float64(MaxInt64) rounds up to it); >= not >
	if n >= 9223372036854775808.0 || n <= -9223372036854775808.0 {
		return fmt.Sprintf("%v", n)
	}
	return fmt.Sprintf("%d", int64(n))
}

func jsonEqual(a, b any) bool {
	ab, _ := json.Marshal(a)
	bb, _ := json.Marshal(b)
	return string(ab) == string(bb)
}

// ---------- contract cross-field rules ----------

func SelectorErrors(sel string, where string) []string {
	var errs []string
	if percentHasBadEscape(sel) {
		return append(errs, where+": percent-escapes must be '%' followed by two uppercase hex digits")
	}
	for _, m := range escapeRe.FindAllStringSubmatch(sel, -1) {
		// m[1] is always exactly two uppercase hex digits (the regex guarantees it)
		ch := rune(hexVal(m[1][0])<<4 | hexVal(m[1][1]))
		if strings.ContainsRune(unreserved, ch) {
			return append(errs, where+": "+m[0]+" encodes an unreserved character; write it literally (RFC 3986 §2.3)")
		}
	}
	// UTF-8 decodability: Go decodes %XX via manual hex; validate UTF-8 of decoded bytes
	decoded := make([]byte, 0, len(sel))
	for i := 0; i < len(sel); i++ {
		if sel[i] == '%' && i+2 < len(sel) {
			b := byte(hexVal(sel[i+1])<<4 | hexVal(sel[i+2]))
			decoded = append(decoded, b)
			i += 2
		} else {
			decoded = append(decoded, sel[i])
		}
	}
	if !utf8.Valid(decoded) {
		return append(errs, where+": percent-escapes do not decode as UTF-8 (RFC 3987 §3.1)")
	}
	return errs
}

func hexVal(c byte) int {
	switch {
	case c >= '0' && c <= '9':
		return int(c - '0')
	case c >= 'A' && c <= 'F':
		return int(c-'A') + 10
	}
	return 0
}

func GrantErrors(grants []any, where string) []string {
	var errs []string
	for i, g := range grants {
		gm, ok := g.(map[string]any)
		if !ok {
			continue
		}
		res, _ := gm["resource"].(map[string]any)
		if res == nil {
			continue
		}
		if sel, ok := res["selector"].(string); ok {
			errs = append(errs, SelectorErrors(sel, fmt.Sprintf("%s/%d/resource/selector", where, i))...)
		}
	}
	return errs
}

func CrossFieldErrors(doc map[string]any) []string {
	var errs []string
	if req, ok := doc["requires"].([]any); ok {
		errs = append(errs, GrantErrors(req, "requires")...)
	}
	declared, _ := doc["effects"].(map[string]any)
	level, _ := declared["level"].(string)
	worst := 0
	if req, ok := doc["requires"].([]any); ok {
		for _, g := range req {
			gm, _ := g.(map[string]any)
			if gm == nil {
				continue
			}
			if eff, ok := gm["effect"].(string); ok {
				if r, ok := LevelRank[eff]; ok && r > worst {
					worst = r
				}
			}
		}
	}
	if _, has := LevelRank[level]; has {
		if LevelRank[level] < worst {
			errs = append(errs, fmt.Sprintf("effects.level '%s' is below the worst effect declared in requires", level))
		}
		if LevelRank[level] > 0 {
			if _, hasComp := declared["compensation"]; !hasComp {
				errs = append(errs, "effects.compensation is required when effects.level != none")
			}
		}
	}
	return errs
}

func ContractErrors(doc map[string]any) []string {
	var errs []string
	rootSchema = ContractSchema
	SchemaErrors(doc, ContractSchema, "<root>", &errs)
	errs = CheckContractVerdict(doc, errs)
	if len(errs) > 0 {
		return errs
	}
	return CrossFieldErrors(doc)
}

// ---------- envelope ----------

func B64url(data []byte) string {
	return base64.RawURLEncoding.EncodeToString(data)
}

func B64urlDecode(s string) ([]byte, error) {
	// base64url alphabet ONLY (RFC 4648 §5). FORCED DIVERGENCE (V13 4-lens M-1,
	// boundary corrected V14): the oracle's decode drops non-alphabet characters
	// and pads by ORIGINAL length, so it accepts whenever the residual string is
	// decodable — 0-mod-4 carriers with a single trailing \n, 3-mod-4 carriers
	// with two, and more. Strict side wins on wire forms: Go rejects every
	// non-alphabet byte; the divergence is pinned in wire_test.
	for i := 0; i < len(s); i++ {
		c := s[i]
		if !(c >= 'A' && c <= 'Z' || c >= 'a' && c <= 'z' || c >= '0' && c <= '9' || c == '-' || c == '_' || c == '=') {
			return nil, base64.CorruptInputError(i)
		}
	}
	return base64.RawURLEncoding.DecodeString(s)
}

func ContractHash(contract map[string]any) (string, error) {
	canonical, err := rfc8785.Canonicalize(contract)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(canonical)
	return "sha256:" + fmt.Sprintf("%x", sum), nil
}

var allowedAlgs = map[string]bool{"ES256": true, "RS256": true, "EdDSA": true}

type TrustStore struct {
	Keys      map[string]map[string]any
	SubjectOf map[string]map[string]bool
}

func LoadTrustStore(path string) (*TrustStore, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var storeDoc map[string]any
	if err := json.Unmarshal(raw, &storeDoc); err != nil {
		return nil, err
	}
	ts := &TrustStore{Keys: map[string]map[string]any{}, SubjectOf: map[string]map[string]bool{}}
	var keys []any
	if rawKeys, has := storeDoc["keys"]; has && rawKeys != nil {
		var isList bool
		keys, isList = rawKeys.([]any)
		if !isList {
			return nil, fmt.Errorf("trusted key store %s: keys must be a list", path)
		}
	} // absent OR null keys = empty store; Python's raw.get returns None for an explicit
	// null and then crashes iterating — our empty store is the fail-closed reading
	for i, k := range keys {
		km, isMap := k.(map[string]any)
		if !isMap {
			return nil, fmt.Errorf("trusted key store %s: keys[%d] is not an object", path, i)
		}
		// WIRE DIALECT LEDGER: kid is a STRING (RFC 7517 §4.5). The oracle's
		// dict lookup happily files an int kid and even completes verification
		// with it (opposite-verdict divergence, V15 4-lens M-1) — strict side wins.
		kid, isStr := km["kid"].(string)
		if !isStr || kid == "" {
			return nil, fmt.Errorf("trusted key store %s: keys[%d] has no kid", path, i)
		}
		if _, dup := ts.Keys[kid]; dup {
			return nil, fmt.Errorf("trusted key store %s: duplicate kid %q at keys[%d]", path, kid, i)
		}
		// WIRE DIALECT LEDGER (V13 F1): pyjwt's b64 silently drops non-alphabet
		// characters, so a JWK coordinate like x+"    " verifies on the oracle
		// and fails here — strict side wins (RFC 4648 §5), enforced at load.
		// string-typed binary members only ("oth" is an object array and private-key
		// only — trust stores consume public members; not scanned)
		for _, member := range []string{"x", "y", "n", "e", "d", "p", "q", "dp", "dq", "qi", "k"} {
			if s, isStr := km[member].(string); isStr {
				if _, err := B64urlDecode(s); err != nil {
					return nil, fmt.Errorf("trusted key store %s: keys[%d].%s is not canonical base64url (strict wire form)", path, i, member)
				}
			}
		}
		ts.Keys[kid] = km
	}
	if soRaw, has := storeDoc["subject_of"]; has && soRaw != nil {
		so, isDict := soRaw.(map[string]any)
		if !isDict {
			return nil, fmt.Errorf("trusted key store %s: subject_of must be an object", path)
		}
		soKids := make([]string, 0, len(so))
		for kid := range so {
			soKids = append(soKids, kid)
		}
		sort.Strings(soKids) // deterministic first-error choice (V23 4-lens M-1 sibling)
		for _, kid := range soKids {
			subjects := so[kid]
			if _, inStore := ts.Keys[kid]; !inStore {
				return nil, fmt.Errorf("trusted key store %s: subject_of names unknown kid %q", path, kid)
			}
			// Python load_trust_store: the value must be a non-empty list and EVERY
			// element a non-empty string — a mixed list silently dropping its bad
			// elements would widen the key's binding (fail-open, V2 M4).
			sl, isList := subjects.([]any)
			if !isList || len(sl) == 0 {
				return nil, fmt.Errorf("trusted key store %s: subject_of[%q] must be a non-empty list of subject ids", path, kid)
			}
			subjectsSet := map[string]bool{}
			for _, s := range sl {
				ss, isStr := s.(string)
				if !isStr || ss == "" {
					return nil, fmt.Errorf("trusted key store %s: subject_of[%q] must be a non-empty list of subject ids", path, kid)
				}
				subjectsSet[ss] = true
			}
			ts.SubjectOf[kid] = subjectsSet
		}
	}
	return ts, nil
}

func EnvelopeErrors(doc map[string]any, ts *TrustStore, loneSurrogate bool) ([]string, []string) {
	var verified []string
	var errs []string
	rootSchema = EnvelopeSchema
	SchemaErrors(doc, EnvelopeSchema, "<root>", &errs)
	errs = CheckEnvelopeVerdict(doc, errs)
	if len(errs) > 0 {
		return errs, verified
	}
	contract, _ := doc["contract"].(map[string]any)
	errs = ContractErrors(contract)
	if len(errs) > 0 {
		return errs, verified
	}
	if loneSurrogate {
		// Python rejects inside contract_hash's canonicalize step: a lone surrogate
		// is legal JSON text but not encodable as UTF-8. Go's parser collapses the
		// escape to U+FFFD, so the evidence comes from a raw scan scoped to the
		// contract member's byte range (V4 MAJOR-1); a surrogate elsewhere in the
		// envelope is accepted by the oracle and never reaches this branch.
		return []string{"contract: document contains a lone surrogate; not canonicalizable"}, verified
	}
	expected, err := ContractHash(contract)
	if err != nil {
		return append(errs, "contract: "+err.Error()), verified
	}
	if hash, _ := doc["contract_hash"].(string); hash != expected {
		return append(errs, fmt.Sprintf("contract_hash %s does not match recomputed %s", hash, expected)), verified
	}

	payloadCanonical, err := rfc8785.Canonicalize(contract)
	if err != nil {
		return append(errs, "contract: "+err.Error()), verified
	}
	payloadB64 := B64url(payloadCanonical)
	subject, _ := contract["subject"].(map[string]any)
	subjectID, _ := subject["id"].(string)

	ownerSigned := false
	seenKids := map[string]int{}
	sigs, _ := doc["signatures"].([]any)
	for i, sigAny := range sigs {
		sig, _ := sigAny.(map[string]any)
		if sig == nil {
			continue
		}
		where := fmt.Sprintf("signatures/%d", i)
		protected, _ := sig["protected"].(string)
		headerBytes, err := B64urlDecode(protected)
		if err != nil {
			errs = append(errs, where+": protected header is not a base64url-encoded JSON object")
			continue
		}
		var hdr map[string]any
		if err := json.Unmarshal(headerBytes, &hdr); err != nil {
			errs = append(errs, where+": protected header is not a base64url-encoded JSON object")
			continue
		}
		alg, _ := hdr["alg"].(string)
		if !allowedAlgs[alg] {
			errs = append(errs, fmt.Sprintf("%s: alg '%s' is not allowed (need one of 'EdDSA', 'ES256', 'RS256')", where, alg))
			continue
		}
		if typ, _ := hdr["typ"].(string); typ != "JOSE" {
			errs = append(errs, where+": typ must be 'JOSE'")
			continue
		}
		if _, hasCrit := hdr["crit"]; hasCrit {
			errs = append(errs, fmt.Sprintf("%s: critical header parameters %v are not supported", where, hdr["crit"]))
			continue
		}
		kid, _ := hdr["kid"].(string)
		jwk, inStore := ts.Keys[kid]
		if !inStore {
			errs = append(errs, fmt.Sprintf("%s: kid %q not in trusted key store", where, kid))
			continue
		}
		if prev, dup := seenKids[kid]; dup {
			errs = append(errs, fmt.Sprintf("%s: kid %q already signed at signatures/%d", where, kid, prev))
			continue
		}
		seenKids[kid] = i
		// RFC 7517 §4.3/§4.4 mirrors: absent or null means unrestricted; anything
		// present must be exactly the signing form. Python's `not in (None, ...)`
		// rejects empty strings and wrong types too — a type-assert to string
		// would silently pass them (V2 m7).
		if useRaw, has := jwk["use"]; has && useRaw != nil {
			use, isStr := useRaw.(string)
			if !isStr || use != "sig" {
				errs = append(errs, fmt.Sprintf("%s: kid %q has use=%v, not a signing key", where, kid, useRaw))
				continue
			}
		}
		if opsRaw, has := jwk["key_ops"]; has && opsRaw != nil {
			hasVerify := false
			switch ops := opsRaw.(type) {
			case []any:
				for _, op := range ops {
					if s, _ := op.(string); s == "verify" {
						hasVerify = true
					}
				}
			case string:
				hasVerify = strings.Contains(ops, "verify") // Python `in` on a str is substring
			}
			// WIRE DIALECT LEDGER: JSON key_ops is an ARRAY (JWA §4.3). Python's
			// `in`-on-dict quirk incidentally accepts {"verify": true}, and an int
			// value crashes the oracle outright; Go enforces the array/str shapes —
			// strict side wins on wire formats (JOSE spec anchors, not Python leniency).
			// Same ledger, base64 family: strict RFC 4648 §5 alphabet everywhere
			// (B64urlDecode rejects \r/\n that Go's decoder would skip). JWK
			// coordinates are NOT covered by go-jose's decoder — pyjwt silently
			// drops non-alphabet chars while go-jose only tolerates \r\n, an
			// opposite-verdict divergence (V13 F1) — so LoadTrustStore applies the
			// same alphabet scan itself and the divergence is pinned in wire_test.
			if !hasVerify {
				errs = append(errs, fmt.Sprintf("%s: kid %q has key_ops=%v without 'verify'", where, kid, opsRaw))
				continue
			}
		}
		if algRaw, has := jwk["alg"]; has && algRaw != nil {
			jwkAlg, isStr := algRaw.(string)
			if !isStr || jwkAlg != alg {
				errs = append(errs, fmt.Sprintf("%s: kid %q is published for alg %v, header says %q", where, kid, algRaw, alg))
				continue
			}
		}
		if bound, isBound := ts.SubjectOf[kid]; isBound && !bound[subjectID] {
			keys := make([]string, 0, len(bound))
			for k := range bound {
				keys = append(keys, k)
			}
			sort.Strings(keys)
			errs = append(errs, fmt.Sprintf("%s: kid %q is bound to %v, not to subject %q", where, kid, keys, subjectID))
			continue
		}
		sigB64, _ := sig["signature"].(string)
		sigBytes, err := B64urlDecode(sigB64)
		if err != nil {
			errs = append(errs, where+": signature is not valid base64url")
			continue
		}
		signingInput := protected + "." + payloadB64
		ok := verifyJWS(alg, jwk, []byte(signingInput), sigBytes)
		if !ok {
			errs = append(errs, fmt.Sprintf("%s: signature does not verify against JCS(contract) with kid %q", where, kid))
			continue
		}
		verified = append(verified, kid)
		if isOwner := ts.SubjectOf[kid]; len(isOwner) > 0 {
			ownerSigned = true
		}
	}
	if len(errs) == 0 && !ownerSigned {
		errs = append(errs, fmt.Sprintf("no signature from a key bound to subject %q: endorsements without the owner's self-declaration are not an envelope (D9 tier 1)", subjectID))
	}
	return errs, verified
}

// verifyJWS delegates the three allowed algorithms to go-jose. JWK parsing, EC
// point validity, RSA exponent constraints and the signature math are library
// territory — the 2026-10-15 legislation (底层判别不定制) forbids hand-rolling
// them, and the V1 collision bugs (RS256 condition inversion, nil-pointer JWK)
// all lived in exactly that hand-written layer. The signing input is the RFC 7515
// "protected.payload" ASCII; the compact line is reconstructed with the signature
// appended so the library verifies precisely the bytes this envelope defines.
func verifyJWS(alg string, jwk map[string]any, signingInput, sigBytes []byte) bool {
	jwkJSON, err := json.Marshal(jwk)
	if err != nil {
		return false
	}
	var key jose.JSONWebKey
	if err := key.UnmarshalJSON(jwkJSON); err != nil {
		return false
	}
	line := string(signingInput) + "." + B64url(sigBytes)
	obj, err := jose.ParseSigned(line, []jose.SignatureAlgorithm{jose.SignatureAlgorithm(alg)})
	if err != nil {
		return false
	}
	_, err = obj.Verify(&key)
	return err == nil
}

// ---------- fixture loading & drivers shared by suites ----------

type Fixture struct {
	Doc           map[string]any
	ExpectMatch   string
	Pin           any // _expect_verified_kids or _expect_composed (never both)
	ParseError    string
	LoneSurrogate bool // raw text has an unpaired \ud800-\udfff escape (Go's parser erases the evidence)
}

// LoadFixture mirrors Python validate.load: pins live at the document root and are
// popped BEFORE validation. FORCED DIVERGENCE (empty-value pins, V23 4-lens n5):
// Python's truthiness check silently skips empty pins ([], "", 0) while Go's
// non-nil check FAILs them loudly — strict side wins, consistent with the
// malformed-pin guards (entry/key/value level). (a nested _expect* key is an additionalProperties
// violation, not a pin — V2 M2); `_expect` is descriptive and never a match pin
// (V2 m4); a document carrying both pins is an authoring error that must surface
// (never silently drop one); NaN/Infinity documents are parse rejections whose
// pins are still read via a lenient re-parse (Python re-parses with the default
// parse_constant); a lone surrogate is only rejectable at canonicalization time,
// and only for envelopes — a contract-only document may legally carry one.
func LoadFixture(path string) (*Fixture, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	f := &Fixture{}
	scan := scanRawJSON(raw)
	if scan.bareNonFinite != "" {
		f.ParseError = fmt.Sprintf("document rejected at parse: %s is not a JSON number (RFC 8259 §6)", scan.bareNonFinite)
		f.readPinsLenient(sanitizeNonFinite(raw, scan))
		return f, nil
	}
	var doc map[string]any
	if err := json.Unmarshal(raw, &doc); err != nil {
		f.ParseError = "document rejected at parse: " + err.Error()
		if m := expectMatchRe.FindSubmatch(raw); m != nil {
			f.ExpectMatch = string(m[1])
		}
		return f, nil
	}
	f.Doc = doc
	f.LoneSurrogate = contractScopedLoneSurrogate(raw)
	f.readPins(doc)
	return f, nil
}

// contractScopedLoneSurrogate reports a lone-surrogate escape inside the RAW
// BYTE RANGE of the top-level "contract" member only. Python's rejection
// happens when canonicalizing the contract subtree; a surrogate anywhere else
// (e.g. signatures[].header) is accepted there and must be here too (V4
// MAJOR-1: the previous file-level flag × tree FFFD conjunction falsely
// rejected a literal-FFFD contract paired with a surrogate elsewhere).
// json.RawMessage preserves the member's exact bytes, so the scan is scoped
// precisely; a non-envelope document (no contract member) keeps the flag off —
// a contract-only document may legally carry a lone surrogate in Python.
func contractScopedLoneSurrogate(raw []byte) bool {
	var top map[string]json.RawMessage
	if err := json.Unmarshal(raw, &top); err != nil {
		return false
	}
	contractRaw, has := top["contract"]
	if !has || len(contractRaw) == 0 {
		return false
	}
	return scanRawJSON(contractRaw).loneSurrogate
}

// readPins pops the root-level pin keys the way Python load() does.
func (f *Fixture) readPins(doc map[string]any) {
	delete(doc, "_expect") // descriptive only
	// _expect_match must be a STRING: a wrong-typed pin is an authoring error
	// and must fail LOUD. Oracle behavior splits (V28 m2): a TRUTHY non-string
	// (5, ["x"]) crashes the suite layer (oracle-undefined face, loud is the
	// only legal direction); a FALSY value (null/0/[]/false) is silently
	// skipped by its truthiness check — our loud rejection is the
	// strict-side-wins reading of that face. Either way, a silent downgrade
	// to "no pin" here would bypass the wrong-reason checks (V28 F-1).
	if m, has := doc["_expect_match"]; has {
		if s, isStr := m.(string); isStr {
			f.ExpectMatch = s
		} else if f.ParseError == "" {
			f.ParseError = fmt.Sprintf("_expect_match must be a string, got %T", m)
		}
	}
	delete(doc, "_expect_match")
	if k, ok := doc["_expect_verified_kids"]; ok {
		f.Pin = k
		delete(doc, "_expect_verified_kids")
	}
	if c, has := doc["_expect_composed"]; has {
		delete(doc, "_expect_composed") // Python pops unconditionally; a null value is simply "no pin" (V11 F1)
		if c != nil {
			if f.Pin != nil {
				if f.ParseError == "" {
					f.ParseError = "fixture carries both _expect_verified_kids and _expect_composed"
				}
			} else {
				f.Pin = c
			}
		}
	}
}

// readPinsLenient recovers pins from a rejected document (sanitized copies of the
// bare NaN/Infinity tokens parse fine, exactly like Python's permissive re-parse).
func (f *Fixture) readPinsLenient(sanitized []byte) {
	var doc map[string]any
	if err := json.Unmarshal(sanitized, &doc); err != nil {
		if m := expectMatchRe.FindSubmatch(sanitized); m != nil {
			f.ExpectMatch = string(m[1])
		}
		return
	}
	f.readPins(doc)
}

// sanitizeNonFinite replaces each bare non-finite token with "0" padded to the
// token's length, so the document parses leniently for pin recovery.
func sanitizeNonFinite(raw []byte, scan rawScan) []byte {
	out := append([]byte(nil), raw...)
	for _, sp := range scan.bareSpans {
		out[sp.start] = '0'
		for i := sp.start + 1; i < sp.end; i++ {
			out[i] = ' '
		}
	}
	return out
}

// CloneDoc deep-copies a parsed JSON document through marshal/unmarshal and
// fails LOUD on any error — the single source for the guard/sign clone family
// (V23 4-lens n3: four copies of this once silently returned nil on error).
func CloneDoc(m map[string]any) map[string]any {
	raw, err := json.Marshal(m)
	if err != nil {
		panic("CloneDoc: " + err.Error())
	}
	var out map[string]any
	if err := json.Unmarshal(raw, &out); err != nil {
		panic("CloneDoc: " + err.Error())
	}
	return out
}

// SetRootSchema sets the root for $defs resolution (compose uses a different schema).
func SetRootSchema(s Schema) { rootSchema = s }

// resolvePointer follows a "#/a/b/c" JSON pointer into a schema map.
func resolvePointer(schema Schema, ptr string) (Schema, bool) {
	parts := strings.Split(strings.TrimPrefix(ptr, "#/"), "/")
	var cur Schema = schema
	for _, p := range parts {
		if next, ok := cur[p].(map[string]any); ok {
			cur = next
		} else {
			return nil, false
		}
	}
	return cur, true
}

// SchemaErrorsDoc is the exported entry for schema validation.
func SchemaErrorsDoc(doc any, schema Schema, path string, errs *[]string) {
	SchemaErrors(doc, schema, path, errs)
}

// LevelRank is shared with the compose package (single definition, V2 m8).
var LevelRank = map[string]int{"none": 0, "reversible": 1, "irreversible": 2}
