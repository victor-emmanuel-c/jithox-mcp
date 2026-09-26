"""Check AP2 risk_data.payee_evidence offline (profile: AP2_PAYEE_EVIDENCE.md).

Needs one package: pip install cryptography
Usage:
  python verify_payee_evidence.py ap2-payee-evidence.example.json [jwks.json] [--credit-iban IBAN]

  jwks.json      a saved copy of https://jithox.com/.well-known/jwks.json. Without it the
                 script fetches it once; everything after that runs without network.
  --credit-iban  the account the executing party is about to credit. It must equal the
                 disclosed newIban.
Input: the example file ({payment_mandate, disclosure_for_the_executing_party}) or a bare
Payment Mandate claim set. Exit code 0 = every entry is valid and bound to payee.id.
"""
import base64
import hashlib
import json
import re
import sys
import urllib.request

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

JWKS_URL = "https://jithox.com/.well-known/jwks.json"
ISSUER = "https://jithox.com"
TYP = "jithox-evidence+jws"
KIND = "payment_change_check"
REFUSED_HEADERS = ("crit", "b64", "jwk", "jku", "x5u", "x5c")
PAYLOAD_FIELDS = {"v", "iss", "kind", "issuedAt", "verdict", "checks", "inputDigest", "toolVersion", "kid"}
B64U = re.compile(r"^[A-Za-z0-9_-]+$")


def b64u_decode(part):
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def verify_jws(jws, keys):
    """Return ("valid", payload) | ("invalid", reason) | ("unknown_key", kid)."""
    parts = jws.strip().split(".") if isinstance(jws, str) else []
    if len(parts) != 3 or not all(p and B64U.match(p) for p in parts):
        return "invalid", "not_a_compact_jws"
    try:
        header = json.loads(b64u_decode(parts[0]))
    except ValueError:
        return "invalid", "header_unreadable"
    if not isinstance(header, dict):
        return "invalid", "header_unreadable"
    if header.get("alg") != "EdDSA":
        return "invalid", "algorithm_not_eddsa"
    if header.get("typ") != TYP:
        return "invalid", "not_jithox_evidence"
    if any(name in header for name in REFUSED_HEADERS):
        return "invalid", "unsupported_header"
    key = next((k for k in keys if k.get("kid") == header.get("kid")), None)
    if key is None or key.get("kty") != "OKP" or key.get("crv") != "Ed25519":
        return "unknown_key", header.get("kid")
    try:
        Ed25519PublicKey.from_public_bytes(b64u_decode(key["x"])).verify(
            b64u_decode(parts[2]), f"{parts[0]}.{parts[1]}".encode("ascii"))
    except (InvalidSignature, ValueError):
        return "invalid", "signature_mismatch"
    try:
        payload = json.loads(b64u_decode(parts[1]))
    except ValueError:
        return "invalid", "payload_unreadable"
    if not isinstance(payload, dict) or set(payload) != PAYLOAD_FIELDS or payload["v"] != 1:
        return "invalid", "payload_shape"
    if payload["kid"] != header["kid"]:
        return "invalid", "kid_mismatch"  # jose/PyJWT do not check this by themselves
    if payload["iss"] != ISSUER or payload["kind"] != KIND:
        return "invalid", "unexpected_issuer_or_kind"
    return "valid", payload


def canonical_input(raw):
    """The input exactly as check_payment_change reads it (see the profile)."""
    def iban(value):
        return re.sub(r"[\s.\u00a0\ufeff-]", "", value).upper()
    on_file = raw.get("ibanOnFile")
    country = raw.get("supplierCountry")
    country = country.strip().upper() if isinstance(country, str) else None
    return {
        "ibanOnFile": iban(on_file) if isinstance(on_file, str) and on_file.strip() else None,
        "newIban": iban(raw.get("newIban") or ""),
        "supplierCountry": country if country and re.fullmatch(r"[A-Z]{2}", country) else None,
    }


def input_digest(salt, canonical):
    text = json.dumps(canonical, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    data = f"jithox.evidence.input.v1\n{KIND}\n{salt}\n{text}".encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def main(argv):
    credit = None
    if "--credit-iban" in argv:
        i = argv.index("--credit-iban")
        credit = re.sub(r"[\s.\u00a0\ufeff-]", "", argv[i + 1]).upper()
        argv = argv[:i] + argv[i + 2:]
    with open(argv[0], encoding="utf-8") as f:
        doc = json.load(f)
    mandate = doc.get("payment_mandate", doc)
    outer_disclosure = doc.get("disclosure_for_the_executing_party")
    if len(argv) > 1:
        with open(argv[1], encoding="utf-8") as f:
            keys = json.load(f)["keys"]
    else:
        with urllib.request.urlopen(JWKS_URL, timeout=20) as resp:
            keys = json.load(resp)["keys"]

    payee_id = (mandate.get("payee") or {}).get("id")
    entries = (mandate.get("risk_data") or {}).get("payee_evidence") or []
    ok = bool(entries)
    for n, entry in enumerate(entries):
        status, detail = verify_jws(entry.get("jws"), keys)
        line = {"entry": n, "status": status}
        if status != "valid":
            line["reason" if status == "invalid" else "kid"] = detail
            ok = False
        else:
            line.update(verdict=detail["verdict"], issuedAt=detail["issuedAt"])
            bound = bool(payee_id) and entry.get("payee_id") == payee_id
            line["payeeBound"] = bound
            ok = ok and bound
            disclosure = entry.get("disclosure") or outer_disclosure
            if disclosure:
                given = disclosure["input"]
                canonical = canonical_input(given)
                # The profile requires the disclosed input in canonical form: hash it as given,
                # and refuse a disclosure that is not already canonical.
                line["inputMatch"] = given == canonical and input_digest(disclosure["salt"], given) == detail["inputDigest"]
                ok = ok and line["inputMatch"]
                if credit is not None:
                    line["creditMatchesNewIban"] = credit == canonical["newIban"]
                    ok = ok and line["creditMatchesNewIban"]
            else:
                line["inputMatch"] = "not_checked"
        print(json.dumps(line))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
