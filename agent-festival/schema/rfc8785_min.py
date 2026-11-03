"""Minimal RFC 8785 (JSON Canonicalization Scheme) serializer.

Scope: exactly what the L3 envelope needs — deterministic bytes for signing and
hashing a parsed JSON document. Implements the three things Python's json module
gets wrong for JCS: ES6 number formatting (600.0 -> "600", 1e16 -> full digits,
1e-7 -> "1e-7"), key ordering by UTF-16 code units, and rejection of non-finite
numbers. String escaping matches JCS already (json.dumps with ensure_ascii=False).

Module is named rfc8785_min rather than jcs on purpose: PyPI publishes a package
called jcs, and the sibling scripts prepend this directory to sys.path, which would
shadow it (code-rules G.PSL.03).

Production implementations should use a full RFC 8785 library; this one exists so
validate.py has no dependency beyond the standard library for canonicalization.
"""
import json
import math
import sys


def _number(x) -> str:
    """ES6 Number::toString (ECMA-262 §7.1.12.1), which RFC 8785 mandates."""
    if isinstance(x, bool):
        raise TypeError("bool is not a JSON number")
    if isinstance(x, int):
        if abs(x) < 2**53:
            return str(x)
        x = float(x)  # beyond 2^53 JSON numbers are IEEE doubles anyway
    if not math.isfinite(x):
        raise ValueError("non-finite numbers cannot be canonicalized")
    if x == 0:
        return "0"  # also normalizes -0.0
    sign = "-" if x < 0 else ""
    mant, _, exp = repr(abs(x)).partition("e")  # repr = shortest round-trip digits
    exp = int(exp) if exp else 0
    ip, _, fp = mant.partition(".")
    raw = ip + fp
    stripped = raw.lstrip("0")
    n = len(ip) + exp - (len(raw) - len(stripped))  # decimal point position
    digits = stripped.rstrip("0")
    k = len(digits)
    if k <= n <= 21:
        s = digits + "0" * (n - k)
    elif 0 < n <= 21:
        s = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        s = "0." + "0" * (-n) + digits
    else:
        e = n - 1
        s = digits if k == 1 else digits[0] + "." + digits[1:]
        s += "e" + ("+" if e >= 0 else "-") + str(abs(e))
    return sign + s


def _serialize(v) -> str:
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, (int, float)):
        return _number(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        return "[" + ",".join(_serialize(i) for i in v) + "]"
    if isinstance(v, dict):
        items = sorted(v.items(), key=lambda kv: kv[0].encode("utf-16-be"))
        body = ",".join(json.dumps(k, ensure_ascii=False) + ":" + _serialize(val) for k, val in items)
        return "{" + body + "}"
    raise TypeError(f"unsupported type {type(v).__name__}")


def canonicalize(doc) -> bytes:
    """Return the RFC 8785 canonical UTF-8 encoding of a parsed JSON value.

    A lone surrogate (legal in a JSON text as "\\ud800", not representable in UTF-8) is a
    ValueError, so a contract carrying hostile external text is rejected instead of crashing
    the verifier (round 16 F-4).
    """
    try:
        return _serialize(doc).encode("utf-8")
    except UnicodeEncodeError as e:
        raise ValueError(f"document contains a lone surrogate at position {e.start}; not canonicalizable") from e


def main() -> int:
    sys.stdout.buffer.write(canonicalize(json.load(sys.stdin)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
