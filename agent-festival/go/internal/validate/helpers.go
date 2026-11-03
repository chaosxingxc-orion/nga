package validate

import (
	"regexp"
)

// expectMatchRe extracts _expect_match from raw JSON bytes when the document
// itself fails to parse (Python oracle reads pins even from rejected docs).
var expectMatchRe = regexp.MustCompile(`"_expect_match"\s*:\s*"([^"]*)"`)

// rawScan reports the two raw-level conditions Python's loader reacts to.
// Both are invisible after encoding/json parses: bare NaN/Infinity tokens are
// a parse rejection there (so the value layer never sees them), and
// lone-surrogate \u escapes are silently collapsed to U+FFFD (conflating them
// with the legal literal character). One walk with string/escape context
// answers both; anything inside a quoted string is never a bare token.
type rawScan struct {
	bareNonFinite string // first bare "NaN" / "Infinity" / "-Infinity", or ""
	bareSpans     []span // every bare non-finite token, for lenient re-parse sanitization
	loneSurrogate bool   // an unpaired \ud800-\udfff escape inside some string
}

type span struct{ start, end int }

func scanRawJSON(raw []byte) rawScan {
	var res rawScan
	inString := false
	escaped := false
	for i := 0; i < len(raw); i++ {
		c := raw[i]
		if inString {
			if escaped {
				escaped = false
				if c != 'u' || i+5 > len(raw) {
					continue
				}
				v, ok := hex4(raw[i+1 : i+5])
				if !ok {
					continue // malformed escape: the parser will report it
				}
				if v >= 0xD800 && v <= 0xDBFF {
					// high surrogate: the escape must be immediately followed
					// by a \udc00-\udfff escape to form one astral character
					j := i + 5
					if j+6 <= len(raw) && raw[j] == '\\' && raw[j+1] == 'u' {
						if low, ok := hex4(raw[j+2 : j+6]); ok && low >= 0xDC00 && low <= 0xDFFF {
							i = j + 5 // consume the pair; loop's i++ lands past it
							continue
						}
					}
					res.loneSurrogate = true
				} else if v >= 0xDC00 && v <= 0xDFFF {
					// a low surrogate reached on its own: its high half is missing
					res.loneSurrogate = true
				}
				continue
			}
			switch c {
			case '\\':
				escaped = true
			case '"':
				inString = false
			}
			continue
		}
		switch {
		case c == '"':
			inString = true
		case matchAt(raw, i, "-Infinity"):
			res.recordBare(i, "-Infinity")
			i += len("-Infinity") - 1
		case matchAt(raw, i, "Infinity"):
			res.recordBare(i, "Infinity")
			i += len("Infinity") - 1
		case matchAt(raw, i, "NaN"):
			res.recordBare(i, "NaN")
			i += len("NaN") - 1
		}
	}
	return res
}

func (s *rawScan) recordBare(start int, tok string) {
	if s.bareNonFinite == "" {
		s.bareNonFinite = tok
	}
	s.bareSpans = append(s.bareSpans, span{start, start + len(tok)})
}

// matchAt reports whether raw[at:] starts with tok as a WHOLE token: a
// following identifier character means a longer token (e.g. "InfinityX") that
// is a syntax error, not a non-finite literal — reporting it as the latter
// names the wrong reason (V34 4-lens N1; verdict-equivalent both sides).
func matchAt(raw []byte, at int, tok string) bool {
	if at+len(tok) > len(raw) {
		return false
	}
	if string(raw[at:at+len(tok)]) != tok {
		return false
	}
	// successor boundary: InfinityX is a longer token (syntax error), not the literal
	if at+len(tok) < len(raw) {
		c := raw[at+len(tok)]
		if c >= 'A' && c <= 'Z' || c >= 'a' && c <= 'z' || c >= '0' && c <= '9' || c == '_' || c == '.' || c == '-' || c == '+' {
			return false
		}
	}
	// predecessor boundary: "1.NaN" / "- Infinity" embed the token inside a
	// syntax error, which must be attributed to the parser, not to a bare
	// non-finite literal (V35 4-lens m-1 second half)
	if at > 0 {
		c := raw[at-1]
		if c >= '0' && c <= '9' || c == '.' || c == '-' || c == '+' {
			return false
		}
		if c == ' ' || c == '\t' || c == '\n' {
			if at >= 2 && (raw[at-2] == '-' || raw[at-2] == '+') {
				return false // a sign separated from its token: "- Infinity"
			}
		}
	}
	return true
}

func hex4(b []byte) (int, bool) {
	v := 0
	for _, c := range b {
		switch {
		case c >= '0' && c <= '9':
			v = v<<4 | int(c-'0')
		case c >= 'a' && c <= 'f':
			v = v<<4 | int(c-'a') + 10
		case c >= 'A' && c <= 'F':
			v = v<<4 | int(c-'A') + 10
		default:
			return 0, false
		}
	}
	return v, true
}
