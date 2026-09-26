"""Deterministic Claude Code payment hook. Standard library only."""
import json
from contextlib import contextmanager
import os
from pathlib import Path
import queue
import re
import sys
import stat
import threading
import time
import urllib.request
import uuid

VERSION = "0.1.0"
ENDPOINT = "https://jithox.com/api/mcp"
TIMEOUT = 3
LIMIT = 256 * 1024
DEFAULT_PATTERN = r"^mcp__.+__.*(?:transfer|send|pay|payment|wire|payout|charge|withdraw).*"
FALLBACK = "Jithox unavailable or unreadable; verify by calling the supplier using your own records."
IBAN_TEXT = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]{2}[0-9]{2}[A-Za-z0-9]*(?:[\s-]+[A-Za-z0-9]{1,4}(?![A-Za-z0-9]))*")


def mod97(iban):
    if not re.fullmatch(r"[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}", iban):
        return False
    digits = "".join(str(ord(c) - 55) if c.isalpha() else c for c in iban[4:] + iban[:4])
    return int(digits) % 97 == 1


def candidates(value):
    if isinstance(value, str):
        found = []
        consumed = 0
        for start in re.finditer(r"(?<![A-Za-z0-9])[A-Za-z]{2}[0-9]{2}", value):
            if start.start() < consumed:
                continue
            match = IBAN_TEXT.match(value, start.start())
            assert match is not None
            iban = ""
            for part in re.finditer(r"[A-Za-z0-9]+", match.group()):
                iban += part.group().upper()
                if mod97(iban):
                    consumed = match.start() + part.end()
                    break
            found.append(iban)
        return list(dict.fromkeys(found))
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, list):
        return list(dict.fromkeys(iban for item in value for iban in candidates(item)))
    return []


def askJithox(new_iban, on_file=None, country=None, *, probe=None):
    arguments = {"newIban": new_iban}
    if on_file:
        arguments["ibanOnFile"] = on_file
    if country:
        arguments["supplierCountry"] = country
    headers = {
        "Content-Type": "application/json", "Accept": "application/json, text/event-stream",
        "User-Agent": "claude-payee-hook/" + VERSION}
    if probe is not None:
        if not re.fullmatch(r"t_[0-9a-f]{8}", probe):
            raise ValueError("invalid probe marker")
        headers["x-jithox-probe"] = probe
    request = urllib.request.Request(ENDPOINT, method="POST", headers=headers, data=json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "check_payment_change", "arguments": arguments}}).encode())
    results = queue.Queue(maxsize=1)

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            raise ValueError("redirect refused")

    def request_result():
        try:
            # No redirects or ambient proxy: account data goes to this origin only.
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
            with opener.open(request, timeout=TIMEOUT) as response:
                if response.status != 200:
                    raise ValueError("HTTP failure")
                body = response.read(LIMIT + 1)
                if len(body) > LIMIT:
                    raise ValueError("response too large")
                text = body.decode("utf-8")
                content_type = response.headers.get("Content-Type", "").split(";")[0].strip()
                if content_type == "text/event-stream":
                    messages = [json.loads("\n".join(line[5:].lstrip() for line in block.splitlines()
                                if line.startswith("data:"))) for block in text.replace("\r\n", "\n").split("\n\n")
                                if any(line.startswith("data:") for line in block.splitlines())]
                    matches = [m for m in messages if isinstance(m, dict) and m.get("id") == 1]
                    if len(matches) != 1:
                        raise ValueError("ambiguous SSE response")
                    envelope = matches[0]
                elif content_type == "application/json":
                    envelope = json.loads(text)
                else:
                    raise ValueError("unexpected response type")
            if envelope.get("jsonrpc") != "2.0" or envelope.get("id") != 1 or "error" in envelope:
                raise ValueError("RPC failure")
            result = envelope["result"]
            if result.get("isError", False) is not False:
                raise ValueError("tool failure")
            content = result["content"]
            if len(content) != 1 or content[0]["type"] != "text":
                raise ValueError("ambiguous tool response")
            payload = json.loads(content[0]["text"])
            if payload["kind"] != "payment_change_check":
                raise ValueError("wrong tool result")
            data = payload["data"]
            if data["verdict"] not in ("no_change", "verify_first", "stop", "invalid_new_account"):
                raise ValueError("unknown verdict")
            steps = data["requiredSteps"]
            if not isinstance(steps, list) or not steps or not all(isinstance(s, str) and s.strip() for s in steps):
                raise ValueError("missing callback steps")
            results.put(data)
        except Exception:
            results.put(None)  # Never echo network bodies, exception strings or accounts.

    threading.Thread(target=request_result, daemon=True).start()
    try:
        result = results.get(timeout=TIMEOUT)
    except queue.Empty:
        result = None
    if result is None:
        raise ValueError("Jithox unavailable")
    return result


def decision(kind, reason):
    # Redact first, truncate second. Includes accounts echoed by the service.
    reason = IBAN_TEXT.sub("[account redacted]", reason)
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
            "permissionDecision": kind, "permissionDecisionReason": reason[:12000]}}


def check_account(iban, on_file, country):
    suffix = "account ending " + iban[-4:] + ". "
    if not mod97(iban):
        return "deny", "invalid_new_account: " + suffix + "Request corrected details using your own supplier contact."
    try:
        result = askJithox(iban, on_file, country)
        kind = "deny" if result["verdict"] in ("stop", "invalid_new_account") else "ask"
        if result["verdict"] == "no_change" and on_file == iban:
            kind = "allow"
        return kind, result["verdict"] + ": " + suffix + " ".join(result["requiredSteps"])
    except Exception:
        return "ask", "error: " + suffix + FALLBACK


def payee_key(data):
    fields = os.environ.get("JITHOX_PAYEE_FIELDS", "name,naam,creditor,beneficiary").split(",")
    if not fields or len(fields) > 16 or any(not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", f) for f in fields):
        raise ValueError("invalid payee field configuration")
    values = []
    for field in fields:
        value = data["tool_input"]
        for part in field.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        values.append(value)
    names = {v.strip() for v in values if isinstance(v, str) and v.strip()}
    if len(names) != 1:
        return None
    return json.dumps([data["tool_name"], names.pop()], separators=(",", ":"))


def successful(response):
    def failed(value):
        if isinstance(value, list):
            return any(failed(v) for v in value)
        if not isinstance(value, dict):
            return False
        if (value.get("isError", False) is not False or value.get("error")
                or value.get("success", True) is False or value.get("ok", True) is False
                or value.get("status") in ("failed", "error", "pending", "cancelled", "rejected")):
            return True
        return any(failed(v) for v in value.values())
    if failed(response):
        return False
    if isinstance(response, dict) and "structuredContent" in response:
        if not successful(response["structuredContent"]):
            return False
        if "content" not in response:
            return True
    if isinstance(response, dict) and "content" in response:
        response = response["content"]
    if isinstance(response, list):
        if len(response) != 1 or not isinstance(response[0], dict) or response[0].get("type") != "text":
            return False
        try:
            return successful(json.loads(response[0]["text"]))
        except (ValueError, KeyError, TypeError):
            return False
    return (isinstance(response, dict) and (response.get("success") is True or response.get("ok") is True
            or response.get("status") in ("succeeded", "completed", "paid")))


def checked_stat(info, *, directory=False):
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError("memory link refused")
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected(info.st_mode) or (not directory and info.st_nlink != 1):
        raise ValueError("unexpected memory file type")
    if os.name == "posix":
        mode = 0o700 if directory else 0o600
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != mode:
            raise ValueError("memory must be private")


@contextmanager
def memory_directory(directory, create=False):
    """Anchor POSIX operations to no-follow directory descriptors, not path strings."""
    if not directory.is_absolute():
        raise ValueError("memory directory must be absolute")
    if os.name != "posix":
        # Windows: refuse visible reparse points/junctions at every component.
        # ACLs and protection against same-user path swaps are operator responsibilities.
        for part in reversed((directory, *directory.parents)):
            try:
                info = part.lstat()
            except FileNotFoundError:
                if part != directory or not create:
                    raise
                try:
                    part.mkdir(mode=0o700)
                except FileExistsError:
                    pass
                info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError("memory directory link refused")
        checked_stat(directory.lstat(), directory=True)
        yield None
        return
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(directory.anchor, flags)
    try:
        for i, part in enumerate(directory.parts[1:], 1):
            if create and i == len(directory.parts) - 1:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        checked_stat(os.fstat(fd), directory=True)
        yield fd
    finally:
        os.close(fd)


def at(directory, fd, name):
    return name if fd is not None else directory / name


def load_memory(directory, fd):
    path = at(directory, fd, "payees.json")
    try:
        before = os.stat(path, dir_fd=fd, follow_symlinks=False)
    except FileNotFoundError:
        return {"version": 1, "payees": {}}
    checked_stat(before)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    handle = os.open(path, flags, dir_fd=fd)
    with os.fdopen(handle, "rb") as stream:
        after = os.fstat(stream.fileno())
        checked_stat(after)
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise ValueError("memory changed during open")
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError("memory too large")
    memory = json.loads(raw)
    if not isinstance(memory, dict) or memory.get("version") != 1 or not isinstance(memory.get("payees"), dict):
        raise ValueError("unknown memory schema")
    for key, iban in memory["payees"].items():
        pair = json.loads(key)
        if not isinstance(pair, list) or len(pair) != 2 or not all(isinstance(v, str) and v for v in pair):
            raise ValueError("invalid memory key")
        if not isinstance(iban, str) or not mod97(iban):
            raise ValueError("invalid memory account")
    return memory


def read_memory(directory):
    try:
        with memory_directory(directory) as fd:
            return load_memory(directory, fd)
    except FileNotFoundError:
        return {"version": 1, "payees": {}}


def remember(directory, key, iban):
    with memory_directory(directory, create=True) as fd:
        lock = at(directory, fd, "write.lock")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        deadline = time.monotonic() + 1
        while True:
            try:
                handle = os.open(lock, flags, 0o600, dir_fd=fd)
                os.close(handle)
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise ValueError("memory writer busy")
                time.sleep(0.01)
        temp = at(directory, fd, "pending-" + uuid.uuid4().hex)
        created = False
        try:
            memory = load_memory(directory, fd)
            memory["payees"][key] = iban
            raw = json.dumps(memory, ensure_ascii=True).encode()
            if len(raw) > LIMIT:
                raise ValueError("memory capacity reached")
            handle = os.open(temp, flags, 0o600, dir_fd=fd)
            created = True
            with os.fdopen(handle, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            # Re-check the destination immediately before atomic replacement.
            load_memory(directory, fd)
            os.replace(temp, at(directory, fd, "payees.json"), src_dir_fd=fd, dst_dir_fd=fd)
            created = False
            if fd is not None:
                os.fsync(fd)
        finally:
            if created:
                os.unlink(temp, dir_fd=fd)
            os.unlink(lock, dir_fd=fd)


def handle(data, mode):
    if mode not in ("PreToolUse", "PostToolUse") or data["hook_event_name"] != mode:
        raise ValueError("wrong event")
    inputs = data["tool_input"]
    if not isinstance(inputs, dict) or not isinstance(data["tool_name"], str):
        raise ValueError("invalid tool event")
    pattern = os.environ.get("JITHOX_PAYEE_TOOL_PATTERN", DEFAULT_PATTERN)
    if not pattern or len(pattern) > 512:
        raise ValueError("invalid matcher configuration")
    if not re.search(pattern, data["tool_name"], re.IGNORECASE):
        return {}
    ibans = candidates(inputs)
    if not ibans:
        return {"systemMessage": "Jithox checked nothing: no IBAN found."}
    if len(ibans) > 16:
        raise ValueError("too many account candidates")
    key = payee_key(data)
    directory = Path(os.environ.get("JITHOX_PAYEE_MEMORY_DIR", str(Path.home() / ".claude-payee-hook")))
    if mode == "PostToolUse":
        if key and len(ibans) == 1 and mod97(ibans[0]) and successful(data.get("tool_response")):
            remember(directory, key, ibans[0])
            return {"systemMessage": "Jithox remembered the account after tool-reported success; not proof of settlement or ownership."}
        return {"systemMessage": "Jithox remembered nothing: success or payee/account association was not explicit."}
    memory = read_memory(directory)
    on_file = memory["payees"].get(key) if key else None
    country = inputs.get("supplierCountry")
    if country is not None:
        if not isinstance(country, str) or not re.fullmatch(r"[A-Za-z]{2}", country):
            raise ValueError("invalid supplier country")
        country = country.upper()
    completed = queue.Queue()

    def check(index, iban):
        completed.put((index, check_account(iban, on_file, country)))

    for index, iban in enumerate(ibans):
        threading.Thread(target=check, args=(index, iban), daemon=True).start()
    deadline = time.monotonic() + TIMEOUT + 0.25
    results = [("ask", "error: account ending " + iban[-4:] + ". " + FALLBACK) for iban in ibans]
    for _ in ibans:
        try:
            index, result = completed.get(timeout=max(0.001, deadline - time.monotonic()))
        except queue.Empty:
            break
        results[index] = result
    kind = max((item[0] for item in results), key=lambda k: {"allow": 0, "ask": 1, "deny": 2}[k])
    note = "No local account record: first registration or missing/ambiguous payee.\n" if on_file is None else ""
    return decision(kind, note + "\n".join(item[1] for item in results))


def main():
    mode = sys.argv[1] if len(sys.argv) == 2 else "PreToolUse"
    try:
        raw = sys.stdin.buffer.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise ValueError("input too large")
        data = json.loads(raw)
        output = handle(data, mode)
    except Exception:
        output = (decision("ask", FALLBACK) if mode != "PostToolUse" else
                  {"systemMessage": "Jithox could not update local memory; the next call must be checked again."})
    print(json.dumps(output))


if __name__ == "__main__":
    main()
