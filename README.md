# Jithox MCP — free EU e-invoice, Peppol, VAT and IBAN checks for AI agents

Jithox runs a remote [MCP](https://modelcontextprotocol.io) server with read-only
checks for e-invoices and payments: Peppol BIS Billing 3.0 rule validation,
Peppol participant (receiver) lookup, EU VAT number format and VIES coverage,
IBAN structure, supplier bank-detail changes, and turning a CSV/XLSX file into
clean data.

It is for developers and AI agents that prepare an e-invoice or a payment and
want a check **before** something is sent, submitted to Peppol, or paid.

This repository holds **examples and a registry manifest only**. It contains no
server code. The server itself is hosted by Jithox.

## Connect

```
https://jithox.com/api/mcp
```

Transport: Streamable HTTP (`POST`, JSON-RPC 2.0). No auth needed for the free
tools below.

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
`%APPDATA%\Claude\claude_desktop_config.json`). Restart Claude Desktop. No
OAuth prompt appears — this endpoint needs no login for the free tools.

## What works without an account

The endpoint lists **19 tools**. **8 of them are free and need no token and no
account** (checked 2026-09-23, curl against production, each with a valid
payload — earlier counts of "7 of 18" were stale):

| Tool | What it does |
| --- | --- |
| `check_peppol_ready` | Checks an invoice against 21 published Peppol BIS Billing 3.0 rules and names each failing rule with a fix. Not the official validator. |
| `lookup_peppol_participant` | Asks the live Peppol registers whether a given customer (by enterprise/VAT number) can receive an e-invoice today, and which document types their access point accepts. |
| `verify_iban` | IBAN structure and check digits (ISO 13616 / ISO 7064). Never claims the account exists or who owns it. |
| `check_vat_list_format` | Up to 20 EU VAT numbers: empty, malformed, duplicate, or not covered by VIES. Local only — does **not** ask the VAT register. |
| `check_payment_change` | A supplier says their bank details changed: checks the new IBAN and says what to verify before updating the record. |
| `file_to_data_inspect` | Reads a CSV / XLSX / JSON file and proposes a column mapping. |
| `file_to_data_transform` | Applies exactly the mapping you send and returns rows plus a per-row error report. |
| `core_condition` | Compares two values and returns a true/false branch. |

The other 11 tools need a Jithox bearer token and cost credits per accepted
call, among them `format_peppol_invoice` (generate the UBL/Peppol XML, 5
credits), `kbo_company_search` and `check_vat_list` (live VIES lookup),
`review_invoice` (full invoice review, 8 credits) and `analyze_kbo_financials`.
Called without a token they return a `payment_required` error that names the
token URL — nothing runs and nothing is charged.

**Limits:** 30 requests per minute per IP on this endpoint; above that you get
HTTP `429` with `Retry-After`. Every answer carries a `doesNotProve` field or a
stated limit — read it before you act on a result.

## Three calls, all run against production on 2026-09-23

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

### 3. Clean a list of EU VAT numbers before invoicing

```bash
curl -s https://jithox.com/api/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"check_vat_list_format","arguments":{"rows":[{"reference":"acme","vatId":"BE0400378485"},{"vatId":"NL 8558.76.323.B01"},{"vatId":"BE0400378486"},{"vatId":"GB123456789"}]}}}'
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
        "detail": "Great Britain left the EU register (VIES) in 2021, so this number cannot be checked here." }
    ],
    "totals": { "rows": 4, "wellFormed": 2, "malformed": 1, "notCovered": 1, "duplicate": 0, … },
    …
  }
}
```

`well_formed` is not `registered`: this tool never asks the VAT register (that
is `check_vat_list`, a paid tool).

## Examples in code

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
- [`examples/csharp/Program.cs`](examples/csharp/Program.cs) — `HttpClient`:
  `initialize`, then `check_vat_list_format`. Runs with `dotnet run` in a
  console project, or `csc -r:System.Net.Http.dll Program.cs` on .NET Framework 4.x.
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
calls to be in the live `tools/list`, and fails on any price in the text.

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
