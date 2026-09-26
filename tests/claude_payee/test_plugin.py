"""Plugin contract and real shell launcher tests, without network calls."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins/claude-payee-hook"


class PluginTests(unittest.TestCase):
    def test_manifest_and_marketplace_load_default_hooks_once(self):
        manifest_path = PLUGIN / ".claude-plugin/plugin.json"
        self.assertTrue(manifest_path.exists(), "plugin manifest required")
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest["name"], "claude-payee-hook")
        self.assertEqual(manifest["version"], "0.1.0")
        self.assertNotIn("hooks", manifest, "hooks/hooks.json is already auto-discovered")
        market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        self.assertEqual(market["name"], "jithox")
        self.assertEqual(market["plugins"][0]["source"], "./plugins/claude-payee-hook")
        hooks = json.loads((PLUGIN / "hooks/hooks.json").read_text())["hooks"]
        self.assertEqual(set(hooks), {"PreToolUse", "PostToolUse"})
        for event, entries in hooks.items():
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["matcher"], "mcp__.*")
            command = entries[0]["hooks"][0]
            self.assertEqual(command["type"], "command")
            self.assertEqual(command["shell"], "bash")
            self.assertEqual(command["timeout"], 15)
            self.assertEqual(command["command"], 'sh "${CLAUDE_PLUGIN_ROOT}/scripts/run.sh" ' + event)

    def launch(self, mode, env):
        launcher = PLUGIN / "scripts/run.sh"
        self.assertTrue(launcher.exists(), "launcher must exist")
        shell = shutil.which("sh")
        self.assertIsNotNone(shell, "sh/Git Bash required for launcher test")
        assert shell is not None
        proc = subprocess.run([shell, str(launcher), mode], input=json.dumps({
            "hook_event_name": mode, "tool_name": "mcp__bank__pay", "tool_input": {"amount": 1}}),
            text=True, capture_output=True, timeout=30, env=env)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr, "")
        return json.loads(proc.stdout)

    def test_launcher_with_python_reports_checked_nothing(self):
        env = {**os.environ, "JITHOX_PAYEE_PYTHON": sys.executable}
        self.assertIn("Jithox checked nothing", self.launch("PreToolUse", env)["systemMessage"])

    def test_missing_python_runtime_asks_instead_of_nonblocking_crash(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("PAYEE_TEST_TMP")) as empty:
            env = {**os.environ, "JITHOX_PAYEE_PYTHON": str(Path(empty) / "no-python")}
            out = self.launch("PreToolUse", env)
            self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "ask")
            self.assertIn("unavailable", out["hookSpecificOutput"]["permissionDecisionReason"])
            self.assertNotIn("permissionDecision", self.launch("PostToolUse", env).get("hookSpecificOutput", {}))


if __name__ == "__main__":
    unittest.main()
