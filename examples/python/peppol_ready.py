"""Jithox MCP: check if an invoice will be accepted by Peppol before you send it.

Standard library only. Run: python peppol_ready.py
"""
import json
import urllib.request

URL = "https://jithox.com/api/mcp"


def call(method, params=None, id_=1):
    body = json.dumps({"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}).encode("utf-8")
    req = urllib.request.Request(
        URL, data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)


def main():
    init = call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                "clientInfo": {"name": "jithox-example", "version": "1.0"}})
    print("server:", init["result"]["serverInfo"]["name"])

    invoice = {
        "invoiceNumber": "INV-2026-0001",
        "issueDate": "2026-09-23",
        "currency": "EUR",
        "buyerReference": "PO-4471",
        "totalWithoutVat": 1000,
        "totalVat": 210,
        "totalWithVat": 1210,
        "lines": [{"description": "Consulting hours", "quantity": 10, "unitPrice": 100, "vatPercent": 21}],
        "supplier": {"name": "Seller BV", "countryCode": "BE", "endpointId": "0403170701", "endpointScheme": "0208"},
        "customer": {"name": "Buyer NV", "countryCode": "BE", "endpointId": "0400378485", "endpointScheme": "0208"},
    }
    res = call("tools/call", {"name": "check_peppol_ready", "arguments": invoice}, id_=2)
    data = json.loads(res["result"]["content"][0]["text"])["data"]
    print("verdict:", data["verdict"], "-", data["summary"])

    # Now look up whether the customer can actually receive a Peppol e-invoice.
    res2 = call("tools/call", {"name": "lookup_peppol_participant", "arguments": {"identifier": "0403170701"}}, id_=3)
    data2 = json.loads(res2["result"]["content"][0]["text"])["data"]
    print("reachable:", data2["reachable"], "participant:", data2["participantId"])


if __name__ == "__main__":
    main()
