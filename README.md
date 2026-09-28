# Jithox MCP — check a payment before your AI agent makes it

Jithox runs a remote [MCP](https://modelcontextprotocol.io) server. Its front
door is `preflight_payment`: one free call, before an agent pays an invoice,
that answers `stop`, `review_required` or `no_blockers_found` with signed
evidence. Next to it are read-only checks for e-invoices and payments: IBAN
structure, supplier bank-detail changes, Peppol BIS Billing 3.0 rule
validation, Peppol participant (receiver) lookup, and VIES lookup.

It is for developers and AI agents that prepare an e-invoice or a payment and
want a check **before** something is sent, submitted to Peppol, or paid.

This repository holds **examples and a registry manifest only**. It contains no
server code. The server itself is hosted by Jithox.

## Before your agent pays: `preflight_payment`

Call `preflight_payment` once, before your agent pays an invoice. It compares
what the person approved, as your agent reports it (payee, amount, currency,
account), with what is about to be paid; checks the IBAN and a changed
supplier bank account against the one on file; and answers `stop`,
`review_required` or `no_blockers_found`, with every check, what it does not
prove, and a signed evidence token. No account, no token. It never pays and
never calls an account safe: a check that did not run is listed as `not_run`,
never as a pass.

Today only the `invoice_bank` rail has checks. For `x402`, `card_or_giftcard`
and `crypto_bridge` payments no rail checks run, and the best answer is
`review_required` with reason `rail_not_covered` (measured 2026-09-25).

The person approved paying invoice 2026-105 to Acme BV; the invoice now asks
for a different account than the one on file:

```bash
curl -s https://jithox.com/api/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"preflight_payment","arguments":{"rail":"invoice_bank","approved":{"amount":"1210.00","currency":"EUR","payee":{"name":"Acme BV"},"purpose":"Invoice 2026-105"},"instructionSource":"human","payment":{"iban":"BE71 0961 2345 6769","amount":"1210.00","currency":"EUR","payeeName":"Acme BV","supplierCountry":"BE"},"ibanOnFile":"BE68539007547034"}}}'
```

The tool result (`result.content[0].text`), unwrapped; run against production
on 2026-09-25, `…` marks where it was shortened for this page:

```json
{
  "kind": "payment_preflight",
  "data": {
    "schemaVersion": "jx.payment-preflight/v1",
    "verdict": "review_required",
    "reasons": [{ "code": "payment_change_verify_first", "check": "payment_change" }],
    "humanStep": "Call the supplier back on a phone number from your own records (never one from this invoice or its e-mail) and have them read the account number to you.",
    "checks": [
      { "id": "approval", "status": "pass", … },
      { "id": "iban", "status": "pass", "value": "BE71 **** **** 6769: structure and check digits are right", … },
      { "id": "payment_change", "status": "warn", "value": "verify_first", "findings": ["bank_changed"], … },
      { "id": "vat_register", "status": "not_run", "reason": "needs_connection", … },
      …
    ],
    "billing": { "charged": false, "units": [] },
    …
  },
  "evidence": {
    "format": "compact-jws",
    "jws": "eyJhbG…",
    "jwks": "https://jithox.com/.well-known/jwks.json",
    "verify": "https://jithox.com/api/v1/evidence/verify",
    …
  }
}
```

Anyone can check that a verdict was not changed: `POST` the `jws` (optionally
with the `input` and its `inputSalt`) to
`https://jithox.com/api/v1/evidence/verify`. The untouched token answered
`"status": "valid"`; the same token with its verdict changed answered
`"invalid"` with reason `signature_mismatch` (tested 2026-09-25).

## Connect

```
https://jithox.com/api/mcp
```

Transport: Streamable HTTP (`POST`, JSON-RPC 2.0).
No account or token is needed for `tools/list`.

```json
{
  "mcpServers": {
    "jithox": { "url": "https://jithox.com/api/mcp" }
  }
}
```

### Claude Desktop

Open Settings → Developer → Edit Config, and add the block above to
`claude_desktop_config.json` (macOS:
`~/Library/Application Support/Claude/claude_desktop_config.json`; Windows:
`%APPDATA%\Claude\claude_desktop_config.json`). Restart Claude Desktop.

## Current tools

Use `tools/list` on this endpoint as the source for current availability:
tool names, descriptions and input schemas. Read that live response rather
than relying on a fixed tool count or catalog in this README.

**Limits:** 30 requests per minute per IP on this endpoint; above that you get
HTTP `429` with `Retry-After`.

## Peppol calls, run against production on 2026-09-23

Output is shown as returned; `…` marks where it was shortened for this page.

### 1. Will Peppol accept this invoice?

```bash
curl -s https://jithox.com/api/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"check_peppol_ready","arguments":{"invoiceNumber":"INV-2026-0001","issueDate":"2026-09-23","currency":"EUR","buyerReference":"PO-4471","totalWithoutVat":1000,"totalVat":210,"totalWithVat":1210,"lines":[{"description":"Consulting hours","quantity":10,"unitPrice":100,"vatPercent":21}],"supplier":{"name":"Seller BV","countryCode":"BE","endpointId":"0403170701","endpointScheme":"0208"},"customer":{"name":"Buyer NV","countryCode":"BE","endpointId":"0400378485","endpointScheme":"0208"}}}}'
```

The tool result (`result.content[0].text`), unwrapped:

```json
{
  "kind": "peppol_ready_check",
  "data": {
    "verdict": "ready",
    "failed": [],
    "passed": [ … 21 rules, e.g. BR-02, PEPPOL-EN16931-R010, PEPPOL-EN16931-R003 … ],
    "notChecked": [],
    "summary": "Nothing is wrong among the 21 rules this check covers.",
    "rulesChecked": 21,
    "doesNotProve": "This checks 21 of the published Peppol BIS Billing 3.0 rules … a clean result here means nothing among these rules is wrong, not that the network will accept the document."
  }
}
```

Change `issueDate` to `"23/09/2026"` or drop `buyerReference` and the same
call returns `"verdict": "will_be_rejected"` with the specific rule that
failed (e.g. `PEPPOL-EN16931-F001`, `PEPPOL-EN16931-R003`) — checked
2026-09-22.

### 2. Can this customer actually receive it over Peppol?

```bash
curl -s https://jithox.com/api/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"lookup_peppol_participant","arguments":{"identifier":"0403170701"}}}'
```

```json
{
  "kind": "peppol_participant_lookup",
  "data": {
    "participantId": "0208:0403170701",
    "reachable": "yes",
    "documentTypes": [
      { "profile": "Peppol BIS Billing 3.0", "document": "Invoice", "raw": "…" }
      …
    ]
  }
}
```

This asks the live Peppol directory about a THIRD PARTY. It is never a
promise the invoice will arrive, be accepted or be paid — every answer says
so.

## Examples in code

- [`examples/python/preflight_payment.py`](examples/python/preflight_payment.py) —
  standard library only: `initialize`, then `preflight_payment` on a payment
  whose supplier bank account changed, then `POST /api/v1/evidence/verify` on
  the signed answer. Run with `python examples/python/preflight_payment.py`.
  Real output against production, 2026-09-25:
  ```
  server: jithox-engine
  verdict: review_required
  reasons: ['payment_change_verify_first']
  checks: {'approval': 'pass', 'mandate': 'not_run', 'instruction': 'pass', 'iban': 'pass', 'supplier_country': 'pass', 'payment_change': 'warn', 'invoice_local': 'not_run', 'hidden_text': 'not_run', 'peppol_participant': 'not_run', 'supplier_memory': 'not_run', 'vat_register': 'not_run', 'sanctions': 'not_run'}
  humanStep: Call the supplier back on a phone number from your own records (never one from this invoice or its e-mail) and have them read the account number to you.
  charged: False
  evidence: valid inputMatch: True
  ```
- [`examples/python/peppol_ready.py`](examples/python/peppol_ready.py) —
  standard library only: `initialize`, then `check_peppol_ready` on a
  compliant invoice, then `lookup_peppol_participant` on the buyer. Run with
  `python examples/python/peppol_ready.py`. Real output against production,
  2026-09-23:
  ```
  server: jithox-engine
  verdict: ready - Nothing is wrong among the 21 rules this check covers.
  reachable: yes participant: 0208:0403170701
  ```
- [`examples/python/free_tools.py`](examples/python/free_tools.py) — standard
  library only: `initialize`, `tools/list`, then `verify_iban`.
- [`examples/csharp/Program.cs`](examples/csharp/Program.cs) — .NET Framework 4.x,
  no packages: `initialize`, then the free `check_payment_change` with fictitious
  Belgian accounts. Prints the server, verdict, reason, human steps and
  `doesNotProve` from the response (`charged` only when supplied). HTTP timeout:
  15 seconds; HTTP, JSON-RPC, tool errors and missing/invalid result fields exit
  nonzero. From `examples/csharp`, compile with
  `csc /nologo /r:System.Net.Http.dll /r:System.Runtime.Serialization.dll Program.cs`,
  run offline checks with `Program.exe --self-test`, then the live example with
  `Program.exe`. Exit 0 means a valid response, not permission to pay.
- [`examples/dogfood/`](examples/dogfood/DOGFOOD_VOORBEELD_2026-09.md) — our own
  dogfood example (in Dutch): the paid `check_vat_list` on the VAT number of an invoice we received.

## Agent Skill: pay-invoices-safely

[`skills/pay-invoices-safely/SKILL.md`](skills/pay-invoices-safely/SKILL.md)
is an [Agent Skill](https://agentskills.io/specification) for an agent that
is about to pay a supplier invoice or change a supplier's bank account. It
teaches the agent to call `check_payment_change` on every new IBAN and to hold
the payment for a call-back by a person, to check the invoice with the free
`POST /api/invoice/review`, and to check VAT numbers against the EU VIES
register with the paid `review_invoice`. Copy the folder into your agent's
skills directory.

Every example in the skill runs against production. To check that it still
does (Node 18+, no dependencies):

```
node scripts/check-skill.mjs
```

It checks the spec rules, runs each curl example, requires every tool it
calls to be in the live `tools/list`, and fails on a euro sign, EUR, USD, a
`$` amount or "<n> credits" in the text.

## Machine-readable pointers

- https://jithox.com/llms.txt
- https://jithox.com/.well-known/mcp.json
- [`server.json`](server.json) in this repository, following the official MCP
  registry schema (`2025-12-11`). The server is also published in the
  official MCP registry as `com.jithox/jithox`
  (`registry.modelcontextprotocol.io/v0/servers?search=com.jithox/jithox`).

## What this server does not do

Nothing on this endpoint sends an invoice, submits it to Peppol, posts, pays
or delivers anything. Results are technical checks, not legal or tax advice.

## License

The examples and files in this repository are MIT-licensed (see [LICENSE](LICENSE)).
The Jithox service itself is not open source.
