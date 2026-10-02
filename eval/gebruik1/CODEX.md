# Codex: native local install and an ephemeral evaluation conversation

This is the second locally available client route, alongside Claude Code. On
2026-10-02, `codex-cli 0.155.0` was present. The native marketplace add/install/list
commands were exercised anonymously on an exported baseline, without a model
turn. A native app-server initialize + ephemeral thread/start smoke returned
`ephemeral=true`, no rollout path and zero turns; after shutdown there were zero
rollout files. These observations do NOT prove OAuth access, inference, natural
skill activation or the forty scored rows. The independent reviewer runs those.

## Sources and installed interface

Read on 2026-10-02:

- https://developers.openai.com/plugins/build/plugins — root portable plugin.json,
  mcp.json and skills; local catalogs, including legacy .claude-plugin/marketplace.json;
  installed cached copies, not direct loading from a marketplace source.
- https://developers.openai.com/codex/auth/ — ChatGPT login versus API-key login;
  credential stores are secret, not evaluation evidence.
- https://developers.openai.com/codex/app-server/ — stdio handshake, thread/start,
  turn/start, streamed item events and human approval responses.
- https://developers.openai.com/codex/config-reference/ — history.persistence,
  analytics.enabled and forced_login_method. History suppression by itself is
  NOT a promise that thread rollouts are ephemeral.
- https://developers.openai.com/codex/noninteractive/ — exec --ephemeral is a
  separate noninteractive route. Do not use two unrelated exec invocations as
  if they were the same consent conversation.

The installed binary's `plugin marketplace add --help`, `plugin add --help`,
`plugin list --help`, `plugin remove --help` and
`app-server generate-json-schema --experimental --out ABS_SCHEMA_DIR` were also
read. Generated ThreadStartParams includes ephemeral, cwd, sandbox and
approvalPolicy; TurnStartParams requires threadId and input. Recheck the schema
if the installed version changes rather than silently guessing protocol fields.

## Isolate and install using the real client

Use a dedicated evaluation OS/profile and a distinct CODEX_HOME for each ref,
not the personal home. Export the revision with prepare.py and apply the current
prompt's running relay URL BEFORE installing. Keep the source revision's skill
and command bytes unchanged. The existing .claude-plugin/marketplace.json works
with this Codex version; no extra production marketplace/manifest is necessary.

In a dedicated POSIX/Git Bash terminal, replace uppercase paths with absolute
paths. Never substitute credentials in these commands:

```sh
export CODEX_HOME=ABS_EVAL_CODEX_HOME
unset OPENAI_API_KEY CODEX_API_KEY CODEX_ACCESS_TOKEN OPENAI_BASE_URL
codex plugin marketplace add ABS_EXPORTED_SNAPSHOT --json
codex plugin add jithox@jithox --json
codex plugin list --marketplace jithox --json
```

The native list must say installed=true and enabled=true and identify the exact
local snapshot. Read back the returned installedPath, not a guessed cache path.
Check its mcp.json/.mcp.json against the current loopback URL and compare all
skills/commands bytes with the exported snapshot. Check that no other plugin,
MCP server, hooks, personal skills, API provider or project instructions enter
this environment. A copied directory or a list alone is not a successful task.

Between prompts, stop the model and relay. Start a fresh relay, re-overlay the
snapshot, then `codex plugin remove jithox@jithox --json` and reinstall it. Removal
is documented to delete the local cache. Read back the new installed bytes and
URL every time; a stale port is a failed setup, not permission to call production
directly. Between refs use separate homes/snapshots. Do not modify global configs.

## Subscription authentication (operator only)

Use the client's own `codex -c 'forced_login_method="chatgpt"' login` browser flow
in the isolated home. The evaluator supplies existing subscription authorization;
no API-key input, credential-file copying, token export or purchase is allowed.
Inspect `codex login status` privately; do not log that output or account/read
responses. Stop if the route is not ChatGPT OAuth, the plan is unavailable, or a
quota/charge requires a decision. Credential storage remains managed by the
client; it must not enter the plugin, relay, reports or transcripts.

## Same-thread, human-operated, in-memory turns

Use Codex's native app-server stdio protocol rather than a TUI that writes
rollouts. The evaluator can operate stdio directly in a non-recording terminal
or use a local protocol UI that has been verified not to save raw events. Do not
redirect/tee stdout, enable JSONL/debug capture, use shell history for prompt
text, or run a protocol UI with remote telemetry. The stdin below belongs to the
client, not a shell: one JSON message per line. Keep an operator watching live
item events and permission requests throughout; never auto-accept them.

```sh
RUST_LOG=off codex app-server --stdio -c 'history.persistence="none"' -c 'analytics.enabled=false' -c 'forced_login_method="chatgpt"'
```

Send the handshake; await the response for id 1 before initialized/thread/start:

```json
{"id":1,"method":"initialize","params":{"clientInfo":{"name":"gebruik1_eval","version":"1.0"}}}
{"method":"initialized","params":{}}
{"id":2,"method":"thread/start","params":{"cwd":"ABS_EMPTY_WORK_DIR","ephemeral":true,"sandbox":"read-only","approvalPolicy":"untrusted"}}
```

Read back result.thread.id, require result.thread.ephemeral=true and no stored
rollout path. Do NOT send a turn if this fails. MCP must be the installed
plugin's current loopback transport. Skills discovery/listing may be inspected
without scoring activation. Do not send skill/mention inputs or inject package
instructions yourself: that would coach discovery.

For the prompt, send turn/start with the returned threadId and only the unchanged
`prompt` text from prompts.json (proper JSON escaping). This is the wire shape;
uppercase values below are placeholders, not input to score:

```json
{"id":3,"method":"turn/start","params":{"threadId":"RETURNED_THREAD_ID","input":[{"type":"text","text":"UNCHANGED_PROMPT_STRING"}]}}
```

Watch item/started, item/completed, item/agentMessage/delta and turn/completed.
A native mcpToolCall item identifies the tool, actual arguments and result/error.
Inspect these on screen, retain only the allowed score fields and relay IDs.
Skill use needs actual loading/read evidence, not a response claiming it used a
skill. Permit reading its installed skill/reference files; deny execution,
write, direct-network and unrelated-data requests. Keep read-only sandboxing.
For item/commandExecution/requestApproval and item/fileChange/requestApproval,
reply to the actual request ID with result {"decision":"decline"} when the
operation is outside that limited read scope. Never approve policy amendments,
payments, MCP OAuth, shell curl workarounds or record changes. Unknown approval
shapes are a stop condition: consult this binary's schema, do not accept blindly.

For P09/P10, the first turn must quote cost and ask permission, with no paid
request. After that turn completes, the human may arm the separate relay and
send the fixed anonymous-probe consent from README in a second turn/start with
the SAME threadId. Do not put consent in the first turn or force the model to
call a named tool. Follow native confirmations if any. The relay remains the
independent one-shot enforcement boundary. One upstream 401 is not a VAT result.

After the final turn/completed, stop the client by closing stdin, wait for exit,
then stop the relay. Inspect the isolated home for unexpected rollout/history
or raw debug files WITHOUT copying their contents into evidence. If the native
client wrote raw conversation/account content despite ephemeral settings, stop
and resolve privacy before any further row; do not label the route validated.
The no-turn smoke establishes protocol support only, not this post-inference
storage property. Do not leave app-server, a daemon or a relay running.

## Scoring and limitations

Use `matrix.py seed --clients claude codex` with the same pinned refs and ten
prompts. Native local install/cache readback is necessary but never contributes
a positive tool-call score. Only real client-generated tools/call receipts count.
No scored runs are supplied by this build. Authentication, model availability,
MCP 401 handling, activation, timing and full native post-turn storage still
require live observation; failures remain null/false as appropriate, not passes.
A compatibility failure must not be replaced with synthetic model responses.
