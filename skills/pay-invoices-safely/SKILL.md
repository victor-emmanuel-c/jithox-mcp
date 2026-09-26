---
name: pay-invoices-safely
description: "Use this to pay invoice safely: run Jithox's live checks before an agent pays a supplier invoice or changes a supplier's bank account. Use it on every supplier bank change (a new IBAN in an e-mail, or an IBAN on the invoice that differs from the vendor record), as payment verification before a payment run, and to hold a payment to a diverted account - a common invoice fraud - until a person has called the supplier back. check_payment_change compares the new IBAN with the account on file and returns the call-back steps. POST /api/invoice/review checks the invoice structure, the totals, the IBAN and the Peppol BIS Billing 3.0 rules, free and without an account. review_invoice, a paid tool that needs a token, also checks the supplier and customer VAT numbers against the EU VIES register. Jithox never pays and never signs a payment; the agent prepares, a person decides."
license: MIT
metadata:
  author: jithox
  version: "1.0"
---

# Pay invoices safely

You are about to pay a supplier invoice, or to change the bank account on a
vendor record. Before any money moves, run the checks below and give the
person who approves the payment what they return.

Use this skill when:

- a supplier (or someone writing as the supplier) sends new bank details;
- the IBAN on an invoice differs from the account on the vendor record;
- you prepare a payment run and want each invoice checked first;
- you are asked "is this invoice OK to pay?".

The two free checks need no account and no token.

## Connect

MCP server (Streamable HTTP, JSON-RPC 2.0):

```json
{
  "mcpServers": {
    "jithox": { "url": "https://jithox.com/api/mcp" }
  }
}
```

Plain HTTP works as well; every example below is a curl call. Set your own
user agent as shown, so these calls can be told apart from other traffic.

## Step 1 - a new or changed bank account: check_payment_change

Call it when a supplier gives a new account, and when the IBAN on the invoice
is not the one on file (then the invoice IBAN is the new one). Leave
`ibanOnFile` out for a first payment to a new supplier; the answer then says
nothing could be compared.

```bash
curl -s https://jithox.com/api/mcp \
  -A 'pay-invoices-safely/1.0' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"check_payment_change","arguments":{"newIban":"DK27 5301 0244 5638 21","ibanOnFile":"DK50 0040 0440 1162 43","supplierCountry":"DK"}}}'
```

The tool result (`result.content[0].text`), run against production on
2026-09-24 and shortened where it says `…`:

```json
{
  "kind": "payment_change_check",
  "data": {
    "verdict": "verify_first",
    "summary": "The new number is a well-formed account and nothing about it stands out. It is still a change of where money goes: confirm it by phone before updating the record.",
    "newAccount": { "status": "valid", "iban": "DK27 5301 0244 5638 21", "country": "Denmark", … },
    "accountOnFile": { "status": "valid", "iban": "DK50 0040 0440 1162 43", "country": "Denmark", … },
    "flags": [
      { "code": "bank_changed", "severity": "note", "what": "Same country, different bank (identifier 0040 → 5301). Ordinary on its own — companies do change banks — and worth mentioning on the call." }
    ],
    "requiredSteps": [
      "Call the supplier on a phone number from your OWN records or a previous, paid invoice — never one from the change request or its e-mail signature.",
      "Have them read the new account number back to you; do not read it to them.",
      "Have a second person approve the change to the vendor record before any payment runs.",
      "Keep the request, the name of the person you spoke to, and the time of the call with the vendor record."
    ],
    "doesNotProve": "Who owns the new account, that it exists or is open, or that the request came from the supplier. No free registry answers those. Only the call-back does.",
    …
  }
}
```

Act on `verdict`:

| `verdict` | What you do |
| --- | --- |
| `no_change` | The same account, written differently. Go on to step 2. If the request insisted the details were new, that mismatch is worth a call. |
| `verify_first` | Do not pay and do not change the vendor record. Hand the `requiredSteps` to a person. |
| `stop` | Red flags. Do not pay, hold other payments to this supplier, hand `flags` and `requiredSteps` to a person. |
| `invalid_new_account` | The number cannot be an IBAN. Do not pay. Ask the supplier for the number through a channel you already know. |

The call-back is the check. A person calls the supplier on a phone number
that does NOT come from the e-mail, the change request or the invoice. You
cannot make that call for them, and a well-formed IBAN is not a safe one.

The same call for the `stop`, `no_change` and `invalid_new_account` cases is
in [references/examples.md](references/examples.md).

## Step 2 - the invoice itself: POST /api/invoice/review (free)

Send the invoice as structured data. It checks the structure, recomputes the
totals, checks the IBAN on it and applies the Peppol BIS Billing 3.0 rules. No
account, no token, nothing charged. Like review_invoice it reads structured
data, not a PDF or a scan: turn those into fields first.

```bash
curl -s https://jithox.com/api/invoice/review \
  -A 'pay-invoices-safely/1.0' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -d '{"invoice":{"invoiceNumber":"2026-0917","issueDate":"2026-09-17","dueDate":"2026-10-17","currency":"DKK","buyerReference":"PO-4471","supplier":{"name":"Nordlys Tryk ApS","countryCode":"DK","vatId":"DK31500060","endpointId":"5790000000012","endpointScheme":"0088"},"customer":{"name":"Havn Logistik A/S","countryCode":"DK","vatId":"DK31500044","endpointId":"5790000000029","endpointScheme":"0088"},"lines":[{"description":"Printing, September","quantity":1,"unitPrice":8000,"vatPercent":25}],"totalWithoutVat":8000,"totalVat":2000,"totalWithVat":10000,"payment":{"iban":"DK27 5301 0244 5638 21"}}}'
```

Run against production on 2026-09-24, shortened:

```json
{
  "review": {
    "checks": [
      { "id": "structure", "status": "pass", … },
      { "id": "arithmetic", "status": "pass", "detail": "Line totals and VAT match the amounts on the invoice.", … },
      { "id": "payment_details", "status": "pass", "detail": "DK27 5301 0244 5638 21 is a structurally valid Denmark IBAN. This does not say the account exists or who it belongs to.", … },
      { "id": "supplier_vat", "status": "skipped", "detail": "The VIES register was not queried: this run had no authorised workspace for it.", … },
      { "id": "customer_vat", "status": "skipped", … },
      { "id": "peppol", "status": "pass", … }
    ],
    "findings": [],
    "readyToSend": true,
    "hasUnknowns": true,
    …
  },
  "verified": false,
  "billing": { "charged": false, "reason": "Signed out: only the free local checks ran, and nothing was charged.", … }
}
```

How to read it:

- Without an account the two VAT checks are `skipped`: the VIES register was
  not asked. That is why `hasUnknowns` is true. Say so to the person; never
  report the VAT numbers as checked.
- Every entry in `findings` has a `severity` and a `fix`. A `blocker` means
  the invoice is wrong (for example, a total that does not add up): do not
  pay it, ask the supplier for a corrected invoice. An example is in
  [references/examples.md](references/examples.md).
- `payment_details` only says the IBAN is well formed. Whether it is the
  supplier's account is step 1, not this check.

## Step 3 - VAT numbers from the EU register: review_invoice (paid)

The same review, plus the supplier and customer VAT numbers checked against
the EU VIES register. It needs a token:

1. A person (not the agent) creates a Jithox connection at
   https://jithox.com/mcp/account#connection.
2. The agent exchanges the connection's id and secret for a token at
   /api/oauth/token:

```bash
curl -s https://jithox.com/api/oauth/token \
  -A 'pay-invoices-safely/1.0' \
  -H 'Accept: application/json' \
  -d grant_type=client_credentials \
  -d "client_id=$JITHOX_CLIENT_ID" \
  -d "client_secret=$JITHOX_CLIENT_SECRET"
```

   Put the access token from the answer in JITHOX_TOKEN. It expires; fetch a
   new one when a call says it is no longer valid.

3. Call the tool with the token (the invoice fields go straight into
   `arguments`):

```bash
curl -s https://jithox.com/api/mcp \
  -A 'pay-invoices-safely/1.0' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Authorization: Bearer $JITHOX_TOKEN" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"review_invoice","arguments":{"invoiceNumber":"2026-0917","issueDate":"2026-09-17","dueDate":"2026-10-17","currency":"DKK","buyerReference":"PO-4471","supplier":{"name":"Nordlys Tryk ApS","countryCode":"DK","vatId":"DK31500060","endpointId":"5790000000012","endpointScheme":"0088"},"customer":{"name":"Havn Logistik A/S","countryCode":"DK","vatId":"DK31500044","endpointId":"5790000000029","endpointScheme":"0088"},"lines":[{"description":"Printing, September","quantity":1,"unitPrice":8000,"vatPercent":25}],"totalWithoutVat":8000,"totalVat":2000,"totalWithVat":10000,"payment":{"iban":"DK27 5301 0244 5638 21"}}}}'
```

The price is not in this file, because prices change: read the `pricing`
field of `review_invoice` in https://jithox.com/mcp.json. Without a token the
tool answers `payment_required`, runs nothing and names `humanUrl` and
`tokenUrl`.

With a token, run against production on 2026-09-24, shortened:

```json
{
  "kind": "invoice_review",
  "data": {
    "checks": [
      …
      { "id": "supplier_vat", "status": "unknown", "source": "eu_vies", "detail": "The VIES register did not answer." },
      { "id": "customer_vat", "status": "fail", "source": "eu_vies", "detail": "VIES reports this number as not registered." },
      …
    ],
    "findings": [
      { "code": "supplier_vat_unverified", "severity": "warning", "what": "We could not reach a verdict on VAT number DK31500060. The VIES register did not answer.", "fix": "Review again later. Treat this as unchecked — it is not evidence that the number is good or bad." },
      { "code": "customer_vat_not_registered", "severity": "blocker", "what": "VIES does not know VAT number DK31500044.", "fix": "Check the number with the customer — a typo, a closed registration or a non-EU number would all look like this." }
    ],
    "readyToSend": false,
    "hasUnknowns": true,
    …
  }
}
```

`unknown` is not a pass: the register did not answer, so the number is
unchecked. A `fail` on the supplier's VAT number is a reason to hold the
payment and ask. The VAT numbers in these examples are made up, so the
register does not know them.

## Step 4 - decide, and say what was not checked

Jithox never pays and never signs a payment, and none of these calls asks for
a bank login or a signing key. You prepare; a person approves the payment.

Hold the payment and hand it to a person when any of these is true:

- step 1 gave a `verdict` other than `no_change`;
- step 2 or 3 has a finding with severity `blocker`;
- a VAT check you needed is `skipped`, `unknown` or `fail`.

Even when everything passes, a clean answer is not a guarantee. Put the
`doesNotProve` text of step 1 and the `detail` of every check that is not
`pass` into your note, word for word. A short note:

```text
Invoice 2026-0917 from Nordlys Tryk ApS, DKK 10000.00 to DK27 5301 0244 5638 21.
Bank account: verify_first (bank changed 0040 -> 5301). NOT paid.
  Call the supplier on the number in our own records; have them read the account back.
  Not proven: who owns the new account, that it exists or is open, or that the request came from the supplier.
Invoice: structure, totals, IBAN format and Peppol rules pass.
VAT: not checked (skipped, no account).
Needs: call-back + second approver before payment.
```
