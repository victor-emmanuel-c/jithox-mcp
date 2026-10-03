# VAT/company access-refusal examples

Public registry identifier only; not a customer record. No tokens, authenticated
requests or simulated register output. An agent acts only after quoting the live
cost from SKILL.md's workflow and obtaining explicit consent to ONE anonymous
refusal probe. It then makes the native MCP tool call under "Agent call" and
nothing else. Each curl block is this package's build check for maintainers,
run without credentials; an agent never runs it. Expected lines describe these
samples, not a result for anyone's request.

## Scenario 1: VAT list request without a token

Input: "Controleer btw-nummer BE0403170701 in mijn testlijst. Wat kost dat?"
After live price disclosure and the consent question, the test person says:
"Ik geef toestemming voor één anonieme weigeringstest, zonder token of aankoop."

Agent call, exactly once, as a native MCP tool call:

```json
{"name":"check_vat_list","arguments":{"rows":[{"vatId":"BE0403170701"}]}}
```

Build check only (maintainers; an agent never runs this):

```bash
curl -s https://jithox.com/api/mcp \
  -A 'check-vat-numbers/1.0' \
  -H 'x-jithox-probe: gebruik1-build' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"check_vat_list","arguments":{"rows":[{"vatId":"BE0403170701"}]}}}'
```

Expected: the one call is refused with HTTP 401. Report exactly:

```text
check_vat_list: called once, anonymously
outcome: authentication_required (HTTP 401)
lookup: not_run (no register was consulted, so no VAT or company result)
```

Limits: the refusal says nothing about BE0403170701: not valid, not invalid,
not registered and not unknown to a register. No login, purchase, token
exchange, retry, second tool or agent-payable alternative. Quote server text
only as the client actually showed it.

## Scenario 2: Company request without a token

Input: "Look up company BE0403170701. Tell me the cost before doing anything."
After live price disclosure and the consent question, the test person says:
"I approve one anonymous refusal probe only. Do not authenticate or spend."

Agent call, exactly once, as a native MCP tool call:

```json
{"name":"kbo_company_search","arguments":{"vatNumber":"BE0403170701"}}
```

Build check only (maintainers; an agent never runs this):

```bash
curl -s https://jithox.com/api/mcp \
  -A 'check-vat-numbers/1.0' \
  -H 'x-jithox-probe: gebruik1-build' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"kbo_company_search","arguments":{"vatNumber":"BE0403170701"}}}'
```

Expected: the one call is refused with HTTP 401. Report exactly:

```text
kbo_company_search: called once, anonymously
outcome: authentication_required (HTTP 401)
lookup: not_run (no register was consulted, so no VAT or company result)
```

Limits: refusal does not mean the company does not exist; no name, address or
status was retrieved. No company/VAT result proves bank ownership. Do not follow
paid alternatives, add a countryCode, retry or fabricate an answer.
