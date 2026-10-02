# Jithox agent package

This package connects one remote server: https://jithox.com/api/mcp.
It contains no server implementation, execution hooks, credentials or payment
function. The only bundled skill is skills/pay-invoices-safely/SKILL.md.
Read that skill for the workflow and its stop conditions.

## Scope

The eight tools observed on 2026-10-02 are check_payment_change,
check_peppol_ready, check_vat_list, kbo_company_search,
lookup_peppol_participant, preflight_payment, review_invoice and verify_iban.
Always rediscover their current input schemas. Installation does not grant
access or consent to a charged call. VAT/company checks requiring an authorized
connection remain not_run when that access or authorization is missing.
Never report ready with an unknown or not_run required check.

The root plugin.json and mcp.json follow Agent Plugins 1.0.0. Host overlays
point at the same server: Claude and Grok use .mcp.json, Cursor's overlay
explicitly selects .mcp.json, and Gemini uses httpUrl in gemini-extension.json.
The three listing starter prompts are in extensions.com.openai.interface.defaultPrompt.

## Installation after publication of this reviewed package

Claude Code:

    /plugin marketplace add victor-emmanuel-c/jithox-mcp
    /plugin install jithox@jithox

Gemini CLI (review the install permissions yourself):

    gemini extensions install https://github.com/victor-emmanuel-c/jithox-mcp

Agent Skills clients:

    npx skills add victor-emmanuel-c/jithox-mcp

These remote commands use the published repository; they do not select an
unreleased development branch. An installation or local validation is not a
successful task, catalog listing, endorsement or guarantee of recommendation.
Public directory submissions, login, publisher verification and acceptance of
terms remain publisher actions. See the repository's validation report for
TESTED and NOT TESTED boundaries. Image provenance is in assets/ORIGIN.md.

Package code and documentation: MIT, see LICENSE. The hosted service is not
open source. No rights in the Jithox name or mark are granted by the code license.
