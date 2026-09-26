"""Test-only transport seam. Production has no mock/endpoint environment switch."""
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import sys
import time
from contextlib import nullcontext
import urllib.error
from unittest.mock import patch

hook_path = Path(os.environ.get("PAYEE_TEST_SOURCE", Path(__file__).resolve().parents[2]
                                / "plugins/claude-payee-hook/scripts/payee_hook.py"))
spec = importlib.util.spec_from_file_location("payee_hook", hook_path)
assert spec is not None and spec.loader is not None
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)
fixture = json.loads(Path(sys.argv.pop(1)).read_text(encoding="utf-8"))


class Response(io.BytesIO):
    def __init__(self, value):
        self.status = value.get("status", 200)
        self.headers = {"Content-Type": value.get("content_type", "application/json")}
        super().__init__(value.get("body", "").encode())


class Opener:
    def open(self, request, timeout):
        args = json.loads(request.data)["params"]["arguments"]
        with open(os.environ["PAYEE_TEST_CAPTURE"], "a", encoding="utf-8") as out:
            out.write(json.dumps({"url": request.full_url, "headers": dict(request.header_items()),
                                  "body": json.loads(request.data), "timeout": timeout}) + "\n")
        value = fixture.get("by_iban", {}).get(args["newIban"], fixture)
        failure = value.get("failure")
        if failure == "dns":
            raise urllib.error.URLError(socket.gaierror("fixture DNS failure"))
        if failure == "timeout":
            raise TimeoutError("fixture timeout")
        if failure == "hang":
            time.sleep(10)
        if failure == "slow_body":
            result = Response(value)
            result.read = lambda *args: (time.sleep(10), b"")[1]
            return result
        return Response(value)


storage = patch("os.replace", side_effect=OSError("fixture write failure")) if fixture.get("replace_failure") else nullcontext()
with patch("urllib.request.build_opener", return_value=Opener()), storage:
    started = time.monotonic()
    hook.main()
    Path(os.environ["PAYEE_TEST_CAPTURE"] + ".elapsed").write_text(str(time.monotonic() - started))
