"""One explicit, read-only production probe. Never imported by the plugin."""
import argparse
import importlib.util
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument("--probe", required=True, help="Kanban own_probe marker, e.g. t_edd8a743")
args = parser.parse_args()
source = Path(__file__).resolve().parents[2] / "plugins/claude-payee-hook/scripts/payee_hook.py"
spec = importlib.util.spec_from_file_location("payee_hook", source)
assert spec is not None and spec.loader is not None
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)
metadata = {"probe": args.probe, "http_status": None, "verdict": None}
real_builder = urllib.request.build_opener


def observed_builder(*handlers):
    opener = real_builder(*handlers)
    real_open = opener.open

    def observed_open(*positional, **keywords):
        try:
            response = real_open(*positional, **keywords)
            metadata["http_status"] = response.status
            return response
        except urllib.error.HTTPError as error:
            metadata["http_status"] = error.code
            raise

    opener.open = observed_open
    return opener


urllib.request.build_opener = observed_builder
started = time.monotonic()
try:
    # Public documentation example; not a customer's account and no payment is made.
    result = hook.askJithox("DE89370400440532013000", "DE89370400440532013000", "DE", probe=args.probe)
    metadata["verdict"] = result["verdict"]
    metadata["required_steps_count"] = len(result["requiredSteps"])
except Exception:
    metadata["error"] = "No usable verdict; hook would ask, never allow."
finally:
    metadata["seconds"] = round(time.monotonic() - started, 3)
    print(json.dumps(metadata))
raise SystemExit(0 if metadata["verdict"] else 1)
