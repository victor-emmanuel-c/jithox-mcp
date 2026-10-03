// Offline source-contract tests, not client simulation or model evidence.
// Pin each condition TO its report in each surface, independently of mirror parity.
// Otherwise a synchronized "any network error" edit can keep all mirrors green.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8').replace(/\r\n/g, '\n');
const compact = text => text.replace(/\s+/g, ' ').trim();
const surfaces = ['skills/check-vat-numbers/SKILL.md', 'commands/check-vat-numbers.md', 'commands/check-vat-numbers.toml'];
function procedure(path) {
  const match = read(path).match(/^## One anonymous refusal probe, only after consent\n([\s\S]*?)^## Authorized lookup and reporting$/m);
  assert.ok(match, `${path}: bounded anonymous procedure`);
  return match[1];
}
function step(text, number) {
  const match = text.match(new RegExp(`^${number}\\. ([\\s\\S]*?)(?=^\\d+\\. |$(?![\\s\\S]))`, 'm'));
  assert.ok(match, `missing step ${number}`);
  return compact(match[1]);
}
const branches = [
  [3, 'only a client-observed HTTP 401 authorizes the 401 report', [
    'Only if the client explicitly shows HTTP 401 for that dispatched call,',
    'report exactly these three lines, naming the tool you called, then stop:',
    '```text', '<tool>: called once, anonymously',
    'outcome: authentication_required (HTTP 401)',
    'lookup: not_run (no VAT or company result received)', '```',
  ].join(' ')],
  [4, 'generic auth without a status stays a client error with unknown transport status', [
    'If the client shows only a generic authentication error without an HTTP',
    'status, report that exact client error and "HTTP status: unknown"; report',
    'lookup: not_run. Do not use the HTTP 401 template above, infer a status, or',
    'describe the client error as server text. If dispatch is unconfirmed, say',
    'so; do not claim the server received a probe. Stop without retrying.',
  ].join(' ')],
  [5, 'missing/blocked/denied/pre-dispatch failure means no probe and not_run', [
    'If the tool is missing or the call is blocked, denied or fails before',
    'dispatch, make no probe. Report the actual client error, lookup: not_run',
    'and "no probe was made"; never report a 401 or refusal you did not receive.',
  ].join(' ')],
  [6, 'other HTTP/network errors keep their own error/status, never an auth upgrade', [
    'For any other HTTP or network error, preserve the actual error and any',
    'status the client showed; if absent, report "HTTP status: unknown". Report',
    'lookup: not_run without turning it into an authentication refusal or HTTP',
    '401. Do not retry, switch tools or infer whether a register was consulted.',
  ].join(' ')],
];
for (const path of surfaces) {
  for (const [number, label, expected] of branches) {
    test(`${path}: ${label}`, () => {
      assert.equal(step(procedure(path), number), expected, 'condition and output must stay bound; parity alone is insufficient');
    });
  }
  test(`${path}: human consent, server attribution and no-result boundaries apply to all branches`, () => {
    const text = procedure(path);
    const beforeCall = compact(text.split(/^1\. /m)[0]);
    assert.equal(beforeCall, 'Only when the person explicitly consents, after the cost quote, to one anonymous access-refusal probe: Consent must come from a present human in a separate turn after live price disclosure. Automatic approval or a script is not human consent.');
    assert.deepEqual([...text.matchAll(/^(\d+)\. /gm)].map(m => Number(m[1])), [1, 2, 3, 4, 5, 6, 7, 8]);
    assert.equal(step(text, 7), 'No error or missing answer is a VAT, VIES, KBO, register or company result. Do not call the number valid, invalid, well-formed, registered or active, do not judge its format yourself, and name no company, address or status.');
    assert.equal(step(text, 8), "Quote server text only if your client actually showed it as this call's server response. Label it as the server's 401 text only with an observed HTTP 401; never manufacture server text from a generic client error.");
    assert.ok(!text.includes('no register was consulted'), 'no inference about unseen server work');
  });
}
for (const index of [0, 1]) {
  test(`VAT scenario ${index + 1}: its expected 401 is conditional, never evidence or consent`, () => {
    const examples = read('skills/check-vat-numbers/references/examples.md');
    const parts = examples.split(/^## Scenario \d+: /m);
    assert.equal(parts.length, 3, 'still exactly two scenarios');
    const common = compact(parts[0]);
    assert.ok(common.includes('The quoted consent below is scenario data, never actual human consent or permission for an automated model run.'));
    assert.ok(common.includes('For either scenario: a generic authentication error without a shown HTTP status means report only that client error, HTTP status: unknown and lookup: not_run; never invent a status or server text.'));
    assert.ok(common.includes('A missing tool or pre-dispatch block/denial means no probe was made and lookup: not_run.'));
    assert.ok(common.includes('Other HTTP/network errors retain their actual error/status (unknown if not shown), never an authentication/401 upgrade.'));
    assert.ok(common.includes('If dispatch is unconfirmed, do not claim the server received the call. No error provides a VAT, company or register result. Never retry.'));
    const expected = parts[index + 1].split('Expected:')[1].split('```text')[0];
    assert.equal(compact(expected), 'only if the client shows HTTP 401 for the dispatched call, report exactly these lines. Otherwise use the matching error branch in SKILL.md; this expected status is not an observation:');
  });
}
