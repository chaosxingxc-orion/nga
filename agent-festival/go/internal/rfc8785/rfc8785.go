package rfc8785

import (
	"bytes"
	"encoding/json"
	"fmt"
	"math"
	"sort"
	"strconv"
	"unicode/utf16"

	jsoncanonicalizer "github.com/cyberphone/json-canonicalization/go/src/webpki.org/jsoncanonicalizer"
)

// Minimal RFC 8785 (JSON Canonicalization Scheme) serializer — Go pilot.
// Mirrors schema/rfc8785_min.py (frozen oracle). The hard part in Go is ES6
// Number::toString (ECMA-262 §7.1.12.1): strconv's 'g' format switches to
// exponent notation at different thresholds, so shortest round-trip digits are
// obtained via strconv.FormatFloat(-1) then reassembled with ES6 placement
// rules (plain digits for 1e-6 < |x| < 1e21, else d.ddde±x).
//
// Since 2026-10-28 the engine of record is the RFC author's reference
// implementation (webpki.org/jsoncanonicalizer, 不重复造轮子立法); this
// package's own serializer is kept as the differential counterpart in
// differential_test.go — two independent ES6 implementations agreeing byte for
// byte is stronger evidence than either alone.

// Canonicalize returns the RFC 8785 canonical bytes of a parsed JSON value.
// Objects and arrays — every product path (contract hashing, envelope payloads)
// — go through the reference implementation; only a top-level scalar falls
// back to the in-repo serializer (the reference Transform rejects those).
func Canonicalize(doc any) ([]byte, error) {
	switch doc.(type) {
	case map[string]any, []any:
	default:
		return canonicalizeLocal(doc)
	}
	raw, err := jsonMarshalNoEscape(doc)
	if err != nil {
		return nil, err
	}
	out, err := jsoncanonicalizer.Transform(raw)
	if err != nil {
		return nil, fmt.Errorf("canonicalize: %w", err)
	}
	return out, nil
}

// canonicalizeLocal is the in-repo ES6 serializer, exercised only by the
// differential test against the reference implementation above.
func canonicalizeLocal(doc any) ([]byte, error) {
	var buf bytes.Buffer
	if err := serialize(&buf, doc); err != nil {
		return nil, err
	}
	// Lone surrogates: JSON decoding of "\ud800" produces U+FFFD replacement in
	// Go strings, and raw UTF-8 input with lone surrogates also becomes U+FFFD.
	// A document that round-trips through encoding/json therefore never carries
	// lone surrogates here; canonical bytes are valid UTF-8 by construction.
	return buf.Bytes(), nil
}

func jsonMarshalNoEscape(v any) ([]byte, error) {
	var b bytes.Buffer
	enc := json.NewEncoder(&b)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(v); err != nil {
		return nil, err
	}
	// Encode appends a newline; strip it
	out := b.Bytes()
	if len(out) > 0 && out[len(out)-1] == '\n' {
		out = out[:len(out)-1]
	}
	// RFC 8785 §3.2.2.2: U+2028/U+2029 pass through raw. Go's encoding/json
	// always escapes them to \u2028/\u2029 even with SetEscapeHTML(false) —
	// the only known deviation — so we unescape them back (JCS = JSON.stringify
	// semantics, and JSON.stringify does not escape line/paragraph separators).
	// A blanket ReplaceAll is wrong: the literal six-character TEXT "\u2028" in
	// a source string marshals as "\\u2028" (escaped backslash), and a blanket
	// replace would corrupt it from the inside — V4 F-1: a Python-signed
	// envelope carrying that text then failed Go canonicalization.
	return unescapeJSLineSeparators(out), nil
}

// unescapeJSLineSeparators rewrites the \u2028/\u2029 escapes into raw UTF-8,
// walking with backslash-escape parity so escaped-backslash sequences (literal
// "\u2028" text) survive untouched.
func unescapeJSLineSeparators(b []byte) []byte {
	out := make([]byte, 0, len(b))
	for i := 0; i < len(b); {
		if b[i] == '\\' && i+1 < len(b) && b[i+1] == '\\' {
			out = append(out, b[i], b[i+1])
			i += 2
			continue
		}
		if b[i] == '\\' && i+5 < len(b) && b[i+1] == 'u' {
			switch string(b[i+2 : i+6]) {
			case "2028":
				out = append(out, 0xE2, 0x80, 0xA8)
				i += 6
				continue
			case "2029":
				out = append(out, 0xE2, 0x80, 0xA9)
				i += 6
				continue
			}
		}
		out = append(out, b[i])
		i++
	}
	return out
}

func serialize(buf *bytes.Buffer, v any) error {
	switch x := v.(type) {
	case nil:
		buf.WriteString("null")
	case bool:
		if x {
			buf.WriteString("true")
		} else {
			buf.WriteString("false")
		}
	case float64:
		s, err := es6Number(x)
		if err != nil {
			return err
		}
		buf.WriteString(s)
	case string:
		b, err := jsonMarshalNoEscape(x) // RFC 8785 §3.2.2.2: no HTML escaping; Go json.Marshal escapes <>& by default
		if err != nil {
			return err
		}
		buf.Write(b)
	case []any:
		buf.WriteByte('[')
		for i, e := range x {
			if i > 0 {
				buf.WriteByte(',')
			}
			if err := serialize(buf, e); err != nil {
				return err
			}
		}
		buf.WriteByte(']')
	case map[string]any:
		keys := make([]string, 0, len(x))
		for k := range x {
			keys = append(keys, k)
		}
		sort.Slice(keys, func(i, j int) bool {
			return utf16Less(keys[i], keys[j])
		})
		buf.WriteByte('{')
		for i, k := range keys {
			if i > 0 {
				buf.WriteByte(',')
			}
			kb, _ := jsonMarshalNoEscape(k)
			buf.Write(kb)
			buf.WriteByte(':')
			if err := serialize(buf, x[k]); err != nil {
				return err
			}
		}
		buf.WriteByte('}')
	default:
		return fmt.Errorf("unsupported type %T", v)
	}
	return nil
}

// utf16Less compares two strings by UTF-16 code unit sequence (JCS key order).
// Non-BMP code points encode as surrogate pairs (units > any BMP unit), which
// compares differently from code-point order exactly in the cases JCS cares
// about (BMP vs astral keys).
func utf16Less(a, b string) bool {
	ua := utf16.Encode([]rune(a))
	ub := utf16.Encode([]rune(b))
	for i := 0; i < len(ua) && i < len(ub); i++ {
		if ua[i] != ub[i] {
			return ua[i] < ub[i]
		}
	}
	return len(ua) < len(ub)
}

// es6Number renders x per ECMA-262 §7.1.12.1 as observed in JS String(x).
func es6Number(x float64) (string, error) {
	if math.IsInf(x, 0) || math.IsNaN(x) {
		return "", fmt.Errorf("non-finite numbers cannot be canonicalized")
	}
	if x == 0 {
		return "0", nil // normalizes -0
	}
	sign := ""
	if x < 0 {
		sign = "-"
		x = -x
	}
	// Shortest round-trip digits, without exponent (strconv 'f' with -1 prec).
	digits := strconv.FormatFloat(x, 'f', -1, 64)
	if digits == "" {
		return "", fmt.Errorf("format failure for %v", x)
	}
	// FormatFloat('f',-1) already applies the plain-decimal rule for the full
	// double range EXCEPT it never produces exponent notation; for |x| >= 1e21
	// the digit string is still exact shortest round-trip in plain form, and we
	// must convert to ES6 exponent form. For |x| < 1e-6 likewise.
	// Determine decimal exponent n = position of decimal point relative to digits.
	// Find if FormatFloat used exponent internally: large/small magnitudes still
	// give plain digits here, so parse placement from the string.
	var intPart, fracPart string
	hasDot := false
	for i := 0; i < len(digits); i++ {
		if digits[i] == '.' {
			hasDot = true
			continue
		}
		if !hasDot {
			intPart += string(digits[i])
		} else {
			fracPart += string(digits[i])
		}
	}
	raw := intPart + fracPart
	stripped := raw
	for len(stripped) > 0 && stripped[0] == '0' {
		stripped = stripped[1:]
	}
	// decimal point position relative to stripped digits
	n := len(intPart) - (len(raw) - len(stripped))
	d := stripped
	for len(d) > 1 && d[len(d)-1] == '0' {
		d = d[:len(d)-1]
	}
	k := len(d)
	if k == 0 {
		return "0", nil
	}
	var s string
	switch {
	case n >= k && n <= 21:
		s = d + repeat0(n-k)
	case n > 0 && n <= 21:
		s = d[:n] + "." + d[n:]
	case n > -6 && n <= 0:
		s = "0." + repeat0(-n) + d
	default:
		e := n - 1
		s = d[:1]
		if k > 1 {
			s += "." + d[1:]
		}
		s += "e"
		if e >= 0 {
			s += "+"
		} else {
			s += "-"
		}
		s += strconv.Itoa(abs(e))
	}
	return sign + s, nil
}

func repeat0(n int) string {
	b := make([]byte, n)
	for i := range b {
		b[i] = '0'
	}
	return string(b)
}

func abs(e int) int {
	if e < 0 {
		return -e
	}
	return e
}
