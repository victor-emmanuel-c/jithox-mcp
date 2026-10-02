# Jithox

Choose the matching task and read its skill instructions before execution:

- Invoice before payment / factuur betalen: skills/pay-invoices-safely/SKILL.md
- IBAN gewijzigd / changement de RIB / Bankverbindung geändert: skills/verify-bank-detail-change/SKILL.md
- e-factuur Peppol / facture électronique: skills/send-peppol-invoice/SKILL.md
- Agent spending preflight / betaling vooraf: skills/agent-payment-preflight/SKILL.md
- VAT list / btw-lijst / TVA / USt-IdNr: skills/check-vat-numbers/SKILL.md

Same-named custom commands are in commands/*.toml. They carry the same safety
workflow, not shell execution or automatic payment authorization.

Use only the tools exposed by the configured Jithox MCP server. Discovery
is not execution. Report each skipped or unreachable check as `not_run`;
never say `ready` when a required check is `unknown` or `not_run`.
Keep approval and any account or payment action with the person.
