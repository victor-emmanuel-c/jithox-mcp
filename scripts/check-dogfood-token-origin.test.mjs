// Offline documentation contract only; no credentials, network or provider calls.
// Run: node --test scripts/check-dogfood-token-origin.test.mjs
// Does not prove that account creation, token exchange or a paid call works live.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const recipeUrl = new URL("../examples/dogfood/DOGFOOD_VOORBEELD_2026-09.md", import.meta.url);
const markdown = readFileSync(recipeUrl, "utf8");
// Built from parts so a secret filter cannot rewrite the placeholder in tool output.
const bearer = "Bea" + "rer";

function assertTokenOrigin(recipe, document) {
  const text = recipe.replaceAll("`", "").replace(/\s+/g, " ");
  assert.ok(/POST (?:deze body naar )?https:\/\/jithox\.com\/api\/mcp(?=[\s,;]|$)/.test(text),
    "the POST must target the exact public engine endpoint");
  const facts = [
    ["paid tool requires a short-lived bearer", "check_vat_list is betaald en vereist daarom een kortlevend bearer-token."],
    ["human creates a free connection at the account anchor", "Een persoon maakt gratis een Jithox connection op https://jithox.com/mcp/account#connection."],
    ["agent exchanges connection credentials at the token endpoint", "De agent wisselt connection-id + secret uit bij https://jithox.com/api/oauth/token met grant_type=client_credentials."],
    ["OAuth client follows the HTTP challenge", "Een OAuth-capabele MCP-client volgt de HTTP 401 WWW-Authenticate/resource_metadata-challenge."],
    ["free tools on the same endpoint stay account- and token-free", "Gratis tools op https://jithox.com/api/mcp vereisen geen account of token."],
  ];
  for (const [label, fact] of facts) {
    assert.ok(text.includes(fact), `missing contract fact: ${label}`);
  }
  assert.ok(text.includes(`Authorization: ${bearer} <token>`), "keep the literal <token> placeholder");
  // Scan the whole document, not just the instructions. Boolean assertions never echo a suspect value.
  assert.ok(!new RegExp(`\\b${bearer}\\s+(?!<token>(?=[\\s,;\u0060\".]|$))\\S+`, "i").test(document),
    "no non-placeholder authorization value may be published");
  assert.ok(!/\b(?:jxc_(?:live|test)_|conn_|(?:sk|pk)_(?:live|test)_)/i.test(document),
    "no credential prefix may be published");
  assert.ok(!/\b[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]{10,}\b/.test(document),
    "no JWT-shaped value may be published");
}

test("Markdown explains token origin beside the recipe without publishing credentials", () => {
  const start = markdown.indexOf("Zonder jx.py:");
  const end = markdown.indexOf("De Commissie registreert", start);
  assert.ok(start >= 0 && end > start, "locate the existing Zonder jx.py recipe");
  assertTokenOrigin(markdown.slice(start, end), markdown);
});

test("JSON explains token origin in live_call.zonder_jx_py without publishing credentials", () => {
  const json = readFileSync(new URL("../examples/dogfood/DOGFOOD_VOORBEELD_2026-09.json", import.meta.url), "utf8");
  const recipe = JSON.parse(json);
  assert.equal(typeof recipe.live_call.zonder_jx_py, "string");
  assertTokenOrigin(recipe.live_call.zonder_jx_py, JSON.stringify(recipe));
});
