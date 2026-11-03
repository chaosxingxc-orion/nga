#!/usr/bin/env python3
"""Regenerate the envelope example suite with fresh ephemeral keys.

Every run creates new EC P-256 key pairs (publisher bound to the two example agents,
tester as unbound endorser, three bound keys that each fail exactly one JWK check
(use=enc / key_ops without verify / alg=RS256), another publisher bound to a different
agent, and a rogue key that is deliberately NOT trusted), signs the valid contracts,
writes the trusted store (JWKS + subject_of owner binding) and three must-reject key
stores, and derives every must-reject envelope by programmatic mutation of a valid one —
so the invalid examples can never drift out of sync with the signatures.

Private keys never touch disk. Re-running rewrites all envelope examples and the
key store together; commit them as one change.

Usage:  python3 schema/sign.py
"""
# TOMBSTONE (2026-10-28): corpus ownership moved to go/cmd/sign (V5 singularity
# F-E). The Go regenerator produces the 4-signer three-algorithm envelope, the
# literal-FFFD and header-surrogate probes, and the RS256/EdDSA endorser keys;
# running THIS script would overwrite them with the 2xES256 shape and silently
# lose positive-path coverage. Kept as the frozen reference for mutant recipes.
import copy
import json
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ec
import jwt.algorithms as algs

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rfc8785_min import canonicalize  # noqa: E402
from validate import b64url, contract_hash  # noqa: E402

HERE = Path(__file__).resolve().parent
EX = HERE / "examples"
ES256 = algs.ECAlgorithm(algs.ECAlgorithm.SHA256)


def new_key(kid: str):
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = ES256.to_jwk(priv.public_key(), as_dict=True)
    pub.update({"kid": kid, "use": "sig", "alg": "ES256"})
    return priv, pub


def sign(contract: dict, priv, kid: str, alg: str = "ES256", typ: str = "JOSE", extra: dict | None = None) -> dict:
    header = {"alg": alg, "typ": typ, "kid": kid, **(extra or {})}
    protected = b64url(json.dumps(header, separators=(",", ":")).encode())
    signing_input = f"{protected}.{b64url(canonicalize(contract))}".encode("ascii")
    return {"protected": protected, "signature": b64url(ES256.sign(signing_input, priv))}


def envelope(contract: dict, signers: list[tuple[str, object]]) -> dict:
    return {
        "_expect_verified_kids": [kid for kid, _ in signers],
        "envelope_version": "0.1.0",
        "contract": contract,
        "contract_hash": contract_hash(contract),
        "signatures": [sign(contract, priv, kid) for kid, priv in signers],
    }


def load_contract(name: str) -> dict:
    doc = json.loads((EX / name).read_text())
    doc.pop("_expect", None)
    doc.pop("_expect_match", None)
    return doc


def flip_first_char(s: str) -> str:
    return ("B" if s[0] == "A" else "A") + s[1:]


def write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=False)
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:  # only the lone-surrogate mutant: keep it as a JSON escape on disk
        text = json.dumps(doc, indent=2, ensure_ascii=True)
    path.write_text(text + "\n", encoding="utf-8")


def main() -> int:
    raise SystemExit("tombstoned: corpus ownership moved to go/cmd/sign (2026-10-28); "
                     "running this would overwrite the 4-signer three-algorithm envelopes")


def _legacy_main() -> int:
    pub_priv, pub_jwk = new_key("publisher-2026-09")
    test_priv, test_jwk = new_key("tester-2026-09")
    rogue_priv, _ = new_key("rogue-2026-09")  # never enters the trusted store
    enc_priv, enc_jwk = new_key("enc-only-2026-09")  # trusted, but published as an encryption key
    enc_jwk["use"] = "enc"
    other_priv, other_jwk = new_key("other-publisher-2026-09")  # trusted owner of a different agent
    ops_priv, ops_jwk = new_key("ops-enc-2026-09")  # trusted, bound, use=sig, but key_ops says encrypt only
    ops_jwk["key_ops"] = ["encrypt"]
    algrs_priv, algrs_jwk = new_key("alg-rs-2026-09")  # trusted, bound, but published for RS256
    algrs_jwk["alg"] = "RS256"

    write(EX / "keys" / "trusted.jwks.json", {
        "keys": [pub_jwk, test_jwk, enc_jwk, other_jwk, ops_jwk, algrs_jwk],
        "subject_of": {  # owner binding (round 16 V-F); kids absent here are endorsers
            "publisher-2026-09": ["doc-extractor", "compliance-filer"],
            # the next three are bound on purpose so that use / key_ops / alg is the only reason each example fails
            "enc-only-2026-09": ["doc-extractor"],
            "ops-enc-2026-09": ["doc-extractor"],
            "alg-rs-2026-09": ["doc-extractor"],
            "other-publisher-2026-09": ["ledger-poster"],
        },
    })
    write(EX / "keys" / "invalid" / "duplicate-kid.jwks.json", {
        "_expect": "REJECT at load: two entries share a kid; last-wins would let the second appender sign as the first",
        "_expect_match": "duplicate kid",
        "keys": [pub_jwk, {**test_jwk, "kid": "publisher-2026-09"}],
    })
    write(EX / "keys" / "invalid" / "missing-kid.jwks.json", {
        "_expect": "REJECT at load: an entry without kid would be silently dropped and its signer "
                   "indistinguishable from an impostor",
        "_expect_match": "has no kid",
        "keys": [pub_jwk, {k: v for k, v in test_jwk.items() if k != "kid"}],
    })
    write(EX / "keys" / "invalid" / "binding-unknown-kid.jwks.json", {
        "_expect": "REJECT at load: subject_of names a kid that has no key; a dangling binding is a typo, not a policy",
        "_expect_match": "unknown kid",
        "keys": [pub_jwk],
        "subject_of": {"publsher-2026-09": ["doc-extractor"]},
    })

    doc_extractor = load_contract("valid/doc-extractor.json")
    compliance_filer = load_contract("valid/compliance-filer.json")
    two_signers = envelope(doc_extractor, [("publisher-2026-09", pub_priv), ("tester-2026-09", test_priv)])
    write(EX / "envelopes" / "valid" / "doc-extractor.envelope.json", two_signers)
    write(EX / "envelopes" / "valid" / "compliance-filer.envelope.json",
          envelope(compliance_filer, [("publisher-2026-09", pub_priv)]))

    inv = EX / "envelopes" / "invalid"
    for stale in inv.glob("*.json"):
        stale.unlink()

    def mutant(expect: str, match: str, edit) -> dict:
        m = copy.deepcopy(two_signers)
        m.pop("_expect_verified_kids", None)
        edit(m)
        return {"_expect": expect, "_expect_match": match, **m}

    def tamper(m):  # contract edited after signing, hash recomputed → only the signatures can catch it
        m["contract"]["bounds"]["max_cost"]["amount"] = m["contract"]["bounds"]["max_cost"]["amount"] + 7
        m["contract_hash"] = contract_hash(m["contract"])

    def bad_hash(m):
        m["contract_hash"] = m["contract_hash"][:-1] + ("0" if m["contract_hash"][-1] != "0" else "1")

    def alg_none(m):
        header = {"alg": "none", "typ": "JOSE", "kid": "publisher-2026-09"}
        protected = b64url(json.dumps(header, separators=(",", ":")).encode())
        m["signatures"] = [{"protected": protected, "signature": "AA"}]

    def bad_typ(m):  # round 16 B3: the typ check had no example and survived deletion
        m["signatures"] = [sign(m["contract"], pub_priv, "publisher-2026-09", typ="JWT")]

    def enc_key(m):  # round 16 R-15: signed with a key whose JWKS entry says use=enc
        m["signatures"] = [sign(m["contract"], enc_priv, "enc-only-2026-09")]

    def unknown_kid(m):
        m["signatures"] = [sign(m["contract"], rogue_priv, "rogue-2026-09")]

    def key_ops_no_verify(m):  # round 16 second pass: key_ops was never read
        m["signatures"] = [sign(m["contract"], ops_priv, "ops-enc-2026-09")]

    def alg_mismatch(m):  # round 16 second pass: the JWK's own alg was never compared with the header
        m["signatures"] = [sign(m["contract"], algrs_priv, "alg-rs-2026-09")]

    def crit_header(m):  # round 16 second pass: RFC 7515 crit was ignored
        m["signatures"] = [sign(m["contract"], pub_priv, "publisher-2026-09", extra={"crit": ["exp"], "exp": 0})]

    def duplicate_signer(m):  # round 16 second pass: the same key counted as two endorsers
        s = sign(m["contract"], pub_priv, "publisher-2026-09")
        m["signatures"] = [s, dict(s)]

    def endorser_only(m):  # round 16 V-F: a tester vouched, but nobody who owns doc-extractor declared it
        m["signatures"] = [sign(m["contract"], test_priv, "tester-2026-09")]

    def wrong_owner(m):  # round 16 V-F: a trusted owner key signing for an agent it does not own
        m["signatures"] = [sign(m["contract"], other_priv, "other-publisher-2026-09")]

    def one_of_two_bad(m):
        m["signatures"][1]["signature"] = flip_first_char(m["signatures"][1]["signature"])

    def no_signatures(m):
        m["signatures"] = []

    def lone_surrogate(m):  # round 16 F-4: legal JSON, not encodable as UTF-8 -> crashed the canonicalizer
        m["contract"]["notes"] = "see \ud800 appendix"  # hash left as-is; canonicalization fails before comparison

    def signed_but_invalid_contract(m):
        bad = load_contract("invalid/wildcard-selector.json")
        m["contract"] = bad
        m["contract_hash"] = contract_hash(bad)
        m["signatures"] = [sign(bad, pub_priv, "publisher-2026-09")]

    cases = {
        "tampered-contract": (
            "REJECT: contract edited after signing (hash recomputed so only JWS verification catches it)",
            "does not verify", tamper),
        "hash-mismatch": ("REJECT: contract_hash does not match JCS(contract)", "contract_hash", bad_hash),
        "alg-none": ("REJECT: alg 'none' is never acceptable", "alg 'none'", alg_none),
        "bad-typ": ("REJECT: protected header typ must be 'JOSE' (A2A §8.4.2)", "typ must be", bad_typ),
        "enc-key": (
            "REJECT: the kid resolves to a key published with use=enc; "
            "encryption keys never verify signatures (RFC 7517 §4.3)",
            "not a signing key", enc_key),
        "unknown-kid": (
            "REJECT: valid signature but kid is not in the trusted key store",
            "not in trusted key store", unknown_kid),
        "key-ops-no-verify": (
            "REJECT: the kid's JWK has key_ops without 'verify' (RFC 7517 §4.3)",
            "without 'verify'", key_ops_no_verify),
        "alg-mismatch": (
            "REJECT: the kid's JWK is published for RS256, the protected header says ES256 (RFC 7517 §4.4)",
            "is published for alg", alg_mismatch),
        "crit-header": (
            "REJECT: a critical header parameter this verifier does not implement (RFC 7515 §4.1.11)",
            "critical header", crit_header),
        "duplicate-signer": (
            "REJECT: one key, two signatures; endorsements are counted per key", "already signed", duplicate_signer),
        "endorser-only": (
            "REJECT: only an endorser (kid with no subject binding) signed; the owner's self-declaration is missing",
            "no signature from a key bound to subject", endorser_only),
        "wrong-owner": (
            "REJECT: the signing kid is bound to a different agent; "
            "any trusted key could otherwise 'self-declare' for anyone",
            "is bound to", wrong_owner),
        "one-of-two-bad": (
            "REJECT: every signature present must verify; a broken second signature is a forgery signal, not noise",
            "signatures/1", one_of_two_bad),
        "no-signatures": ("REJECT: an envelope with no endorser is not an envelope", "non-empty", no_signatures),
        "lone-surrogate": (
            "REJECT (not crash): contract text contains a lone UTF-16 surrogate; RFC 8785 output must be UTF-8",
            "lone surrogate", lone_surrogate),
        "signed-but-invalid-contract": (
            "REJECT: a valid signature never relaxes the contract gate (D8 wildcard selector)",
            "selector", signed_but_invalid_contract),
    }
    for name, (expect, match, edit) in cases.items():
        write(inv / f"{name}.json", mutant(expect, match, edit))

    print(f"wrote 1 key store + 3 invalid key stores, 2 valid envelopes, {len(cases)} invalid envelopes "
          f"under {EX.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
