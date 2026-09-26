# Verification — t_edd8a743

Date: 2026-09-26. Branch: `jx/claude-payee-hook`.
Started from the requested clean `cbaab86` basis, not the separate skill branch.
The exact delivered commit is the build-card handoff / branch head; a document
cannot include its own eventual commit SHA without changing that SHA.

## Executed platform results

Command from the repository root:

```sh
python -m unittest discover -s tests/claude_payee -p 'test_*.py' -v
```

On WSL use `python3`. Tests and mutants use only fixtures; they do not call
Jithox. `PAYEE_TEST_TMP` can select a private test directory. On WSL it was a
Linux filesystem directory under `$HOME/.cache/payee-tests`, not NTFS mounted
at `/mnt/c`, so file modes and symlinks were genuinely exercised on Linux.

| Platform | Result | Recorded duration |
| --- | --- | --- |
| Windows 11, Python 3.11.16 | **32 geslaagd / 0 rood van 34; 2 overgeslagen** | 32.683 s |
| WSL Ubuntu-24.04, Python 3.12.3; Linux 6.18.33.2-microsoft-standard-WSL2 | **34 geslaagd / 0 rood van 34; 0 overgeslagen** | 33.514 s |

The two Windows skips are explicit in `verification/windows-tests.txt`:
POSIX file-mode enforcement, and creating a file symlink without the required
Windows privilege. The actual Windows **junction** test ran and passed. The
WSL file-symlink and 0600/0700 tests ran and passed. A Windows run is not being
used as a substitute for those Linux tests.

Output files:

- `verification/windows-tests.txt`
- `verification/wsl-tests.txt`
- `verification/windows-mutants.jsonl`
- `verification/wsl-mutants.jsonl`

Additional executed checks: Python `compile()` on all six Python source/test
drivers, shell launcher execution on both platforms, and `git diff --check`.
There is no package install, Next build, Vitest suite or GitHub Actions claim.

## Test scope

- Real subprocess stdin/stdout fixtures for no decision, allow, ask and deny.
- Comparison comes from local memory, never caller `ibanOnFile` or prose.
- Nested strings, duplicate/formatted IBANs, checksum rejection, multiple
  accounts and worst-verdict aggregation; all requests are captured offline.
- Exact JSON-RPC arguments, endpoint, Accept and User-Agent. No names, amounts,
  or `x-jithox-probe` in the installed hook's requests.
- DNS exception, timeout, a hanging connect, a hanging body, HTTP 500/406,
  JSON and HTML 403 challenges, a 200 HTML challenge, malformed/empty JSON,
  `isError`, unknown verdict, wrong RPC version/id, malformed result and
  missing/malformed callback steps. Error tests start with an existing record
  so a missing error guard cannot hide behind the first-registration rule.
- PreToolUse never writes; PostToolUse requires explicit successful results,
  including JSON text/structured MCP envelopes. No learning on failures,
  ambiguous payees/accounts or unknown result schemas.
- Corrupt/insecure memory, hardlinks, symlinks/junctions, atomic-replace failure,
  existing writer lock, and simultaneous successful posts for two payees.
- Configurable payee path/tool matcher, oversized input, invalid country,
  missing runtime fallback and schema/default hook discovery.

Implementation proceeded in red/green slices. Observed red tests included the
initial absent executable, stop mapping, network failures, mod-97 rejection,
recursive formatted candidates, account redaction, successful-post persistence,
file-link/mode protection, atomic replacement, configuration, parallel deadline,
launcher/manifest absence, and MCP success-envelope interpretation. Additional
malformed-response cases characterize error handling already present.

## Six actual mutants

Run with `python tests/claude_payee/mutants.py`. Each mutation is applied to a
syntax-checked disposable source copy, not the working tree. A green baseline
with the same selected test count is required. A syntax/import crash does not
count as a kill: the runner requires named assertion failures and no errors.
The JSONL output records names/counts, not account values from failed assertions.

| Mutation | Test turning red | Windows / WSL |
| --- | --- | --- |
| Error becomes allow | `test_transport_failures_are_ask_never_allow` | killed / killed |
| Reference comes from tool input | `test_local_record_cannot_be_replaced_by_caller_reference` | killed / killed |
| Stop becomes ask | `test_stop_is_deny_not_ask` | killed / killed |
| Skip mod-97 | `test_mod97_failure_denies_without_request` | killed / killed |
| Persist in PreToolUse | `test_known_account_pre_never_writes_memory` | killed / killed |
| Follow memory link | `test_memory_parent_link_is_refused`; also `test_memory_symlink_is_never_read_or_written` on Linux | killed / killed |

**6/6 killed on each platform.** Windows killed the link mutant through a real
junction; its file-symlink subtest was skipped, not falsely counted as passed.
Linux killed both link assertions. The link mutant substitutes a path-based
read for the entire guarded read, since removing only one of two independent
link guards would be an equivalent mutation for a static symlink.

## One live read-only own probe

Executed exactly once:

```sh
python tests/claude_payee/probe.py --probe t_edd8a743
```

The driver calls the real `askJithox`, adds `x-jithox-probe: t_edd8a743` only in
this test path, and observes the real urllib response status. It uses a public
documentation account example, not a customer's account. Actual output:

```json
{"probe":"t_edd8a743","http_status":200,"verdict":"no_change","required_steps_count":1,"seconds":0.219}
```

This proves the request/envelope path worked against production at that moment.
It does not prove continuous availability or an external customer's call.
Database classification of the marker was not separately queried.

## Real Claude Code CLI

Installed version: **2.1.278**. `claude auth status` confirmed a logged-in
Claude account; no credentials or account identifiers were read into evidence.

Both commands executed with exit 0 and `Validation passed`, no warnings:

```sh
claude plugin validate ./plugins/claude-payee-hook --strict
claude plugin validate . --strict
```

This is the real CLI validation requested by the task, plus executable
stdin/launcher tests. A live model conversation, actual permission prompt,
actual payment tool execution and Agent SDK session: **NIET GEDRAAID**.
Reason: validation is read-only; a model/payment session was not needed for
this bounded build and could consume funds. No claim of end-to-end bank or
SDK permission enforcement is made.

## doesNotProve / remaining limits

- No real payment, settlement, human call-back, ownership or account existence.
- No external adoption measurement, package publication, directory submission,
  installation into the operator's live Claude configuration, or release to main.
- No GitHub CI, macOS execution, Windows file-symlink privilege test, Windows
  ACL audit or resistance to a same-user Windows path-swap race.
- No claim that all payment schemas, obfuscations, encodings or tool aliases
  are found by the heuristic matcher/extractor.
- Operator-controlled hooks, environment and history must remain outside the
  agent's write authority; an agent with unrestricted local execution can
  bypass local hooks. Harness-level termination/disabled hooks are not an ask.
- `allow` is only the requested unchanged-account rule; it can approve the
  whole matched tool call and does not enforce amount or invoice authorization.

README.md is a known collision hotspot with the separate skill work. This
branch changes only its repository-description line and an independent short
plugin section; it does not touch any skill files or existing tool counts.

FOLLOW-UP: Evaluate preflight_payment inside askJithox | One transport/envelope function is the replacement point; no migration implemented here.
FOLLOW-UP: Measure external claude-payee-hook tools_call after reviewed distribution | The one recorded live call is own_probe, not evidence of adoption.
