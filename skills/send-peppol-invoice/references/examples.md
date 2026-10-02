# Peppol preparation examples

Fictional invoice and public participant, not customer data. These are inputs and
conditional expectations, not a captured result or legal-compliance guarantee.

## Scenario 1: Prepare without sending

Input: "Bereid deze e-factuur Peppol voor: SAMPLE-001, 2026-10-02, DKK,
PO-SAMPLE, verkoper Example Supplier en koper Example Buyer allebei BE met
endpoint 0208:0403170701; één dienst van 1000, 21 procent btw, totalen
1000/210/1210. Controleer de ontvanger; verstuur niets."

```bash
curl -s https://jithox.com/api/mcp \
  -A 'send-peppol-invoice/1.0' \
  -H 'x-jithox-probe: gebruik1-build' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"check_peppol_ready","arguments":{"invoiceNumber":"SAMPLE-001","issueDate":"2026-10-02","currency":"DKK","buyerReference":"PO-SAMPLE","supplier":{"name":"Example Supplier","countryCode":"BE","endpointId":"0403170701","endpointScheme":"0208"},"customer":{"name":"Example Buyer","countryCode":"BE","endpointId":"0403170701","endpointScheme":"0208"},"lines":[{"description":"Example service","quantity":1,"unitPrice":1000,"vatPercent":21}],"totalWithoutVat":1000,"totalVat":210,"totalWithVat":1210}}}'
```
```bash
curl -s https://jithox.com/api/mcp \
  -A 'send-peppol-invoice/1.0' \
  -H 'x-jithox-probe: gebruik1-build' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"lookup_peppol_participant","arguments":{"identifier":"0403170701","scheme":"0208"}}}'
```

Expected: read the actual local-rule verdict and recipient response. A ready
subset is possible, but live registry availability/document support may vary.
Limits: registration is not document acceptance or delivery. No full official
validation and no legal opinion; nothing is sent by this package.

## Scenario 2: Invalid date and absent reference

Input: "Please check the same fictional invoice, but its date is 02/10/2026
and there is no buyer or order reference. Can I call this facture électronique
ready for Peppol? Do not send it."

```bash
curl -s https://jithox.com/api/mcp \
  -A 'send-peppol-invoice/1.0' \
  -H 'x-jithox-probe: gebruik1-build' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"check_peppol_ready","arguments":{"invoiceNumber":"SAMPLE-001","issueDate":"02/10/2026","currency":"DKK","supplier":{"name":"Example Supplier","countryCode":"BE","endpointId":"0403170701","endpointScheme":"0208"},"customer":{"name":"Example Buyer","countryCode":"BE","endpointId":"0403170701","endpointScheme":"0208"},"lines":[{"description":"Example service","quantity":1,"unitPrice":1000,"vatPercent":21}],"totalWithoutVat":1000,"totalVat":210,"totalWithVat":1210}}}'
```

Expected: failed date/reference rules should prevent readiness; use actual failed
findings and notChecked, not a manufactured success. Lookup alone cannot fix it.
Limits: fix those fields and recheck only with the user's data. Errors/timeouts
leave unknown or not_run; no response is never a pass. Nothing is submitted.
