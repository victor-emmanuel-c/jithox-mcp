"""Anonymous, fixed-destination MCP relay; standard library, Python >=3.11.

Not a general proxy, OAuth broker, payment client, or evidence of model behavior.
No environment proxy, cookies, credentials, redirect following, or retries.
"""
import argparse
from datetime import datetime, timezone
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import re
import socket
import sys
import threading
import time
import uuid

UPSTREAM_URL = "https://jithox.com/api/mcp"
UPSTREAM_HOST = "jithox.com"
UPSTREAM_PATH = "/api/mcp"
MAX_REQUEST = 65536
MAX_RESPONSE = 1048576
TOOLS = frozenset({"preflight_payment", "verify_iban", "check_payment_change", "check_peppol_ready", "lookup_peppol_participant", "review_invoice", "check_vat_list", "kbo_company_search"})
PAID_COSTS = {
    "check_vat_list": "1 credit (EUR 0.01) per answered row; needs a bearer token.",
    "kbo_company_search": "2 credits (EUR 0.02) per successful call; needs a bearer token.",
}
PAID_ARGS = {
    "check_vat_list": {"rows": [{"vatId": "BE0403170701"}]},
    "kbo_company_search": {"vatNumber": "BE0403170701"},
}
RECEIPT_FIELDS = frozenset({"event_id", "session_id", "client", "ref", "prompt_id", "call_index", "tool", "outcome", "upstream_count", "started_at", "duration", "header_labels"})


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def valid_identity(client, ref, prompt_id):
    return client in {"claude", "gemini", "codex"} and isinstance(ref, str) and re.fullmatch(r"[0-9a-f]{40}", ref) and isinstance(prompt_id, str) and re.fullmatch(r"P(?:0[1-9]|10)", prompt_id)


def reject_constants(value):
    raise ValueError("Non-finite JSON is forbidden")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def parse_json(data):
    return json.loads(data, parse_constant=reject_constants, object_pairs_hook=unique_object)


def has_credential_fields(value):
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = key.lower().replace("_", "").replace("-", "")
            if normalized in {"authorization", "proxyauthorization", "cookie", "setcookie", "apikey", "accesstoken", "refreshtoken", "bearertoken", "password", "clientsecret"} or has_credential_fields(item):
                return True
    elif isinstance(value, list):
        return any(has_credential_fields(item) for item in value)
    return False


class Session:
    def __init__(self, client, ref, prompt_id, receipt, timeout=20):
        if not valid_identity(client, ref, prompt_id):
            raise ValueError("Expected an allowed client, resolved commit SHA, and P01..P10")
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 60:
            raise ValueError("Timeout must be finite and in (0, 60] seconds")
        self.client, self.ref, self.prompt_id = client, ref, prompt_id
        self.receipt = Path(receipt)
        self.timeout = timeout
        self.session_id = uuid.uuid4().hex
        self.host = "127.0.0.1"
        self.lock = threading.Lock()
        self.call_index = 0
        self.allowances = set()
        self.used_paid = set()
        self.server = None
        self.thread = None
        self.handle = None

    def __enter__(self):
        self.receipt.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation prevents mixing sessions or silently overwriting evidence.
        self.handle = self.receipt.open("x", encoding="utf-8", newline="\n")
        try:
            session = self

            class Handler(BaseHTTPRequestHandler):
                server_version = "gebruik1"
                sys_version = ""
                protocol_version = "HTTP/1.0"

                def setup(self):
                    super().setup()
                    self.connection.settimeout(session.timeout)

                def log_message(self, format, *args):
                    pass  # Base server logs contain paths/body fragments; never enable them.

                def do_POST(self):
                    session.handle_request(self)

                def do_GET(self):
                    session.handle_request(self)

                do_DELETE = do_GET
                do_PUT = do_GET
                do_PATCH = do_GET
                do_OPTIONS = do_GET
                do_HEAD = do_GET
                do_CONNECT = do_GET
                do_TRACE = do_GET

                def send_error(self, code, message=None, explain=None):
                    # Never echo request paths, malformed methods, or exception details.
                    session.respond(self, code, b'{"error":"request rejected"}')

            class Server(ThreadingHTTPServer):
                daemon_threads = False
                block_on_close = True
                allow_reuse_address = False

                def handle_error(self, request, client_address):
                    pass  # Never print raw exception context.

            self.server = Server((self.host, 0), Handler)
            self.port = self.server.server_port
            self.url = f"http://{self.host}:{self.port}/mcp"
            self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, name="gebruik1-loopback", daemon=False)
            self.thread.start()
            return self
        except BaseException:
            if self.server:
                self.server.server_close()
            self.handle.close()
            raise

    def __exit__(self, *unused):
        self.close()

    def close(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()  # Joins handlers; inbound/outbound sockets have deadlines.
            self.thread.join()
            self.server = None
        if self.handle is not None:
            self.handle.close()
            self.handle = None
        with self.lock:
            self.allowances.clear()

    def arm_paid(self, tool, consent):
        if tool not in PAID_COSTS or consent != f"ALLOW ANONYMOUS 401 {tool}":
            raise ValueError("Exact human consent required for an allowed anonymous fixture")
        with self.lock:
            if tool in self.used_paid:
                raise ValueError("This session already attempted that paid-boundary probe; no retry")
            self.allowances.add(tool)

    def consume_paid(self, tool, args):
        with self.lock:
            if args != PAID_ARGS[tool] or tool not in self.allowances:
                return False
            self.allowances.remove(tool)
            self.used_paid.add(tool)
            return True

    @staticmethod
    def respond(handler, status, body, headers=None):
        try:
            handler.send_response(status)
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Content-Length", str(len(body)))
            handler.send_header("Connection", "close")
            # Only protocol/session headers; no cookies, auth challenge, redirect or CORS.
            for key, value in (headers or {}).items():
                handler.send_header(key, value)
            handler.end_headers()
            if handler.command != "HEAD":
                handler.wfile.write(body)
        except (OSError, ValueError):
            pass
        handler.close_connection = True

    def handle_request(self, handler):
        started, clock = timestamp(), time.monotonic()
        with self.lock:
            self.call_index += 1
            call_index = self.call_index
        event_id = f"{self.session_id}-{call_index}"
        agent = f"gebruik1-eval/{self.client}/{self.ref}/{self.prompt_id}/{self.session_id}/call-{call_index}"
        receipt = dict(event_id=event_id, session_id=self.session_id, client=self.client, ref=self.ref, prompt_id=self.prompt_id, call_index=call_index, tool=None, outcome="request_rejected", upstream_count=0, started_at=started, duration=0, header_labels={"User-Agent": agent, "x-jithox-probe": "gebruik1-eval"})
        response_to_send = (400, b'{"error":"request_rejected"}', {})
        body_consumed = False
        def reject(status, outcome):
            nonlocal response_to_send
            receipt["outcome"] = outcome
            response_to_send = (status, json.dumps({"error": outcome}).encode(), {})
        try:
            if handler.command != "POST":
                return reject(405, "method_blocked")
            if handler.path != "/mcp":
                return reject(403, "destination_blocked")
            hosts = handler.headers.get_all("Host", [])
            if len(hosts) != 1 or hosts[0] not in {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}:
                return reject(403, "host_blocked")
            origins = handler.headers.get_all("Origin", [])
            if len(origins) > 1 or (origins and origins[0] != f"http://127.0.0.1:{self.port}"):
                return reject(403, "origin_blocked")
            if any(any(part in key.lower() for part in ("authorization", "cookie", "api-key", "apikey", "auth-token", "access-token")) for key in handler.headers):
                return reject(403, "credentials_blocked")
            if handler.headers.get("Transfer-Encoding") is not None:
                return reject(400, "framing_blocked")
            lengths = handler.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,10}", lengths[0]):
                return reject(400, "framing_blocked")
            length = int(lengths[0])
            if length > MAX_REQUEST:
                return reject(413, "request_too_large")
            if handler.headers.get_content_type() != "application/json":
                return reject(415, "content_type_blocked")
            data = handler.rfile.read(length)
            body_consumed = True
            if len(data) != length:
                return reject(400, "incomplete_request")
            try:
                obj = parse_json(data)
            except (ValueError, UnicodeError, RecursionError):
                return reject(400, "invalid_json")
            if not isinstance(obj, dict) or obj.get("jsonrpc") != "2.0" or not isinstance(obj.get("params", {}), dict):
                return reject(400, "invalid_rpc")
            if has_credential_fields(obj):
                return reject(403, "credentials_blocked")
            method = obj.get("method")
            if method == "tools/call" and "params" not in obj:
                return reject(400, "invalid_rpc")
            if method not in ("initialize", "notifications/initialized", "notifications/cancelled", "ping", "tools/list", "tools/call"):
                return reject(403, "rpc_method_blocked")
            if method == "tools/call":
                params = obj["params"]
                tool = params.get("name")
                if not isinstance(tool, str) or tool not in TOOLS:
                    return reject(403, "tool_blocked")
                receipt["tool"] = tool
                if not isinstance(params.get("arguments", {}), dict):
                    return reject(400, "arguments_blocked")
                if tool == "review_invoice":
                    return reject(403, "paid_review_blocked")
                if tool in PAID_COSTS and not self.consume_paid(tool, params.get("arguments", {})):
                    return reject(403, "paid_blocked")
            headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", "User-Agent": agent, "x-jithox-probe": "gebruik1-eval"}
            for key in ("MCP-Protocol-Version", "Mcp-Session-Id"):
                value = handler.headers.get(key)
                if value is not None:
                    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,200}", value):
                        return reject(400, "protocol_header_blocked")
                    headers[key] = value
            connection = None
            deadline_timer = None
            deadline_expired = threading.Event()
            try:
                connection = http.client.HTTPSConnection(UPSTREAM_HOST, timeout=self.timeout)
                connection.connect()
                upstream_socket = connection.sock
                def expire_upstream():
                    deadline_expired.set()
                    try:
                        upstream_socket.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                # A socket inactivity timeout alone permits an endless drip-feed.
                # Bound the entire request/headers/body phase as well.
                deadline_timer = threading.Timer(self.timeout, expire_upstream)
                deadline_timer.start()
                connection.request("POST", UPSTREAM_PATH, body=data, headers=headers)
                receipt["upstream_count"] = 1
                response = connection.getresponse()
                payload = response.read(MAX_RESPONSE + 1)
                if deadline_expired.is_set():
                    return reject(504, "upstream_timeout")
                if len(payload) > MAX_RESPONSE:
                    return reject(502, "upstream_response_too_large")
                if 300 <= response.status < 400:
                    return reject(502, "upstream_redirect_blocked")
                if response.status >= 400:
                    receipt["outcome"] = f"upstream_http_{response.status}"
                elif response.status in (202, 204) and not payload:
                    receipt["outcome"] = "upstream_notification_accepted"
                else:
                    try:
                        result = parse_json(payload)
                        if not isinstance(result, dict) or result.get("jsonrpc") != "2.0" or not ("result" in result or "error" in result):
                            raise ValueError("Invalid RPC response")
                    except (ValueError, UnicodeError, RecursionError):
                        return reject(502, "upstream_invalid_response")
                    if "error" in result:
                        receipt["outcome"] = "upstream_rpc_error"
                    elif isinstance(result.get("result"), dict) and result["result"].get("isError") is True:
                        receipt["outcome"] = "upstream_tool_error"
                    else:
                        receipt["outcome"] = "upstream_ok"
                response_headers = {}
                for key in ("MCP-Protocol-Version", "Mcp-Session-Id"):
                    value = response.getheader(key)
                    if value is not None and re.fullmatch(r"[A-Za-z0-9._:-]{1,200}", value):
                        response_headers[key] = value
                response_to_send = (response.status, payload, response_headers)
            except (TimeoutError, socket.timeout):
                reject(504, "upstream_timeout")
            except (OSError, http.client.HTTPException):
                if deadline_expired.is_set():
                    reject(504, "upstream_timeout")
                else:
                    reject(502, "upstream_connection_error")
            finally:
                if deadline_timer is not None:
                    deadline_timer.cancel()
                    deadline_timer.join()
                if connection is not None:
                    connection.close()
        except (TimeoutError, socket.timeout):
            reject(408, "request_timeout")
        except (OSError, ValueError, TypeError, RecursionError):
            reject(400, "request_rejected")
        finally:
            # Drain only a bounded, explicitly framed rejected body. Otherwise
            # Windows can reset the connection before the rejection is received.
            if not body_consumed:
                lengths = handler.headers.get_all("Content-Length", [])
                if len(lengths) == 1 and re.fullmatch(r"[0-9]{1,10}", lengths[0]) and int(lengths[0]) <= MAX_REQUEST + 1 and handler.headers.get("Transfer-Encoding") is None:
                    try:
                        handler.rfile.read(int(lengths[0]))
                    except OSError:
                        pass
            receipt["duration"] = round(time.monotonic() - clock, 6)
            with self.lock:
                self.handle.write(json.dumps(receipt, ensure_ascii=True, allow_nan=False) + "\n")
                self.handle.flush()
            # A caller must not observe a response before its receipt is flushed.
            self.respond(handler, *response_to_send)


def operator_consent(session, tool, input_fn=input, is_tty=None):
    if is_tty is None:
        is_tty = sys.stdin.isatty()
    if not is_tty or tool not in PAID_COSTS:
        raise ValueError("Consent requires an interactive human terminal and supported tool")
    print(PAID_COSTS[tool])
    print("Anonymous access-refusal test only. Never authenticate or pay. One request, no retry.")
    consent = input_fn(f"Type ALLOW ANONYMOUS 401 {tool} to consent: ")
    session.arm_paid(tool, consent)
    print("One anonymous fixture request armed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", choices=("claude", "gemini", "codex"), required=True)
    parser.add_argument("--ref", required=True, help="Resolved 40-character commit SHA, not HEAD or a tag")
    parser.add_argument("--prompt", required=True, help="P01..P10")
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=20)
    args = parser.parse_args()
    if not sys.stdin.isatty():
        parser.error("Interactive operator terminal required; no autoapproval or background daemon")
    try:
        with Session(args.client, args.ref, args.prompt, args.receipt, args.timeout) as session:
            print(f"loopback={session.url} session_id={session.session_id}")
            print("Commands: arm check_vat_list | arm kbo_company_search | stop")
            try:
                while True:
                    command = input("operator> ").strip()
                    if command == "stop":
                        break
                    if command.startswith("arm "):
                        try:
                            operator_consent(session, command[4:])
                        except ValueError:
                            print("Not armed; consent was absent or invalid.")
                    else:
                        print("Unknown command; nothing changed.")
            except (KeyboardInterrupt, EOFError):
                pass
    except (OSError, ValueError):
        parser.exit(1, "Proxy could not start or finish; no credentials or exception details logged.\n")


if __name__ == "__main__":
    main()
