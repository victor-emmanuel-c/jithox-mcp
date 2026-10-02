# Executed test evidence — 2026-10-02

The original harness-only observations below are retained as history. Parent
integration subsequently ran 31/31 offline tests after three additional observed
RED→GREEN cycles: failed connection dispatch count (1 != 0), an uncited blocked
unknown tool incorrectly passing the gate (True != False), and missing all
candidate calls for one task incorrectly passing (True != False). Dispatch count
now increments only after request submission; the gate rejects blocked unknown
tool attempts and requires candidate evidence for every task on each client.
A final overlay regression also failed with 'http' != 'streamable-http': the
portable mcp.json now retains streamable-http, while Claude .mcp.json uses http.
The README task-documentation link was separately caught RED and corrected.
The aggregate false-claim criterion remains the approved per-client count,
not a newly invented paired-row criterion.

Parent live validator and host observations are in ../../docs/PLUGIN_VALIDATION.md.
Those include anonymous real tools/call/401 probes and a native Codex local install
plus ephemeral zero-turn handshake. They supersede the harness-only statement
that only tools/list/help had run; they are still NOT a scored model comparison.

## Scope and environment

Windows 11, Python **3.14.7**. Tests use only the standard library, real loopback
HTTP sockets and disposable directories under the supplied scratch directory.
Matrix tests create/delete two tiny commits in an **isolated temporary test
repository** to verify actual git resolution; no commit was made in the project.
The final four Python files also parsed with Python's `feature_version=(3,11)`.
That is syntax compatibility, not a claim that a Python 3.11 interpreter ran.
No Node dependency was added.

Fake upstream responses are deliberately **offline fixtures**, not captured live
service/model evidence. No offline receipt or fabricated positive score was
published as a real evaluation result.

## RED before implementation

The test module was written before `proxy.py`, `matrix.py` or `prepare.py` existed.
Running:

```sh
python scripts/test_gebruik1_eval.py
```

returned **exit 1**, with:

```text
import proxy
ModuleNotFoundError: No module named 'proxy'
```

The initially specified assertions covered header injection, credentials,
closed destination, malformed input, paid consent, response classes, cleanup,
privacy, ten prompts, forty rows, gate criteria and transport overlay.

## Additional observed failing regressions, then fixes

These are actual failures seen during development, not predicted RED results.

| Test/regression | Observed failure | Implemented fix |
|---|---|---|
| Recursive credential fields | `200 != 403` | Reject credential-named fields before forwarding; also reject a tools/call without params. |
| Unhashable row identity | `TypeError: cannot use 'list' as a dict key` | Validate identifier types before dictionary membership. |
| Uncited wrong tool | Gate returned true | Inspect all supplied row receipts, not just event IDs selected by the scorer. |
| Re-arming an already-used paid probe | `ValueError not raised` | One paid-boundary attempt per tool/session; no rearm/retry after consumption. |
| Slowly trickling upstream body | `200 != 504` | Add a whole request/header/body deadline, not only socket inactivity timeout; cancel/join its watchdog on exit. |
| Receipt visibility race | `IndexError: list index out of range` | Flush the sanitized receipt before delivering the response. |
| Early rejection on Windows | `ConnectionAbortedError`, WinError 10053 | Drain only bounded, explicitly framed rejected bodies before closing the connection. |
| Exported baseline skill bytes | CRLF bytes differed from committed LF bytes | Disable local Git autocrlf conversion for reproducible archive export. |

A first matrix fixture also needed its second P08 preflight receipt added: P08
contains two complete rails, so one test receipt cannot represent both. This was
a fixture correction, not a real client score or relaxation of the rubric.

## Final GREEN

Final command:

```sh
python -B scripts/test_gebruik1_eval.py
```

returned **exit 0**:

```text
Ran 28 tests in 14.232s
OK
```

Earlier full 26-test runs also passed twice consecutively after the transport
race/Windows fixes. The final 28-test run adds committed export verification and
CLI refusal of piped consent/arbitrary upstream options.

The assertions exercise:

- Unique client/ref/prompt/session/call User-Agent labels plus x-jithox-probe on
  initialize, notification, tools/list and tools/call, including concurrent calls.
- Real fake-upstream HTTP requests, not merely mocked transport return values.
  Tests replace only the HTTPS connection constructor to point at that fake server;
  production still has one fixed HTTPS host/path and no upstream CLI setting.
- Rejected Authorization, Cookie, Proxy-Authorization, API-key/auth-token headers;
  recursive credential JSON; dropped unknown headers; stripped response cookies,
  authentication challenge and redirect headers; no credential logging.
- Blocked arbitrary path/query/Host/Origin, CONNECT, unknown methods/tools, batch
  JSON, malformed JSON, oversize inputs, paid review and invalid paid fixtures.
- Interactive exact human consent; anonymous valid VAT/KBO fixtures; one-shot
  allowance; blocked reuse; HTTP 401 passed through and correctly classified.
- HTTP errors, redirects without following them, invalid responses, JSON-RPC/tool
  errors, response limit, ordinary timeout, trickle deadline and closed listeners
  both on normal exit and exception. Watchdog/server threads are joined.
- Privacy checks inject sentinel strings into request, response, RPC ID, headers
  and exceptions and assert none appear in persisted receipts.
- Exactly ten unique prompts, two per stable task, NL/EN distribution and FR/DE
  triggers; four rail labels; example identifiers preserved; agent preflight's
  one-tool boundary; exactly forty unique rows, initially all score fields null.
- Strict improvement per client, nonincreasing false claims, zero unsafe claims,
  missing/duplicate/unobserved rows, invalid score types/duration, wrong ref,
  missing receipts, genuine-upstream-401 requirements and extra-tool detection.
- Export from the actual pinned baseline, eval/tests excluded from exported
  runtime, unchanged skill bytes after export and transport overlay, no overwrite
  of an existing destination, no arbitrary loopback destination.

`matrix.py --help`, `proxy.py --help` and `prepare.py --help` returned successfully.
No proxy is left running by the tests; lifecycle/closed-port assertions passed.

## What was not tested or claimed

- No model inference, OAuth login, subscription request or live tools/call.
- No real 40-row comparison, demonstrated improvement or completed scoring file.
  Generating a real matrix requires the owner's distinct committed candidate;
  the package never invents that SHA or evaluates uncommitted changes as a commit.
- No real paid-boundary 401: only anonymous live tools/list discovery was performed.
- Gemini was absent; its official automatic session recording is a privacy blocker
  for zero-raw-transcript execution until the operator supplies a verified solution.
- Claude/Codex checks were availability/version/help only, not client integration.
- No full MCP SSE/session interoperability, TLS fake-server integration, CI on
  Linux/macOS, or runtime execution on Python 3.11. The bounded JSON transport
  intentionally fails closed on unsupported operations.
- Native client transcript/auth storage is outside the relay's control. Sanitized
  relay logs cannot prove skill activation or final-answer semantics; these require
  honest human attestation. Unsigned local files cannot prevent evidence forgery.

Primary-source URLs and live discovery facts are in `SOURCES.md`; the human-run
protocol and its blockers are in `README.md`.
