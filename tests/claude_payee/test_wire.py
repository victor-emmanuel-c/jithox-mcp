"""Real loopback HTTP capture; no production traffic or payment execution."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(os.environ.get("PAYEE_TEST_SOURCE", ROOT / "plugins/claude-payee-hook/scripts/payee_hook.py"))


def capture():
    spec = importlib.util.spec_from_file_location("payee_wire_hook", SOURCE)
    assert spec is not None and spec.loader is not None
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    # Public example fixtures; distinct from the stdin regression accounts.
    current = "NL91ABNA0417164300"
    unrelated = "FR1420041010050500013M02606"
    assert current != unrelated and hook.mod97(current) and hook.mod97(unrelated)
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_POST(self):
            raw = self.rfile.read(int(self.headers["Content-Length"]))
            requests.append((self.path, sorted(self.headers.items()), raw))
            args = json.loads(raw)["params"]["arguments"]
            verdict = "no_change" if args["newIban"] == current else "stop"
            result = {"kind": "payment_change_check", "data": {
                "verdict": verdict, "requiredSteps": ["Call using your own records."]}}
            body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {
                "content": [{"type": "text", "text": json.dumps(result)}]}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    reports = []
    try:
        with tempfile.TemporaryDirectory(dir=os.environ.get("PAYEE_TEST_TMP")) as temp:
            memory = Path(temp) / "state"
            env = {**os.environ, "JITHOX_PAYEE_MEMORY_DIR": str(memory)}
            for key in ("JITHOX_PAYMENT_IBAN_FIELDS", "JITHOX_PAYEE_FIELDS", "JITHOX_PAYEE_TOOL_PATTERN"):
                env.pop(key, None)
            with patch.dict(os.environ, env, clear=True), patch.object(
                    hook, "ENDPOINT", "http://127.0.0.1:" + str(server.server_port) + "/api/mcp"):
                inputs = {"beneficiary": "Wire fixture supplier", "iban": current,
                          "supplierCountry": "nl", "amount": 123}

                def call(values, mode="PreToolUse"):
                    requests.clear()
                    return hook.handle({"hook_event_name": mode, "tool_name": "mcp__wire__pay",
                        "tool_input": values, "tool_response": {"success": True}}, mode)

                call(inputs, "PostToolUse")
                assert requests == []
                control = call(inputs)
                assert control["hookSpecificOutput"]["permissionDecision"] == "allow"
                baseline = list(requests)
                assert len(baseline) == 1
                headers = {key.lower(): value for key, value in baseline[0][1]}
                assert headers["user-agent"] == "claude-payee-hook/" + hook.VERSION
                assert "x-jithox-probe" not in headers
                args = json.loads(baseline[0][2])["params"]["arguments"]
                assert args == {"newIban": current, "ibanOnFile": current, "supplierCountry": "NL"}
                for field in ("ibanOnFile", "description", "prompt", "message", "notes", "reference", "unknown"):
                    value = unrelated if field in ("ibanOnFile", "unknown") else "Account mentioned in text: " + unrelated
                    actual = call({**inputs, field: value})
                    assert requests == baseline, "wire changed for " + field
                    assert unrelated.encode() not in requests[0][2]
                    assert actual == control, "decision changed for " + field
                    reports.append({"case": field, "requests": len(requests), "raw_request_equal": True,
                                    "decision_equal": True, "unrelated_account_sent": False})

                no_payment = {"beneficiary": inputs["beneficiary"], "unknown": unrelated}
                out = call(no_payment)
                assert "Jithox checked nothing" in out["systemMessage"] and not requests
                reports.append({"case": "unknown_only", "requests": 0, "decision": "none"})
                configured = {"beneficiary": inputs["beneficiary"], "settlementAccount": current,
                              "supplierCountry": "nl"}
                with patch.dict(os.environ, {"JITHOX_PAYMENT_IBAN_FIELDS": "settlementAccount"}):
                    actual = call(configured)
                assert requests == baseline and actual == control
                reports.append({"case": "local_extra_field", "requests": 1, "raw_request_equal": True,
                                "decision_equal": True})
                return {"transport": "real loopback HTTP; no Jithox traffic", "cases": reports,
                        "user_agent": headers["user-agent"], "probe_header": False,
                        "argument_keys": sorted(args), "baseline_requests": len(baseline)}
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


class WireTests(unittest.TestCase):
    def test_structured_field_boundary_on_real_http_wire(self):
        capture()


if __name__ == "__main__":
    print(json.dumps(capture(), indent=2))
