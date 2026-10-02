"""Offline distribution contracts. Run with the pinned JSON Schema validator."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://jithox.com/api/mcp"


class ManifestTests(unittest.TestCase):
    def test_portable_package_declares_one_streamable_http_server(self):
        for name in ("plugin.json", "mcp.json"):
            self.assertTrue((ROOT / name).is_file(), f"Missing portable manifest: {name}")
        plugin = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(plugin["$schema"], "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json")
        self.assertEqual(plugin["name"], "jithox")
        self.assertEqual(plugin["version"], "1.0.0")
        mcp = json.loads((ROOT / "mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(mcp, {
            "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
            "mcpServers": {"jithox": {"type": "streamable-http", "url": ENDPOINT}},
        })

    def test_host_overlays_share_the_endpoint_and_root_skill(self):
        expected = {
            ".mcp.json": {"mcpServers": {"jithox": {"type": "http", "url": ENDPOINT}}},
            "gemini-extension.json": {
                "name": "jithox", "version": "1.0.0",
                "description": "Check invoice payments, changed supplier bank details, Peppol readiness and VAT or company records.",
                "mcpServers": {"jithox": {"httpUrl": ENDPOINT}},
                "contextFileName": "GEMINI.md",
            },
        }
        for name, value in expected.items():
            self.assertTrue((ROOT / name).is_file(), f"Missing host manifest: {name}")
            self.assertEqual(json.loads((ROOT / name).read_text(encoding="utf-8")), value)
        for host in ("claude", "cursor"):
            path = ROOT / f".{host}-plugin/plugin.json"
            self.assertTrue(path.is_file(), f"Missing {host} manifest")
            manifest = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["name"], "jithox")
            self.assertEqual(manifest["version"], "1.0.0")
            self.assertEqual(manifest["mcpServers"], "./.mcp.json")
        market = ROOT / ".claude-plugin/marketplace.json"
        self.assertTrue(market.is_file(), "Missing Claude marketplace")
        catalog = json.loads(market.read_text(encoding="utf-8"))
        self.assertEqual(catalog["name"], "jithox")
        self.assertEqual(catalog["owner"]["name"], "Jithox")
        self.assertEqual(catalog["plugins"], [{"name": "jithox", "source": "./"}])
        self.assertTrue((ROOT / "GEMINI.md").is_file())

    def test_openai_listing_has_exactly_three_grounded_starter_prompts(self):
        plugin = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        self.assertIn("extensions", plugin, "Missing OpenAI presentation")
        ui = plugin["extensions"]["com.openai"]["interface"]
        self.assertEqual(ui["displayName"], "Jithox")
        self.assertEqual(ui["developerName"], "Jithox")
        self.assertEqual(ui["category"], "Productivity")
        self.assertLessEqual(len(ui["shortDescription"]), 30)
        self.assertEqual(ui["capabilities"], ["Invoice payment checks", "Peppol checks", "VAT and company lookups"])
        self.assertEqual(ui["defaultPrompt"], [
            "Check this invoice before payment, including its changed bank details against our supplier record. Report unchecked items.",
            "Check this invoice's Peppol readiness and whether participant 0208:0403170701 supports receiving BIS Billing invoices.",
            "Check supplier BE0417497106 in VIES and KBO; report unknown or not_run if access or a register is unavailable.",
        ])
        for prompt in ui["defaultPrompt"]:
            self.assertLessEqual(len(prompt), 128)
        self.assertEqual(ui["websiteURL"], "https://jithox.com")
        self.assertEqual(ui["privacyPolicyURL"], "https://jithox.com/privacy")
        self.assertEqual(ui["termsOfServiceURL"], "https://jithox.com/terms")
        self.assertEqual(ui["composerIcon"], "./assets/icon.png")
        self.assertEqual(ui["logo"], "./assets/logo.png")

    def test_skill_requires_real_calls_before_claiming_a_check(self):
        text = (ROOT / "skills/pay-invoices-safely/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Never claim a check ran without its actual tools/call response.", text)
        self.assertIn("Report every skipped or unreachable check as `not_run`, with a reason.", text)
        self.assertIn("Never report `ready` while any required check is `unknown` or `not_run`.", text)
        self.assertIn("Use before paying a supplier invoice or when supplier bank details change", text)
        self.assertNotIn("/api/invoice/review", text)
        for name in ("preflight_payment", "check_payment_change", "check_peppol_ready", "review_invoice"):
            self.assertIn(name, text)
        self.assertEqual(sorted(p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")), ["pay-invoices-safely"])

    def test_official_agent_plugins_schemas_validate_the_portable_files(self):
        import jsonschema
        for name in ("plugin", "mcp"):
            schema_path = ROOT / f"scripts/schemas/{name}.schema.json"
            self.assertTrue(schema_path.is_file(), f"Missing official schema: {name}")
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator.check_schema(schema)
            value = json.loads((ROOT / f"{name}.json").read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator(schema).validate(value)
            value["inventedField"] = True
            with self.assertRaises(jsonschema.ValidationError):
                jsonschema.Draft202012Validator(schema).validate(value)

    def test_package_builder_emits_a_deterministic_allowlisted_zip(self):
        self.assertTrue((ROOT / "scripts/plugin_package.py").is_file(), "Missing deterministic ZIP builder")
        from scripts.plugin_package import package_bytes
        import io
        import zipfile
        first = package_bytes(ROOT)
        self.assertEqual(first, package_bytes(ROOT))
        with zipfile.ZipFile(io.BytesIO(first)) as archive:
            names = archive.namelist()
            self.assertEqual(names, sorted([
                ".claude-plugin/marketplace.json", ".claude-plugin/plugin.json",
                ".cursor-plugin/plugin.json", ".mcp.json", "GEMINI.md", "LICENSE",
                "PACKAGE.md", "assets/ORIGIN.md", "assets/icon.png", "assets/logo.png", "assets/invoice-check-live.png",
                "gemini-extension.json", "mcp.json", "plugin.json",
                "skills/pay-invoices-safely/SKILL.md", "skills/pay-invoices-safely/references/examples.md",
            ]))
            self.assertEqual(len(names), len(set(names)))
            for info in archive.infolist():
                self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
                self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
                self.assertNotIn("\r\n", archive.read(info).decode("utf-8") if not info.filename.endswith(".png") else "")

    def test_readme_documents_the_listed_skill_and_host_package(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("npx skills add victor-emmanuel-c/jithox-mcp", text)
        self.assertIn("/plugin marketplace add victor-emmanuel-c/jithox-mcp", text)
        self.assertIn("[PACKAGE.md](PACKAGE.md)", text)
        self.assertNotIn("registry manifest only", text)

    def test_builder_rejects_secret_or_machine_path_in_an_allowed_file(self):
        from scripts.plugin_package import PACKAGE_FILES, package_bytes
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            clone = Path(directory)
            for name in PACKAGE_FILES:
                (clone / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, clone / name)
            # Git may check out PACKAGE.md as CRLF; construct both fixtures from LF.
            original = (clone / "PACKAGE.md").read_bytes().replace(b"\r\n", b"\n")
            self.assertIn(b"\n", original)
            self.assertNotIn(b"\r", original)
            crlf = original.replace(b"\n", b"\r\n")
            self.assertEqual(crlf.count(b"\r\n"), original.count(b"\n"))
            self.assertNotIn(b"\r\r\n", crlf)
            self.assertNotIn(b"\n", crlf.replace(b"\r\n", b""))
            for value in ("sk_" + "live_" + "notarealsecret123456789", "C:" + "/Users/example/private.txt"):
                with self.subTest(value_type=value[:3]):
                    (clone / "PACKAGE.md").write_bytes(original + value.encode())
                    with self.assertRaisesRegex(ValueError, "Unsafe package content"):
                        package_bytes(clone)
            (clone / "PACKAGE.md").write_bytes(original)
            lf_package = package_bytes(clone)
            self.assertEqual(package_bytes(ROOT), lf_package)
            (clone / "PACKAGE.md").write_bytes(crlf)
            self.assertEqual(lf_package, package_bytes(clone))
            (clone / ".env").write_text("unrelated-secret", encoding="utf-8")
            self.assertEqual(lf_package, package_bytes(clone))

    def test_live_catalog_requires_exactly_the_existing_eight_tools(self):
        self.assertTrue((ROOT / "scripts/check_plugin_live.py").is_file(), "Missing live eight-tool boundary check")
        from scripts.check_plugin_live import check_catalog
        expected = ["check_payment_change", "check_peppol_ready", "check_vat_list", "kbo_company_search",
                    "lookup_peppol_participant", "preflight_payment", "review_invoice", "verify_iban"]
        payload = {"result": {"tools": [{"name": name, "inputSchema": {"type": "object"}} for name in expected]}}
        self.assertEqual(check_catalog(payload), expected)
        for tools in (payload["result"]["tools"][:-1],
                      payload["result"]["tools"] + [{"name": "invented_tool"}],
                      payload["result"]["tools"] + [payload["result"]["tools"][0]], None, [None]):
            with self.subTest(tools_type=type(tools).__name__):
                with self.assertRaises(ValueError):
                    check_catalog({"result": {"tools": tools}})

    def test_assets_include_provenance_and_an_unedited_live_screenshot(self):
        import hashlib
        import struct
        ui = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))["extensions"]["com.openai"]["interface"]
        self.assertEqual(ui.get("screenshots"), ["./assets/invoice-check-live.png"])
        origin = (ROOT / "assets/ORIGIN.md").read_text(encoding="utf-8")
        expected = {"icon.png": (512, 512), "logo.png": (512, 512), "invoice-check-live.png": (1280, 900)}
        for name, size in expected.items():
            data = (ROOT / "assets" / name).read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", data[16:24]), size)
            self.assertIn(hashlib.sha256(data).hexdigest(), origin)
        self.assertIn("2026-10-02T13:43:53.489387+00:00", origin)
        self.assertIn("https://jithox.com/invoice-check", origin)
        self.assertIn("no form input or submission", origin)

    def test_live_catalog_receipt_cli_exits_nonzero_for_drift(self):
        import subprocess
        import sys
        import tempfile
        from scripts.check_plugin_live import EXPECTED_TOOLS
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / "tools-list.json"
            for names, ok in ((EXPECTED_TOOLS, True), (EXPECTED_TOOLS[:-1], False)):
                receipt.write_text(json.dumps({"result": {"tools": [{"name": name} for name in names]}}), encoding="utf-8")
                result = subprocess.run([sys.executable, str(ROOT / "scripts/check_plugin_live.py"), str(receipt)], capture_output=True, text=True)
                if ok:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("PASS: 8 existing tools", result.stdout)
                else:
                    self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
