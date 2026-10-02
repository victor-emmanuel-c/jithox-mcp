"""Pin the distribution's eight-tool boundary against a tools/list JSON receipt.

Discovery is not evidence of a tools/call, successful task or authorized access.
"""

EXPECTED_TOOLS = sorted((
    "check_payment_change", "check_peppol_ready", "check_vat_list",
    "kbo_company_search", "lookup_peppol_participant", "preflight_payment",
    "review_invoice", "verify_iban",
))


def check_catalog(payload):
    result = payload.get("result") if isinstance(payload, dict) else None
    tools = result.get("tools") if isinstance(result, dict) else None
    if not isinstance(tools, list) or any(
        not isinstance(tool, dict) or not isinstance(tool.get("name"), str)
        for tool in tools
    ):
        raise ValueError("Invalid tools/list result.tools")
    names = sorted(tool["name"] for tool in tools)
    if names != EXPECTED_TOOLS:
        raise ValueError("Live tool catalog differs from the eight-tool package boundary")
    return names


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    try:
        names = check_catalog(json.loads(args.receipt.read_text(encoding="utf-8")))
    except (ValueError, OSError) as error:
        parser.exit(1, f"FAIL: {error}\n")
    print(f"PASS: {len(names)} existing tools; discovery only, not execution")
    print("\n".join(names))
