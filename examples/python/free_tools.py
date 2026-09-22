"""Call the free Jithox MCP tools from Python, standard library only.

No account, no token. Runs: initialize -> tools/list -> tools/call (verify_iban).
Usage:  python free_tools.py
"""
import json
import urllib.request

URL = "https://jithox.com/api/mcp"


def rpc(method, params=None, id_=1):
    body = {"jsonrpc": "2.0", "id": id_, "method": method}
    if params is not None:
        body["params"] = params
    req = urllib.request.Request(
        URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


init = rpc("initialize", {
    "protocolVersion": "2025-06-18",
    "capabilities": {},
    "clientInfo": {"name": "jithox-mcp-python-example", "version": "1.0.0"},
})
print("server:", init["result"]["serverInfo"]["name"])

tools = rpc("tools/list", id_=2)["result"]["tools"]
print("tools listed:", len(tools))

result = rpc("tools/call", {
    "name": "verify_iban",
    "arguments": {"iban": "BE68 5390 0754 7034"},
}, id_=3)["result"]

if result.get("isError"):
    print("tool error:", result["content"][0]["text"])
else:
    answer = json.loads(result["content"][0]["text"])
    print("status:", answer["data"]["status"])
    print("doesNotProve:", answer["data"]["doesNotProve"])
