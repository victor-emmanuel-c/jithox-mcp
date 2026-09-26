# More examples for pay-invoices-safely

Every call below was run against production on 2026-09-24. Output is the tool
result (`result.content[0].text`) or the HTTP body, shortened where it says
`…`. The IBANs have valid check digits but belong to nobody we know; the
supplier is made up.

## check_payment_change: the account moved abroad (`stop`)

The supplier is in Denmark, the account on file is Danish, and the new one is
German.

```bash
curl -s https://jithox.com/api/mcp \
  -A 'pay-invoices-safely/1.0' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"check_payment_change","arguments":{"newIban":"DE89 3704 0044 0532 0130 00","ibanOnFile":"DK50 0040 0440 1162 43","supplierCountry":"DK"}}}'
```

```json
{
  "kind": "payment_change_check",
  "data": {
    "verdict": "stop",
    "summary": "2 red flags. Do not update the vendor record until a person has cleared them with the supplier.",
    "flags": [
      { "code": "account_country_differs_from_supplier", "severity": "red", "what": "The supplier is established in DK, and the new account is issued in Germany (DE). Ordinary for some groups — and also what a diverted payment looks like, so a person has to tell the two apart." },
      { "code": "account_moved_to_another_country", "severity": "red", "what": "The account on file is in Denmark; the new one is in Germany. A supplier moving its receiving account abroad does happen, and is also what a diversion looks like." }
    ],
    "requiredSteps": [
      "Do not update the vendor record yet, and hold payments to this supplier that are not already in flight.",
      "Call the supplier on a phone number from your OWN records or a previous, paid invoice — never one from the change request or its e-mail signature.",
      …
    ],
    …
  }
}
```

## check_payment_change: the same account, written differently (`no_change`)

```bash
curl -s https://jithox.com/api/mcp \
  -A 'pay-invoices-safely/1.0' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"check_payment_change","arguments":{"newIban":"dk5000400440116243","ibanOnFile":"DK50 0040 0440 1162 43","supplierCountry":"DK"}}}'
```

```json
{
  "kind": "payment_change_check",
  "data": {
    "verdict": "no_change",
    "summary": "This is the account already on file, written differently. Nothing changes.",
    "flags": [],
    "requiredSteps": [
      "No update is needed. If the request insisted the details were NEW, treat that mismatch as worth a call."
    ],
    …
  }
}
```

## check_payment_change: one digit swapped (`invalid_new_account`)

```bash
curl -s https://jithox.com/api/mcp \
  -A 'pay-invoices-safely/1.0' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"check_payment_change","arguments":{"newIban":"DK27 5301 0244 5638 12","ibanOnFile":"DK50 0040 0440 1162 43","supplierCountry":"DK"}}}'
```

```json
{
  "kind": "payment_change_check",
  "data": {
    "verdict": "invalid_new_account",
    "summary": "The new account number cannot be a valid IBAN. The check digits do not match the rest of the number. Usually one character was typed or copied wrongly.",
    "flags": [],
    "requiredSteps": [
      "Do not update the vendor record.",
      "Ask the supplier for the account number again — through a contact you already hold, not by replying to the request."
    ],
    …
  }
}
```

## POST /api/invoice/review: a total that does not add up (a `blocker`)

The invoice from SKILL.md, with `totalWithVat` 10500 instead of 10000.

```bash
curl -s https://jithox.com/api/invoice/review \
  -A 'pay-invoices-safely/1.0' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -d '{"invoice":{"invoiceNumber":"2026-0917","issueDate":"2026-09-17","dueDate":"2026-10-17","currency":"DKK","buyerReference":"PO-4471","supplier":{"name":"Nordlys Tryk ApS","countryCode":"DK","vatId":"DK31500060","endpointId":"5790000000012","endpointScheme":"0088"},"customer":{"name":"Havn Logistik A/S","countryCode":"DK","vatId":"DK31500044","endpointId":"5790000000029","endpointScheme":"0088"},"lines":[{"description":"Printing, September","quantity":1,"unitPrice":8000,"vatPercent":25}],"totalWithoutVat":8000,"totalVat":2000,"totalWithVat":10500,"payment":{"iban":"DK27 5301 0244 5638 21"}}}'
```

```json
{
  "review": {
    "checks": [
      …
      { "id": "peppol", "status": "fail", "detail": "The Peppol network refuses this invoice: BR-CO-15 is broken. The export below is a draft to correct, not one to send.", … }
    ],
    "findings": [
      { "code": "peppol_rule_failed", "severity": "blocker", "rule": "BR-CO-15", "what": "BR-CO-15: 8000.00 + 2000.00 is 10000.00, and the invoice says 10500.00.", "fix": "The gross total is not the net total plus the VAT. Usually a rounding difference of a cent; correct one of the three." }
    ],
    "readyToSend": false,
    "hasUnknowns": true,
    …
  },
  …
}
```

Do not pay an amount the invoice cannot account for. Ask the supplier for a
corrected invoice through a contact you already hold.
