# Primary sources reviewed for GEBRUIK1

Scope note: the discovery-only statements below describe the initial eval-harness
subtask, not the subsequent parent build. The parent ran all five live skill
validators, including genuine anonymous VAT/KBO 401 probes; see
../../docs/PLUGIN_VALIDATION.md. It also verified a native Codex local installation
and ephemeral zero-turn handshake; CODEX.md records that route and its official
sources. Neither phase ran model inference or the forty scored rows.

Reviewed on **2026-10-02 (UTC)**. Public documentation only; no account pages,
client credential files or model sessions were inspected. Search results were
restricted to the publishers below and followed by direct anonymous HTTPS GETs.
The eleven core documentation URLs below each returned HTTP 200 in this run.
The search tool's configured OpenAI-native backend fell back to keyless search;
its extraction backend was unavailable, so direct HTTPS was used to verify the
pages themselves. This is not a claim that a model-client comparison ran.

| Source URL | What it establishes for this package |
|---|---|
| https://agentskills.io/specification | A skill directory contains SKILL.md with name/description frontmatter; descriptions are trigger metadata, not evidence of activation. |
| https://code.claude.com/docs/en/plugins-reference | Plugin skill and Markdown command discovery; components live at the plugin root, not inside .claude-plugin. |
| https://code.claude.com/docs/en/authentication | Subscription-account browser OAuth differs from Console/API-key authentication; inherited API credentials can override the intended route. |
| https://code.claude.com/docs/en/cli-reference | --plugin-dir, --mcp-config, --strict-mcp-config; --no-session-persistence is print-mode only, while CLAUDE_CODE_SKIP_PROMPT_HISTORY is documented for any mode. |
| https://geminicli.com/docs/get-started/authentication/ | Sign in with Google; use the subscription's Google account for AI Pro/Ultra; organization/project requirements vary. |
| https://geminicli.com/docs/extensions/reference/ | Link/uninstall a local extension; gemini-extension.json, skills/ and commands/*.toml are extension components. |
| https://geminicli.com/docs/cli/custom-commands/ | TOML commands use a prompt field; {{args}} is argument substitution. Explicit commands are not an implicit-trigger evaluation. |
| https://geminicli.com/docs/cli/cli-reference/ | --extensions selects extensions; --approval-mode default retains confirmations, unlike yolo/auto_edit. |
| https://geminicli.com/docs/reference/configuration/ | GEMINI_CLI_HOME isolates user-level storage; no claim that a different home disables session recording. |
| https://geminicli.com/docs/cli/session-management/ | Gemini automatically records prompts/responses/tool inputs/outputs; retention settings control cleanup, not a verified recording-off mode. This is an explicit privacy blocker for strict zero-transcript runs. |
| https://cursor.com/docs/reference/plugins | Cursor discovers commands/*.md alongside skills/. No separate Cursor command directory or extra ten-prompt run is implied. |

Additional official installation/MCP entry points for operators:

- https://geminicli.com/docs/get-started/installation/
- https://geminicli.com/docs/tools/mcp-server/
- https://geminicli.com/docs/extensions/

These are setup references, not a guarantee that a current Gemini installation
works on Node 18. The evaluation harness itself is dependency-free Python 3.11+.
Recheck the client's installation/runtime requirements on the day of execution.

## Live MCP discovery (not execution evidence)

Endpoint: https://jithox.com/api/mcp .

One anonymous `tools/list` POST returned HTTP 200 during this implementation.
It included `x-jithox-probe: gebruik1-eval` and a unique discovery User-Agent with
client/baseline/discovery/call identity. The response contained the eight existing
tools: preflight_payment, verify_iban, check_payment_change, check_peppol_ready,
lookup_peppol_participant, review_invoice, check_vat_list, kbo_company_search.
The VAT and KBO prices in `prompts.json`/README were matched to that response.
The discovered valid paid-boundary argument forms are:

```json
{"rows":[{"vatId":"BE0403170701"}]}
{"vatNumber":"BE0403170701"}
```

`review_invoice` was described as a paid authenticated tool too; this harness
always blocks it. It must not accidentally become an anonymous 'free invoice
check'. No `tools/call` was sent to the live endpoint by this implementation.
Discovery alone proves neither a model selected a tool nor a register was checked.
No 401 live paid-boundary evidence has been collected.

## Client observations, not execution

Only availability/version/help were inspected: Claude Code **2.1.278**, Codex CLI
**0.155.0**; Gemini CLI was absent from PATH. No model inference, OAuth login,
subscription consumption, client config mutation or paid request was run.
Codex help exposes `exec --ephemeral` in noninteractive mode; this must not be
misrepresented as a verified interactive, human-consent-compatible comparison.
The matrix/relay accept the Codex client label so a later separately verified
adapter can use the same rubric; the documented primary workflow is Claude +
Gemini, with Gemini's native-history limitation stated rather than concealed.
