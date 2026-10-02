# Jithox MCP — check a payment before your AI agent makes it

Jithox runs a remote [MCP](https://modelcontextprotocol.io) server. Its front
door is `preflight_payment`: one free call, before an agent pays an invoice,
that answers `stop`, `review_required` or `no_blockers_found` with signed
evidence. Next to it are read-only checks for e-invoices and payments: IBAN
structure, supplier bank-detail changes, Peppol BIS Billing 3.0 rule
validation, Peppol participant (receiver) lookup, and VIES lookup.

It is for developers and AI agents that prepare an e-invoice or a payment and
want a check **before** something is sent, submitted to Peppol, or paid.

This repository holds examples, a registry manifest and one agent plugin
package. It contains no server code. The server itself is hosted by Jithox.

## Agent package

See [PACKAGE.md](PACKAGE.md) for the portable Agent Plugins package and its
Claude Code, Cursor, Gemini and Grok configuration. Validation scope and
primary sources are in [docs/PLUGIN_VALIDATION.md](docs/PLUGIN_VALIDATION.md).
No public directory listing or recommendation is implied.

After the reviewed package reaches the public default branch, Claude Code
can discover this repository marketplace with:

```text
/plugin marketplace add victor-emmanuel-c/jithox-mcp
/plugin install jithox@jithox
```

For Agent-Skills-compatible clients:

```bash
npx skills add victor-emmanuel-c/jithox-mcp
```

The v1.0.0 discovery-only check `DISABLE_TELEMETRY=1 npx skills add . --list`
listed one skill on 2026-10-02. The GEBRUIK1 candidate contains five skills;
that file inventory is not an installation or completed agent task. The remote command installs from the published repo;
review its permissions and selected version before accepting.

Build the upload ZIP deterministically from the repository root:

```bash
python scripts/plugin_package.py ../directories/jithox-agent-plugin-1.0.0.zip
```

The builder includes only its explicit runtime-file allowlist. ZIP uploads,
publisher verification and directory applications remain owner actions.

## Wat je je agent kunt vragen

| Natuurlijke vraag | Skill / commandnaam | Gratis/betaald | Eerlijke uitkomst |
|---|---|---|---|
| "Controleer deze factuur en betaalrun voordat ik betaal; meld wat niet gecontroleerd is." | `pay-invoices-safely` | Basischecks gratis; VAT/volledige review betaald na prijs en toestemming | Bevindingen en openstaande controles; geen betaling of betaaltoestemming. |
| "Het leveranciers-IBAN is gewijzigd; vergelijk het met onze administratie." | `verify-bank-detail-change` | Gratis | stop, verify_first of no_change; terugbellen via eigen administratie, geen recordwijziging. |
| "Bereid deze e-factuur Peppol voor en controleer de ontvanger." | `send-peppol-invoice` | Gratis | Regelbevindingen en documentondersteuning; geen verzending, acceptatie- of leveringsgarantie. |
| "Controleer dit betaalvoorstel voordat mijn agent geld uitgeeft." | `agent-payment-preflight` | Gratis | Echte preflight en beperkingen; onbekend is geen pass, er wordt niets betaald. |
| "Controleer deze btw-lijst of zoek dit bedrijf op; wat kost het?" | `check-vat-numbers` | Betaald; actuele kosten eerst uit live tools/list | Toestemming vóór de call; zonder toegang not_run en de live verbindingsstap, geen verzonnen registerantwoord. |

Gebruik gewone vragen voor skillselectie; activatie verschilt per client en is
nog geen bewezen taak. Expliciet: Claude `/jithox:<commandnaam>` (pluginnamespace),
Gemini `/<commandnaam>` (bij naamconflict kan de extensionnamespace verschijnen).
De bestanden staan in `commands/*.md` en `commands/*.toml`; alle vijf skills
hebben precies twee scenario's in hun eigen `references/examples.md`.
Zie [GEBRUIK1-validatie](docs/PLUGIN_VALIDATION.md) en het
[reproduceerbare evalpakket](eval/gebruik1/README.md). Eigen probes zijn geen
extern gebruik. Deze kandidaat is niet gepubliceerd of als beter geëvalueerd.

## Before your agent pays: `preflight_payment`

Call `preflight_payment` once, before your agent pays an invoice. It compares
what the person approved, as your agent reports it (payee, amount, currency,
account), with what is about to be paid; checks the IBAN and a changed
supplier bank account against the one on file; and answers `stop`,
`review_required` or `no_blockers_found`, with every check, what it does not
prove, and a signed evidence token. No account, no token. It never pays and
never calls an account safe: a check that did not run is listed as `not_run`,
never as a pass.

The 2026-09-25 measurement covered only `invoice_bank`; the other rails then
returned `review_required` with `rail_not_covered`. This is historical evidence,
not current coverage: read the live schema and every returned check for the
actual `invoice_bank`, `x402`, `card_or_giftcard` or `crypto_bridge` proposal.

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
the payment for a call-back by a person, to compare approval and proposed
payment with `preflight_payment`, and to check the invoice with
`check_peppol_ready`. Required VAT/company checks use the existing tools only
with an authorized connection; missing access is reported as `not_run`.
A required `unknown` or `not_run` check prevents a `ready` report.

It is written for three triggers: every supplier bank change, every invoice
IBAN that differs from the vendor record, and every payment run.

### Install from a clean folder

Set `SKILLS_DIR` to the skills directory that the documentation of your own
Agent-Skills-compatible client names. This repository does not know that path
for any client; do not guess it. Then run this in a POSIX shell (Git Bash on
Windows works), with git and Node 18+ installed. It pins the public repository
at commit `9193a770320aa144e66e8630c830be33858f21ad`, the `main` head
measured on 2026-09-28; use a newer commit only after you have reviewed it.

```
SKILLS_DIR=                     # absolute path from your client's documentation
: "${SKILLS_DIR:?set SKILLS_DIR before copying}" &&
SRC=$(mktemp -d) &&
git -C "$SRC" init -q &&
git -C "$SRC" fetch -q --depth 1 https://github.com/victor-emmanuel-c/jithox-mcp.git 9193a770320aa144e66e8630c830be33858f21ad &&
git -C "$SRC" checkout -q FETCH_HEAD &&
mkdir -p "$SKILLS_DIR" &&
cp -R "$SRC/skills/pay-invoices-safely" "$SKILLS_DIR/" &&
(cd "$SRC" && node scripts/check-skill.mjs skills/pay-invoices-safely)
```

If `SKILLS_DIR` is empty the flow stops with a non-zero status before anything
is fetched or copied. Otherwise it copies exactly `skills/pay-invoices-safely`
(`SKILL.md` and `references/examples.md`) to `$SKILLS_DIR/pay-invoices-safely`,
overwriting files of the same name there.

The last command checks the source copy, not your installed one: it verifies
the spec rules, runs each curl example against production (free, read-only
HTTP calls), requires every tool it calls to be in the live `tools/list`, and
rejects price-like text. The current checker makes one narrow exception for the
two exact VAT-skill cost lines when they also match live tools/list; it does not
allow arbitrary prices or money claims elsewhere. Commands mirror the skill
body and are pinned separately.

A clone, a copy and our own checker show that the files can be fetched and
that the examples still run. They do not show that any agent loaded the skill,
completed a task with it, or used it a second time.

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

The examples and package code/documentation are MIT-licensed (see [LICENSE](LICENSE)).
Official schema snapshots retain their Apache-2.0 license in scripts/schemas/.
Brand-asset provenance and rights are in assets/ORIGIN.md.
The Jithox service itself is not open source.
