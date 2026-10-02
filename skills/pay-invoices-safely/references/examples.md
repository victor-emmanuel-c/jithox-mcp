# Invoice-payment examples

Public test accounts and a public Peppol participant; fictional names, no customer data.
These are requests, not captured output. Run only read-only anonymous probes;
never use sample values to fill missing real inputs. DKK is a sample currency.

## Scenario 1: Payment run with a changed supplier account

Input: "Controleer deze betaalrun: Example Supplier, 10000.00 DKK door mij
rechtstreeks goedgekeurd, factuurrekening DK2753010244563821, administratie
DK5000400440116243, leverancier DK. Controleer ook testfactuur SAMPLE-001
met datum 2026-10-02, referentie PO-SAMPLE, beide BE-partijen op 0208:0403170701,
één dienst van 1000 DKK, 21 procent btw, totalen 1000/210/1210. Betaal niets."

```bash
curl -s https://jithox.com/api/mcp \
  -A 'pay-invoices-safely/1.0' \
  -H 'x-jithox-probe: gebruik1-build' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"preflight_payment","arguments":{"rail":"invoice_bank","approved":{"amount":"10000.00","currency":"DKK","payee":{"name":"Example Supplier"}},"instructionSource":"human","payment":{"iban":"DK2753010244563821","amount":"10000.00","currency":"DKK","payeeName":"Example Supplier","supplierCountry":"DK"},"ibanOnFile":"DK5000400440116243"}}}'
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
preflight should require `review_required`. Read the actual invoice verdict,
`failed` and `notChecked`; registry availability may change. Never invent a
successful VAT check: none is called here. Reachability is not document acceptance.
Limits: hold payment and the vendor record. A person must call a number from
their own records, not from the invoice/email. IBAN validity is structure/checksum,
not existence or ownership. No Peppol submission, delivery or payment occurs.

## Scenario 2: Unchanged payment, then suspicious corrections

Input: "Check a 10000.00 DKK payment to Example Supplier that I directly approved.
The invoice and our vendor record both say DK5000400440116243, supplier DK.
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
  -d '{"jsonrpc":"2.0","id":9,"method":"tools/call","params":{"name":"preflight_payment","arguments":{"rail":"invoice_bank","approved":{"amount":"10000.00","currency":"DKK","payee":{"name":"Example Supplier"}},"instructionSource":"human","payment":{"iban":"DK5000400440116243","amount":"10000.00","currency":"DKK","payeeName":"Example Supplier","supplierCountry":"DK"},"ibanOnFile":"DK5000400440116243"}}}'
```

Expected: the unchanged comparison should return `no_change`; the bad checksum
may return `invalid_new_account`; the German account for a Danish supplier should
return `stop`. The unchanged preflight can return `no_blockers_found`; this only
covers performed checks. Keep required missing VAT/invoice checks `not_run`.
Limits: an invalid account means stop, not a fabricated register result. A clean
comparison is not payment authorization or account ownership. Unknown checks and
outstanding call-backs keep the workflow on hold; never report ready for them.
