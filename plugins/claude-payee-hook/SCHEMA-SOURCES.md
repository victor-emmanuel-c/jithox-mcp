# Official schema sources

Retrieved on **2026-09-26**. Commands were validated using the installed
Claude Code **2.1.278**, not an assumed latest version. The `.md` versions of
the first three pages were fetched directly; the SDK page used
`Accept: text/markdown`. These notes distinguish upstream fields from our own
configuration and response interpretation.

## Marketplace (`.claude-plugin/marketplace.json` at repository root)

Source, all rows: https://code.claude.com/docs/en/plugin-marketplaces
("Create a marketplace", "Add plugin entries"), retrieved 2026-09-26.

| Used field | Meaning / chosen value |
| --- | --- |
| `name` | Marketplace identifier: `jithox`. |
| `description` | Human-readable catalog description. |
| `owner` | Owner object. |
| `owner.name` | Owner display name: `Jithox`. |
| `plugins` | List of marketplace entries. |
| `plugins[].name` | Installed plugin identifier: `claude-payee-hook`. |
| `plugins[].source` | Path relative to marketplace root: `./plugins/claude-payee-hook`. |
| `plugins[].description` | Catalog-entry summary. |

## Plugin (`plugins/claude-payee-hook/.claude-plugin/plugin.json`)

Fetched source: https://code.claude.com/docs/en/plugins-reference
(current page heading: "Plugin manifest reference"; canonical reference:
https://code.claude.com/docs/en/plugins/manifest-reference), retrieved 2026-09-26.

| Used field | Meaning / chosen value |
| --- | --- |
| `name` | Namespaced identifier: `claude-payee-hook`. |
| `version` | Version string: `0.1.0`. |
| `description` | Short plugin summary. |
| `author` | Author object. |
| `author.name` | Author display name: `Jithox`. |
| `license` | SPDX identifier: `MIT`. |

`hooks/hooks.json` is a standard, automatically discovered location. We do not
repeat it in manifest `hooks`, which would risk loading hooks twice. The same
reference documents `${CLAUDE_PLUGIN_ROOT}` for the installed plugin location.

## Hooks (`hooks/hooks.json`)

Source, all rows: https://code.claude.com/docs/en/hooks
("Configuration", "Hook handler fields", "PreToolUse decision control",
"PostToolUse input", "JSON output"), retrieved 2026-09-26.

| Used field | Meaning / chosen value |
| --- | --- |
| `hooks` | Root event configuration object. |
| `hooks.PreToolUse` | Matcher groups before execution. |
| `hooks.PostToolUse` | Matcher groups after successful tool execution. |
| `matcher` | Tool-name regex, `mcp__.*`; payment selection is further restricted inside the script. |
| Matcher group's `hooks` | Handler array. |
| Handler `type` | `command`, synchronous; no prompt/model hook. |
| Handler `command` | `sh "${CLAUDE_PLUGIN_ROOT}/scripts/run.sh"` with a fixed `PreToolUse` or `PostToolUse` argument. |
| Handler `shell` | `bash`, including Git Bash on Windows. |
| Handler `timeout` | `15` seconds, a host backstop above the script's network deadline. |

### Fields consumed from stdin

Source: https://code.claude.com/docs/en/hooks#pretooluse-input and
https://code.claude.com/docs/en/hooks#posttooluse-input, retrieved 2026-09-26.

| Used field | Interpretation |
| --- | --- |
| `hook_event_name` | Must agree with the fixed launcher stage. |
| `tool_name` | Actual tool name; used by matcher and local namespace. |
| `tool_input` | Tool-specific argument object; recursively searched for candidate strings. |
| `tool_response` | PostToolUse result, tool-specific. Our explicit-success rules are **our policy**, not a universal upstream payment schema. |

Other common fields (`session_id`, `transcript_path`, `cwd`, `tool_use_id`,
permission metadata) are not read for account decisions and are not sent.

### Fields emitted to stdout

Source: https://code.claude.com/docs/en/hooks#pretooluse-decision-control and
https://code.claude.com/docs/en/hooks#json-output, retrieved 2026-09-26.

| Used field | Meaning |
| --- | --- |
| `hookSpecificOutput` | PreToolUse-specific response object. |
| `hookEventName` | `PreToolUse`. |
| `permissionDecision` | `allow`, `deny` or `ask`. No decision for no candidate. |
| `permissionDecisionReason` | Verdict, account suffix, sanitized steps. |
| `systemMessage` | User-facing notice for no candidate or PostToolUse outcome. |

We omit the permission decision rather than use `defer` for an absent IBAN:
upstream `defer` pauses non-interactive execution and is not a generic
"nothing checked" signal. Exit zero lets Claude process our JSON. A missing
Python interpreter is handled by the shell, because ordinary nonzero hook
errors are not a substitute for a permission decision.

## Runtime and SDK

- https://code.claude.com/docs/en/setup — retrieved 2026-09-26. Native binary
  installation does not imply a separately callable Node/Python interpreter.
  Our Python and Bash prerequisites are explicit, not upstream guarantees.
- https://platform.claude.com/docs/en/agent-sdk/plugins — retrieved 2026-09-26.
  `ClaudeAgentOptions.plugins` accepts entries with `type: "local"` and `path`.
  The documented init `plugins` list / `plugin_errors` field must be inspected
  because missing paths can be skipped. This is a documented loading shape,
  not a claim of executed SDK end-to-end coverage.

## Payment comparison and VoP

- `check_payment_change` contract was traced to the existing Jithox source
  (`src/features/mcp-plugins/plugins/check-payment-change-plugin.ts` and
  `src/features/payment-change/payment-change.ts` in aiconnect-platform),
  then exercised once through https://jithox.com/api/mcp on 2026-09-26 with
  `x-jithox-probe: t_edd8a743`. Exact observation: VERIFICATION.md.
- https://www.ecb.europa.eu/paym/retail/instant_payments/html/instant_payments_regulation.en.html
  — retrieved 2026-09-26. The ECB describes free Verification of Payee for
  both standard and instant credit transfers, with the euro-area deadline
  9 October 2025 and non-euro-area EU deadline 9 July 2027. We do not present
  an IBAN-history comparison as a replacement for that bank service.
