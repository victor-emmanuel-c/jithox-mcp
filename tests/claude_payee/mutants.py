"""Run six local safety mutants in disposable copies, never editing the plugin."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "plugins/claude-payee-hook/scripts/payee_hook.py"
source = SOURCE.read_text(encoding="utf-8")
mutants = [
    ("error_to_allow", 'return "ask", "error: " + suffix + FALLBACK',
     'return "allow", "error: " + suffix + FALLBACK',
     ["test_transport_failures_are_ask_never_allow"]),
    ("caller_reference", 'on_file = memory["payees"].get(key) if key else None',
     'on_file = inputs.get("ibanOnFile")',
     ["test_local_record_cannot_be_replaced_by_caller_reference"]),
    ("stop_to_ask", 'kind = "deny" if result["verdict"] in ("stop", "invalid_new_account") else "ask"',
     'kind = "deny" if result["verdict"] == "invalid_new_account" else "ask"',
     ["test_stop_is_deny_not_ask"]),
    ("skip_mod97", 'return int(digits) % 97 == 1', 'return True',
     ["test_mod97_failure_denies_without_request"]),
    ("remember_in_pre", 'memory = read_memory(directory)',
     'remember(directory, key, ibans[0]); memory = read_memory(directory)',
     ["test_known_account_pre_never_writes_memory"]),
    ("follow_memory_link", 'with memory_directory(directory) as fd:',
     'return json.loads((directory / "payees.json").read_text(encoding="utf-8"))\n        with memory_directory(directory) as fd:',
     ["test_memory_parent_link_is_refused", "test_memory_symlink_is_never_read_or_written"]),
]


def run(path, names):
    proc = subprocess.run([sys.executable, "-m", "unittest", "-v",
        *("test_hook.HookTests." + name for name in names)],
        cwd=ROOT / "tests/claude_payee", capture_output=True, text=True,
        timeout=90, env={**os.environ, "PAYEE_TEST_SOURCE": str(path), "PYTHONDONTWRITEBYTECODE": "1"})
    output = proc.stdout + proc.stderr
    count = re.search(r"Ran (\d+) tests?", output)
    # Only names/counts are recorded: failing assertions can contain fixture IBANs.
    return {"exit": proc.returncode, "tests": int(count[1]) if count else None,
            "failures": sorted(set(re.findall(r"^FAIL: (test_\w+)", output, re.M))),
            "errors": sorted(set(re.findall(r"^ERROR: (test_\w+)", output, re.M))),
            "skips": len(re.findall(r"\.\.\. skipped", output))}


names = sorted({name for _, _, _, tests in mutants for name in tests})
base = run(SOURCE, names)
print(json.dumps({"baseline": base}), flush=True)
if base["exit"] != 0 or base["tests"] != len(names):
    raise SystemExit("Baseline is not green; no mutant results accepted.")
results = []
with tempfile.TemporaryDirectory(prefix="payee-mutants-", dir=os.environ.get("PAYEE_TEST_TMP")) as temp:
    for name, old, new, tests in mutants:
        if source.count(old) != 1:
            raise SystemExit("Mutation anchor is not unique: " + name)
        changed = source.replace(old, new, 1)
        compile(changed, "mutant", "exec")
        path = Path(temp) / (name + ".py")
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(changed)
        result = {"mutant": name, "target_tests": tests, **run(path, tests)}
        result["killed"] = (result["exit"] == 1 and result["tests"] == len(tests)
                            and bool(result["failures"]) and not result["errors"])
        results.append(result)
        print(json.dumps(result), flush=True)
print(json.dumps({"killed": sum(row["killed"] for row in results), "total": len(results), "platform": sys.platform}))
raise SystemExit(0 if all(row["killed"] for row in results) else 1)
