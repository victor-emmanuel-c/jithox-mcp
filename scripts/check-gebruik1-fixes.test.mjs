// Offline regressions for invoice provenance and explicit lookup-price claims.
// Fake discovery below tests the checker, never a live lookup or model result.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { extractCurlExamples, runChecks } from './check-skill.mjs';

const read = path => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8').replace(/\r\n/g, '\n');
const examples = () => read('skills/pay-invoices-safely/references/examples.md').split(/^## Scenario \d+: /m).slice(1);
const preflight = text => extractCurlExamples(text).map(call => JSON.parse(call.body))
  .filter(rpc => rpc.params.name === 'preflight_payment').map(rpc => rpc.params.arguments);

for (const index of [0, 1]) {
  test(`invoice scenario ${index + 1} preserves document source separately from human approval`, () => {
    const scenario = examples()[index];
    assert.ok(scenario.includes(index === 0 ? 'uit de factuur' : 'from the invoice'));
    const calls = preflight(scenario);
    assert.equal(calls.length, 1);
    const args = calls[0];
    assert.equal(args.instructionSource, 'ingested_content');
    assert.deepEqual(args.approved, {amount:'10000.00', currency:'DKK', payee:{name:'Example Supplier'}});
    assert.equal(args.payment.amount, '10000.00');
    assert.equal(args.payment.currency, 'DKK');
    assert.equal(args.payment.iban, index === 0 ? 'DK2753010244563821' : 'DK5000400440116243');
    assert.equal(args.ibanOnFile, 'DK5000400440116243');
    const expected = scenario.split('Expected:')[1].split('Limits:')[0];
    for (const value of ['`review_required`', '`instruction`', '`warn`', '`instruction_not_from_human`']) assert.ok(expected.includes(value), value);
    assert.ok(!expected.includes('`no_blockers_found`'));
  });
}

test('DKK 1210 sample is explicitly independent of the DKK 10000 payment run', () => {
  const scenario = examples()[0];
  assert.ok(scenario.includes('onafhankelijke controle'));
  assert.ok(scenario.includes('niet de factuur van deze betaalrun'));
  const args = preflight(scenario)[0];
  assert.equal(args.invoice, undefined, 'do not compare an unrelated invoice against this payment');
  const invoice = extractCurlExamples(scenario).map(call => JSON.parse(call.body).params)
    .find(params => params.name === 'check_peppol_ready').arguments;
  assert.equal(invoice.invoiceNumber, 'SAMPLE-001');
  assert.equal(invoice.currency, 'DKK');
  assert.equal(invoice.totalWithVat, 1210);
  assert.notEqual(Number(args.payment.amount), invoice.totalWithVat);
});

test('README invoice example separates approval, invoice provenance and historical output', () => {
  const readme = read('README.md');
  const [args] = preflight(readme);
  assert.equal(args.instructionSource, 'ingested_content');
  assert.equal(args.approved.amount, '1210.00');
  assert.equal(args.approved.purpose, 'Invoice 2026-105');
  assert.ok(readme.includes('Historical output from the old, incorrectly human-labelled request'));
  assert.ok(readme.includes('not the response to the corrected request above'));
});

test('Python sibling uses the same document source as the README request', () => {
  const source = read('examples/python/preflight_payment.py');
  assert.match(source, /"instructionSource": "ingested_content"/);
  assert.ok(!source.includes('"instructionSource": "human"'));
  assert.ok(read('README.md').includes('Historical output from the old Python example'));
});

const costs = {
  check_vat_list: '1 credit (EUR 0.01) per answered row; needs a bearer token.',
  kbo_company_search: '2 credits (EUR 0.02) per successful call; needs a bearer token.',
};
const quotes = Object.entries(costs).map(([name, cost]) => `- ${name}: ${cost}`).join('\n');
const skill = '---\nname: check-vat-numbers\ndescription: Check a VAT list.\n---\n' + quotes;
async function checkPrices({text = skill, extra = [], descriptions = costs} = {}) {
  const fetch = async (_url, init) => {
    assert.equal(JSON.parse(init.body).method, 'tools/list');
    return new Response(JSON.stringify({result:{tools:Object.entries(descriptions).map(([name, description]) => ({name, description}))}}), {headers:{'content-type':'application/json'}});
  };
  return runChecks({text, extra, dirName:'check-vat-numbers', fetch});
}

test('runChecks accepts the two exact grounded costs and ordinary invoice amounts', async () => {
  const text = skill + '\nSample invoice: NOK 7, SEK 7, DKK 1210; payment approval: 10000 DKK.\n' +
    '```json\n{"currency":"NOK","amount":7,"unitPrice":7}\n```';
  assert.deepEqual((await checkPrices({text})).errors, []);
});

for (const claim of ['This lookup costs NOK 7.', 'This lookup costs SEK 7.', 'This lookup costs ZAR 7.', 'This lookup costs XYZ 7.', 'This lookup costs 7 NOK.', 'Fee: SEK 7.', 'NOK 7 per lookup.']) {
  test(`runChecks rejects an unverified explicit price: ${claim}`, async () => {
    const result = await checkPrices({text:skill + '\n' + claim});
    assert.ok(result.errors.some(error => error.includes('price-like text')), JSON.stringify(result.errors));
  });
}

test('runChecks rejects added prices in another file, duplicate quotes and price drift', async () => {
  for (const options of [
    {extra:[{path:'references/examples.md',text:'This lookup costs NOK 7.'}]},
    {extra:[{path:'references/examples.md',text:quotes}]},
    {text:skill + '\n' + quotes},
    {text:skill.replace('EUR 0.01', 'EUR 0.99')},
    {descriptions:{}},
  ]) {
    const result = await checkPrices(options);
    assert.ok(result.errors.some(error => error.includes('price-like text')), JSON.stringify(options));
  }
});
