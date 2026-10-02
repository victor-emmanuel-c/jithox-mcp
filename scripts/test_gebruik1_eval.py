"""Offline tests only: fake HTTP upstream responses are NOT live/model evidence."""
import copy
import http.client
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "eval" / "gebruik1"
sys.path.insert(0, str(PACKAGE))
# Strict TDD: these imports deliberately fail before implementation exists.
import proxy
import matrix
import prepare

SHA = "2af58b5517c2307310f081948b74e4ff33c927a3"
OTHER = "1" * 40


class FakeUpstream:
    """Real offline HTTP server, deliberately not a source of scored evidence."""
    def __init__(self):
        self.requests = []
        self.status = 200
        self.body = b'{"jsonrpc":"2.0","id":1,"result":{"content":[]}}'
        self.delay = 0.0
        self.chunk_delay = 0.0
        self.response_headers = {}
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                outer.requests.append((self.path, dict(self.headers), body))
                time.sleep(outer.delay)
                try:
                    self.send_response(outer.status)
                    self.send_header("Content-Type", "application/json")
                    for key, value in outer.response_headers.items():
                        self.send_header(key, value)
                    self.send_header("Content-Length", str(len(outer.body)))
                    self.end_headers()
                    if outer.chunk_delay:
                        for byte in outer.body:
                            self.wfile.write(bytes([byte]))
                            self.wfile.flush()
                            time.sleep(outer.chunk_delay)
                    else:
                        self.wfile.write(outer.body)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)


class ProxyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.log = Path(self.tmp.name) / "receipt.jsonl"
        self.fake = FakeUpstream()
        # Only tests replace the connection constructor. Runtime has NO upstream option.
        def connection(host, timeout):
            self.assertEqual(host, "jithox.com")
            return http.client.HTTPConnection("127.0.0.1", self.fake.server.server_port, timeout=timeout)
        self.replacement = patch.object(proxy.http.client, "HTTPSConnection", side_effect=connection)
        self.replacement.start()
        self.session = proxy.Session("claude", SHA, "P01", self.log, timeout=0.15)
        self.session.__enter__()

    def tearDown(self):
        self.session.__exit__(None, None, None)
        self.replacement.stop()
        self.fake.close()
        self.tmp.cleanup()

    def request(self, data=None, headers=None, path="/mcp", method="POST", raw=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.session.port, timeout=2)
        if data is None:
            data = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        body = raw if raw is not None else json.dumps(data).encode()
        fields = {"Content-Type": "application/json"}
        fields.update(headers or {})
        connection.request(method, path, body=body, headers=fields)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def call(self, name, arguments):
        return self.request({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}})

    def receipts(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_headers_on_initialize_notification_discovery_and_call(self):
        for method in ("initialize", "notifications/initialized", "tools/list"):
            data = {"jsonrpc": "2.0", "method": method, "params": {}}
            if not method.startswith("notifications/"):
                data["id"] = 1
            self.assertEqual(self.request(data)[0], 200)
        self.assertEqual(self.call("verify_iban", {"iban": "BE68 5390 0754 7034"})[0], 200)
        agents = []
        for path, headers, _ in self.fake.requests:
            self.assertEqual(path, "/api/mcp")
            fields = {key.lower(): value for key, value in headers.items()}
            self.assertEqual(fields["x-jithox-probe"], "gebruik1-eval")
            self.assertIn(f"/claude/{SHA}/P01/", fields["user-agent"])
            agents.append(fields["user-agent"])
        self.assertEqual(len(set(agents)), 4)
        self.assertEqual(len(self.receipts()), 4)

    def test_failed_connection_does_not_count_as_dispatched_call(self):
        with patch.object(proxy.http.client, "HTTPSConnection") as constructor:
            constructor.return_value.connect.side_effect = OSError("offline fixture")
            self.assertEqual(self.call("verify_iban", {"iban": "BE68 5390 0754 7034"})[0], 502)
            constructor.return_value.request.assert_not_called()
        self.assertEqual(self.receipts()[-1]["upstream_count"], 0)
        self.assertEqual(self.receipts()[-1]["outcome"], "upstream_connection_error")

    def test_concurrent_unique_call_ids(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(list(pool.map(lambda _: self.request()[0], range(8))), [200] * 8)
        records = self.receipts()
        self.assertEqual(len({row["event_id"] for row in records}), 8)
        self.assertEqual(sorted(row["call_index"] for row in records), list(range(1, 9)))

    def test_credentials_rejected_not_logged_or_forwarded(self):
        for header in ("Authorization", "Cookie", "Proxy-Authorization", "X-Api-Key", "X-Auth-Token"):
            self.assertEqual(self.request(headers={header: "SECRET_DO_NOT_LOG"})[0], 403)
        self.assertEqual(self.fake.requests, [])
        self.assertNotIn("SECRET_DO_NOT_LOG", self.log.read_text())

    def test_unknown_headers_dropped_response_cookies_and_redirect_stripped(self):
        self.fake.response_headers = {"Set-Cookie": "SECRET_COOKIE", "WWW-Authenticate": "Bearer SECRET_AUTH", "Location": "https://evil.invalid"}
        status, headers, _ = self.request(headers={"X-Anything": "SECRET_HEADER", "User-Agent": "SECRET_UA"})
        self.assertEqual(status, 200)
        self.assertFalse({"set-cookie", "www-authenticate", "location"} & {x.lower() for x in headers})
        self.assertNotIn("SECRET", str(self.fake.requests[0][1]))
        self.assertNotIn("SECRET", self.log.read_text())

    def test_closed_destination_path_host_origin_and_connect(self):
        for path in ("/mcp?url=https://evil.invalid", "https://evil.invalid/api/mcp", "/other"):
            self.assertEqual(self.request(path=path)[0], 403)
        self.assertEqual(self.request(headers={"Host": "evil.invalid"})[0], 403)
        self.assertEqual(self.request(headers={"Origin": "https://evil.invalid"})[0], 403)
        self.assertEqual(self.request(method="CONNECT", path="evil.invalid:443")[0], 405)
        self.assertEqual(self.fake.requests, [])

    def test_malformed_batch_oversize_unknown_tool_and_method(self):
        self.assertEqual(self.request(raw=b"{not json")[0], 400)
        self.assertEqual(self.request(data=[{"method": "tools/list"}])[0], 400)
        self.assertEqual(self.request(raw=b" " * (proxy.MAX_REQUEST + 1))[0], 413)
        self.assertEqual(self.request(data={"jsonrpc": "2.0", "id": 1, "method": "arbitrary"})[0], 403)
        self.assertEqual(self.call("arbitrary", {})[0], 403)
        self.assertEqual(self.fake.requests, [])

    def test_no_logging_bodies_rpc_ids_exception_or_credentials(self):
        self.fake.body = b'{"jsonrpc":"2.0","id":"SECRET_RESPONSE","result":{"content":[{"text":"SECRET_ACCOUNT"}]}}'
        self.request({"jsonrpc": "2.0", "id": "SECRET_RPC_ID", "method": "tools/call", "params": {"name": "verify_iban", "arguments": {"iban": "SECRET_PROMPT"}}})
        self.assertNotIn("SECRET", self.log.read_text())
        self.assertEqual(set(self.receipts()[0]), proxy.RECEIPT_FIELDS)
        with patch.object(proxy.http.client, "HTTPSConnection", side_effect=OSError("SECRET_EXCEPTION")):
            self.assertEqual(self.request()[0], 502)
        self.assertNotIn("SECRET", self.log.read_text())

    def test_paid_denied_until_exact_human_consent_and_one_shot(self):
        args = {"rows": [{"vatId": "BE0403170701"}]}
        self.assertEqual(self.call("check_vat_list", args)[0], 403)
        with self.assertRaises(ValueError):
            self.session.arm_paid("check_vat_list", "yes")
        self.assertEqual(self.fake.requests, [])
        self.session.arm_paid("check_vat_list", "ALLOW ANONYMOUS 401 check_vat_list")
        self.fake.status = 401
        self.fake.body = b'{"error":"Authentication required"}'
        status, _, body = self.call("check_vat_list", args)
        self.assertEqual((status, body), (401, self.fake.body))
        self.assertEqual(self.receipts()[-1]["outcome"], "upstream_http_401")
        self.assertEqual(self.receipts()[-1]["upstream_count"], 1)
        self.assertEqual(self.call("check_vat_list", args)[0], 403)
        with self.assertRaises(ValueError):
            self.session.arm_paid("check_vat_list", "ALLOW ANONYMOUS 401 check_vat_list")
        self.assertEqual(len(self.fake.requests), 1)

    def test_paid_fixture_validation_kbo_and_review_always_denied(self):
        self.session.arm_paid("check_vat_list", "ALLOW ANONYMOUS 401 check_vat_list")
        for args in ({"vatIds": ["BE0403170701"]}, {"rows": [{"vatId": "OTHER"}]}, {"rows": [{"vatId": "BE0403170701"}], "requesterVatId": "SECRET"}):
            self.assertEqual(self.call("check_vat_list", args)[0], 403)
        self.session.arm_paid("kbo_company_search", "ALLOW ANONYMOUS 401 kbo_company_search")
        self.fake.status = 401
        self.assertEqual(self.call("kbo_company_search", {"vatNumber": "BE0403170701"})[0], 401)
        self.assertEqual(self.call("review_invoice", {})[0], 403)
        self.assertEqual(len(self.fake.requests), 1)

    def test_operator_consent_cannot_be_armed_non_interactively(self):
        with self.assertRaises(ValueError):
            proxy.operator_consent(self.session, "check_vat_list", input_fn=lambda _: "ALLOW ANONYMOUS 401 check_vat_list", is_tty=False)
        self.assertEqual(self.call("check_vat_list", {"rows": [{"vatId": "BE0403170701"}]})[0], 403)

    def test_credential_fields_and_missing_call_params_rejected(self):
        for params in ({"authorization": "SECRET"}, {"nested": {"access_token": "SECRET"}}, {"items": [{"api_key": "SECRET"}]}):
            self.assertEqual(self.request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": params})[0], 403)
        self.assertEqual(self.request({"jsonrpc": "2.0", "id": 1, "method": "tools/call"})[0], 400)
        self.assertEqual(self.fake.requests, [])
        self.assertNotIn("SECRET", self.log.read_text())

    def test_context_exception_closes_listener(self):
        port = None
        with self.assertRaises(RuntimeError):
            with proxy.Session("claude", SHA, "P01", Path(self.tmp.name) / "exception.jsonl") as other:
                port = other.port
                raise RuntimeError("test-only interruption")
        with self.assertRaises(OSError):
            socket.create_connection(("127.0.0.1", port), timeout=0.2)

    def test_response_failure_classes_and_no_redirect_following(self):
        for status, body, expected in (
            (503, b'failure SECRET', "upstream_http_503"),
            (302, b'redirect SECRET', "upstream_redirect_blocked"),
            (200, b'not json SECRET', "upstream_invalid_response"),
            (200, b'{"jsonrpc":"2.0","id":1,"error":{"code":-1,"message":"SECRET"}}', "upstream_rpc_error"),
            (200, b'{"jsonrpc":"2.0","id":1,"result":{"isError":true,"content":[]}}', "upstream_tool_error"),
        ):
            self.fake.status, self.fake.body = status, body
            self.request()
            self.assertEqual(self.receipts()[-1]["outcome"], expected)
        self.assertEqual(len(self.fake.requests), 5)
        self.assertNotIn("SECRET", self.log.read_text())

    def test_total_response_deadline_stops_trickling_body(self):
        self.fake.chunk_delay = 0.03
        started = time.monotonic()
        self.assertEqual(self.request()[0], 504)
        self.assertLess(time.monotonic() - started, 0.8)
        self.assertEqual(self.receipts()[-1]["outcome"], "upstream_timeout")

    def test_upstream_timeout_and_cleanup(self):
        self.fake.delay = 0.35
        self.assertEqual(self.request()[0], 504)
        self.assertEqual(self.receipts()[-1]["outcome"], "upstream_timeout")
        port = self.session.port
        self.session.close()
        with self.assertRaises(OSError):
            socket.create_connection(("127.0.0.1", port), timeout=0.2)
        self.assertFalse(self.session.thread.is_alive())

    def test_response_limit_and_streaming_fail_closed(self):
        self.fake.body = b" " * (proxy.MAX_RESPONSE + 1)
        self.assertEqual(self.request()[0], 502)
        self.assertEqual(self.receipts()[-1]["outcome"], "upstream_response_too_large")
        self.fake.body = b"data: SECRET_STREAM\n\n"
        self.assertEqual(self.request()[0], 502)
        self.assertEqual(self.request(method="GET")[0], 405)

    def test_ref_prompt_client_validation_and_unique_runs(self):
        for client, ref, prompt_id in (("SECRET", SHA, "P01"), ("claude", "HEAD", "P01"), ("claude", SHA, "SECRET")):
            with self.assertRaises(ValueError):
                proxy.Session(client, ref, prompt_id, self.log)
        with proxy.Session("claude", SHA, "P01", Path(self.tmp.name) / "second.jsonl") as second:
            self.assertNotEqual(self.session.session_id, second.session_id)
            self.assertEqual(second.host, "127.0.0.1")


class MatrixTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        def git(*args):
            return subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True, text=True).stdout.strip()
        self.git = git
        git("init")
        git("-c", "user.name=Offline Test", "-c", "user.email=test@example.invalid", "commit", "--allow-empty", "-m", "baseline")
        self.base = git("rev-parse", "HEAD")
        git("-c", "user.name=Offline Test", "-c", "user.email=test@example.invalid", "commit", "--allow-empty", "-m", "candidate")
        self.candidate = git("rev-parse", "HEAD")
        # Test repo is isolated; production default baseline is immutable SHA.
        with patch.object(matrix, "BASELINE", self.base):
            self.document = matrix.make_matrix(self.repo, "HEAD")

    def tearDown(self):
        self.tmp.cleanup()

    def complete(self):
        doc = copy.deepcopy(self.document)
        receipts = []
        prompts = {p["id"]: p for p in matrix.load_prompts()}
        for row in doc["rows"]:
            row.update(skill_activated=True, correct_tool_called=row["role"] == "candidate", correct_outcome=True, false_claim=False, unsafe_claim=False, duration=1.2, reviewer_id="R01", evidence_kind="live_observed")
            row["evidence_ids"] = []
            tools = list(prompts[row["prompt_id"]]["required_tools"])
            if row["prompt_id"] == "P08":
                tools.append("preflight_payment")
            for n, name in enumerate(tools, 1):
                event_id = f"{row['row_id']}-{n}"
                row["evidence_ids"].append(event_id)
                receipts.append({"event_id": event_id, "client": row["client"], "ref": row["ref"], "prompt_id": row["prompt_id"], "tool": name, "outcome": "upstream_http_401" if name in proxy.PAID_COSTS else "upstream_ok", "upstream_count": 1})
        return doc, receipts

    def test_exact_40_unique_rows_real_refs_and_all_unset(self):
        rows = self.document["rows"]
        self.assertEqual(len(rows), 40)
        self.assertEqual(len({row["row_id"] for row in rows}), 40)
        self.assertEqual({row["ref"] for row in rows}, {self.base, self.candidate})
        for row in rows:
            for field in matrix.SCORE_FIELDS:
                self.assertIsNone(row[field])
        self.assertFalse(matrix.gate(self.document, [])["passed"])
        with patch.object(matrix, "BASELINE", self.base), self.assertRaises(ValueError):
            matrix.make_matrix(self.repo, self.base)

    def test_gate_strict_improvement_per_client_no_unsafe_and_no_more_false_claims(self):
        doc, receipts = self.complete()
        self.assertTrue(matrix.gate(doc, receipts)["passed"])
        for row in doc["rows"]:
            row["correct_tool_called"] = True
        self.assertFalse(matrix.gate(doc, receipts)["passed"])
        doc, receipts = self.complete()
        doc["rows"][-1]["unsafe_claim"] = True
        self.assertFalse(matrix.gate(doc, receipts)["passed"])
        doc, receipts = self.complete()
        next(row for row in doc["rows"] if row["role"] == "candidate")["false_claim"] = True
        self.assertFalse(matrix.gate(doc, receipts)["passed"])

    def test_missing_duplicate_or_unobserved_rows_fail(self):
        doc, receipts = self.complete()
        for changed in (doc["rows"][:-1], doc["rows"] + [doc["rows"][0]], [doc["rows"][0]] * 40):
            test = copy.deepcopy(doc)
            test["rows"] = changed
            self.assertFalse(matrix.gate(test, receipts)["passed"])
        doc["rows"][0]["evidence_kind"] = "offline_fixture"
        self.assertFalse(matrix.gate(doc, receipts)["passed"])

    def test_receipt_provenance_and_paid_401_not_listing_or_local_denial(self):
        doc, receipts = self.complete()
        self.assertFalse(matrix.gate(doc, [])["passed"])
        for receipt in receipts:
            if receipt["tool"] in proxy.PAID_COSTS:
                receipt["outcome"] = "paid_blocked"
                receipt["upstream_count"] = 0
        self.assertFalse(matrix.gate(doc, receipts)["passed"])
        doc, receipts = self.complete()
        for receipt in receipts:
            receipt["ref"] = "f" * 40
        self.assertFalse(matrix.gate(doc, receipts)["passed"])

    def test_scores_reject_strings_nonfinite_and_unapproved_fields(self):
        for field, value in (("correct_tool_called", "true"), ("duration", float("nan")), ("duration", -1), ("reviewer_id", "contains account data")):
            doc, receipts = self.complete()
            doc["rows"][0][field] = value
            self.assertFalse(matrix.gate(doc, receipts)["passed"])
        doc, receipts = self.complete()
        doc["rows"][0]["raw_response"] = "SECRET"
        self.assertFalse(matrix.gate(doc, receipts)["passed"])

    def test_gate_rejects_unhashable_identity_without_crashing(self):
        for field in ("role", "client", "prompt_id"):
            doc, receipts = self.complete()
            doc["rows"][0][field] = ["not-an-id"]
            self.assertFalse(matrix.gate(doc, receipts)["passed"])

    def test_omitted_wrong_tool_receipt_cannot_hide_extra_tool(self):
        doc, receipts = self.complete()
        row = next(row for row in doc["rows"] if row["role"] == "candidate" and row["prompt_id"] == "P07")
        receipts.append({"event_id": "unexpected-call", "client": row["client"], "ref": row["ref"], "prompt_id": row["prompt_id"], "tool": "verify_iban", "outcome": "upstream_ok", "upstream_count": 1})
        self.assertFalse(matrix.gate(doc, receipts)["passed"])

    def test_candidate_requires_real_calls_for_every_task_on_each_client(self):
        doc, receipts = self.complete()
        for row in doc["rows"]:
            if row["role"] == "candidate" and row["client"] == "claude" and row["skill_id"] == "verify-bank-detail-change":
                row["correct_tool_called"] = False
        self.assertFalse(matrix.gate(doc, receipts)["passed"])

    def test_blocked_unknown_tool_invalidates_positive_row(self):
        doc, receipts = self.complete()
        row = next(row for row in doc["rows"] if row["role"] == "candidate" and row["prompt_id"] == "P07")
        receipts.append({"event_id": "blocked-call", "client": row["client"], "ref": row["ref"], "prompt_id": row["prompt_id"], "tool": None, "outcome": "tool_blocked", "upstream_count": 0})
        self.assertFalse(matrix.gate(doc, receipts)["passed"])

    def test_prompt_manifest_ten_two_each_languages_and_safety(self):
        prompts = matrix.load_prompts()
        self.assertEqual(len(prompts), 10)
        from collections import Counter
        self.assertEqual(set(Counter(p["skill"] for p in prompts).values()), {2})
        self.assertEqual({p["language"] for p in prompts}, {"nl", "en"})
        self.assertEqual({p["id"] for p in prompts}, {f"P{i:02d}" for i in range(1, 11)})
        for prompt in prompts:
            self.assertNotIn("jithox", prompt["prompt"].lower())
            self.assertTrue(prompt["expected_outcome"])
            self.assertTrue(prompt["required_tools"])
        all_text = json.dumps(prompts, ensure_ascii=False)
        for value in ("BE68 5390 0754 7034", "BE68 5390 0754 7035", "BE71096123456769", "0208:0403170701", "facture", "Rechnung", "ingested_content", "invoice_bank", "x402", "card_or_giftcard", "crypto_bridge"):
            self.assertIn(value, all_text)
        for prompt in prompts:
            if prompt["skill"] == "agent-payment-preflight":
                self.assertEqual(prompt["required_tools"], ["preflight_payment"])
                self.assertEqual(prompt["allowed_tools"], ["preflight_payment"])


class PrepareTests(unittest.TestCase):
    def test_committed_export_excludes_eval_and_preserves_skill_bytes(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            destination = Path(tmp) / "baseline"
            ref, count = prepare.snapshot(ROOT, SHA, destination)
            self.assertEqual(ref, SHA)
            self.assertGreater(count, 0)
            self.assertFalse((destination / "eval").exists())
            self.assertFalse((destination / "scripts").exists())
            relative = "skills/pay-invoices-safely/SKILL.md"
            original = subprocess.run(["git", "-C", str(ROOT), "show", f"{SHA}:{relative}"], check=True, capture_output=True).stdout
            self.assertEqual((destination / relative).read_bytes(), original)
            prepare.overlay(destination, "http://127.0.0.1:43210/mcp")
            self.assertEqual((destination / relative).read_bytes(), original)
            with self.assertRaises(ValueError):
                prepare.snapshot(ROOT, SHA, destination)

    def test_proxy_cli_rejects_piped_consent_and_upstream_options(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            receipt = Path(tmp) / "must-not-exist.jsonl"
            args = [sys.executable, "-B", str(PACKAGE / "proxy.py"), "--client", "claude", "--ref", SHA, "--prompt", "P01", "--receipt", str(receipt)]
            for extra in ([], ["--upstream", "https://example.invalid"]):
                result = subprocess.run(args + extra, input="ALLOW ANONYMOUS 401 check_vat_list\n", capture_output=True, text=True, timeout=5)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(receipt.exists())

    def test_transport_overlay_rewrites_only_mcp_transport(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            root = Path(tmp)
            (root / ".claude-plugin").mkdir()
            (root / ".claude-plugin/plugin.json").write_text(json.dumps({"name": "jithox", "mcpServers": "./.mcp.json"}))
            (root / ".mcp.json").write_text(json.dumps({"mcpServers": {"jithox": {"type": "http", "url": proxy.UPSTREAM_URL}}}))
            (root / "mcp.json").write_text(json.dumps({"mcpServers": {"jithox": {"url": proxy.UPSTREAM_URL}}}))
            (root / "gemini-extension.json").write_text(json.dumps({"name": "jithox", "mcpServers": {"jithox": {"httpUrl": proxy.UPSTREAM_URL}}}))
            (root / "SKILL.md").write_text("must not change")
            prepare.overlay(root, "http://127.0.0.1:43210/mcp")
            self.assertEqual(json.loads((root / ".mcp.json").read_text())["mcpServers"]["jithox"]["url"], "http://127.0.0.1:43210/mcp")
            self.assertEqual(json.loads((root / "mcp.json").read_text())["mcpServers"]["jithox"]["type"], "streamable-http")
            extension = json.loads((root / "gemini-extension.json").read_text())
            self.assertEqual(extension["mcpServers"]["jithox"]["httpUrl"], "http://127.0.0.1:43210/mcp")
            self.assertFalse(extension["mcpServers"]["jithox"].get("trust", False))
            self.assertEqual((root / "SKILL.md").read_text(), "must not change")
            for url in ("https://evil.invalid", "http://0.0.0.0:1234/mcp", "http://127.0.0.1:1234/mcp?x=1"):
                with self.assertRaises(ValueError):
                    prepare.overlay(root, url)


if __name__ == "__main__":
    unittest.main(verbosity=2)
