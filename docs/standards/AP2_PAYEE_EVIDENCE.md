AP2 risk_data profile: payee_evidence (draft 0.1)
=================================================

Status 2026-09-24: draft by Jithox, not an AP2 or FIDO document. Files: [schema](ap2-payee-evidence.schema.json),
[real example](ap2-payee-evidence.example.json), [offline verifier](verify_payee_evidence.py) (Python, `cryptography` only).

**Problem.** AP2 v0.2 gives the closed Payment Mandate an open `risk_data` object ("risk signals collected by the trusted
surface", no schema; issue #163). `payee` is a Merchant `{id, name, website}` with no account field, and `payee.id` may be
empty, which makes matching fall back to `name + website` (#315). Nothing says which account was checked for that payee.

**Profile.** The Trusted Surface asks a checker about the account to be credited, before the mandate is signed, and puts
the signed answer under one key in `risk_data`. It adds no AP2 field; `risk_data` is open by design.

```json
"risk_data": { "payee_evidence": [ { "format": "compact-jws", "jws": "<token>", "payee_id": "<= payee.id>" } ] }
```

- `jws`: compact JWS (RFC 7515), header `{"alg":"EdDSA","kid":…,"typ":"jithox-evidence+jws"}`, Ed25519 (RFC 8037). The
  payload has exactly `v, iss, kind, issuedAt, verdict, checks[{id,status,source}], inputDigest, toolVersion, kid`.
  `inputDigest = "sha256:" + hex(SHA-256("jithox.evidence.input.v1\n" + kind + "\n" + salt + "\n" + canonicalJson(input)))`,
  with a fresh 16-byte salt per token. That digest is the account fingerprint; the token holds no IBAN, name or country.
- `payee_id` MUST equal `payee.id` and MUST NOT be empty. The token does not name the payee: the link between the
  fingerprint and the Merchant comes from the mandate signature over `risk_data`, not from ours.
- The input and salt go ONLY to the party that executes the payment, as a selectively disclosable claim or out of band:
  `{"input": {"newIban", "ibanOnFile", "supplierCountry"}, "salt"}`, input already canonical (IBAN without spaces, dots or
  dashes, upper case; `ibanOnFile` null only when there is none; country two letters or null). With the salt, anyone who
  can guess an account can confirm it, so never put it in the clear.

**Verify offline** (the free `POST https://jithox.com/api/v1/evidence/verify` does steps 1-4 and the digest of step 6 online):
1. Fetch `https://jithox.com/.well-known/jwks.json` once and store it (max-age 300, CORS `*`). After that nothing goes over
   the network. An unknown `kid` means `unknown_key`: neither valid nor invalid.
2. Refuse unless `alg` = `EdDSA` and `typ` = `jithox-evidence+jws`. Refuse `crit`, `b64`, `jwk`, `jku`, `x5u` and `x5c`
   (a key inside the token anchors nothing).
3. Verify the Ed25519 signature over the ASCII bytes `header.payload`. Do not re-serialise anything.
4. Require the 9 payload fields, `v` = 1 and payload `kid` = header `kid`. jose and PyJWT do not check `typ` or the
   payload `kid`, so check those two yourself.
5. Require `iss` = `https://jithox.com`, `kind` = `payment_change_check` and `payee_id` = `payee.id`, not empty.
6. Executing party: recompute `inputDigest` from the disclosed input and salt, then require the account you are about to
   credit to equal `input.newIban`. Without this step the token is not tied to any account.
7. Apply `verdict`. `stop` or `invalid_new_account`: do not pay without a person. `verify_first`: a real change, so the
   call-back on an independently known number is still required. `no_change`: the account equals the one on file.
   No verdict means "safe".

**Real example.** The file above holds a closed Payment Mandate claim set (the mandate itself is unsigned here) with a
production token. That token came from the free `check_payment_change` on `https://jithox.com/api/mcp` at
2026-09-24T12:47:58Z, with verdict `stop` and kid `kQIl-VFhDW4MaVRUas4_Q6wJnzzGEnrwPGpQFOEC55w`. It uses the documented
example IBANs GB33 BUKB 2020 1555 5555 55 and BE68 5390 0754 7034, so there is no personal data.
Command: `python verify_payee_evidence.py ap2-payee-evidence.example.json --credit-iban GB33BUKB20201555555555`.

**Live (measured 2026-09-24):** the JWKS has 1 Ed25519 key. The anonymous tool call returns `evidence.jws`, and the
verify route answers `valid`, with `inputMatch` true for the real input and false for another one.

**Not done:**
- Jithox does not prove who owns an account. That needs Verification of Payee or a bank-issued IBAN attestation.
- `issuedAt` is our server clock, not an RFC 3161 timestamp.
- There is no revocation. Old keys stay listed for verification.
- Only `payment_change_check` is signed today.
- No known AP2 implementation reads this profile.
- It has not been submitted to FIDO.
