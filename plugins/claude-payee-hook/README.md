# claude-payee-hook (experimental)

A deterministic Claude Code / Agent SDK plugin that runs before payment-like
MCP tools. It compares IBAN-shaped candidates with this hook's local history
using Jithox `check_payment_change`. It makes no payment itself.

This is a distribution experiment, not demonstrated market demand. A useful
outcome is an external `tools/call` with the `claude-payee-hook` user-agent,
not a download, star, our own probe, or a successful plugin validation.

## Prerequisites and local use

- Python 3.9+ with its standard library; no pip/npm dependencies.
- `sh` and Bash (Git Bash on Windows). The hook explicitly selects Bash.
- Claude Code with command-hook/plugin support. Validated with 2.1.278.
- An interactive permission host that actually honors `ask` and `deny`.

Python is an explicit prerequisite, **not something Claude Code guarantees**.
The current native installation is a standalone binary; even the npm install
uses that binary at runtime. Neither a separate Python nor Node interpreter
is guaranteed everywhere Claude Code runs. Python was chosen for its stdlib
HTTP, JSON, file descriptors and cross-platform tests; it is already the host
runtime for a Python Agent SDK application. See [source notes](SCHEMA-SOURCES.md).

From a checkout containing this plugin:

```sh
claude plugin validate ./plugins/claude-payee-hook --strict
claude --plugin-dir ./plugins/claude-payee-hook
```

For an optional, persistent installation from this local marketplace:

```sh
claude plugin marketplace add .
claude plugin install claude-payee-hook@jithox
```

These commands change your Claude configuration only when **you** run them.
This change does not submit anything to Anthropic's directory or publish a
package. The plugin must exist in your checkout; do not assume it is on main
before its separate review/release has completed.

The shell launcher tries `python3`, then `python`. Set `JITHOX_PAYEE_PYTHON`
to an executable path if necessary (including a Windows path with spaces).
A missing/crashed interpreter produces `ask` in PreToolUse, not a nonzero,
non-blocking Python crash. Missing Bash, an externally killed hook, disabled
hooks, or a harness that ignores hook output cannot be fixed by this script.

### Agent SDK

The documented local-plugin option works with the same plugin directory:

```python
from pathlib import Path
from claude_agent_sdk import ClaudeAgentOptions

options = ClaudeAgentOptions(plugins=[{
    "type": "local",
    "path": str(Path("plugins/claude-payee-hook").absolute()),
}])
```

Provide your application's human-permission integration; do not silently
approve an `ask`. Check the SDK init message's `plugins` and `plugin_errors`
fields: a missing plugin path can be skipped while the session continues.
This loading shape is from the official SDK documentation; a live SDK/model
session and payment execution were **not** tested here. CLI validation is not
proof that a particular SDK application enforces these decisions.

## Configuration (operator environment, never tool arguments)

| Variable | Default / interpretation |
| --- | --- |
| `JITHOX_PAYEE_PYTHON` | Optional executable path; otherwise `python3`, then `python`. |
| `JITHOX_PAYEE_MEMORY_DIR` | Absolute `~/.claude-payee-hook` under the executing user's home. Its parent must already exist. Do not use a shared/project directory. |
| `JITHOX_PAYEE_FIELDS` | `name,naam,creditor,beneficiary`; comma-separated, case-sensitive dot paths into tool input. Example: `recipient.vendor_id`. Exactly one distinct, nonempty string value must be found. |
| `JITHOX_PAYEE_TOOL_PATTERN` | Case-insensitive Python regex: `^mcp__.+__.*(?:transfer\|send\|pay\|payment\|wire\|payout\|charge\|withdraw).*`. Use actual payment-tool names to avoid overmatching. |

The JSON hook matcher invokes the script for `mcp__.*`; the script applies
the configurable payment matcher. Thus changing the environment does not
require editing the plugin's packaged JSON. Nonmatching tools return `{}`
and neither call Jithox nor update history. This does not cover Bash commands,
native payment tools, obfuscated/encoded account data, or payments outside
Claude's matched MCP tool calls.

History keys combine the **exact MCP tool name** with the trimmed payee key.
Names are not case-folded or guessed. Different tools are separate namespaces.
Missing/ambiguous keys cannot establish a record or produce an automatic allow.
Choose a stable supplier ID field rather than a display name where possible.

## Decision contract

The script walks strings in nested objects and arrays, extracts compact or
space/hyphen-grouped IBAN candidates, uppercases them and checks mod-97. It
is a conservative text heuristic, not a parser for every bank's payment schema.
Malformed candidates are not silently treated as an absent account.

| Observation | PreToolUse result |
| --- | --- |
| No IBAN candidate | No permission decision; `systemMessage` says **Jithox checked nothing**. Other permission checks still apply. |
| Local mod-97 failure | `deny`, `invalid_new_account`; no remote request for that candidate. |
| `stop` or `invalid_new_account` from Jithox | `deny` |
| `verify_first` | `ask` |
| No local record, even if the service says `no_change` | `ask` (first registration) |
| `no_change` and this exact candidate equals the local record | `allow` |
| Contradictory `no_change`, any exception, non-200, DNS/timeout, HTML challenge, `isError`, malformed/unknown response | `ask`, never `allow` |

Every distinct candidate is checked; `deny` wins over `ask`, which wins over
`allow`. At most 16 candidates are processed, in parallel. Input, response and
memory files each have a 256 KiB cap; exceeding a limit requests approval.
The network deadline is three seconds including DNS/connect/body handling,
not just receipt of HTTP headers. No retries or redirects. JSON and SSE
JSON-RPC responses are accepted only with the expected tool result and
nonempty callback steps. A broken/hanging service cannot authorize a call.

Reasons include verdict, account suffix and sanitized callback steps. No
complete IBAN is printed by the hook. The `allow` result can skip the normal
permission prompt for the **whole tool call**, not just the account field.
It does not approve the amount, invoice, recipient identity or purchase.
Only enable this behavior where you also enforce the appropriate amount and
business-authorization controls. See Claude's decision semantics in the
[source notes](SCHEMA-SOURCES.md).

## Local memory: only after successful execution

PreToolUse is read-only. `ibanOnFile` in the outgoing request is read only
from `payees.json`, never from an identically named field or a sentence in
`tool_input`. Incoming reference-like strings are still scanned as candidates;
they cannot replace the locally trusted comparison value.

PostToolUse does **not** call Jithox. It remembers one account only when there
is one unambiguous payee and one mod-97-valid candidate, and the tool reports
explicit success: `success: true`, `ok: true`, or `status` equal to `succeeded`,
`completed` or `paid`. The same markers can be inside a single MCP JSON text
block or `structuredContent`. Error/failure flags veto learning. Unknown,
non-JSON, contradictory, failed or multi-account responses do not learn.
A tool's success is not independent proof of bank settlement or ownership.

- POSIX: private, current-user directory (`0700`), regular single-link file
  (`0600`); `O_NOFOLLOW` directory traversal and directory-relative operations
  refuse symlinks. Writes use a private temporary file, fsync, atomic replace
  and directory fsync. Reads check permissions, file identity and schema.
- Concurrent writers: exclusive `write.lock`, up to one second waiting,
  re-read under the lock, then replace. Readers see an old or a new complete
  file. Two different payees are not lost to a blind overwrite. For the same
  payee the last completed writer wins; there is no distributed ledger.
- Windows: reject visible symlinks and reparse points/junctions in the path;
  check regular-file identity/link count before reading, then use atomic
  `os.replace`. POSIX `0600` is **not** a Windows ACL. Use a private directory
  with a restrictive inherited Windows ACL. Python has no equivalent
  `O_NOFOLLOW`/directory-fd guarantee here; protection from a same-user
  path-swap race is not claimed. Windows junction behavior is tested; Linux
  symlink/mode tests are run on WSL's Linux filesystem, not `/mnt/c`.

Corrupt or insecure existing memory is not reset automatically. Stop active
hook processes before inspecting/removing a stale `write.lock` left by a killed
writer. Back up/reset `payees.json` only as an operator; removing a record makes
the next use a first registration requiring approval. Never put this plaintext
history (names/IDs and complete IBANs) in git or share it with the model.

## Privacy and limits

Only current IBAN candidates that pass mod-97, the associated stored IBAN when
present, and an optional two-letter supplier country go to `jithox.com` over
HTTPS. No supplier name, amount, invoice, tool name, conversation or transcript
is sent. The hook emits no extra telemetry beyond its
`claude-payee-hook/0.1.0` User-Agent; ordinary network metadata such as the IP
address is necessarily visible to the service. A test-only probe driver adds
`x-jithox-probe`; the installed hook never adds that header. We have not audited
the service's logs or retention.

There is no LLM judgment in this hook. A match is not a statement that an
account is safe, open, owned by the supplier, or that a change request is
legitimate. Use a phone number from your **own** records, not the request, for
independent confirmation. Banks offer **Verification of Payee (VoP) free of
charge** under the EU instant-payments rules (euro-area deadline 9 October
2025; other EU member states have a later deadline). This comparison with your
local history is not VoP, does not replace it, and the arithmetic itself can
be performed offline. See the ECB source in [source notes](SCHEMA-SOURCES.md).

The operator, hook files, environment, tool result and local history must be
trusted. An agent allowed to edit those files, disable the plugin, alter its
environment, or pay by another path can bypass it. A later hook may also change
tool input. This plugin is **not** an OS isolation boundary or a bank control.

## Verification

Run from the repository root; no live traffic in the test suite:

```sh
python -m unittest discover -s tests/claude_payee -p 'test_*.py' -v
python tests/claude_payee/mutants.py
```

Opt-in, one read-only production probe with a public documentation example:

```sh
python tests/claude_payee/probe.py --probe t_edd8a743
```

Do not run that command as a traffic generator. The marker excludes our own
probe from external adoption. [VERIFICATION.md](VERIFICATION.md) records the
actual Windows/WSL/CLI results, skips, six mutant test names and live observation.
All Jithox request/envelope handling is in `askJithox`; a future service change
belongs there, not in payment-tool-specific branches.
