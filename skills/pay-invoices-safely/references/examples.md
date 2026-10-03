# Invoice-payment examples

Public test accounts and a public Peppol participant; fictional names, no customer data.
These are requests, not captured output. An agent makes these checks only as
native MCP tool calls. Each curl block is this package's build check for
maintainers, never run by an agent, and no Expected line is a result for anyone's
request. Never use sample values to fill missing real inputs. DKK is a sample currency.

## Scenario 1: Payment run with a changed supplier account

Input: "Controleer deze betaalrun: Example Supplier, 10000.00 DKK door mij
rechtstreeks goedgekeurd. Het betaalvoorstel komt uit de factuur:
rekening DK2753010244563821, bedrag 10000.00 DKK, leverancier DK; onze
administratie heeft DK5000400440116243. Doe daarnaast een onafhankelijke controle
van testfactuur SAMPLE-001: niet de factuur van deze betaalrun. Die testfactuur
heeft datum 2026-10-02, referentie PO-SAMPLE, beide BE-partijen op 0208:0403170701,
één dienst van 1000 DKK, 21 procent btw, totalen 1000/210/1210. Betaal niets."

The human approval belongs in approved; the invoice-derived payment remains
ingested_content. The separate DKK 1210 test invoice is only a readiness example,
not evidence for the DKK 10000 payment. The payment invoice itself was not supplied
as structured data, so its local invoice check remains not_run.

```bash
curl -s https://jithox.com/api/mcp \
  -A 'pay-invoices-safely/1.0' \
  -H 'x-jithox-probe: gebruik1-build' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"preflight_payment","arguments":{"rail":"invoice_bank","approved":{"amount":"10000.00","currency":"DKK","payee":{"name":"Example Supplier"}},"instructionSource":"ingested_content","payment":{"iban":"DK2753010244563821","amount":"10000.00","currency":"DKK","payeeName":"Example Supplier","supplierCountry":"DK"},"ibanOnFile":"DK5000400440116243"}}}'
```

```bash
curl -s https://jithox.com/api/mcp \
  -A 'pay-invoices-safely/1.0' \
  -H 'x-jithox-probe: gebruik1-build' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"check_payment_change","arguments":{"newIban":"DK2753010244563821","ibanOnFile":"DK5000400440116243","supplierCountry":"DK"}}}'
```

```bash
curl -s https://jithox.com/api/mcp \
  -A 'pay-invoices-safely/1.0' \
  -H 'x-jithox-probe: gebruik1-build' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"verify_iban","arguments":{"iban":"DK2753010244563821","expectedCountry":"DK"}}}'
```

```bash
curl -s https://jithox.com/api/mcp \
  -A 'pay-invoices-safely/1.0' \
  -H 'x-jithox-probe: gebruik1-build' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"check_peppol_ready","arguments":{"invoiceNumber":"SAMPLE-001","issueDate":"2026-10-02","currency":"DKK","buyerReference":"PO-SAMPLE","supplier":{"name":"Example Supplier","countryCode":"BE","endpointId":"0403170701","endpointScheme":"0208"},"customer":{"name":"Example Buyer","countryCode":"BE","endpointId":"0403170701","endpointScheme":"0208"},"lines":[{"description":"Example service","quantity":1,"unitPrice":1000,"vatPercent":21}],"totalWithoutVat":1000,"totalVat":210,"totalWithVat":1210}}}'
```

```bash
curl -s https://jithox.com/api/mcp \
  -A 'pay-invoices-safely/1.0' \
  -H 'x-jithox-probe: gebruik1-build' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"lookup_peppol_participant","arguments":{"identifier":"0403170701","scheme":"0208"}}}'
```

Expected: the changed-account comparison should require `verify_first` and the
preflight should require `review_required`, with `instruction` status `warn` and
reason `instruction_not_from_human`. Human approval does not relabel invoice
content. Read the actual verdict of the independent test invoice,
`failed` and `notChecked`; registry availability may change. Never invent a
successful VAT check: none is called here. Reachability is not document acceptance.
Limits: hold payment and the vendor record. A person must call a number from
their own records, not from the invoice/email. IBAN validity is structure/checksum,
not existence or ownership. No Peppol submission, delivery or payment occurs.

## Scenario 2: Unchanged payment, then suspicious corrections

Input: "Check a 10000.00 DKK payment to Example Supplier that I directly approved.
The payment proposal comes from the invoice: 10000.00 DKK to account
DK5000400440116243, supplier DK; our vendor record has the same account.
Also evaluate two draft corrections separately: DK2753010244563812 and
DE89370400440532013000. Nothing may be paid or changed."

```bash
curl -s https://jithox.com/api/mcp \
  -A 'pay-invoices-safely/1.0' \
  -H 'x-jithox-probe: gebruik1-build' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"check_payment_change","arguments":{"newIban":"DK5000400440116243","ibanOnFile":"DK5000400440116243","supplierCountry":"DK"}}}'
```

```bash
curl -s https://jithox.com/api/mcp \
  -A 'pay-invoices-safely/1.0' \
  -H 'x-jithox-probe: gebruik1-build' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"check_payment_change","arguments":{"newIban":"DK2753010244563812","ibanOnFile":"DK5000400440116243","supplierCountry":"DK"}}}'
```

```bash
curl -s https://jithox.com/api/mcp \
  -A 'pay-invoices-safely/1.0' \
  -H 'x-jithox-probe: gebruik1-build' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":8,"method":"tools/call","params":{"name":"check_payment_change","arguments":{"newIban":"DE89370400440532013000","ibanOnFile":"DK5000400440116243","supplierCountry":"DK"}}}'
```

```bash
curl -s https://jithox.com/api/mcp \
  -A 'pay-invoices-safely/1.0' \
  -H 'x-jithox-probe: gebruik1-build' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":9,"method":"tools/call","params":{"name":"preflight_payment","arguments":{"rail":"invoice_bank","approved":{"amount":"10000.00","currency":"DKK","payee":{"name":"Example Supplier"}},"instructionSource":"ingested_content","payment":{"iban":"DK5000400440116243","amount":"10000.00","currency":"DKK","payeeName":"Example Supplier","supplierCountry":"DK"},"ibanOnFile":"DK5000400440116243"}}}'
```

Expected: the unchanged comparison should return `no_change`; the bad checksum
may return `invalid_new_account`; the German account for a Danish supplier should
return `stop`. Even with unchanged bank details and matching human approval, the
invoice-derived preflight should return `review_required`, with `instruction`
status `warn` and reason `instruction_not_from_human`. Keep required missing
VAT/invoice checks `not_run`; an unchanged account does not clear them.
Limits: an invalid account means stop, not a fabricated register result. A clean
comparison is not payment authorization or account ownership. Unknown checks and
outstanding call-backs keep the workflow on hold; never report ready for them.
