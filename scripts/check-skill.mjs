// check-skill: every Agent Skill in skills/ against the Agent Skills spec AND the live Jithox site.
//
//   node scripts/check-skill.mjs                    all skills in skills/
//   node scripts/check-skill.mjs skills/<name>      one skill
//   node scripts/check-skill.mjs --header 'Name: value'   add a header to every request (repeatable)
//
// Node 18+, no dependencies. Exit 0 = green, 1 = red, 2 = could not run.
//
// What it checks, per skill:
//   1. Spec (https://agentskills.io/specification): frontmatter fields, name = directory name, [a-z0-9-] without
//      leading, trailing or double hyphens, name 1-64 and description 1-1024 characters, compatibility <= 500.
//   2. No price in the text (euro sign, EUR, USD, "$" + digit, "<n> credits"): prices live in mcp.json only.
//   3. Every curl example in SKILL.md and in the other .md files of the skill is RUN against production:
//      tools it calls must be in the live tools/list of https://jithox.com/api/mcp, the answer must be JSON (a
//      missing route answers a POST with the HTML 404 page), and a tool error other than payment_required is red.
//      Each example must set the skill's own user agent (-A '<name>/<metadata.version>') and only the headers
//      Content-Type, Accept and Authorization. The Authorization header is never sent.
//   4. Every URL and /api/ path in the text answers something other than 404 or 5xx.
//   5. Every snake_case word outside code blocks is a live tool or a word a live answer uses, and every `word`
//      in backticks occurs in a live answer (tools/list, the answers of the examples, the JSON URLs).
//
// What it does not prove: that the prose is true (only that the words it leans on exist live), that a paid
// call works with a real token (the token is never sent, so a paid tool answers payment_required), or that the
// output shown in ```json blocks equals what the site returns today.

import { readFileSync, readdirSync, existsSync, statSync } from "node:fs";
import { join, basename, resolve, dirname, relative } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

export const MCP_URL = "https://jithox.com/api/mcp";
export const SITE = "https://jithox.com";
const CHECKER_UA = "check-skill/1.0";
const ALLOWED_FIELDS = new Set(["name", "description", "license", "compatibility", "metadata", "allowed-tools"]);
const ALLOWED_EXAMPLE_HEADERS = new Set(["content-type", "accept", "authorization"]);
const IDENT = /^[A-Za-z][A-Za-z0-9_]*$/;
const SNAKE = /\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b/g;
const ALWAYS_GROUND = ["true", "false", "null"];

// ---- frontmatter -------------------------------------------------------------------------------

function unquote(raw, lineNo) {
  const v = raw.trim();
  if (v.startsWith('"')) {
    if (!/^"(?:[^"\\]|\\.)*"$/.test(v)) throw new Error(`frontmatter line ${lineNo}: unterminated double-quoted value`);
    return JSON.parse(v);
  }
  if (v.startsWith("'")) {
    if (!/^'(?:[^']|'')*'$/.test(v)) throw new Error(`frontmatter line ${lineNo}: unterminated single-quoted value`);
    return v.slice(1, -1).replace(/''/g, "'");
  }
  if (v === "" || /^[[{|>&*!%@`-]/.test(v) || /:\s|:$/.test(v) || /\s#/.test(v)) {
    throw new Error(`frontmatter line ${lineNo}: unsupported or invalid plain YAML value ${JSON.stringify(v.slice(0, 40))} (quote it)`);
  }
  return v;
}

/** The small YAML subset a SKILL.md needs: `key: value` and one level of `key:` + indented `sub: value`. */
export function parseFrontmatter(text) {
  const lines = text.split(/\r?\n/);
  if (lines[0] !== "---") throw new Error("SKILL.md must start with YAML frontmatter (---)");
  const end = lines.indexOf("---", 1);
  if (end < 0) throw new Error("frontmatter is not closed with ---");
  const data = {};
  let parent = null;
  for (let i = 1; i < end; i++) {
    const line = lines[i];
    if (line.trim() === "" || /^\s*#/.test(line)) continue;
    const nested = /^( {2,})([A-Za-z0-9_-]+):(.*)$/.exec(line);
    if (nested) {
      if (parent === null) throw new Error(`frontmatter line ${i + 1}: unsupported indentation`);
      data[parent][nested[2]] = unquote(nested[3], i + 1);
      continue;
    }
    const top = /^([A-Za-z0-9_-]+):(.*)$/.exec(line);
    if (!top) throw new Error(`frontmatter line ${i + 1}: unsupported YAML ${JSON.stringify(line.slice(0, 40))}`);
    const [, key, rest] = top;
    if (key in data) throw new Error(`frontmatter line ${i + 1}: duplicate key ${key}`);
    if (rest.trim() === "") {
      data[key] = {};
      parent = key;
    } else {
      data[key] = unquote(rest, i + 1);
      parent = null;
    }
  }
  return { data, body: lines.slice(end + 1).join("\n") };
}

export function checkSpec(data, dirName) {
  const errors = [];
  for (const key of Object.keys(data)) {
    if (!ALLOWED_FIELDS.has(key)) errors.push(`unexpected frontmatter field ${key}; allowed: ${[...ALLOWED_FIELDS].join(", ")}`);
  }
  const { name, description, compatibility, metadata, license } = data;
  if (typeof name !== "string" || name.length === 0) {
    errors.push("name must be a non-empty string");
  } else {
    if (name.length > 64) errors.push(`name is ${name.length} characters; the maximum is 64`);
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(name)) {
      errors.push(`name ${JSON.stringify(name)} may only use a-z, 0-9 and single hyphens, and must not start or end with a hyphen`);
    }
    if (name !== dirName) errors.push(`name ${JSON.stringify(name)} must equal the directory name ${JSON.stringify(dirName)}`);
  }
  if (typeof description !== "string" || description.trim().length === 0) {
    errors.push("description must be a non-empty string");
  } else if (description.length > 1024) {
    errors.push(`description is ${description.length} characters; the maximum is 1024`);
  }
  if (compatibility !== undefined && (typeof compatibility !== "string" || compatibility.length === 0 || compatibility.length > 500)) {
    errors.push("compatibility must be a string of 1-500 characters");
  }
  if (license !== undefined && typeof license !== "string") errors.push("license must be a string");
  if (metadata !== undefined) {
    const ok = typeof metadata === "object" && metadata !== null && Object.values(metadata).every((v) => typeof v === "string");
    if (!ok) errors.push("metadata must be a map of string keys to string values");
  }
  return errors;
}

// ---- prices ------------------------------------------------------------------------------------

const PRICE_PATTERNS = [/€/g, /EUR/g, /USD/g, /\$\s?\d/g, /\b\d+(?:[.,]\d+)?\s*credits?\b/gi];

export function findPrices(text) {
  const hits = [];
  for (const re of PRICE_PATTERNS) {
    for (const m of text.matchAll(re)) {
      const line = text.slice(0, m.index).split("\n").length;
      hits.push({ match: m[0], line });
    }
  }
  return hits;
}

// ---- curl examples -----------------------------------------------------------------------------

function fencedBlocks(text) {
  const blocks = [];
  const re = /^```([^\n]*)\n([\s\S]*?)^```[ \t]*$/gm;
  for (const m of text.replace(/\r\n/g, "\n").matchAll(re)) blocks.push({ lang: m[1].trim(), code: m[2], index: m.index, length: m[0].length });
  return blocks;
}

function shellWords(line) {
  const words = [];
  let cur = "";
  let started = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (c === "'") {
      const close = line.indexOf("'", i + 1);
      if (close < 0) throw new Error("unterminated single quote");
      cur += line.slice(i + 1, close);
      i = close;
      started = true;
    } else if (c === '"') {
      i++;
      while (i < line.length && line[i] !== '"') {
        if (line[i] === "\\" && i + 1 < line.length && '"\\$`'.includes(line[i + 1])) i++;
        cur += line[i++];
      }
      if (i >= line.length) throw new Error("unterminated double quote");
      started = true;
    } else if (c === "\\" && i + 1 < line.length) {
      cur += line[++i];
      started = true;
    } else if (/\s/.test(c)) {
      if (started) words.push(cur);
      cur = "";
      started = false;
    } else {
      cur += c;
      started = true;
    }
  }
  if (started) words.push(cur);
  return words;
}

const FLAG_ONLY = new Set(["-s", "-S", "-sS", "-Ss", "--silent", "--show-error", "-i", "--include", "-f", "--fail"]);

function parseCurl(words) {
  const ex = { url: null, method: null, userAgent: null, headers: {}, body: null, toolNames: [] };
  const data = [];
  for (let i = 1; i < words.length; i++) {
    const w = words[i];
    const next = () => {
      if (i + 1 >= words.length) throw new Error(`curl option ${w} has no value`);
      return words[++i];
    };
    if (FLAG_ONLY.has(w)) continue;
    if (w === "-A" || w === "--user-agent") ex.userAgent = next();
    else if (w === "-H" || w === "--header") {
      const h = next();
      const colon = h.indexOf(":");
      if (colon < 1) throw new Error(`header without a name: ${h}`);
      ex.headers[h.slice(0, colon).trim().toLowerCase()] = h.slice(colon + 1).trim();
    } else if (w === "-d" || w === "--data" || w === "--data-raw" || w === "--data-binary") {
      const d = next();
      if (d.startsWith("@")) throw new Error(`body read from a file (${d}); inline it so it can be checked`);
      data.push(d);
    } else if (w === "-X" || w === "--request") ex.method = next().toUpperCase();
    else if (w.startsWith("-")) throw new Error(`unsupported curl option ${w}`);
    else if (ex.url === null) ex.url = w;
    else throw new Error(`a second URL in one curl command: ${w}`);
  }
  if (ex.url === null) throw new Error("curl command without a URL");
  if (data.length > 0) {
    ex.body = data.join("&");
    if (!("content-type" in ex.headers)) ex.headers["content-type"] = "application/x-www-form-urlencoded";
  }
  ex.method ??= data.length > 0 ? "POST" : "GET";
  try {
    const rpc = JSON.parse(ex.body ?? "");
    if (rpc && rpc.method === "tools/call" && typeof rpc.params?.name === "string") ex.toolNames.push(rpc.params.name);
  } catch {
    // not JSON: no tool in it
  }
  return ex;
}

/** Every curl command inside a fenced code block, parsed the way a POSIX shell would read it. */
export function extractCurlExamples(text) {
  const out = [];
  for (const block of fencedBlocks(text)) {
    const joined = block.code.replace(/\\\n/g, " ");
    for (const line of joined.split("\n")) {
      const trimmed = line.trim();
      if (!/^curl\s/.test(trimmed)) continue;
      out.push({ ...parseCurl(shellWords(trimmed)), index: out.length + 1 });
    }
  }
  return out;
}

// ---- URLs --------------------------------------------------------------------------------------

export function extractUrls(text) {
  const urls = new Set();
  const clean = (u) => u.replace(/#.*$/, "").replace(/[.,;:!?)\]]+$/, "");
  for (const m of text.matchAll(/https?:\/\/[^\s'"`<>)\]]+/g)) urls.add(clean(m[0]));
  for (const m of text.matchAll(/(?:^|[\s`(])(\/api\/[A-Za-z0-9_\-./]+)/gm)) urls.add(SITE + clean(m[1]));
  return [...urls];
}

// ---- grounding ---------------------------------------------------------------------------------

/** Keys and whole identifier values of a live answer, JSON inside strings included; never words from free text. */
export function collectGround(node, ground = new Set(ALWAYS_GROUND)) {
  const walk = (value, key, { isToolEntry = false, isToolReference = false } = {}) => {
    if (typeof value === "string") {
      const s = value.trim();
      if (IDENT.test(s) && !isToolReference && !(isToolEntry && key === "name")) ground.add(s);
      if (s.startsWith("{") || s.startsWith("[")) {
        try {
          walk(JSON.parse(s), key);
        } catch {
          // free text that happens to start with a bracket
        }
      }
      for (const m of value.matchAll(/`([A-Za-z][A-Za-z0-9]*)`/g)) ground.add(m[1]);
    } else if (Array.isArray(value)) {
      for (const item of value) {
        walk(item, key, {
          isToolEntry: key === "tools" && item && typeof item === "object",
          isToolReference: key === "tools" && typeof item === "string",
        });
      }
    } else if (value && typeof value === "object") {
      for (const [k, v] of Object.entries(value)) {
        if (IDENT.test(k)) ground.add(k);
        walk(v, k, { isToolEntry, isToolReference: k === "tool" });
      }
    }
  };
  walk(node, null);
  return ground;
}

function unknownArguments(argumentsValue, schema, path = "") {
  if (!argumentsValue || typeof argumentsValue !== "object" || !schema || typeof schema !== "object") return [];
  if (Array.isArray(argumentsValue)) {
    if (!schema.items) return [];
    return argumentsValue.flatMap((item, index) => unknownArguments(item, schema.items, `${path}[${index}]`));
  }
  if (!schema.properties || typeof schema.properties !== "object") return [];
  const errors = [];
  for (const [key, value] of Object.entries(argumentsValue)) {
    const childPath = path ? `${path}.${key}` : key;
    if (!(key in schema.properties)) {
      errors.push(childPath);
      continue;
    }
    errors.push(...unknownArguments(value, schema.properties[key], childPath));
  }
  return errors;
}

function prose(md) {
  let out = md.replace(/\r\n/g, "\n");
  for (const b of fencedBlocks(out).reverse()) out = out.slice(0, b.index) + "\n".repeat(b.code.split("\n").length + 1) + out.slice(b.index + b.length);
  return out.replace(/https?:\/\/[^\s'"`<>)\]]+/g, " ");
}

export function checkGrounding(md, { toolNames, ground }) {
  const errors = [];
  const text = prose(md);
  const seen = new Set();
  for (const m of text.matchAll(SNAKE)) {
    const w = m[0];
    if (seen.has(w)) continue;
    seen.add(w);
    if (!toolNames.has(w) && !ground.has(w)) errors.push(`${w} is not a live tool and no live answer uses it`);
  }
  for (const m of text.matchAll(/`([^`\n]+)`/g)) {
    const w = m[1].trim();
    if (!IDENT.test(w) || w.includes("_") || seen.has(w)) continue;
    seen.add(w);
    if (!toolNames.has(w) && !ground.has(w)) errors.push(`\`${w}\` does not occur in any live answer`);
  }
  return errors;
}

// ---- live ----------------------------------------------------------------------------------------

async function readJson(res) {
  const type = res.headers.get("content-type") ?? "";
  const text = await res.text();
  if (type.includes("text/event-stream")) {
    const data = text.split(/\r?\n/).filter((l) => l.startsWith("data:")).map((l) => l.slice(5).trim()).pop();
    return { type, json: JSON.parse(data) };
  }
  if (!type.includes("json")) return { type, json: undefined };
  return { type, json: JSON.parse(text) };
}

function toolResultPayload(result) {
  const text = result?.content?.[0]?.text;
  if (typeof text !== "string") return { raw: result };
  try {
    return { parsed: JSON.parse(text) };
  } catch {
    return { raw: text };
  }
}

function summarise(payload) {
  if (!payload || typeof payload !== "object") return "";
  const parts = [];
  if (payload.kind) parts.push(`kind=${payload.kind}`);
  if (payload.data?.verdict) parts.push(`verdict=${payload.data.verdict}`);
  const review = payload.review ?? (payload.kind === "invoice_review" ? payload.data : undefined);
  if (review && typeof review === "object") {
    parts.push(`readyToSend=${review.readyToSend} hasUnknowns=${review.hasUnknowns}`);
    if (Array.isArray(review.checks)) parts.push(review.checks.map((c) => `${c.id}:${c.status}`).join(" "));
  }
  if (payload.error?.code ?? payload.error) parts.push(`error=${payload.error?.code ?? payload.error}`);
  return parts.join(" ");
}

/**
 * Run every check for one skill. `text` is SKILL.md, `extra` the other .md files of the skill as {path, text}.
 * Returns {errors, info}; errors empty = green.
 */
export async function runChecks({ text, dirName, fetch = globalThis.fetch, extra = [], headers = {}, mcpUrl = MCP_URL }) {
  const errors = [];
  const info = [];
  const base = { "user-agent": CHECKER_UA };
  for (const [k, v] of Object.entries(headers)) base[k.toLowerCase()] = v;
  const files = [{ path: "SKILL.md", text }, ...extra];

  // 1. spec
  let data = {};
  let body = "";
  try {
    ({ data, body } = parseFrontmatter(text));
    for (const e of checkSpec(data, dirName)) errors.push(`SKILL.md: ${e}`);
    if (typeof data.description === "string") info.push(`description: ${data.description.length} characters (max 1024)`);
  } catch (e) {
    errors.push(`SKILL.md: ${e.message}`);
  }
  const version = data.metadata && typeof data.metadata.version === "string" ? data.metadata.version : null;
  const expectedUa = typeof data.name === "string" ? `${data.name}/${version ?? ""}` : null;
  if (typeof data.name === "string" && /^(jithox|hermes)-/.test(data.name)) {
    errors.push("SKILL.md: names starting with jithox- or hermes- are reserved for Jithox's own tools");
  }

  // 2. prices
  for (const f of files) {
    for (const hit of findPrices(f.text)) errors.push(`${f.path}:${hit.line}: price-like text ${JSON.stringify(hit.match)}; point to the pricing field in mcp.json instead`);
  }

  // 3. live tools/list
  const toolNames = new Set();
  const toolSchemas = new Map();
  const ground = new Set(ALWAYS_GROUND);
  try {
    const res = await fetch(mcpUrl, {
      method: "POST",
      headers: { ...base, "content-type": "application/json", accept: "application/json, text/event-stream" },
      body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/list" }),
    });
    const { type, json } = await readJson(res);
    if (json === undefined) throw new Error(`answered HTTP ${res.status} ${type}, not JSON`);
    const tools = json?.result?.tools;
    if (!Array.isArray(tools)) throw new Error(`answered without result.tools (HTTP ${res.status})`);
    for (const t of tools) {
      if (typeof t?.name !== "string") continue;
      toolNames.add(t.name);
      toolSchemas.set(t.name, t.inputSchema);
    }
    collectGround(json, ground);
    info.push(`live tools/list: ${toolNames.size} tools`);
  } catch (e) {
    errors.push(`tools/list on ${mcpUrl}: ${e.message}`);
  }

  // 4. every curl example, run
  for (const f of files) {
    let examples = [];
    try {
      examples = extractCurlExamples(f.text);
    } catch (e) {
      errors.push(`${f.path}: a curl example cannot be read: ${e.message}`);
      continue;
    }
    for (const ex of examples) {
      const where = `${f.path} curl example ${ex.index}`;
      if (expectedUa && ex.userAgent !== expectedUa) errors.push(`${where}: must set -A '${expectedUa}' (has ${JSON.stringify(ex.userAgent)})`);
      for (const h of Object.keys(ex.headers)) {
        if (!ALLOWED_EXAMPLE_HEADERS.has(h)) errors.push(`${where}: sends header ${h}; only ${[...ALLOWED_EXAMPLE_HEADERS].join(", ")} are allowed`);
      }
      for (const tool of ex.toolNames) {
        if (!toolNames.has(tool)) errors.push(`${where}: tool ${tool} is not in the live tools/list of ${mcpUrl}`);
      }
      try {
        const rpc = JSON.parse(ex.body ?? "");
        if (rpc?.method === "tools/call" && typeof rpc.params?.name === "string") {
          for (const path of unknownArguments(rpc.params.arguments, toolSchemas.get(rpc.params.name))) {
            errors.push(`${where}: argument ${path} is not in the live inputSchema of ${rpc.params.name}; the server drops it`);
          }
        }
      } catch {
        // The live request below reports unreadable or non-JSON bodies.
      }
      const send = { ...base };
      for (const h of ["content-type", "accept"]) if (ex.headers[h] !== undefined) send[h] = ex.headers[h];
      let res;
      try {
        res = await fetch(ex.url, { method: ex.method, headers: send, ...(ex.body !== null ? { body: ex.body } : {}) });
      } catch (e) {
        errors.push(`${where}: ${ex.method} ${ex.url} failed: ${e.message}`);
        continue;
      }
      if (res.status === 404 || res.status >= 500) {
        errors.push(`${where}: ${ex.method} ${ex.url} answered ${res.status}`);
        continue;
      }
      let parsed;
      try {
        parsed = await readJson(res);
      } catch (e) {
        errors.push(`${where}: ${ex.method} ${ex.url} answered unreadable JSON: ${e.message}`);
        continue;
      }
      if (parsed.json === undefined) {
        errors.push(`${where}: ${ex.method} ${ex.url} answered ${parsed.type || "no content type"}, not JSON (a missing route answers POST with the HTML 404 page, status 200)`);
        continue;
      }
      const json = parsed.json;
      collectGround(json, ground);
      if (json && typeof json === "object" && "jsonrpc" in json) {
        if (json.error) {
          errors.push(`${where}: JSON-RPC error ${JSON.stringify(json.error).slice(0, 200)}`);
          continue;
        }
        const payload = toolResultPayload(json.result);
        if (json.result?.isError) {
          const code = payload.parsed?.error?.code;
          if (code === "payment_required") {
            if (!("authorization" in ex.headers)) errors.push(`${where}: calls a paid tool without an Authorization header`);
            info.push(`${where}: HTTP ${res.status} payment_required (paid tool, no token sent by this checker)`);
          } else {
            errors.push(`${where}: tool answered an error: ${code ?? JSON.stringify(payload.raw ?? payload.parsed).slice(0, 200)}`);
          }
          continue;
        }
        info.push(`${where}: HTTP ${res.status} ${summarise(payload.parsed)}`);
      } else if (res.status === 401 || res.status === 403) {
        info.push(`${where}: HTTP ${res.status} ${summarise(json)} (needs real credentials)`);
      } else if (res.status >= 400) {
        errors.push(`${where}: ${ex.method} ${ex.url} answered ${res.status} ${JSON.stringify(json).slice(0, 200)}`);
      } else {
        info.push(`${where}: HTTP ${res.status} ${summarise(json)}`);
      }
    }
  }

  // 5. every URL and /api/ path
  const urls = new Set();
  for (const f of files) for (const u of extractUrls(f.text)) urls.add(u);
  for (const url of urls) {
    try {
      const res = await fetch(url, { method: "GET", headers: { ...base, accept: "application/json, text/html;q=0.9, */*;q=0.1" } });
      if (res.status === 404 || res.status >= 500) {
        errors.push(`${url} answered ${res.status}`);
        continue;
      }
      if ((res.headers.get("content-type") ?? "").includes("json")) {
        try {
          collectGround(await res.json(), ground);
        } catch {
          // a JSON content type with a body that is not JSON: the status check above is all this URL gives
        }
      }
      info.push(`GET ${url}: ${res.status}`);
    } catch (e) {
      errors.push(`GET ${url} failed: ${e.message}`);
    }
  }

  // 6. every word the text leans on
  const description = typeof data.description === "string" ? data.description : "";
  for (const e of checkGrounding(`${description}\n${body || text}`, { toolNames, ground })) errors.push(`SKILL.md: ${e}`);
  for (const f of extra) for (const e of checkGrounding(f.text, { toolNames, ground })) errors.push(`${f.path}: ${e}`);

  return { errors, info };
}

// ---- CLI -----------------------------------------------------------------------------------------

function markdownFiles(dir, root = dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...markdownFiles(full, root));
    else if (entry.endsWith(".md") && relative(root, full) !== "SKILL.md") out.push(full);
  }
  return out;
}

async function main(argv) {
  const repo = resolve(dirname(fileURLToPath(import.meta.url)), "..");
  const headers = {};
  const dirs = [];
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--header") {
      const h = argv[++i] ?? "";
      const colon = h.indexOf(":");
      if (colon < 1) {
        console.error(`--header needs 'Name: value', got ${JSON.stringify(h)}`);
        return 2;
      }
      headers[h.slice(0, colon).trim()] = h.slice(colon + 1).trim();
    } else dirs.push(resolve(argv[i]));
  }
  if (dirs.length === 0) {
    const skills = join(repo, "skills");
    if (existsSync(skills)) for (const d of readdirSync(skills)) if (existsSync(join(skills, d, "SKILL.md"))) dirs.push(join(skills, d));
  }
  if (dirs.length === 0) {
    console.error("no skill directory found");
    return 2;
  }
  const timed = (url, init) => globalThis.fetch(url, { ...init, signal: AbortSignal.timeout(30_000) });
  let red = false;
  for (const dir of dirs) {
    const skillMd = join(dir, "SKILL.md");
    if (!existsSync(skillMd)) {
      console.error(`${dir}: no SKILL.md`);
      red = true;
      continue;
    }
    const extra = markdownFiles(dir).map((p) => ({ path: relative(dir, p).replace(/\\/g, "/"), text: readFileSync(p, "utf8") }));
    const { errors, info } = await runChecks({ text: readFileSync(skillMd, "utf8"), dirName: basename(dir), fetch: timed, extra, headers });
    console.log(`# ${relative(repo, dir).replace(/\\/g, "/")}`);
    for (const line of info) console.log(`  ok   ${line}`);
    for (const line of errors) console.log(`  FAIL ${line}`);
    console.log(errors.length === 0 ? "  GREEN" : `  RED: ${errors.length} problem(s)`);
    if (errors.length > 0) red = true;
  }
  return red ? 1 : 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main(process.argv.slice(2)).then(
    (code) => process.exit(code),
    (e) => {
      console.error(e);
      process.exit(2);
    },
  );
}
