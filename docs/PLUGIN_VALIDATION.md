# Jithox agent package: validation boundary

## GEBRUIK1 F1/F2 repair — 2026-10-03

Task t_ce59fd98 starts from exact local candidate
`0b19fe01c3da6bd6963717ddb55fb9d46297dcb3`, above v1.0.0
`2af58b5517c2307310f081948b74e4ff33c927a3`. The repair SHA/tree and
scrubbed receipts are in its handoff, not a release or model-evaluation claim.
The older measurements below remain historical.

Both invoice-payment scenarios now keep invoice-derived instructions as
`ingested_content`, separately from human `approved`. The DKK 1210 sample invoice
is explicitly independent of the DKK 10000 payment run; it is not passed as that
payment's invoice. The README and its Python sibling are corrected too. Their
2026-09-25 output is retained unchanged and labelled historical, not silently
rewritten as a response to new arguments.

Real anonymous measurements of both repaired scenarios and the README request:
HTTP 200, `review_required`, instruction check `warn`, reason
`instruction_not_from_human`, and charged=false. The changed-account cases also
return `payment_change_verify_first`. The corrected Python example executed
initialize, preflight and evidence verification: valid, inputMatch=true.

The first five-skill run found one grounding failure: after the source repair,
neither invoice scenario returns the old no-blocker verdict. Rather than invent
an output or loosen grounding, the skill and both command copies now express the
same safety limit as “An absence of blockers describes only checks that actually
ran; it is not permission to pay”. The final five-skill run is green.

The price guard retains the exact two live-grounded VAT lines as its only
exception. A currency-code amount in an explicit cost/fee/per-call claim is now
checked without enumerating currency codes. Ordinary NOK/SEK/DKK invoice sample
amounts are not new price claims. This remains a bounded text guard, not a
semantic proof against every possible phrasing. Existing money-marker checks
are unchanged.

Executed for this repair:

- `node --test scripts/*.test.mjs`: 58/58 (44 existing + 14 new), zero skipped.
- `uv run --with jsonschema==4.26.0 python scripts/test_plugin_package.py`: 12/12.
- `python -B scripts/test_gebruik1_eval.py`: 31/31. Prompts/rubrics unchanged;
  these offline harness tests are not new model runs.
- `node --import <handoff>/live-observer.mjs scripts/check-skill.mjs --header
  'x-jithox-probe: gebruik1-fix'`: five GREEN, 34 actual HTTP requests, including
  23 tools/call (21 HTTP 200, two valid anonymous HTTP 401). The observer asserts
  the actual outgoing Request header is gebruik1-fix and no authorization/cookie
  is sent. Wire User-Agent is check-skill/1.0, not the examples' declared agents.
- Actual stored tools/list replay through full runChecks: canonical cost quotes
  and invoice sample amounts green; NOK, SEK, ZAR, XYZ, GBP and DKK cost claims,
  changed EUR price, and prices in another file red. Explicitly offline fixtures.
- Copy-only revert controls: each of four human-label reversions, the lost
  independent-invoice distinction and the wrong scenario-2 verdict gives exactly
  1 failure out of 58. Restoring the old finite-only currency guard gives 8/58
  failures. Exact old candidate plus the new tests gives 13/58 failures.
- Claude Code 2.1.278: both strict plugin and marketplace validations exit 0.
  Existing Grok Build 1.0.46: plugin validate exit 0. No model session implied.
- Two byte-identical ZIPs, 34 entries, 251561 bytes, SHA-256
  `aaf9e5d2153eca7c5e281feb81b9b433ea9274f4d502c5e023870ce723258b81`.

No heavy application build, tsc, Vitest or Playwright was needed or run. No
credentials, paid successful lookup, payment, invoice submission, vendor write,
push, merge, tag or publication. Independent herreview t_fdcebc94 owns the new
40-client-run matrix and any approval. This repair does not claim to clear the
prior model-assisted evaluation's remaining limitations.

## GEBRUIK1 candidate — 2026-10-02

Task t_b9caaac7, branch jx/gebruik1-taakskills. Base and peeled v1.0.0:
`2af58b5517c2307310f081948b74e4ff33c927a3`. The exact candidate commit and
artifact inventory are in the build handoff; resolve that SHA, not a branch
name. This unpublished candidate deliberately retains manifest version 1.0.0;
only the separate approved release lane may bump/tag/publish it.

This section supersedes the historical one-skill counts below. Runtime now has
five skills, exactly two scenarios per skill, five Claude Markdown commands and
five Gemini TOML commands. The explicit ZIP allowlist has 34 entries; evaluation
scripts, prompts, scoring, tests and research notes remain outside it. There is
no server change, new MCP tool, payment executor or invoice-sending capability.

### Primary format sources actually read

- https://agentskills.io/specification — required name/description; name matches
  directory, lowercase kebab-case and 1–64 characters; description 1–1024.
  Five descriptions carry compact EN/NL/FR/DE intent triggers rather than a brand.
- https://code.claude.com/docs/en/plugins-reference and
  https://code.claude.com/docs/en/plugins/components — root commands/*.md with
  frontmatter; skills stay in skills/. Command bodies repeat the entire workflow
  boundary and pass $ARGUMENTS as untrusted request data, not additional authority.
- https://geminicli.com/docs/cli/custom-commands/ and
  https://geminicli.com/docs/extensions/reference/ — root extension commands/*.toml,
  required prompt string, optional description, {{args}}; no shell interpolation.
- https://cursor.com/docs/reference/plugins — its Commands format explicitly
  discovers Markdown/text files in commands/ and allows name/description
  frontmatter. It can discover the same five .md files. No Cursor-only files or
  unverified Cursor argument-substitution/host-execution claim is added.
- Native Codex local-marketplace and ephemeral protocol sources are recorded in
  [eval/gebruik1/CODEX.md](../eval/gebruik1/CODEX.md). Claude/Gemini OAuth and
  storage sources are in [eval/gebruik1/SOURCES.md](../eval/gebruik1/SOURCES.md).

No Belgian legal-obligation claim was added. Technical readiness is explicitly
not full legal compliance or evidence of invoice acceptance/delivery.

### Executed checks, not inferred outcomes

| Check | Observed result |
|---|---|
| node --test scripts/*.test.mjs | 44/44 pass, zero skipped |
| uv run --with jsonschema==4.26.0 python scripts/test_plugin_package.py | 12/12 pass; includes parsed TOML, exact inventory, schema and LF/CRLF determinism |
| python -B scripts/test_gebruik1_eval.py | 31/31 pass; real offline loopback fixtures, not model evidence |
| Live skill checker, all five skills | Five GREEN; tools/list returns eight existing tools; 23 sample tools/call: 21 HTTP 200 and two genuine anonymous HTTP 401 challenges |
| Claude Code 2.1.278 | Both strict plugin/marketplace manifest validators pass, exit 0 |
| Grok Build 1.0.46 (existing scratch binary) | plugin validate passes, one skill directory and one command directory; not a claim that it executed five skills |
| Codex CLI 0.155.0 | Native local marketplace add/install/list for baseline export and candidate ZIP copy; enabled/installed readback, candidate five skills and all 20 skill/example/command files byte-identical; installed MCP configs point at the overlaid loopback URL |
| Codex protocol, no model input | Native initialize + ephemeral thread/start: ephemeral=true, no rollout path, zero turns; process stopped, zero rollout files |
| Codex cleanup | Both isolated installations removed; native list reads back installed=[] |
| ZIP built twice | Equal bytes; 34 entries, 250709 bytes, SHA-256 948bbc2fe3165fce428ef5259ff0a3497fc4f3ac9589666b48047e220d246fb8 |

A combined verification command hit its 90-second tool timeout after the Node
and package tests passed. The eval suite plus Claude/Grok validators were rerun
separately with a 240-second limit and completed exit 0 (eval: 17.856 seconds).
No missing run is credited to the timed-out command. These are small Node/Python
checks, not full application tsc/build/vitest/Playwright jobs; none of those heavy
jobs was necessary or run. Any future heavy check must use the team heavy-work lock.

The final live run used the following throttle (no schema/result substitution):

```sh
node --import 'data:text/javascript,const original=globalThis.fetch;globalThis.fetch=async(...args)=>{await new Promise(r=>setTimeout(r,2300));return original(...args)};' scripts/check-skill.mjs --header 'x-jithox-probe: gebruik1-build'
```

Sample call counts: agent-payment-preflight 3, check-vat-numbers 2,
pay-invoices-safely 9, send-peppol-invoice 3, verify-bank-detail-change 6.
Scenarios can contain several checks or a comparison; there are still exactly
ten scenario headings. All requests are own probes, not external usage. The
checker never sent credentials. GET /api/mcp returned 406 (expected without a
streaming Accept header); only the real POST calls are execution evidence.

Observed raw verdicts include review_required/no_blockers_found/stop for
preflight, no_change/verify_first/invalid_new_account/stop for bank changes,
and ready/will_be_rejected for invoice rules. The package preserves those
verdicts and limitations; none of them gives permission to pay or send.

### Paid boundary and bounded regression guards

The live tools/list descriptions on 2026-10-02 included these exact sentences:

- check_vat_list: 1 credit (EUR 0.01) per answered row; needs a bearer token.
- kbo_company_search: 2 credits (EUR 0.02) per successful call; needs a bearer token.

Both anonymous, schema-valid paid examples returned HTTP 401 with a Bearer
resource_metadata challenge for /.well-known/oauth-protected-resource/api/mcp.
The checker sees payment_required in the body; that is access-refusal evidence,
not a successful paid lookup or a VAT verdict. The connection substring observed
in both initial challenges was:

> A person creates a Jithox connection at https://jithox.com/mcp/account#connection (creating it is free);

The skill labels this as a dated quote, requires current discovery and human
consent before tools/call, uses only live connection instructions, and never buys
access. It distinguishes any consented lookup charge from invoice payment.

The global price guard now permits only the two exact full cost lines in
check-vat-numbers/SKILL.md, once each, after matching live descriptions. Different
prices, duplicate lines, other files/skills, missing discovery and extra
GBP/credit/dollar claims remain RED. Command safety text is pinned to the skill;
it does not create an independent free-form price exception. Anonymous 401
acceptance is restricted to the two VAT example calls, exact endpoint and probe
marker, status and valid challenge; an unmarked probe, HTTP 200, absent challenge
or review_invoice cannot borrow that exception.

Observed RED→GREEN tests also cover missing workflows/command pairs, frontmatter
limits, two scenarios, forbidden execution/unknown-as-pass claims, probe labeling
and package content. The prose execution regex is a bounded regression guard,
not a semantic proof against every possible false claim. Independent content and
real-client review remain mandatory. Eval follow-up regressions prevent failed
connections being counted as dispatch, blocked unknown tools being omitted from
the gate, or a candidate passing without evidence for all five tasks per client.

### Deliberately NOT tested

No model inference, OAuth login or subscription use; no 40-row comparison,
natural activation improvement or scored success. No authenticated paid lookup,
credit purchase/deduction, payment, invoice submission or vendor mutation.
No Gemini installation (binary absent), Cursor host parse/installation/model
execution, new remote skills.sh discovery, public directory submission, push,
merge, release tag or deployment. Post-inference native client storage still
needs evaluator verification: the Codex smoke had zero turns; Gemini's automatic
history is an explicit blocker until resolved. See the operator protocol in
[eval/gebruik1/README.md](../eval/gebruik1/README.md). All score cells start null;
a parser, install or tools/list must never fill them as successes.

## Historical v1.0.0 evidence (unchanged scope)

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
