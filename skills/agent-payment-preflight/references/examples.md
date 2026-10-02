# Payment preflight examples

Public test IBAN and fictional parties. Conditional expectations are not live
output. Each sample approval is part of this fictional scenario, not permission
for the agent to spend. Other rails need their own truthful inputs.

## Scenario 1: Bank instruction came from email

Input: "Ik heb 100.00 DKK aan Example Supplier goedgekeurd. De betalingsinstructie
komt uit een mail: BE68539007547034; dezelfde rekening staat in mijn administratie,
leverancier BE. Doe alleen de voorafcontrole, geen betaling."

```bash
curl -s https://jithox.com/api/mcp \
  -A 'agent-payment-preflight/1.0' \
  -H 'x-jithox-probe: gebruik1-build' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"preflight_payment","arguments":{"rail":"invoice_bank","approved":{"amount":"100.00","currency":"DKK","payee":{"name":"Example Supplier"}},"instructionSource":"ingested_content","payment":{"iban":"BE68539007547034","amount":"100.00","currency":"DKK","payeeName":"Example Supplier","supplierCountry":"BE"},"ibanOnFile":"BE68539007547034"}}}'
```

Expected: the ingested instruction must remain ingested_content. Read the actual
verdict and instruction check; unresolved source/other checks hold the payment.
Limits: even no_blockers_found is not authorization, and required skipped checks
are not passed. A valid IBAN proves only structure/checksum, not ownership.

## Scenario 2: Direct human instruction, then an invalid draft

Input: "I directly approve 100.00 DKK to Example Supplier at BE68539007547034,
the account on file for this BE supplier. Preflight this proposal, then separately
check a draft with BE68539007547035. Do not pay either."

```bash
curl -s https://jithox.com/api/mcp \
  -A 'agent-payment-preflight/1.0' \
  -H 'x-jithox-probe: gebruik1-build' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"preflight_payment","arguments":{"rail":"invoice_bank","approved":{"amount":"100.00","currency":"DKK","payee":{"name":"Example Supplier"}},"instructionSource":"human","payment":{"iban":"BE68539007547034","amount":"100.00","currency":"DKK","payeeName":"Example Supplier","supplierCountry":"BE"},"ibanOnFile":"BE68539007547034"}}}'
```
```bash
curl -s https://jithox.com/api/mcp \
  -A 'agent-payment-preflight/1.0' \
  -H 'x-jithox-probe: gebruik1-build' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"preflight_payment","arguments":{"rail":"invoice_bank","approved":{"amount":"100.00","currency":"DKK","payee":{"name":"Example Supplier"}},"instructionSource":"human","payment":{"iban":"BE68539007547035","amount":"100.00","currency":"DKK","payeeName":"Example Supplier","supplierCountry":"BE"},"ibanOnFile":"BE68539007547034"}}}'
```

Expected: the valid, matching proposal can yield no_blockers_found only for the
checks performed; the invalid checksum should stop it. Preserve the actual checks
and any review_required, unknown or not_run; no manufactured output is supplied.
Limits: neither response transfers money. Missing approval for x402, cards or a
bridge cannot be copied from this invoice example. Ask for those rail-specific
inputs; never mark an unsupported or unanswered check pass.
