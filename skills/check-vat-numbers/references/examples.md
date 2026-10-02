# VAT/company access-refusal examples

Public registry identifier only; not a customer record. No tokens, authenticated
requests or simulated register output. Run only after showing the live costs from
SKILL.md's workflow and obtaining explicit consent to ONE anonymous refusal probe.
These examples never buy access. The build checker runs them without credentials.

## Scenario 1: VAT list request without a token

Input: "Controleer btw-nummer BE0403170701 in mijn testlijst. Wat kost dat?"
After live price disclosure and the consent question, the test person says:
"Ik geef toestemming voor één anonieme weigeringstest, zonder token of aankoop."

```bash
curl -s https://jithox.com/api/mcp \
  -A 'check-vat-numbers/1.0' \
  -H 'x-jithox-probe: gebruik1-build' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"check_vat_list","arguments":{"rows":[{"vatId":"BE0403170701"}]}}}'
```

Expected: a valid anonymous request should return HTTP 401 with payment_required
and the current connection step. Mark the VAT check not_run, not valid or invalid.
Limits: no register answer is supplied here. If the response differs, report it
honestly and stop; no automatic login, purchase, token exchange or repeated call.

## Scenario 2: Company request without a token

Input: "Look up company BE0403170701. Tell me the cost before doing anything."
After live price disclosure and the consent question, the test person says:
"I approve one anonymous refusal probe only. Do not authenticate or spend."

```bash
curl -s https://jithox.com/api/mcp \
  -A 'check-vat-numbers/1.0' \
  -H 'x-jithox-probe: gebruik1-build' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"kbo_company_search","arguments":{"vatNumber":"BE0403170701"}}}'
```

Expected: HTTP 401/payment_required with the live connection instructions, not
company details. Report the lookup not_run. The server's response, not this file,
is the source of current cost/auth text.
Limits: refusal does not mean the company does not exist. No company/VAT result
proves bank ownership. Do not follow paid alternatives or fabricate an answer.
