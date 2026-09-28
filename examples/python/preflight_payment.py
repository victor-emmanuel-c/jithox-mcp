"""Check a payment before your agent makes it: Jithox preflight_payment, standard library only.

No account, no token. Runs: initialize -> tools/call preflight_payment (a supplier's bank account
changed) -> POST /api/v1/evidence/verify (is the signed verdict intact?).
Usage:  python preflight_payment.py
The IBANs are the usual Belgian example numbers, not real supplier accounts.
"""
import json
import os
import urllib.request

MCP = "https://jithox.com/api/mcp"
VERIFY = "https://jithox.com/api/v1/evidence/verify"
EXTRA = {"x-jithox-probe": os.environ["JITHOX_PROBE"]} if os.environ.get("JITHOX_PROBE") else {}


def post(url, body, accept="application/json"):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": accept, **EXTRA},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
    if raw.startswith("event:"):  # Streamable HTTP may answer as one SSE event
        raw = raw.split("data: ", 1)[1].split("\n", 1)[0]
    return json.loads(raw)


def rpc(method, params, id_):
    body = {"jsonrpc": "2.0", "id": id_, "method": method, "params": params}
    return post(MCP, body, accept="application/json, text/event-stream")


init = rpc("initialize", {
    "protocolVersion": "2025-06-18",
    "capabilities": {},
    "clientInfo": {"name": "jithox-mcp-preflight-example", "version": "1.0.0"},
}, 1)
print("server:", init["result"]["serverInfo"]["name"])

# The person approved paying invoice 2026-105 to Acme BV. The invoice now asks for a different account.
payment = {
    "rail": "invoice_bank",
    "approved": {"amount": "1210.00", "currency": "EUR", "payee": {"name": "Acme BV"},
                 "purpose": "Invoice 2026-105"},
    "instructionSource": "human",
    "payment": {"iban": "BE71 0961 2345 6769", "amount": "1210.00", "currency": "EUR",
                "payeeName": "Acme BV", "supplierCountry": "BE"},
    "ibanOnFile": "BE68539007547034",
}
result = rpc("tools/call", {"name": "preflight_payment", "arguments": payment}, 2)["result"]
if result.get("isError"):
    raise SystemExit("tool error: " + result["content"][0]["text"])

answer = json.loads(result["content"][0]["text"])
data = answer["data"]
print("verdict:", data["verdict"])
print("reasons:", [r["code"] for r in data["reasons"]])
print("checks:", {c["id"]: c["status"] for c in data["checks"]})
print("humanStep:", data["humanStep"])
print("charged:", data["billing"]["charged"])

# The verdict is signed. Anyone can check that it was not changed, and that it was about THIS input.
check = post(VERIFY, {"jws": answer["evidence"]["jws"], "input": payment,
                      "inputSalt": answer["evidence"]["inputSalt"]})
print("evidence:", check["status"], "inputMatch:", check["inputMatch"])
