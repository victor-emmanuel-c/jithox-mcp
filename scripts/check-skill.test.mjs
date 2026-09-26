// Tests for check-skill.mjs. Run: node --test scripts/check-skill.test.mjs
// Fixed inputs and a fake site only; the live run is `node scripts/check-skill.mjs`.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  parseFrontmatter,
  checkSpec,
  findPrices,
  extractCurlExamples,
  checkGrounding,
  collectGround,
  extractUrls,
  runChecks,
} from "./check-skill.mjs";

// Built from parts so no secret filter rewrites it in an editor or a log.
const AUTH_VALUE = "Bea" + "rer $JITHOX_TOKEN";

const FM = [
  "---",
  "name: pay-invoices-safely",
  "description: Checks an invoice before paying it. Use when paying an invoice.",
  "license: MIT",
  "metadata:",
  "  author: jithox",
  '  version: "1.0"',
  "---",
  "# Body",
  "",
].join("\r\n");

test("parseFrontmatter reads scalars and one nested map, also with CRLF", () => {
  const { data, body } = parseFrontmatter(FM);
  assert.equal(data.name, "pay-invoices-safely");
  assert.equal(data.description, "Checks an invoice before paying it. Use when paying an invoice.");
  assert.equal(data.license, "MIT");
  assert.deepEqual(data.metadata, { author: "jithox", version: "1.0" });
  assert.match(body, /# Body/);
});

test("parseFrontmatter refuses a file without frontmatter", () => {
  assert.throws(() => parseFrontmatter("# no frontmatter\n"), /frontmatter/);
});

test("parseFrontmatter refuses a construct it does not understand instead of guessing", () => {
  assert.throws(() => parseFrontmatter("---\nname: x\ntags: [a, b]\n---\n"), /unsupported/);
});

test("checkSpec accepts a valid skill", () => {
  const { data } = parseFrontmatter(FM);
  assert.deepEqual(checkSpec(data, "pay-invoices-safely"), []);
});

test("checkSpec: name must equal the directory name", () => {
  const { data } = parseFrontmatter(FM);
  assert.match(checkSpec(data, "other-dir").join("\n"), /directory/);
});

test("checkSpec: name characters, hyphens and length", () => {
  const base = { description: "d" };
  for (const bad of ["Pay-Invoices", "-pay", "pay-", "pay--invoices", "pay_invoices", "a".repeat(65), ""]) {
    assert.notDeepEqual(checkSpec({ ...base, name: bad }, bad), [], `accepted bad name ${JSON.stringify(bad)}`);
  }
  assert.deepEqual(checkSpec({ ...base, name: "a".repeat(64) }, "a".repeat(64)), []);
});

test("checkSpec: description must be 1-1024 characters", () => {
  assert.deepEqual(checkSpec({ name: "x", description: "d".repeat(1024) }, "x"), []);
  assert.match(checkSpec({ name: "x", description: "d".repeat(1025) }, "x").join("\n"), /1024/);
  assert.match(checkSpec({ name: "x", description: "" }, "x").join("\n"), /description/);
  assert.match(checkSpec({ name: "x" }, "x").join("\n"), /description/);
});

test("checkSpec: unknown fields, long compatibility, non-string metadata values", () => {
  assert.match(checkSpec({ name: "x", description: "d", tags: "a" }, "x").join("\n"), /tags/);
  assert.match(checkSpec({ name: "x", description: "d", compatibility: "c".repeat(501) }, "x").join("\n"), /500/);
  assert.match(checkSpec({ name: "x", description: "d", metadata: "flat" }, "x").join("\n"), /metadata/);
});

test("findPrices finds a euro sign, EUR, $0 and a credit count; a clean text gives none", () => {
  assert.equal(findPrices("costs €0.08").length, 1);
  assert.equal(findPrices("costs 0.08 EUR").length, 1);
  assert.equal(findPrices("costs $0.01").length, 1);
  assert.equal(findPrices("costs 8 credits").length, 1);
  assert.deepEqual(findPrices("read the pricing field of review_invoice in mcp.json"), []);
});

const CURL_MD = [
  "Text before.",
  "```bash",
  "curl -s https://jithox.com/api/mcp \\",
  "  -A 'pay-invoices-safely/1.0' \\",
  "  -H 'Content-Type: application/json' \\",
  `  -H "Authorization: ${AUTH_VALUE}" \\`,
  "  -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"check_payment_change\",\"arguments\":{\"newIban\":\"BE71 0961 2345 6769\"}}}'",
  "```",
  "```bash",
  "curl -s https://jithox.com/api/oauth/token -A 'pay-invoices-safely/1.0' \\",
  "  -d grant_type=client_credentials -d client_id=$JITHOX_CLIENT_ID",
  "```",
].join("\n");

test("extractCurlExamples reads URL, method, user agent, headers and body of each curl block", () => {
  const ex = extractCurlExamples(CURL_MD);
  assert.equal(ex.length, 2);
  assert.equal(ex[0].url, "https://jithox.com/api/mcp");
  assert.equal(ex[0].method, "POST");
  assert.equal(ex[0].userAgent, "pay-invoices-safely/1.0");
  assert.equal(ex[0].headers["content-type"], "application/json");
  assert.equal(ex[0].headers.authorization, AUTH_VALUE);
  assert.equal(JSON.parse(ex[0].body).params.name, "check_payment_change");
  assert.deepEqual(ex[0].toolNames, ["check_payment_change"]);
  assert.equal(ex[1].body, "grant_type=client_credentials&client_id=$JITHOX_CLIENT_ID");
  assert.equal(ex[1].headers["content-type"], "application/x-www-form-urlencoded");
});

test("collectGround keeps keys and whole identifier values, never words from free text", () => {
  const g = collectGround({ data: { verdict: "verify_first", summary: "call preflight_invoice now", n: 3 } });
  assert.ok(g.has("verdict") && g.has("verify_first") && g.has("data"));
  assert.ok(!g.has("preflight_invoice"));
});

test("collectGround reads JSON that a tool returns as a string (MCP content[0].text)", () => {
  const text = JSON.stringify({ kind: "payment_change_check", data: { verdict: "stop" } });
  const g = collectGround({ result: { content: [{ type: "text", text }] } });
  assert.ok(g.has("stop") && g.has("verdict") && g.has("payment_change_check"));
});

test("collectGround takes a backticked word from live text, but never a snake_case one", () => {
  const g = collectGround({ description: "a lookup that fails is reported as `unknown`; pairs with `send_email_resend`" });
  assert.ok(g.has("unknown"));
  assert.ok(!g.has("send_email_resend"));
});

test("collectGround: a tool name in a tools array is not ground (only the live tools/list makes a tool live)", () => {
  const g = collectGround({ tools: [{ name: "send_email_resend", pricing: "included" }] });
  assert.ok(g.has("pricing") && g.has("tools"));
  assert.ok(!g.has("send_email_resend"));
});

test("checkGrounding: a live tool passes, a live field or value passes, anything else is named", () => {
  const md = [
    "Call `check_payment_change`. On `verify_first`, stop.",
    "Then call preflight_invoice and read `allow`.",
    "```bash",
    "not_checked_inside_code",
    "```",
  ].join("\n");
  const errors = checkGrounding(md, { toolNames: new Set(["check_payment_change"]), ground: new Set(["verify_first"]) });
  assert.equal(errors.length, 2, errors.join("\n"));
  assert.match(errors.join("\n"), /preflight_invoice/);
  assert.match(errors.join("\n"), /allow/);
  assert.match(errors.join("\n"), /not a live tool/);
});

test("extractUrls returns each jithox.com URL once, without fragment or trailing punctuation, plus bare /api paths", () => {
  const urls = extractUrls("See https://jithox.com/mcp.json. And https://jithox.com/mcp/account#connection, then `/api/invoice/review`.");
  assert.deepEqual(urls.sort(), ["https://jithox.com/api/invoice/review", "https://jithox.com/mcp.json", "https://jithox.com/mcp/account"]);
});

// ---- runChecks against a fake site -----------------------------------------------------------

const SKILL = (extra = "") =>
  [
    "---",
    "name: demo-skill",
    "description: Demo. Use when testing.",
    "metadata:",
    '  version: "1.0"',
    "---",
    "Call `check_payment_change`; on `verify_first` a person calls back. Price is in `pricing` at https://jithox.com/mcp.json.",
    extra,
    "```bash",
    "curl -s https://jithox.com/api/mcp -A 'demo-skill/1.0' -H 'Content-Type: application/json' \\",
    "  -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"check_payment_change\",\"arguments\":{\"newIban\":\"X\"}}}'",
    "```",
  ].join("\n");

function fakeSite({ tools = ["check_payment_change"], status404 = [], htmlPost = false } = {}) {
  const calls = [];
  const fetch = async (url, init = {}) => {
    calls.push({ url, init });
    const json = (status, body, ct = "application/json") =>
      new Response(typeof body === "string" ? body : JSON.stringify(body), { status, headers: { "content-type": ct } });
    if (status404.includes(url)) return json(404, "<html>not found</html>", "text/html");
    if (url === "https://jithox.com/mcp.json") return json(200, { tools: [{ name: "check_payment_change", pricing: "included" }] });
    if (url === "https://jithox.com/api/mcp" && init.method === "POST") {
      if (htmlPost) return json(200, "<html></html>", "text/html");
      const rpc = JSON.parse(init.body);
      if (rpc.method === "tools/list") {
        return json(200, { jsonrpc: "2.0", id: rpc.id, result: { tools: tools.map((name) => ({ name, description: "d", inputSchema: { type: "object", properties: { newIban: { type: "string" } } } })) } });
      }
      const text = JSON.stringify({ kind: "payment_change_check", data: { verdict: "verify_first" } });
      return json(200, { jsonrpc: "2.0", id: rpc.id, result: { content: [{ type: "text", text }] } });
    }
    if (url === "https://jithox.com/api/mcp") return json(406, { error: "not acceptable" });
    return json(404, "<html>not found</html>", "text/html");
  };
  return { fetch, calls };
}

test("runChecks is green for a skill whose tools, words, examples and URLs are all live", async () => {
  const { fetch } = fakeSite();
  const r = await runChecks({ text: SKILL(), dirName: "demo-skill", fetch });
  assert.deepEqual(r.errors, []);
});

test("runChecks is red when a curl example calls a tool that is not in the live tools/list", async () => {
  const { fetch } = fakeSite({ tools: ["verify_iban"] });
  const r = await runChecks({ text: SKILL(), dirName: "demo-skill", fetch });
  assert.match(r.errors.join("\n"), /check_payment_change.*not in the live tools\/list/);
});

test("runChecks is red when prose names a tool that is not live", async () => {
  const { fetch } = fakeSite();
  const r = await runChecks({ text: SKILL("Then call `preflight_invoice`."), dirName: "demo-skill", fetch });
  assert.match(r.errors.join("\n"), /preflight_invoice/);
});

test("runChecks is red when a mentioned URL answers 404", async () => {
  const { fetch } = fakeSite({ status404: ["https://jithox.com/mcp.json"] });
  const r = await runChecks({ text: SKILL(), dirName: "demo-skill", fetch });
  assert.match(r.errors.join("\n"), /mcp\.json.*404/);
});

test("runChecks is red when a POST example gets HTML back (a missing route answers POST with the HTML 404 page)", async () => {
  const { fetch } = fakeSite({ htmlPost: true });
  const r = await runChecks({ text: SKILL(), dirName: "demo-skill", fetch });
  assert.match(r.errors.join("\n"), /text\/html/);
});

test("runChecks is red when a curl example lacks the skill's user agent or sends a header outside the allowlist", async () => {
  const { fetch } = fakeSite();
  const noUa = SKILL().replace(" -A 'demo-skill/1.0'", "");
  assert.match((await runChecks({ text: noUa, dirName: "demo-skill", fetch })).errors.join("\n"), /-A 'demo-skill\/1\.0'/);
  const extraHeader = SKILL().replace("-A 'demo-skill/1.0'", "-A 'demo-skill/1.0' -H 'x-debug: me'");
  assert.match((await runChecks({ text: extraHeader, dirName: "demo-skill", fetch })).errors.join("\n"), /x-debug/);
});

test("runChecks: an example in a reference file runs too and grounds the words of SKILL.md", async () => {
  const { fetch } = fakeSite();
  const text = SKILL("On `payment_change_check` nothing else.");
  assert.deepEqual((await runChecks({ text, dirName: "demo-skill", fetch })).errors, []);
  const words = SKILL("Also `extra_word`.");
  const ref = { path: "references/examples.md", text: "More: `extra_word` is not live either." };
  const r = await runChecks({ text: words, dirName: "demo-skill", fetch, extra: [ref] });
  assert.match(r.errors.join("\n"), /extra_word/);
  assert.match(r.errors.join("\n"), /references\/examples\.md/);
});

test("runChecks is red when a tool call answers with an error that is not payment_required", async () => {
  const { fetch: base } = fakeSite();
  const fetch = async (url, init = {}) => {
    if (init.method === "POST" && JSON.parse(init.body).method === "tools/call") {
      const text = JSON.stringify({ error: { code: "invalid_arguments", message: "newIban is required" } });
      return new Response(JSON.stringify({ jsonrpc: "2.0", id: 1, result: { isError: true, content: [{ type: "text", text }] } }), { status: 200, headers: { "content-type": "application/json" } });
    }
    return base(url, init);
  };
  const r = await runChecks({ text: SKILL(), dirName: "demo-skill", fetch });
  assert.match(r.errors.join("\n"), /invalid_arguments/);
});

test("runChecks is red on a price in the skill", async () => {
  const { fetch } = fakeSite();
  const r = await runChecks({ text: SKILL("It costs €0.08."), dirName: "demo-skill", fetch });
  assert.match(r.errors.join("\n"), /price/);
});

function paidSite() {
  const { fetch: base } = fakeSite();
  return async (url, init = {}) => {
    if (init.method === "POST" && JSON.parse(init.body).method === "tools/call") {
      const text = JSON.stringify({ error: { code: "payment_required", message: "needs a token" } });
      return new Response(JSON.stringify({ jsonrpc: "2.0", id: 1, result: { isError: true, content: [{ type: "text", text }] } }), { status: 401, headers: { "content-type": "application/json" } });
    }
    return base(url, init);
  };
}

test("runChecks: a paid tool refused with payment_required is fine only when the example sends an Authorization header", async () => {
  const noAuth = await runChecks({ text: SKILL("On `payment_required` get a token."), dirName: "demo-skill", fetch: paidSite() });
  assert.match(noAuth.errors.join("\n"), /Authorization/);
  const withAuth = SKILL("On `payment_required` get a token.").replace("-H 'Content-Type: application/json'", `-H 'Content-Type: application/json' -H "Authorization: ${AUTH_VALUE}"`);
  const ok = await runChecks({ text: withAuth, dirName: "demo-skill", fetch: paidSite() });
  assert.deepEqual(ok.errors.filter((e) => !/verify_first/.test(e)), []);
});

test("runChecks never sends the example's Authorization header and adds extra headers only when asked", async () => {
  const withAuth = SKILL().replace("-H 'Content-Type: application/json'", `-H 'Content-Type: application/json' -H "Authorization: ${AUTH_VALUE}"`);
  const a = fakeSite();
  await runChecks({ text: withAuth, dirName: "demo-skill", fetch: a.fetch });
  for (const c of a.calls) {
    const h = c.init.headers ?? {};
    assert.equal(h.authorization, undefined);
    assert.equal(h["x-run-id"], undefined);
    assert.match(h["user-agent"], /^check-skill\//);
  }
  const b = fakeSite();
  await runChecks({ text: SKILL(), dirName: "demo-skill", fetch: b.fetch, headers: { "X-Run-Id": "t_1" } });
  assert.ok(b.calls.every((c) => c.init.headers["x-run-id"] === "t_1"));
});
