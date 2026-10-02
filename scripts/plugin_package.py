"""Build a deterministic distribution ZIP from an explicit runtime-file allowlist."""
import argparse
import hashlib
import io
import re
from pathlib import Path
import zipfile

PACKAGE_FILES = (
    ".claude-plugin/marketplace.json", ".claude-plugin/plugin.json",
    ".cursor-plugin/plugin.json", ".mcp.json", "GEMINI.md", "LICENSE", "PACKAGE.md",
    "assets/ORIGIN.md", "assets/icon.png", "assets/logo.png", "assets/invoice-check-live.png",
    "gemini-extension.json", "mcp.json", "plugin.json",
    "skills/pay-invoices-safely/SKILL.md",
    "skills/pay-invoices-safely/references/examples.md",
    "skills/verify-bank-detail-change/SKILL.md",
    "skills/verify-bank-detail-change/references/examples.md",
    "skills/send-peppol-invoice/SKILL.md",
    "skills/send-peppol-invoice/references/examples.md",
    "skills/agent-payment-preflight/SKILL.md",
    "skills/agent-payment-preflight/references/examples.md",
    "skills/check-vat-numbers/SKILL.md",
    "skills/check-vat-numbers/references/examples.md",
    "commands/pay-invoices-safely.md", "commands/pay-invoices-safely.toml",
    "commands/verify-bank-detail-change.md", "commands/verify-bank-detail-change.toml",
    "commands/send-peppol-invoice.md", "commands/send-peppol-invoice.toml",
    "commands/agent-payment-preflight.md", "commands/agent-payment-preflight.toml",
    "commands/check-vat-numbers.md", "commands/check-vat-numbers.toml",
)


def package_bytes(root):
    root = Path(root).resolve()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(PACKAGE_FILES):
            data = (root / name).read_bytes()
            if not name.endswith(".png"):
                data = data.replace(b"\r\n", b"\n")
                text = data.decode("utf-8")
                forbidden = (
                    r"(?:sk_(?:live|test)_|jxc_live_|gh[pousr]_|xai-)[A-Za-z0-9_-]{12,}",
                    r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----",
                    r"(?i:authorization\s*:\s*bearer\s+)[A-Za-z0-9._-]{16,}",
                    r"(?<![A-Za-z])[A-Za-z]:[/\\](?!/)",
                    r"/(?:Users|home)/[^\s/]+/",
                )
                if any(re.search(pattern, text) for pattern in forbidden):
                    raise ValueError(f"Unsafe package content: {name}")
            entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_STORED
            archive.writestr(entry, data)
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = package_bytes(Path(__file__).resolve().parents[1])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(f"sha256={hashlib.sha256(data).hexdigest()} files={len(PACKAGE_FILES)} bytes={len(data)}")


if __name__ == "__main__":
    main()
