# Structured payment-field fix — t_bc51b642

Date: 2026-09-27. Existing branch: `jx/claude-payee-hook`.
Fetched and verified starting HEAD and remote at the requested HOLD commit
`41b1ee7617eeb1eaf7d5fcdb8f2bc47429880489`. Scope: F1 from review
`t_143a577a`, not a second distribution product. The exact delivered fix SHA
is recorded in the build-card handoff; this document cannot contain its own
final commit SHA.

## Changed boundary

- Default case-insensitive leaf names: `iban`, `newIban`, `beneficiaryIban`,
  `recipientIban`, `destinationIban`, `creditorIban`.
- Traverse structured objects/arrays of objects, never scan arbitrary strings.
  A recognized string leaf must be a whole account-shaped value; bare strings
  in arrays and embedded prose do not supply accounts.
- `ibanOnFile`, `description`, `prompt`, `message`, `notes`, `reference` and
  their subtrees are excluded. Unknown string fields cannot generate requests.
- Extra leaf names come only from the operator environment variable
  `JITHOX_PAYMENT_IBAN_FIELDS`, using the existing environment-config style.
  A same-named tool argument is not configuration. Reserved names are refused
  even in operator configuration, which fails closed before network/storage.
- No candidate: no permission decision, with `Jithox checked nothing`.
  Existing local checksum rejection is retained: account-shaped but mod-97
  invalid recognized leaves deny locally. Only valid accounts cross the wire.
- Multiple recognized accounts retain the worst verdict and common deadline.
  PostToolUse applies the same selector to that call's input; only explicit
  success with one unambiguous account/payee can be remembered. Accounts in
  the tool response are not learned. Caller noise cannot prevent learning the
  actual recognized account or introduce another stored account.

No endpoint, payment-check tool, version, transport, permission mapping or
memory implementation was changed. The original six mutants and safety tests
remain; three multi-account fixtures now use real structured payment keys
instead of the obsolete arbitrary-string extraction behavior.

## Test-first observation

Before changing the production extractor, ran four newly added test methods
against HOLD code on Windows. Actual result: `Ran 4 tests in 4.317s`, exit 1,
`FAILED (failures=8)`, zero errors. The eight assertion failures were:

- `test_caller_reference_different_account_leaves_wire_and_decision_unchanged`
- `test_free_text_different_account_leaves_wire_and_decision_unchanged`:
  five subtests (`description`, `prompt`, `message`, `notes`, `reference`)
- `test_unknown_field_leaves_wire_and_decision_unchanged`
- `test_local_extra_leaf_configuration_controls_pre_and_post`

The baseline payment and extra caller field contain different, mod-97-valid
fixture accounts. The unchanged payment's fixture response is `no_change`;
only the unrelated account would receive `stop`. Assertions compare request
count and complete captured requests, then the entire hook decision. No real
payment, production request or customer input was used in these regressions.

## Executed final platform results

All logs below are under `verification/`, with `f1-` prefixes so the original
build's evidence is not overwritten.

| Platform | Passed | Failed | Skipped | Total | Duration |
| --- | ---: | ---: | ---: | ---: | ---: |
| Windows 11 / Python 3.11.16 | 42 | 0 | 2 | 44 | 50.541 s |
| WSL Ubuntu-24.04 / Python 3.12.3 | 44 | 0 | 0 | 44 | 51.225 s |

Commands from the repository root:

```sh
python -m unittest discover -s tests/claude_payee -p 'test_*.py' -v
python tests/claude_payee/mutants.py
python tests/claude_payee/test_wire.py
```

On WSL, use `python3`; `PAYEE_TEST_TMP` was set to the executing user's
`$HOME/.cache/hermes-jithox-builder/payee-t_bc51b642` on the Linux filesystem,
not `/mnt/c`. Windows used the builder profile's Hermes scratch directory.
`PYTHONDONTWRITEBYTECODE=1` was set for both runs.

The Windows skips are POSIX mode enforcement and file-symlink creation
(privilege unavailable). The real Windows junction test passed. WSL exercised
0600/0700 checks, symlinks, hardlinks, atomic replacement and concurrent writers.
The existing transport-failure matrix, shared deadline, redaction, explicit
success rules and launcher fallback tests all remain green.

Additional checks: Python `compile()` succeeded for all seven Python files;
`git diff --check` passed. Credential-pattern scanning of all 15 staged files,
including the new logs, found zero matches (credential prefixes were matched
as tokens, not the incidental substring inside test names starting with `ask`).
Claude Code **2.1.278** executed both commands with
exit 0 and `Validation passed`:

```sh
claude plugin validate ./plugins/claude-payee-hook --strict
claude plugin validate . --strict
```

No new live probe was needed or executed: **0 production requests** in this
fix run. Original own-probe results remain historical in `VERIFICATION.md`,
not a new availability claim. Schema files are unchanged; this run repeated
the installed CLI validation, not a new upstream documentation review.

## Real HTTP wire capture

`test_wire.py` runs the real hook transport against its own ephemeral loopback
HTTP server, then stops and closes that server in a `finally` block. It patches
the endpoint in the test process only; production has no endpoint/config switch.
It uses a second pair of valid public-example fixtures, distinct from the
stdin regression pair. The server returns `no_change` for the known account
and `stop` for any other account.

On both Windows and WSL:

- Control: `allow`, exactly one HTTP request.
- Seven variants adding caller `ibanOnFile`, description, prompt, message,
  notes, reference or an unknown field: exactly one request each, byte-identical
  JSON request body, equal path/header values, identical complete decision,
  and no unrelated account in the request body.
- Unknown-only control: no request, `Jithox checked nothing`.
- Local extra-field control: exactly the same request and decision as control.
- Arguments are exactly `newIban`, the locally stored `ibanOnFile`, and
  `supplierCountry`; UA is `claude-payee-hook/0.1.0`, no probe header. No name,
  amount, tool name or description is included in the arguments.

Nine recorded cases per platform, plus the baseline. Reports contain only
counts/booleans/field names, not full account values. This is real local HTTP
capture, not a production wire capture or a TLS/network-availability test.

## Mutation evidence

**12/12 killed on Windows and 12/12 on WSL.** Every accepted kill has a named
assertion failure, the expected test count, and zero test errors. Disposable
syntax-checked copies are used; production files are never temporarily changed.
The selected baseline contains 13 test methods (one Windows file-symlink skip).

| Mutant | Target assertion test |
| --- | --- |
| `error_to_allow` | `test_transport_failures_are_ask_never_allow` |
| `caller_reference` | `test_local_record_cannot_be_replaced_by_caller_reference` |
| `stop_to_ask` | `test_stop_is_deny_not_ask` |
| `skip_mod97` | `test_mod97_failure_denies_without_request` |
| `remember_in_pre` | `test_known_account_pre_never_writes_memory` |
| `follow_memory_link` | `test_memory_parent_link_is_refused`, plus file-symlink test on WSL |
| `unknown_leaf_allowed` | `test_unknown_field_leaves_wire_and_decision_unchanged` |
| `ignore_local_fields` | `test_local_extra_leaf_configuration_controls_pre_and_post` |
| `caller_configures_fields` | `test_caller_cannot_configure_extra_leaf_fields` |
| `reserved_fields_enabled` | `test_local_configuration_cannot_enable_reserved_fields` |
| `post_uses_response_accounts` | `test_post_learns_only_recognized_account_from_that_successful_call` |
| `best_verdict_wins` | `test_nested_formatted_accounts_are_all_checked_worst_verdict_wins` |

The six added mutants each change one source line. An initial run correctly
rejected one result as a test error (missing output key), not a kill; the test
now asserts absence of a permission decision before inspecting the notice.
The final logs above contain only valid assertion-based kills.

## doesNotProve

- No payment, bank settlement, ownership, account existence, human callback,
  external adoption, customer installation or demand evidence.
- No live model/Agent SDK session or interactive permission-host enforcement.
- No macOS execution, Windows ACL audit, privileged Windows file-symlink test,
  or same-user Windows path-swap guarantee.
- No new production-availability measurement, main merge, deployment, package
  publication, marketplace submission or GitHub CI result.
- This is a local hook, not an isolation boundary against an agent that can
  change hook/configuration/history files or use another payment path.
- Independent security acceptance remains with existing child `t_2bc8b900`;
  the existing release chain remains exact-APPROVE-only.

FOLLOW-UP: Independent security herreview | Existing child t_2bc8b900 checks F1 independently before the existing release chain.
