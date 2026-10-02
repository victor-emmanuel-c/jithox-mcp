"""Export an existing git revision, then overlay ONLY its local MCP transport.

Never changes skills/commands, registers extensions, logs in, or launches a model.
"""
import argparse
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
from urllib.parse import urlsplit

from matrix import resolve_ref

RUNTIME_FILES = frozenset({".mcp.json", "mcp.json", "gemini-extension.json", "GEMINI.md", "plugin.json", "LICENSE", "PACKAGE.md"})
RUNTIME_DIRS = frozenset({".claude-plugin", ".cursor-plugin", "skills", "commands", "assets"})


def snapshot(repo, ref, destination):
    sha = resolve_ref(repo, ref)
    destination = Path(destination)
    if destination.exists():
        raise ValueError("Snapshot destination must not exist")
    result = subprocess.run(["git", "-C", str(Path(repo).resolve()), "-c", "core.autocrlf=false", "-c", "core.eol=lf", "archive", "--format=tar", sha], capture_output=True)
    if result.returncode:
        raise ValueError("Could not export committed revision")
    selected = []
    with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:") as archive:
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or "\\" in member.name or not path.parts:
                raise ValueError("Unsafe archive path")
            if member.name not in RUNTIME_FILES and path.parts[0] not in RUNTIME_DIRS:
                continue
            if not (member.isdir() or member.isfile()):
                raise ValueError("Runtime symlinks/special files are not supported")
            if member.isfile():
                handle = archive.extractfile(member)
                if handle is None:
                    raise ValueError("Unreadable runtime file")
                selected.append((path, handle.read()))
    destination.mkdir(parents=True)
    for path, data in selected:
        target = destination.joinpath(*path.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (destination / ".gebruik1-source.json").write_text(json.dumps({"ref": sha, "runtime_file_count": len(selected)}, indent=2) + "\n", encoding="utf-8")
    return sha, len(selected)


def overlay(root, url):
    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path != "/mcp" or parsed.port is None or not 1 <= parsed.port <= 65535:
        raise ValueError("Only the running loopback proxy URL is accepted")
    if not re.fullmatch(r"http://127\.0\.0\.1:[0-9]{1,5}/mcp", url):
        raise ValueError("Unexpected loopback URL form")
    root = Path(root)
    changes = []
    for name in (".mcp.json", "mcp.json", "gemini-extension.json"):
        file = root / name
        if not file.exists():
            continue
        value = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or set(value.get("mcpServers", {})) != {"jithox"}:
            raise ValueError("Unexpected MCP server configuration; stop rather than merge")
        value["mcpServers"] = {"jithox": {"httpUrl": url} if name == "gemini-extension.json" else {"type": "streamable-http" if name == "mcp.json" else "http", "url": url}}
        changes.append((file, json.dumps(value, indent=2) + "\n"))
    if len(changes) != 3:
        raise ValueError("Expected all three runtime MCP manifests")
    for file, content in changes:
        file.write_text(content, encoding="utf-8")
    return len(changes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--repo", default=str(Path(__file__).resolve().parents[2]))
    export.add_argument("--ref", required=True)
    export.add_argument("--destination", required=True, type=Path)
    patch = commands.add_parser("overlay")
    patch.add_argument("--snapshot", required=True, type=Path)
    patch.add_argument("--loopback", required=True)
    args = parser.parse_args()
    try:
        if args.command == "export":
            sha, count = snapshot(args.repo, args.ref, args.destination)
            print(f"ref={sha} runtime_file_count={count}")
        else:
            print(f"transport_file_count={overlay(args.snapshot, args.loopback)}")
    except (ValueError, OSError, subprocess.SubprocessError, tarfile.TarError):
        parser.exit(1, "Preparation refused: invalid revision, snapshot or loopback transport.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
