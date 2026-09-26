"""Offline stdin contract tests; all accounts and responses are test fixtures."""
import json
import os
import stat
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
HOOK = Path(os.environ.get("PAYEE_TEST_SOURCE", ROOT / "plugins/claude-payee-hook/scripts/payee_hook.py"))
IBAN = "DE89370400440532013000"
OTHER = "GB82WEST12345698765432"
TOOL = "mcp__bank__send_payment"


def event(mode="PreToolUse", **fields):
    return {"hook_event_name": mode, "tool_name": TOOL,
            "tool_input": {"beneficiary": "Fixture supplier", "iban": IBAN},
            "tool_use_id": "fixture-call", **fields}


def reply(verdict="verify_first", **extra):
    result = {"kind": "payment_change_check", "data": {
        "verdict": verdict, "requiredSteps": ["Call using your own records."]}}
    return {"body": json.dumps({"jsonrpc": "2.0", "id": 1,
            "result": {"content": [{"type": "text", "text": json.dumps(result)}]}}), **extra}


class HookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="payee-test-", dir=os.environ.get("PAYEE_TEST_TMP"))
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.memory = self.home / "state"
        self.env = {**os.environ, "JITHOX_PAYEE_MEMORY_DIR": str(self.memory),
                    "PYTHONDONTWRITEBYTECODE": "1"}
        for key in ("JITHOX_PAYEE_FIELDS", "JITHOX_PAYEE_TOOL_PATTERN"):
            self.env.pop(key, None)

    def run_hook(self, data, fixture=None, mode=None):
        args = [sys.executable, str(HOOK), mode or data["hook_event_name"]]
        if fixture is not None:
            fixture_path = self.home / "fixture.json"
            fixture_path.write_text(json.dumps(fixture), encoding="utf-8")
            self.env["PAYEE_TEST_CAPTURE"] = str(self.home / "requests.jsonl")
            args = [sys.executable, str(Path(__file__).with_name("stdin_driver.py")),
                    str(fixture_path), mode or data["hook_event_name"]]
        proc = subprocess.run(args, input=json.dumps(data), text=True,
                              capture_output=True, env=self.env, timeout=30)
        self.assertEqual(proc.returncode, 0, "hook must emit a decision, not crash")
        self.assertEqual(proc.stderr, "", "no raw data or exceptions on stderr")
        return json.loads(proc.stdout)

    def decision(self, out):
        return out.get("hookSpecificOutput", {}).get("permissionDecision")

    def requests(self):
        path = self.home / "requests.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def seed(self, iban=IBAN, payee="Fixture supplier", tool=TOOL):
        self.memory.mkdir(mode=0o700, exist_ok=True)
        path = self.memory / "payees.json"
        key = json.dumps([tool, payee], separators=(",", ":"))
        path.write_text(json.dumps({"version": 1, "payees": {key: iban}}), encoding="utf-8")
        path.chmod(0o600)
        return path

    def test_no_iban_reports_checked_nothing_without_permission_decision(self):
        out = self.run_hook(event(tool_input={"amount": 100, "memo": "invoice"}))
        self.assertNotIn("permissionDecision", out.get("hookSpecificOutput", {}))
        self.assertIn("Jithox checked nothing", out["systemMessage"])
        self.assertFalse(self.memory.exists())

    def test_first_registration_asks_and_sends_only_account_and_country(self):
        out = self.run_hook(event(tool_input={"beneficiary": "Fixture supplier",
            "amount": 100, "iban": IBAN, "ibanOnFile": IBAN, "supplierCountry": "de"}), reply("no_change"))
        self.assertEqual(self.decision(out), "ask")
        req = self.requests()[0]
        self.assertEqual(req["body"]["params"], {"name": "check_payment_change",
            "arguments": {"newIban": IBAN, "supplierCountry": "DE"}})
        self.assertEqual(req["url"], "https://jithox.com/api/mcp")
        headers = {k.lower(): v for k, v in req["headers"].items()}
        self.assertEqual(headers["accept"], "application/json, text/event-stream")
        self.assertEqual(headers["user-agent"], "claude-payee-hook/0.1.0")
        self.assertNotIn("x-jithox-probe", headers)
        self.assertEqual(req["timeout"], 3)
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("no_change", reason)
        self.assertIn("Call using your own records.", reason)
        self.assertIn(IBAN[-4:], reason)
        self.assertNotIn(IBAN, json.dumps(out))
        self.assertFalse(self.memory.exists(), "PreToolUse must never remember an account")

    def test_stop_is_deny_not_ask(self):
        self.assertEqual(self.decision(self.run_hook(event(), reply("stop"))), "deny")

    def test_invalid_new_account_is_deny(self):
        self.assertEqual(self.decision(self.run_hook(event(), reply("invalid_new_account"))), "deny")

    def test_verify_first_is_ask(self):
        self.assertEqual(self.decision(self.run_hook(event(), reply())), "ask")

    def test_transport_failures_are_ask_never_allow(self):
        self.seed()
        fixtures = {
            "dns": {"failure": "dns"}, "timeout": {"failure": "timeout"},
            "500": reply("no_change", status=500), "406": reply("no_change", status=406),
            "403_json_challenge": {"status": 403, "body": '{"error":{"code":"challenge"}}'},
            "403_html_challenge": {"status": 403, "body": "<html>Vercel Security Checkpoint</html>", "content_type": "text/html"},
            "html_challenge": {"body": "<html>Vercel Security Checkpoint</html>", "content_type": "text/html"},
            "bad_json": {"body": "{"}, "empty": {"body": ""},
            "unknown": reply("safe"), "null": {"body": "null"},
        }
        is_error = json.loads(reply("no_change")["body"])
        is_error["result"]["isError"] = True
        fixtures["isError"] = {"body": json.dumps(is_error)}
        for label, update in {
            "rpc_error": {"error": {"code": -32603}}, "wrong_id": {"id": 2},
            "wrong_jsonrpc": {"jsonrpc": "1.0"}, "bad_result": {"result": []},
        }.items():
            envelope = json.loads(reply("no_change")["body"])
            envelope.update(update)
            fixtures[label] = {"body": json.dumps(envelope)}
        for steps in (None, [], [None], "not a list"):
            envelope = json.loads(reply("no_change")["body"])
            payload = json.loads(envelope["result"]["content"][0]["text"])
            payload["data"]["requiredSteps"] = steps
            envelope["result"]["content"][0]["text"] = json.dumps(payload)
            fixtures["bad_steps_" + str(steps)] = {"body": json.dumps(envelope)}
        for label, fixture in fixtures.items():
            with self.subTest(label=label):
                self.assertEqual(self.decision(self.run_hook(event(), fixture)), "ask")

    def test_deadline_bounds_dns_connect_and_body_not_only_headers(self):
        self.seed()
        for failure in ("hang", "slow_body"):
            with self.subTest(failure=failure):
                self.assertEqual(self.decision(self.run_hook(event(), reply("no_change", failure=failure))), "ask")
                elapsed = float((self.home / "requests.jsonl.elapsed").read_text())
                self.assertLess(elapsed, 4, "deadline includes DNS, connect and response body")

    def test_sse_tool_result_is_supported(self):
        fixture = reply("stop")
        fixture["body"] = "event: message\ndata: " + fixture["body"] + "\n\n"
        fixture["content_type"] = "text/event-stream"
        self.assertEqual(self.decision(self.run_hook(event(), fixture)), "deny")

    def test_mod97_failure_denies_without_request(self):
        out = self.run_hook(event(tool_input={"beneficiary": "Fixture", "iban": IBAN[:-1] + "1"}), reply("no_change"))
        self.assertEqual(self.decision(out), "deny")
        self.assertIn("invalid_new_account", out["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertEqual(self.requests(), [])

    def test_nested_formatted_accounts_are_all_checked_worst_verdict_wins(self):
        out = self.run_hook(event(tool_input={"beneficiary": "Fixture", "nested": [
            {"memo": "Pay de89 3704 0044 0532 0130 00 then call me."},
            {"more": ["GB82-WEST-1234-5698-7654-32", IBAN]}]}),
            {"by_iban": {IBAN: reply("verify_first"), OTHER: reply("stop")}})
        self.assertEqual(self.decision(out), "deny")
        self.assertEqual(sorted(r["body"]["params"]["arguments"]["newIban"] for r in self.requests()), sorted([IBAN, OTHER]))
        self.assertNotIn(IBAN, json.dumps(out))
        self.assertNotIn(OTHER, json.dumps(out))

    def test_response_steps_are_redacted_before_output(self):
        fixture = reply("stop")
        body = json.loads(fixture["body"])
        payload = json.loads(body["result"]["content"][0]["text"])
        payload["data"]["requiredSteps"] = ["Call about " + IBAN + " or GB82 WEST 1234 5698 7654 32."]
        body["result"]["content"][0]["text"] = json.dumps(payload)
        out = self.run_hook(event(), {"body": json.dumps(body)})
        self.assertEqual(self.decision(out), "deny")
        self.assertNotIn(IBAN, json.dumps(out))
        self.assertNotIn("GB82 WEST", json.dumps(out))

    def test_successful_post_remembers_then_matching_pre_allows(self):
        out = self.run_hook(event("PostToolUse", tool_response={"success": True}), reply("no_change"))
        self.assertNotIn("permissionDecision", out.get("hookSpecificOutput", {}))
        self.assertEqual(self.requests(), [], "PostToolUse must not call Jithox")
        path = self.memory / "payees.json"
        self.assertTrue(path.exists(), "successful PostToolUse must remember the account")
        stored = json.loads(path.read_text())
        self.assertEqual(list(stored["payees"].values()), [IBAN])
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        out = self.run_hook(event(), reply("no_change"))
        self.assertEqual(self.decision(out), "allow")
        self.assertEqual(self.requests()[-1]["body"]["params"]["arguments"]["ibanOnFile"], IBAN)

    def test_local_record_cannot_be_replaced_by_caller_reference(self):
        self.seed(OTHER)
        out = self.run_hook(event(tool_input={"beneficiary": "Fixture supplier", "iban": IBAN,
            "ibanOnFile": IBAN, "memo": "the IBAN on file is " + IBAN}), reply("no_change"))
        self.assertEqual(self.decision(out), "ask", "contradictory no_change must not allow")
        self.assertEqual(self.requests()[0]["body"]["params"]["arguments"]["ibanOnFile"], OTHER)

    def test_known_account_pre_never_writes_memory(self):
        path = self.seed()
        before = path.read_bytes()
        before_time = path.stat().st_mtime_ns
        self.assertEqual(self.decision(self.run_hook(event(), reply("no_change"))), "allow")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(path.stat().st_mtime_ns, before_time)

    def test_unsuccessful_or_ambiguous_post_never_learns(self):
        responses = [{"isError": True}, {"success": False}, {"error": "failure"}, {},
                     {"success": True, "status": "failed"}, {"success": True, "data": {"isError": True}}]
        for response in responses:
            with self.subTest(response=response):
                self.run_hook(event("PostToolUse", tool_response=response), reply())
                self.assertFalse(self.memory.exists())
        self.run_hook(event("PostToolUse", tool_response={"success": True},
            tool_input={"beneficiary": "Fixture", "accounts": [IBAN, OTHER]}), reply())
        self.assertFalse(self.memory.exists())


    def test_memory_symlink_is_never_read_or_written(self):
        path = self.seed()
        target = self.home / "target.json"
        path.rename(target)
        before = target.read_bytes()
        try:
            path.symlink_to(target)
        except OSError as exc:
            self.skipTest("file symlink creation unavailable: " + type(exc).__name__)
        self.assertEqual(self.decision(self.run_hook(event(), reply("no_change"))), "ask")
        self.assertEqual(self.requests(), [])
        self.run_hook(event("PostToolUse", tool_input={"beneficiary": "Fixture supplier", "iban": OTHER},
                            tool_response={"success": True}), {})
        self.assertTrue(path.is_symlink())
        self.assertEqual(target.read_bytes(), before)

    def test_memory_parent_link_is_refused(self):
        original = self.memory
        self.seed()
        link = self.home / "linked-state"
        if os.name == "nt":
            proc = subprocess.run(["cmd.exe", "/c", "mklink", "/J", str(link), str(original)], capture_output=True)
            self.assertEqual(proc.returncode, 0)
            self.addCleanup(lambda: os.rmdir(link))
        else:
            link.symlink_to(original, target_is_directory=True)
        self.env["JITHOX_PAYEE_MEMORY_DIR"] = str(link)
        self.assertEqual(self.decision(self.run_hook(event(), reply("no_change"))), "ask")
        self.assertEqual(self.requests(), [])

    @unittest.skipUnless(os.name == "posix", "POSIX permissions require Linux/macOS")
    def test_insecure_memory_permissions_are_refused(self):
        path = self.seed()
        path.chmod(0o644)
        self.assertEqual(self.decision(self.run_hook(event(), reply("no_change"))), "ask")
        path.chmod(0o600)
        self.memory.chmod(0o755)
        self.assertEqual(self.decision(self.run_hook(event(), reply("no_change"))), "ask")

    def test_hardlinked_memory_is_refused(self):
        path = self.seed()
        os.link(path, self.home / "other-link.json")
        self.assertEqual(self.decision(self.run_hook(event(), reply("no_change"))), "ask")

    def test_corrupt_memory_is_not_replaced_or_trusted(self):
        path = self.seed()
        for content in ('{"version":99,"payees":{}}', '{"version":1,"payees":{"x":3}}', '{'):
            with self.subTest(content=content):
                path.write_text(content)
                self.assertEqual(self.decision(self.run_hook(event(), reply("no_change"))), "ask")
                self.run_hook(event("PostToolUse", tool_response={"success": True}), {})
                self.assertEqual(path.read_text(), content)

    def test_replace_failure_preserves_previous_record(self):
        path = self.seed()
        before = path.read_bytes()
        out = self.run_hook(event("PostToolUse", tool_input={"beneficiary": "Fixture supplier", "iban": OTHER},
                                 tool_response={"success": True}), {"replace_failure": True})
        self.assertIn("could not update", out["systemMessage"])
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in self.memory.iterdir()), ["payees.json"])

    def test_existing_writer_lock_is_not_removed_or_overwritten(self):
        path = self.seed()
        before = path.read_bytes()
        lock = self.memory / "write.lock"
        lock.write_text("fixture lock")
        self.run_hook(event("PostToolUse", tool_input={"beneficiary": "Fixture supplier", "iban": OTHER},
                            tool_response={"success": True}), {})
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(lock.read_text(), "fixture lock")

    def test_parallel_posts_preserve_both_payees(self):
        processes = []
        for name, account in (("Fixture A", IBAN), ("Fixture B", OTHER)):
            p = subprocess.Popen([sys.executable, str(HOOK), "PostToolUse"], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.env)
            assert p.stdin is not None
            p.stdin.write(json.dumps(event("PostToolUse", tool_input={"beneficiary": name, "iban": account},
                                          tool_response={"success": True})))
            p.stdin.close()
            p.stdin = None
            processes.append(p)
        for p in processes:
            out, err = p.communicate(timeout=30)
            self.assertEqual(p.returncode, 0)
            self.assertEqual(err, "")
            self.assertIn("remembered the account", out)
        stored = json.loads((self.memory / "payees.json").read_text())
        self.assertEqual(sorted(stored["payees"].values()), sorted([IBAN, OTHER]))


    def test_configured_payee_path_and_tool_matcher(self):
        self.env["JITHOX_PAYEE_FIELDS"] = "recipient.vendor_id"
        self.env["JITHOX_PAYEE_TOOL_PATTERN"] = r"^mcp__bank__execute$"
        custom = event("PostToolUse", tool_name="mcp__bank__execute", tool_input={
            "recipient": {"vendor_id": "vendor-42"}, "iban": IBAN}, tool_response={"success": True})
        self.run_hook(custom, {})
        custom["hook_event_name"] = "PreToolUse"
        self.assertEqual(self.decision(self.run_hook(custom, reply("no_change"))), "allow")
        self.assertEqual(self.requests()[-1]["body"]["params"]["arguments"]["ibanOnFile"], IBAN)

    def test_nonmatching_tools_do_not_call_or_learn(self):
        for mode in ("PreToolUse", "PostToolUse"):
            out = self.run_hook(event(mode, tool_name="mcp__bank__get_balance", tool_response={"success": True}), reply())
            self.assertIsNone(self.decision(out))
        self.assertFalse(self.memory.exists())
        self.assertEqual(self.requests(), [])

    def test_missing_or_ambiguous_payee_never_allows_or_learns(self):
        self.seed()
        for inputs in ({"iban": IBAN}, {"iban": IBAN, "name": "Fixture supplier", "beneficiary": "Different"}):
            with self.subTest(inputs=inputs):
                self.assertEqual(self.decision(self.run_hook(event(tool_input=inputs), reply("no_change"))), "ask")
                before = (self.memory / "payees.json").read_bytes()
                self.run_hook(event("PostToolUse", tool_input=inputs, tool_response={"success": True}), {})
                self.assertEqual((self.memory / "payees.json").read_bytes(), before)

    def test_many_accounts_share_one_deadline(self):
        fixture = {"by_iban": {IBAN: reply(failure="hang"), OTHER: reply(failure="hang")}}
        out = self.run_hook(event(tool_input={"beneficiary": "Fixture", "accounts": [IBAN, OTHER]}), fixture)
        self.assertEqual(self.decision(out), "ask")
        self.assertEqual(len(self.requests()), 2)
        self.assertLess(float((self.home / "requests.jsonl.elapsed").read_text()), 4)

    def test_oversized_input_is_ask_without_network(self):
        self.seed()
        out = self.run_hook(event(tool_input={"iban": IBAN, "beneficiary": "Fixture supplier",
                                             "memo": "x" * (256 * 1024)}), reply("no_change"))
        self.assertEqual(self.decision(out), "ask")
        self.assertEqual(self.requests(), [])

    def test_invalid_country_is_not_silently_ignored(self):
        self.seed()
        self.assertEqual(self.decision(self.run_hook(event(tool_input={"iban": IBAN,
            "beneficiary": "Fixture supplier", "supplierCountry": "not-a-country"}), reply("no_change"))), "ask")

    def test_mcp_content_success_is_remembered_but_embedded_failure_is_not(self):
        text = {"type": "text", "text": json.dumps({"success": True})}
        for response in ({"isError": False, "content": [text]}, [text],
                         {"structuredContent": {"success": True}}):
            with self.subTest(response=response):
                (self.memory / "payees.json").unlink(missing_ok=True)
                self.run_hook(event("PostToolUse", tool_response=response), {})
                path = self.memory / "payees.json"
                self.assertTrue(path.exists())
                before = path.read_bytes()
                bad = {"content": [{"type": "text", "text": '{"success":false}'}]}
                self.run_hook(event("PostToolUse", tool_response=bad,
                    tool_input={"beneficiary": "Fixture supplier", "iban": OTHER}), {})
                self.assertEqual(path.read_bytes(), before)

    def test_formatted_bban_country_like_block_is_not_another_account(self):
        # Synthetic mod-97-valid fixture. No claim that this is an open bank account.
        bban = "2004101005AB12345678901"
        digits = "".join(str(ord(c) - 55) if c.isalpha() else c for c in bban + "FR00")
        iban = "FR" + str(98 - int(digits) % 97).zfill(2) + bban
        spaced = iban[:14] + " " + " ".join(iban[i:i + 4] for i in range(14, len(iban), 4))
        out = self.run_hook(event(tool_input={"beneficiary": "Fixture", "iban": spaced}), reply())
        self.assertEqual(self.decision(out), "ask")
        self.assertEqual(self.requests()[0]["body"]["params"]["arguments"]["newIban"], iban)


if __name__ == "__main__":
    unittest.main()
