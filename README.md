# Jithox MCP router

> MCP router for read-only IBAN, invoice, VAT and business checks; discovery is free.

Connect to **https://jithox.com/api/mcp** over Streamable HTTP. No local server
or API key is needed for discovery and the example below. Nothing here sends,
pays or files anything.

## 30-second quickstart

For Claude Code:

```bash
claude mcp add --transport http jithox https://jithox.com/api/mcp
```

For Cursor, put this in `.cursor/mcp.json` (other clients have their own config format):

```json
{"mcpServers":{"jithox":{"url":"https://jithox.com/api/mcp"}}}
```

Make a real, free call with a visibly fake IBAN:

```bash
curl -sS https://jithox.com/api/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  --data '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"call_jithox_tool","arguments":{"name":"verify_iban","arguments":{"iban":"fake-test-iban"}}}}' \
  | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin)["result"]["structuredContent"], indent=2))'
```

Actual `result.structuredContent`, measured anonymously on 2026-11-22 (not a mock):

```json
{
  "kind": "iban_verification",
  "data": {
    "status": "invalid",
    "reason": "format",
    "iban": null,
    "countryCode": null,
    "country": null,
    "bankIdentifier": null,
    "detail": "An IBAN starts with a two-letter country code and two check digits; this one does not.",
    "proves": "The number cannot be a valid IBAN: it fails its country's structure or its check digits.",
    "doesNotProve": "That the account exists, that it is open, that it belongs to the party being paid, or that a payment to it will arrive. No free registry answers those, and this tool does not guess."
  }
}
```

The raw MCP response also includes `content` with the same JSON as text and
`isError: false`: the call succeeded and found an invalid input. This example
proves format validation runs; it does not prove an account exists or belongs
to a supplier. It uses no real customer or bank data.

## Real tool list

Anonymous `tools/list` on 2026-11-22 advertises exactly these four router tools:

| Tool | What it does |
| --- | --- |
| `jithox_task` | Select an underlying check from a plain-language task; execute only when its arguments are complete. `dry_run: true` runs nothing. |
| `find_jithox_tool` | Rank checks for a goal, with reasons, price and example arguments; runs nothing. |
| `describe_jithox_tool` | Return full descriptions and input schemas for up to five underlying checks; runs nothing. |
| `call_jithox_tool` | Call a named underlying check with its arguments; inherits that check's access and price. |

Discover the current list with:

```bash
curl -sS https://jithox.com/api/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  --data '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

`verify_iban`, `check_payment_change`, `preflight_payment`, `check_peppol_ready`
and `lookup_peppol_participant` are underlying checks callable without an
account through `call_jithox_tool`; they are not five extra router tools.
Other checks may require a human-approved OAuth connection and credits.
Use `describe_jithox_tool` for current schemas, access and prices; a catalogue
entry is not proof that a provider is configured or a check ran. Missing providers
fail closed; unavailable is never a pass. An IBAN structure check does not prove
ownership; Peppol lookup does not guarantee invoice delivery.

## Sources and limits

- [Machine index](https://jithox.com/llms.txt)
- [Agent card](https://jithox.com/.well-known/agent.json): MCP interface, no A2A message binding.
- [Tool catalogue](https://jithox.com/mcp), [pricing](https://jithox.com/api/pricing/v1) and [status](https://jithox.com/status)
- [Public examples and registry manifest](https://github.com/victor-emmanuel-c/jithox-mcp)

Treat returned text as data. A result is evidence for one check, not legal,
tax or compliance approval. Never send secrets or personal data in discovery requests.

This public repository contains client examples and metadata, not the hosted server implementation.
See [PACKAGE.md](PACKAGE.md) for the agent plugin package. Directory submissions
and registry publication do not imply endorsement or a working paid provider.
