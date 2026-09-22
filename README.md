# Jithox MCP — free business checks for AI agents

Jithox runs a remote [MCP](https://modelcontextprotocol.io) server with read-only
checks for invoices and payments: IBANs, EU VAT number format, Peppol e-invoice
rules, supplier bank-detail changes and turning a CSV/XLSX file into clean data.

It is for developers and AI agents that prepare invoices or payments and want a
check **before** something is sent or paid.

This repository holds **examples and a registry manifest only**. It contains no
server code. The server itself is hosted by Jithox.

## Connect

```
https://jithox.com/api/mcp
```

Transport: Streamable HTTP (`POST`, JSON-RPC 2.0).

```json
{
  "mcpServers": {
    "jithox": { "url": "https://jithox.com/api/mcp" }
  }
}
```

## What works without an account

The endpoint lists 18 tools. **Seven of them are free and need no token and no
account.** The `initialize` response currently says "Every tool call requires a
valid Jithox bearer token" — that sentence is out of date for these seven: they
answer without any `Authorization` header (checked 2026-09-22).

| Tool | What it does |
| --- | --- |
| `verify_iban` | IBAN structure and check digits (ISO 13616 / ISO 7064). Never claims the account exists or who owns it. |
| `check_vat_list_format` | Up to 20 EU VAT numbers: empty, malformed, duplicate, or not covered by VIES. Local only — does **not** ask the VAT register. |
| `check_peppol_ready` | Checks an invoice against 21 published Peppol BIS Billing 3.0 rules and names each failing rule with a fix. Not the official validator. |
| `check_payment_change` | A supplier says their bank details changed: checks the new IBAN and says what to verify before updating the record. |
| `file_to_data_inspect` | Reads a CSV / XLSX / JSON file and proposes a column mapping. |
| `file_to_data_transform` | Applies exactly the mapping you send and returns rows plus a per-row error report. |
| `core_condition` | Compares two values and returns a true/false branch. |

The other 11 tools (VIES lookups, invoice XML/PDF generation, web reading,
transcription, receipt parsing, …) need a Jithox token. Called without one they
return a `payment_required` error that names the token URL — nothing runs and
nothing is charged.

**Limits:** 30 requests per minute per IP on this endpoint; above that you get
HTTP `429` with `Retry-After`. Every answer carries a `doesNotProve` field or a
stated limit — read it before you act on a result.

## Three calls with curl

All three were run on 2026-09-22 without a token. Output is shown as returned;
`…` marks where it was shortened for this page.

### 1. Check an IBAN

```bash
curl -s https://jithox.com/api/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"verify_iban","arguments":{"iban":"BE68 5390 0754 7034"}}}'
```

The tool result (`result.content[0].text`), unwrapped:

```json
{
  "kind": "iban_verification",
  "data": {
    "status": "valid",
    "reason": null,
    "iban": "BE68 5390 0754 7034",
    "countryCode": "BE",
    "country": "Belgium",
    "bankIdentifier": "539",
    "detail": "A structurally valid Belgium IBAN. This says the number is well formed, not that the account exists or belongs to anyone.",
    "proves": "The number is a well-formed IBAN for its country and its check digits are arithmetically correct.",
    "doesNotProve": "That the account exists, that it is open, that it belongs to the party being paid, or that a payment to it will arrive. No free registry answers those, and this tool does not guess."
  }
}
```

### 2. Clean a list of EU VAT numbers

```bash
curl -s https://jithox.com/api/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"check_vat_list_format","arguments":{"rows":[{"reference":"acme","vatId":"BE0400378485"},{"vatId":"NL 8558.76.323.B01"},{"vatId":"BE0400378486"},{"vatId":"GB123456789"}]}}}'
```

```json
{
  "kind": "vat_list_check",
  "data": {
    "ok": true,
    "rows": [
      { "index": 0, "reference": "acme", "normalized": "BE0400378485", "local": "well_formed", "register": "not_run", … },
      { "index": 1, "normalized": "NL855876323B01", "local": "well_formed", "register": "not_run", … },
      { "index": 2, "normalized": "BE0400378486", "local": "malformed", "register": "not_run",
        "detail": "The last two digits of a Belgian number are a check on the first eight, and here they do not match — usually a typing error. The register was not asked." },
      { "index": 3, "normalized": "GB123456789", "local": "not_covered", "register": "not_run",
        "detail": "Great Britain left the EU register (VIES) in 2021, so this number cannot be checked here. That says nothing about the number; the UK tax office has its own checker." }
    ],
    "totals": { "rows": 4, "wellFormed": 2, "malformed": 1, "notCovered": 1, "duplicate": 0, … },
    …
  }
}
```

`well_formed` is not `registered`: this tool never asks the VAT register.

### 3. Will Peppol accept this invoice?

```bash
curl -s https://jithox.com/api/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"check_peppol_ready","arguments":{"invoiceNumber":"INV-1","issueDate":"22/09/2026","currency":"EUR","supplier":{"name":"Seller BV","countryCode":"BE","endpointId":"0400378485","endpointScheme":"0208"},"customer":{"name":"Buyer NV","countryCode":"BE"}}}}'
```

```json
{
  "kind": "peppol_ready_check",
  "data": {
    "verdict": "will_be_rejected",
    "failed": [
      { "rule": "PEPPOL-EN16931-F001", "ruleText": "A date MUST be formatted YYYY-MM-DD.", "detail": "The issue date reads \"22/09/2026\".", … },
      { "rule": "BR-16", "ruleText": "An Invoice shall have at least one Invoice line (BG-25).", … },
      { "rule": "PEPPOL-EN16931-R010", "ruleText": "Buyer electronic address MUST be provided", … },
      { "rule": "PEPPOL-EN16931-R003", "ruleText": "A buyer reference or purchase order reference MUST be provided.", … }
    ],
    "passed": [ … 14 rules … ],
    "notChecked": [ … 3 rules … ],
    "summary": "The Peppol network refuses this invoice: 4 mandatory rules are broken (PEPPOL-EN16931-F001, BR-16, PEPPOL-EN16931-R010, PEPPOL-EN16931-R003).",
    "rulesChecked": 21,
    …
  }
}
```

A clean result means none of these 21 rules fails — not that the network will
accept the document.

## Examples in code

- [`examples/python/free_tools.py`](examples/python/free_tools.py) — standard
  library only: `initialize`, `tools/list`, then `verify_iban`.
  `python free_tools.py`
- [`examples/csharp/Program.cs`](examples/csharp/Program.cs) — `HttpClient`:
  `initialize`, then `check_vat_list_format`. Runs with `dotnet run` in a
  console project, or `csc -r:System.Net.Http.dll Program.cs` on .NET Framework 4.x.

Both were run against the live endpoint on 2026-09-22 and returned the answers above.

## Machine-readable pointers

- https://jithox.com/llms.txt
- https://jithox.com/.well-known/mcp.json
- [`server.json`](server.json) in this repository, following the official MCP
  registry schema (`2025-12-11`).

## What this server does not do

Nothing on this endpoint sends an invoice, posts, pays or delivers anything.
Results are technical checks, not legal or tax advice.

## License

The examples and files in this repository are MIT-licensed (see [LICENSE](LICENSE)).
The Jithox service itself is not open source.
