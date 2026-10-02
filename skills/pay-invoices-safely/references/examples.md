# Reproduce the checks

These are sample inputs only, not customer invoices or payment instructions.
The account numbers are public examples; the names are fictional. The Belgian
participant is a public registry example, not a claim that it is a customer.
Never use these values in a real payment. Run each call and read its actual
response: this file supplies no manufactured output or expected pass.

## Compare the payment and changed account

```bash
curl -s https://jithox.com/api/mcp \
  -A 'pay-invoices-safely/1.0' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"preflight_payment","arguments":{"rail":"invoice_bank","approved":{"amount":"10000.00","currency":"DKK","payee":{"name":"Example Supplier"}},"instructionSource":"human","payment":{"iban":"DK2753010244563821","amount":"10000.00","currency":"DKK","payeeName":"Example Supplier","supplierCountry":"DK"},"ibanOnFile":"DK5000400440116243"}}}'
```

```bash
curl -s https://jithox.com/api/mcp \
  -A 'pay-invoices-safely/1.0' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"check_payment_change","arguments":{"newIban":"DK2753010244563821","ibanOnFile":"DK5000400440116243","supplierCountry":"DK"}}}'
```

## Check IBAN structure, not ownership

```bash
curl -s https://jithox.com/api/mcp \
  -A 'pay-invoices-safely/1.0' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"verify_iban","arguments":{"iban":"DK2753010244563821","expectedCountry":"DK"}}}'
```

## Peppol subset and recipient

```bash
curl -s https://jithox.com/api/mcp \
  -A 'pay-invoices-safely/1.0' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"check_peppol_ready","arguments":{"invoiceNumber":"SAMPLE-001","issueDate":"2026-10-02","currency":"DKK","buyerReference":"PO-SAMPLE","supplier":{"name":"Example Supplier","countryCode":"BE","endpointId":"0403170701","endpointScheme":"0208"},"customer":{"name":"Example Buyer","countryCode":"BE","endpointId":"0403170701","endpointScheme":"0208"},"lines":[{"description":"Example service","quantity":1,"unitPrice":1000,"vatPercent":21}],"totalWithoutVat":1000,"totalVat":210,"totalWithVat":1210}}}'
```

```bash
curl -s https://jithox.com/api/mcp \
  -A 'pay-invoices-safely/1.0' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"lookup_peppol_participant","arguments":{"identifier":"0403170701","scheme":"0208"}}}'
```

## Additional bank-change outcomes

These sample calls exercise the other account-change branches; the unchanged
payment does not make any unperformed required check pass.

```bash
curl -s https://jithox.com/api/mcp \
  -A 'pay-invoices-safely/1.0' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"check_payment_change","arguments":{"newIban":"DK5000400440116243","ibanOnFile":"DK5000400440116243","supplierCountry":"DK"}}}'
```

```bash
curl -s https://jithox.com/api/mcp \
  -A 'pay-invoices-safely/1.0' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"check_payment_change","arguments":{"newIban":"DK2753010244563812","ibanOnFile":"DK5000400440116243","supplierCountry":"DK"}}}'
```

```bash
curl -s https://jithox.com/api/mcp \
  -A 'pay-invoices-safely/1.0' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":8,"method":"tools/call","params":{"name":"check_payment_change","arguments":{"newIban":"DE89370400440532013000","ibanOnFile":"DK5000400440116243","supplierCountry":"DK"}}}'
```

```bash
curl -s https://jithox.com/api/mcp \
  -A 'pay-invoices-safely/1.0' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":9,"method":"tools/call","params":{"name":"preflight_payment","arguments":{"rail":"invoice_bank","approved":{"amount":"10000.00","currency":"DKK","payee":{"name":"Example Supplier"}},"instructionSource":"human","payment":{"iban":"DK5000400440116243","amount":"10000.00","currency":"DKK","payeeName":"Example Supplier","supplierCountry":"DK"},"ibanOnFile":"DK5000400440116243"}}}'
```

## Authorized checks

No authenticated call is supplied or executed by these examples. For
review_invoice, check_vat_list and kbo_company_search, first obtain the
person's authorization and configure their connection securely in the host.
Discover the input schema and use the person's actual invoice or supplier
identifiers. Without that access, each required VAT/company check is
`not_run`, not a pass. Never report `ready` for an unresolved required check.
