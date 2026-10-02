# Jithox agent package: validation boundary

Measured 2026-10-02 for task t_dc1ae9dc, branch jx/universal-agent-plugin.
Base: 32edcc1843f85b19933f669203dde9167cb38ff2 (fetched origin/main before editing).
Repair task t_1d925880 starts from A1 e88aa52cab460eaa18deea0bebed7948a89d6ad5.
This is a distribution of the existing endpoint, not new server functionality.
A passing parser/schema is not a successful host task or directory acceptance.

## Primary sources read on 2026-10-02

- Agent Plugins: https://agent-plugins.org/ and
  https://github.com/agentplugins/agent-plugins-spec
- Official portable schemas (unaltered snapshots and hashes in scripts/schemas/):
  https://agent-plugins.org/schemas/1.0.0/plugin.schema.json and
  https://agent-plugins.org/schemas/1.0.0/mcp.schema.json
- OpenAI: https://developers.openai.com/plugins/build/plugins and
  https://developers.openai.com/plugins/deploy/submission
- Claude: https://code.claude.com/docs/en/plugins-reference,
  https://code.claude.com/docs/en/plugin-marketplaces and
  https://claude.com/docs/directory/publish
- Cursor: https://cursor.com/docs/reference/plugins
- Gemini: https://geminicli.com/docs/extensions/reference/ and
  https://geminicli.com/docs/tools/mcp-server/
- Grok: https://github.com/xai-org/plugin-marketplace/blob/main/README.md
  (primary component reference: `.mcp.json`, `skills/`, optional `plugin.json`).
  The previously cited https://docs.x.ai/build/cli/plugins returned HTTP 404
  on 2026-10-02; it is not current validation evidence.
- Agent Skills discovery: https://skills.sh/docs/cli

## File responsibilities

| File(s) | Role |
|---|---|
| plugin.json, mcp.json | Agent Plugins 1.0.0; one Streamable HTTP server; OpenAI presentation |
| .mcp.json | Claude/Grok HTTP configuration; also selected by the Cursor overlay |
| .claude-plugin/plugin.json, marketplace.json | Claude bundle and repo marketplace |
| .cursor-plugin/plugin.json | Cursor bundle |
| gemini-extension.json, GEMINI.md | Gemini HTTP endpoint and instruction entry point |
| skills/pay-invoices-safely/ | The only skill, including nine runnable sample calls |
| assets/ | Original publisher icon/logo and real public input-screen screenshot; provenance |
| PACKAGE.md, LICENSE | Runtime package notes and existing MIT license |
| scripts/plugin_package.py | Deterministic ZIP, fixed timestamps/permissions, explicit allowlist |
| scripts/check_plugin_live.py | Exact eight-tool boundary against a saved live tools/list receipt |
| scripts/test_plugin_package.py, schemas/ | Offline contract tests and official portable schemas |

There are no hooks, executables, credentials or environment files in the ZIP.
The builder includes 16 explicit runtime files; tests, logs and downloaded
research sources are excluded. It normalizes text CRLF to LF and uses ZIP_STORED
so timestamps, checkout line endings and compression-library versions cannot
change the artifact. Tests cover duplicate-free inventory, negative secret/path
fixtures, ignored unrelated files and equal bytes across separate directories.
The known-pattern scan is a guard, not a guarantee against every possible secret.

A1 recorded 11/11 Python contract tests and 33/33 existing Node tests. A2
then reproduced 10/11 Python tests on a fresh `core.autocrlf=true` checkout:
its test fixture converted existing CRLF to CRCRLF, not a ZIP-builder defect.
Repair t_1d925880 normalizes the fixture basis to LF, asserts real LF/CRLF
without CRCRLF, and retains equality between the resulting ZIP bytes.
Exact-revision CRLF/LF suite results, the 33-test Node rerun, three independent
skill-stop mutants, a disabled-ZIP-normalization mutant, and the unchanged
ZIP hash are recorded in `UNIVERSEEL_PLUGIN_HANDOFF.json` and its repair logs.

## TESTED / NOT TESTED

| Surface | TESTED | NOT TESTED |
|---|---|---|
| Portable package | Official JSON Schemas 1.0.0, jsonschema 4.26.0; unexpected-field negative controls | None of the vendor extensions is covered by the portable schema |
| OpenAI | Local interface field/three-prompt/path/asset contracts against the primary field reference | Official ZIP upload, dashboard scans, identity/domain verification, ChatGPT/Codex execution, publication |
| Claude Code 2.1.278 | A1: both `claude plugin validate --strict .claude-plugin/plugin.json` and `claude plugin validate --strict .claude-plugin/marketplace.json`: Validation passed, exit 0. A2 review evidence only (t_8587be96, comment 2226): anonymous local install in isolated `CLAUDE_CONFIG_DIR`, 1 skill, 1 MCP server, exact endpoint; uninstall followed by empty list. Not rerun by this repair | Installed host/model session; docs describe added MCP-entry validation in 2.1.281, not present in this older validator |
| Grok Build 1.0.46 | A1 downloaded the official Windows binary to isolated scratch without login; repair reused it and reran `grok plugin validate <repo>`: valid, 1 skill dir, MCP servers, exit 0 with root plugin.json present | Model session, directory submission, signed-in installation |
| skills.sh | `DISABLE_TELEMETRY=1 npx --yes skills add <local repo> --list`: Found 1 skill, pay-invoices-safely, exit 0 | Installation or remote default-branch discovery of this unreleased branch |
| Gemini | Local manifest/context contracts against primary docs | Local host validate/install: gemini not on PATH; no CLI installed for this optional check; model execution |
| Cursor | Portable official schema and local overlay/path contracts against primary docs; desktop launcher 3.23.12 present, version/help checked by repair | Agent-plugin CLI validation unavailable: inspected desktop launcher help exposes VSIX/MCP options, not an agent-plugin validator. Actual host parse/install/model execution NOT TESTED. The template marketplace validator is not a single-plugin host test and was not used as one |
| Live MCP | tools/list contains exactly the existing eight names; nine unauthenticated sample tools/call requests, all HTTP 200, skill checker GREEN | Paid/authorized VAT/company/invoice calls; model-based end-to-end behavior |
| Assets/URLs | Five public metadata/asset URLs HTTP 200; source PNG dimensions and hashes; live screenshot via Playwright under the heavy-work lock | Screenshot is not evidence of a completed invoice check |

The `--list` CLI printed a generic noninteractive-install banner, then only its
Available Skills list and instructions to install separately. No install command
was run by A1 or this repair. The separate A2 Claude local-install evidence
above belongs to the reviewer, not this repair. No host login, terms acceptance,
payment, purchase, model task, public catalog submission or main-branch merge
was performed by A1 or this repair.

## Exact live boundary and observations

check_payment_change, check_peppol_ready, check_vat_list, kbo_company_search,
lookup_peppol_participant, preflight_payment, review_invoice, verify_iban.
The nine calls exercise five distinct free tools. In example order:

1. preflight_payment: review_required
2. check_payment_change: verify_first
3. verify_iban: iban_verification response
4. check_peppol_ready: ready (tool verdict, not permission to pay)
5. lookup_peppol_participant: peppol_participant_lookup response
6. check_payment_change: no_change
7. check_payment_change: invalid_new_account
8. check_payment_change: stop
9. preflight_payment: no_blockers_found (does not clear other required checks)

Each response was HTTP 200. GET /api/mcp without the streaming Accept header
returned 406; this is not used as proof of a working MCP task.
The actual POST tools/call requests are the execution evidence.
Homepage, privacy, terms, contact and icon endpoints returned HTTP 200;
that status is not a legal-content approval. Brand color contrast against white
was calculated as 9.2848:1. The screenshot's capture action/time/hash is in
assets/ORIGIN.md; no customer input or form submission was used.

## Reproduce from the repository root

```sh
uv run --with jsonschema==4.26.0 python -m unittest scripts.test_plugin_package -v
node --test scripts/*.test.mjs
claude plugin validate --strict .claude-plugin/plugin.json
claude plugin validate --strict .claude-plugin/marketplace.json
grok plugin validate .
DISABLE_TELEMETRY=1 npx --yes skills add . --list
node scripts/check-skill.mjs --header 'x-jithox-probe: plugin-validation'
```

For the live boundary, capture a fresh tools/list JSON response (not a model):

```sh
curl -sS https://jithox.com/api/mcp -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' -H 'x-jithox-probe: plugin-validation' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' > tools-list.json
python scripts/check_plugin_live.py tools-list.json
python scripts/plugin_package.py ../directories/jithox-agent-plugin-1.0.0.zip
```

Do not commit the receipt, private credentials or validator logs. The separate
handoff records the exact commit/tree, author readback, push readback, ZIP hash
and per-entry inventory. Submission remains a publisher action after independent
review and explicit release approval; the package alone grants none of those.
