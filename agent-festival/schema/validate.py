#!/usr/bin/env python3
"""Validate L3 capability contracts and signed contract envelopes.

Contracts: JSON Schema + the cross-field rules JSON Schema cannot express.
Envelopes: contract rules + contract_hash recomputation + JWS verification of
every signature against JCS(contract) using the trusted key store, plus the
owner binding: a kid listed under the store's `subject_of` may only sign for
those subjects, and at least one such owner signature must be present.
Key stores: examples/keys/invalid/*.jwks.json must be refused at load time.

Exit 0 iff every examples/**/valid/* passes AND every examples/**/invalid/* is
rejected — and, when an invalid example carries `_expect_match`, rejected for
that reason (a rejection for the wrong reason is a false green and fails).

Usage:  python3 schema/validate.py                         # run both example suites
        python3 schema/validate.py FILE...                 # validate specific files (auto-detects envelope vs contract)
        python3 schema/validate.py --jwks KEYS.json FILE... # use a different trusted key store

Dependencies: jsonschema, pyjwt[crypto] (only envelopes need pyjwt).
"""
import base64
import hashlib
import json
import math
import re
import sys
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote

import jsonschema
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rfc8785_min import canonicalize  # noqa: E402

HERE = Path(__file__).resolve().parent
CONTRACT_SCHEMA = json.loads((HERE / "capability-contract.schema.json").read_text())
ENVELOPE_SCHEMA = json.loads((HERE / "contract-envelope.schema.json").read_text())
def as_resource(schema: dict) -> Resource:
    """Register a schema WITHOUT its `$schema` key. When a `$ref` lands in a resource that carries `$schema`,
    jsonschema looks the dialect up in its process-wide table and would swap in the stock validator class,
    losing the Decimal-aware `integer` check below. Dropping the key from the registered copy (the file on
    disk keeps it) makes the resolver keep whichever validator class started the walk; the dialect is still
    pinned explicitly. This is scoped to our registry, unlike `validators.validates(...)`, which would
    silently change `integer` for every other jsonschema user in the same process (round 16 fifth pass)."""
    return Resource.from_contents({k: v for k, v in schema.items() if k != "$schema"},
                                  default_specification=DRAFT202012)


REGISTRY = Registry().with_resources([
    (CONTRACT_SCHEMA["$id"], as_resource(CONTRACT_SCHEMA)),
    (ENVELOPE_SCHEMA["$id"], as_resource(ENVELOPE_SCHEMA)),
])
DEFAULT_JWKS = HERE / "examples" / "keys" / "trusted.jwks.json"
LEVEL = {"none": 0, "reversible": 1, "irreversible": 2}
ALLOWED_ALGS = {"ES256", "RS256", "EdDSA"}


# ---------- contract ----------

def _is_integer(checker, instance) -> bool:
    """JSON has one number type; `3.0` is an integer whether the parser produced float or Decimal (round 16 P4-3)."""
    if isinstance(instance, bool):
        return False
    if isinstance(instance, int):
        return True
    if isinstance(instance, float):
        return instance.is_integer()
    if isinstance(instance, Decimal):
        return instance.is_finite() and instance == instance.to_integral_value()
    return False


Validator = jsonschema.validators.extend(
    jsonschema.Draft202012Validator,
    type_checker=jsonschema.Draft202012Validator.TYPE_CHECKER.redefine("integer", _is_integer))


def reject_constant(name: str):
    """json.loads accepts NaN / Infinity / -Infinity by default; RFC 8259 does not, and a NaN budget is not a
    budget (round 16 P4-2: it crashed the comparison in compose and passed `minimum: 0` in jsonschema)."""
    raise ValueError(f"{name} is not a JSON number (RFC 8259 §6)")


def _finite(x) -> bool:
    if isinstance(x, bool):
        return False
    if isinstance(x, int):
        return True
    if isinstance(x, float):
        return math.isfinite(x)
    if isinstance(x, Decimal):
        return x.is_finite()
    return False


def bounds_errors(bounds: dict, where: str = "bounds") -> list[str]:
    """Every bound amount must be a finite number, also when the document did not come through our JSON loader."""
    errs = []
    for name, v in bounds.items():
        amount = v.get("amount") if name == "max_cost" and isinstance(v, dict) else v
        if not _finite(amount):
            errs.append(f"{where}/{name}: {amount!r} is not a finite number")
    return errs


def _schema_errors(doc, schema, registry=None) -> list[str]:
    v = Validator(schema, registry=registry or REGISTRY, format_checker=jsonschema.FormatChecker())
    # best_match descends into oneOf/anyOf branches so the message names the leaf that failed,
    # not "is not valid under any of the given schemas"
    errs = [jsonschema.exceptions.best_match([e]) for e in v.iter_errors(doc)]
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errs]


_PERCENT = re.compile(r"%(?![0-9A-F]{2})")
_UNRESERVED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")


def selector_errors(selector: str, where: str) -> list[str]:
    """Canonical percent-encoding (RFC 3986 §6.2.2) is the selector's *only* form; nothing ever decodes it (D40).

    Round 16 third and fourth passes tried to police the decoded form of a selector and lost twice: whatever
    list of decoded look-alikes the gate bans, another one exists (' * ', NUL, zero-width, full-width, Hangul
    filler, combining marks...). The root cause was a contract that said "the runtime decodes once before
    matching". D40 removes that contract: the design compares selectors, held grants and request URIs in
    RFC 3986 canonical encoded form, so '%EF%BC%8A' is a path segment that matches only itself and reads as
    an opaque escape, never as a wildcard. THIS module only checks that static selector strings (requires,
    caller_holds) are canonical; normalizing live request URIs to the same form is the L3 runtime's job and is
    not implemented here (ADR-0001 §6 item 11). What is checked:
      - every '%' is followed by two UPPERCASE hex digits (§6.2.2.1);
      - no escape encodes an unreserved character (§2.3: '%41' for 'A' would give one resource two spellings
        and defeat exact-match coverage);
      - the escapes decode as UTF-8 (RFC 3987 §3.1: an IRI maps to a URI through UTF-8), so the selector is
        a well-formed name and not arbitrary bytes.
    """
    errs = []
    if _PERCENT.search(selector):
        errs.append(f"{where}: percent-escapes must be '%' followed by two uppercase hex digits")
        return errs
    for m in re.finditer(r"%([0-9A-F]{2})", selector):
        if chr(int(m.group(1), 16)) in _UNRESERVED:
            errs.append(f"{where}: {m.group(0)} encodes an unreserved character; write it literally (RFC 3986 §2.3)")
            return errs
    try:
        unquote(selector, errors="strict")
    except UnicodeDecodeError:
        errs.append(f"{where}: percent-escapes do not decode as UTF-8 (RFC 3987 §3.1)")
    return errs


def grant_errors(grants: list[dict], where: str) -> list[str]:
    errs = []
    for i, g in enumerate(grants):
        sel = g.get("resource", {}).get("selector")
        if isinstance(sel, str):
            errs += selector_errors(sel, f"{where}/{i}/resource/selector")
    return errs


def cross_field_errors(doc: dict) -> list[str]:
    errs = grant_errors(doc.get("requires", []), "requires")
    if isinstance(doc.get("bounds"), dict):
        errs += bounds_errors(doc["bounds"])
    declared = doc.get("effects", {}).get("level")
    worst = max((LEVEL.get(g.get("effect"), 0) for g in doc.get("requires", [])), default=0)
    if declared in LEVEL and LEVEL[declared] < worst:
        errs.append(f"effects.level '{declared}' is below the worst effect declared in requires")
    if declared in LEVEL and LEVEL[declared] > 0 and "compensation" not in doc.get("effects", {}):
        errs.append("effects.compensation is required when effects.level != none")
    return errs


def contract_errors(doc: dict) -> list[str]:
    return _schema_errors(doc, CONTRACT_SCHEMA) or cross_field_errors(doc)


# ---------- envelope ----------

def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def contract_hash(contract: dict) -> str:
    return "sha256:" + hashlib.sha256(canonicalize(contract)).hexdigest()


def load_trust_store(path: Path) -> tuple[dict, dict]:
    """Trusted key store: (kid -> JWK, kid -> set of subject ids the key is bound to).

    Fails loud on the two silent-shadowing shapes round 16 found: an entry without kid (would vanish,
    and a real signer would then fail with the same message as an impostor) and a duplicate kid
    (last-wins would let whoever appends second sign under a trusted identity).

    `subject_of` (round 16 V-F): a kid listed there may only sign contracts whose subject.id is in its
    list, and every envelope needs at least one signature from a kid bound to its subject — that is
    what makes "self-declared" (D9 tier 1) a verifiable statement instead of a label. Kids absent from
    `subject_of` are endorsers (tester, certifier) and may sign any contract.
    """
    raw = json.loads(path.read_text())
    store: dict = {}
    for i, k in enumerate(raw.get("keys", [])):
        kid = k.get("kid")
        if not kid:
            raise ValueError(f"trusted key store {path}: keys[{i}] has no kid")
        if kid in store:
            raise ValueError(f"trusted key store {path}: duplicate kid {kid!r} at keys[{i}]")
        store[kid] = k
    subject_of: dict = {}
    for kid, subjects in raw.get("subject_of", {}).items():
        if kid not in store:
            raise ValueError(f"trusted key store {path}: subject_of names unknown kid {kid!r}")
        if not isinstance(subjects, list) or not subjects or not all(isinstance(x, str) and x for x in subjects):
            raise ValueError(f"trusted key store {path}: subject_of[{kid!r}] must be a non-empty list of subject ids")
        subject_of[kid] = set(subjects)
    return store, subject_of


def envelope_errors(doc: dict, jwks: dict, subject_of: dict | None = None) -> list[str]:
    return verify_envelope(doc, jwks, subject_of)[0]


def verify_envelope(doc: dict, jwks: dict, subject_of: dict | None = None) -> tuple[list[str], list[str]]:
    """(errors, kids that verified). The kid list is what L4 turns into an endorsement tier; it is
    only meaningful when errors is empty, and it is the value the valid examples pin (round 16 B-9)."""
    subject_of = subject_of or {}
    verified: list[str] = []
    errs = _schema_errors(doc, ENVELOPE_SCHEMA)
    if errs:
        return errs, verified
    contract = doc["contract"]
    errs = cross_field_errors(contract)
    if errs:
        return errs, verified
    try:
        expected = contract_hash(contract)
    except ValueError as e:
        return [f"contract: {e}"], verified
    if doc["contract_hash"] != expected:
        return [f"contract_hash {doc['contract_hash']} does not match recomputed {expected}"], verified

    import jwt.algorithms as algs  # imported lazily so contract-only use needs no pyjwt
    import jwt.exceptions
    payload_b64 = b64url(canonicalize(contract))
    subject = contract["subject"]["id"]
    owner_signed = False
    seen_kids: dict[str, int] = {}
    for i, sig in enumerate(doc["signatures"]):
        where = f"signatures/{i}"
        try:
            hdr = json.loads(b64url_decode(sig["protected"]))
        except ValueError:  # covers binascii.Error, JSONDecodeError, UnicodeDecodeError
            errs.append(f"{where}: protected header is not base64url-encoded JSON")
            continue
        alg = hdr.get("alg")
        if alg not in ALLOWED_ALGS:
            errs.append(f"{where}: alg {alg!r} is not allowed (need one of {sorted(ALLOWED_ALGS)})")
            continue
        if hdr.get("typ") != "JOSE":
            errs.append(f"{where}: typ must be 'JOSE'")
            continue
        if "crit" in hdr:  # RFC 7515 §4.1.11: unsupported critical parameters mean the signature must be rejected
            errs.append(f"{where}: critical header parameters {hdr['crit']!r} are not supported")
            continue
        kid = hdr.get("kid")
        if kid not in jwks:
            errs.append(f"{where}: kid {kid!r} not in trusted key store")
            continue
        if kid in seen_kids:  # one endorsement per key; a repeated kid would inflate an endorser count
            errs.append(f"{where}: kid {kid!r} already signed at signatures/{seen_kids[kid]}")
            continue
        seen_kids[kid] = i
        jwk = jwks[kid]
        key_use = jwk.get("use")
        if key_use not in (None, "sig"):  # RFC 7517 §4.3: an encryption key must never verify signatures
            errs.append(f"{where}: kid {kid!r} has use={key_use!r}, not a signing key")
            continue
        key_ops = jwk.get("key_ops")
        if key_ops is not None and "verify" not in key_ops:  # RFC 7517 §4.3
            errs.append(f"{where}: kid {kid!r} has key_ops={key_ops!r} without 'verify'")
            continue
        if jwk.get("alg") not in (None, alg):  # RFC 7517 §4.4: the key is published for one algorithm
            errs.append(f"{where}: kid {kid!r} is published for alg {jwk['alg']!r}, header says {alg!r}")
            continue
        if kid in subject_of and subject not in subject_of[kid]:
            errs.append(f"{where}: kid {kid!r} is bound to {sorted(subject_of[kid])}, not to subject {subject!r}")
            continue
        try:
            algo = algs.get_default_algorithms()[alg]
            key = algo.from_jwk(json.dumps(jwks[kid]))
            signing_input = f"{sig['protected']}.{payload_b64}".encode("ascii")
            ok = algo.verify(signing_input, key, b64url_decode(sig["signature"]))
        except (ValueError, TypeError, KeyError, NotImplementedError, jwt.exceptions.PyJWTError) as e:
            ok = False  # malformed key / signature bytes, or an algorithm the library cannot load
            errs.append(f"{where}: verification error: {e}")
        if not ok:
            errs.append(f"{where}: signature does not verify against JCS(contract) with kid {kid!r}")
            continue
        verified.append(kid)
        owner_signed = owner_signed or kid in subject_of
    if not errs and not owner_signed:
        errs.append(f"no signature from a key bound to subject {subject!r}: endorsements without the owner's "
                    "self-declaration are not an envelope (D9 tier 1)")
    return errs, verified


# ---------- driver ----------

def load(path: Path, parse_float=float):
    """(doc, _expect_match, expected-output pin, parse_error). NaN / Infinity make the whole document a
    rejection; the fixture's own `_expect*` keys are still read (permissively) so the suite can assert on them."""
    text = path.read_text()
    try:
        doc = json.loads(text, parse_float=parse_float, parse_constant=reject_constant)
        parse_error = None
    except ValueError as e:
        doc, parse_error = json.loads(text), f"document rejected at parse: {e}"
    doc.pop("_expect", None)
    match = doc.pop("_expect_match", None)
    kids, composed = doc.pop("_expect_verified_kids", None), doc.pop("_expect_composed", None)
    if kids is not None and composed is not None:  # one pin per fixture; a second one would be silently dropped
        parse_error = parse_error or "fixture carries both _expect_verified_kids and _expect_composed"
    return doc, match, kids if kids is not None else composed, parse_error


def validate(path: Path, jwks: dict, subject_of: dict) -> list[str]:
    doc, _, _, parse_error = load(path)
    if parse_error:
        return [parse_error]
    return envelope_errors(doc, jwks, subject_of) if "envelope_version" in doc else contract_errors(doc)


def run_suite(name: str, valid_dir: Path, invalid_dir: Path, check, verified=None) -> int:
    valid = sorted(valid_dir.glob("*.json"))
    invalid = sorted(invalid_dir.glob("*.json"))
    if not valid or not invalid:
        print(f"[{name}] suite incomplete: need at least one valid and one invalid example")
        return 1
    bad = 0
    for f in valid:
        doc, _, expected, parse_error = load(f)
        errs = [parse_error] if parse_error else check(doc)
        if not errs and expected is not None and verified(doc) != expected:
            errs = [f"verified kids {verified(doc)} != expected {expected}"]
        print(f"[{name}] {'PASS' if not errs else 'FAIL'} must-accept {f.name}")
        for e in errs:
            print(f"      {e}")
        bad += bool(errs)
    for f in invalid:
        doc, match, _, parse_error = load(f)
        errs = [parse_error] if parse_error else check(doc)
        if not errs:
            print(f"[{name}] FAIL must-reject {f.name}  (was accepted!)")
            bad += 1
        elif match and not any(match in e for e in errs):
            print(f"[{name}] FAIL must-reject {f.name}  (rejected for the wrong reason: {errs[0]!r} lacks {match!r})")
            bad += 1
        else:
            print(f"[{name}] PASS must-reject {f.name}  ({errs[0]})")
    print(f"[{name}] {len(valid)} must-accept + {len(invalid)} must-reject, {bad} failures\n")
    return bad


def run_guard_suite() -> int:
    """Rejections that only a programmatic caller can reach: a dict built in code, never parsed by load(), can
    carry float('nan') / float('inf'). JSON fixtures cannot express these (the parser refuses them first), so
    the guards are exercised here; without this the guards would be GREEN under mutation (round 16 fourth pass)."""
    base = json.loads((HERE / "examples" / "valid" / "doc-extractor.json").read_text())
    base.pop("_expect", None)
    cases = []
    # only `number` fields reach the guard: for `integer` fields a non-finite float already fails `type` and
    # `minimum`; for `number` fields `minimum` / `exclusiveMinimum` are vacuous on NaN (every comparison is False)
    for name, value in (("max_cost", {"amount": float("nan"), "unit": "USD"}), ("max_seconds", float("inf")),
                        ("max_seconds", float("nan"))):
        doc = json.loads(json.dumps(base))
        doc["bounds"][name] = value
        cases.append((f"contract bounds.{name}={value!r}", contract_errors(doc), "not of type 'integer'"))
    # a fixture carrying both pins is an authoring error that must surface, not silently drop one (fifth pass)
    both = HERE / "examples" / ".both-pins.tmp.json"
    both.write_text(json.dumps({**base, "_expect_verified_kids": [], "_expect_composed": {}}))
    try:
        _, _, _, parse_error = load(both)
    finally:
        both.unlink()
    cases.append(("fixture with both _expect_verified_kids and _expect_composed", [parse_error or ""], "both"))
    bad = 0
    for label, errs, match in cases:
        ok = bool(errs) and any(match in e for e in errs)
        print(f"[guards] {'PASS' if ok else 'FAIL'} must-reject {label}" + ("" if ok else f"  (errors: {errs})"))
        bad += not ok
    print(f"[guards] {len(cases)} programmatic must-reject, {bad} failures\n")
    return bad


def run_keystore_suite(invalid_dir: Path) -> int:
    """Every examples/keys/invalid/*.jwks.json must be refused by load_trust_store for the reason it names."""
    files = sorted(invalid_dir.glob("*.jwks.json"))
    if not files:
        print("[keystore] suite incomplete: need at least one must-reject key store")
        return 1
    bad = 0
    for f in files:
        match = json.loads(f.read_text()).get("_expect_match")
        try:
            load_trust_store(f)
        except ValueError as e:
            if match and match not in str(e):
                print(f"[keystore] FAIL must-reject {f.name}  (rejected for the wrong reason: {e!r} lacks {match!r})")
                bad += 1
            else:
                print(f"[keystore] PASS must-reject {f.name}  ({e})")
        else:
            print(f"[keystore] FAIL must-reject {f.name}  (was loaded!)")
            bad += 1
    print(f"[keystore] {len(files)} must-reject, {bad} failures\n")
    return bad


def main(argv: list[str]) -> int:
    jwks_path = DEFAULT_JWKS
    if argv[:1] == ["--jwks"]:
        jwks_path, argv = Path(argv[1]), argv[2:]
    try:
        jwks, subject_of = load_trust_store(jwks_path) if jwks_path.exists() else ({}, {})
    except ValueError as e:
        print(f"FAIL {e}")
        return 2

    if argv:
        rc = 0
        for f in argv:
            errs = validate(Path(f), jwks, subject_of)
            print(f"{'OK  ' if not errs else 'FAIL'} {f}")
            for e in errs:
                print(f"      {e}")
            rc |= bool(errs)
        return rc

    ex = HERE / "examples"
    bad = run_suite("contract", ex / "valid", ex / "invalid", contract_errors)
    bad += run_suite("envelope", ex / "envelopes" / "valid", ex / "envelopes" / "invalid",
                     lambda d: envelope_errors(d, jwks, subject_of),
                     verified=lambda d: verify_envelope(d, jwks, subject_of)[1])
    bad += run_keystore_suite(ex / "keys" / "invalid")
    bad += run_guard_suite()
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
