// Offline regressions for the check-vat-numbers anonymous refusal path (gebruik1 P09/P10).
// They pin the agent's exact single call, the 401 -> authentication_required/not_run report and the
// absence of register claims. No live request is made here; eval/gebruik1 is only read.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { extractCurlExamples, parseFrontmatter } from './check-skill.mjs';

const read = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8').replace(/\r\n/g, '\n');
const blocks = text => [...text.matchAll(/^```([^\n]*)\n([\s\S]*?)^```[ \t]*$/gm)].map(m => ({lang: m[1].trim(), code: m[2], index: m.index}));
const scenarios = () => read('skills/check-vat-numbers/references/examples.md').split(/^## Scenario \d+: /m).slice(1);
// The benchmark writes arguments as {rows:[{vatId:'BE0403170701'}]}; same notation from JSON.
const benchNotation = value => JSON.stringify(value).replace(/"([A-Za-z]+)":/g, '$1:').replace(/"/g, "'");
const report = tool => [
  `${tool}: called once, anonymously`,
  'outcome: authentication_required (HTTP 401)',
  'lookup: not_run (no VAT or company result received)',
].join('\n');
// Words that would turn a refusal into a register, VAT or company result.
const RESULT_CLAIM = /\b(valid|invalid|well-formed|registered|active|exists?|found|retrieved|success(ful)?|charged|paid|vies|kbo)\b/i;

const CASES = [
  {index: 0, prompt: 'P09', language: 'nl', tool: 'check_vat_list', args: {rows: [{vatId: 'BE0403170701'}]}, input: 'Controleer btw-nummer BE0403170701'},
  {index: 1, prompt: 'P10', language: 'en', tool: 'kbo_company_search', args: {vatNumber: 'BE0403170701'}, input: 'Look up company BE0403170701'},
];

for (const c of CASES) {
  test(`${c.tool} scenario: one native call with the exact supplied argument`, () => {
    const scenario = scenarios()[c.index];
    assert.ok(scenario.includes(c.input), c.input);
    const consentAt = scenario.indexOf('the test person says');
    const agentAt = scenario.indexOf('Agent call, exactly once, as a native MCP tool call:');
    assert.ok(consentAt > 0 && agentAt > consentAt, 'the call is shown only after the separate consent');
    const json = blocks(scenario).filter(b => b.lang === 'json');
    assert.equal(json.length, 1, 'exactly one agent call');
    assert.ok(json[0].index > agentAt);
    const call = JSON.parse(json[0].code);
    assert.deepEqual(Object.keys(call).sort(), ['arguments', 'name']);
    assert.equal(call.name, c.tool);
    assert.deepEqual(call.arguments, c.args, 'no requesterVatId, countryCode, reference, token or extra row');
    const bench = JSON.parse(read('eval/gebruik1/prompts.json')).find(p => p.id === c.prompt);
    assert.equal(bench.language, c.language);
    assert.deepEqual(bench.required_tools, [c.tool]);
    assert.ok(bench.argument_checks.some(check => check.includes(`arguments=${benchNotation(c.args)}`)), benchNotation(c.args));
  });

  test(`${c.tool} scenario: the build check probes exactly that call anonymously, once`, () => {
    const scenario = scenarios()[c.index];
    const native = blocks(scenario).find(b => b.lang === 'json');
    assert.ok(native, 'the scenario must contain a native agent call');
    const call = JSON.parse(native.code);
    const curls = extractCurlExamples(scenario);
    assert.equal(curls.length, 1, 'one probe, no retry and no second tool');
    const rpc = JSON.parse(curls[0].body);
    assert.equal(rpc.method, 'tools/call');
    assert.deepEqual(rpc.params, call);
    assert.equal(curls[0].headers.authorization, undefined);
    assert.equal(curls[0].headers['x-jithox-probe'], 'gebruik1-build');
    const bashAt = blocks(scenario).find(b => b.lang === 'bash').index;
    assert.ok(scenario.lastIndexOf('Build check only (maintainers; an agent never runs this):', bashAt) > 0, 'curl is labelled as build check');
  });

  test(`${c.tool} scenario: one 401 is reported as authentication_required/not_run without result claims`, () => {
    const scenario = scenarios()[c.index];
    const expected = scenario.split('Expected:')[1].split('Limits:')[0];
    assert.equal((expected.match(/HTTP 401/g) ?? []).length, 2, 'the 401 sentence and the outcome line');
    const text = blocks(expected).filter(b => b.lang === 'text');
    assert.equal(text.length, 1);
    assert.equal(text[0].code.trim(), report(c.tool));
    assert.ok(!RESULT_CLAIM.test(text[0].code), 'report claims no register result');
    assert.ok(!/payment_required|connection step|connection instructions/.test(expected), 'no server text promised by the example');
    const limits = scenario.split('Limits:')[1];
    assert.ok(limits.includes('retry'), 'limits forbid a retry');
    assert.match(limits, /[Nn]o (login|name)/, 'limits forbid login or deny a retrieved name');
  });
}

test('SKILL.md template: one consented native call, exact report, no unreceived 401', () => {
  const {body} = parseFrontmatter(read('skills/check-vat-numbers/SKILL.md'));
  for (const phrase of [
    'Make every call as a native MCP tool call from your host. Never use curl, a',
    'Make exactly ONE native MCP tool call with the number the person supplied,',
    'Never both tools, never a retry.',
    'Add no requesterVatId, countryCode, reference, token or extra row.',
    'never report a 401 or refusal you did not receive.',
    'Do not call the\n   number valid, invalid, well-formed, registered or active',
    'End that turn with the\nconsent question and no tools/call.',
    'their curl blocks are\nthis package\'s build check, not your call and not a result.',
  ]) assert.ok(body.includes(phrase), phrase);
  const text = blocks(body).filter(b => b.lang === 'text');
  assert.equal(text.length, 2);
  assert.deepEqual(text[0].code.trim().split('\n').map(line => line.trim().split(/\s+/)), [
    ['check_vat_list', '{"rows":[{"vatId":"<supplied', 'number>"}]}'],
    ['kbo_company_search', '{"vatNumber":"<supplied', 'number>"}'],
  ]);
  assert.equal(text[1].code.trim(), report('<tool>'));
  for (const c of CASES) assert.equal(text[1].code.trim().replace('<tool>', c.tool), report(c.tool));
  // A 401 challenge is not a pre-consent price source, and the examples are not the agent's call.
  assert.ok(!body.includes('or a\nvalid anonymous HTTP 401 challenge'));
  assert.ok(!body.includes('The reference examples are exactly such public-input probes'));
});

test('both host command mirrors carry the same refusal procedure', () => {
  const md = read('commands/check-vat-numbers.md');
  const toml = read('commands/check-vat-numbers.toml');
  for (const text of [md, toml]) {
    assert.ok(text.includes('Make exactly ONE native MCP tool call with the number the person supplied,'));
    assert.ok(text.includes(report('<tool>')));
    assert.ok(text.includes('](../skills/check-vat-numbers/references/examples.md): their curl blocks are'));
  }
});

test('free task skills route checks through native MCP calls, never their curl build checks', () => {
  for (const name of ['pay-invoices-safely', 'verify-bank-detail-change', 'send-peppol-invoice']) {
    const skill = read(`skills/${name}/SKILL.md`).replace(/\s+/g, ' ');
    assert.ok(skill.includes('The tool definitions your host loaded from this MCP server are that live list.'), name);
    assert.ok(skill.includes('native MCP tool call; never use curl, a shell, a script or another direct request for it.'), name);
    assert.ok(!/\bRunnable\b|Run only read-only anonymous probes/.test(skill), name);
    const examples = read(`skills/${name}/references/examples.md`).replace(/\s+/g, ' ');
    assert.ok(examples.includes("Each curl block is this package's build check for maintainers, never run by an agent"), name);
    assert.ok(examples.includes("no Expected line is a result for anyone's request"), name);
    for (const ext of ['md', 'toml']) {
      const command = read(`commands/${name}.${ext}`).replace(/\s+/g, ' ');
      assert.ok(command.includes('native MCP tool call; never use curl'), `${name}.${ext}`);
    }
  }
});
