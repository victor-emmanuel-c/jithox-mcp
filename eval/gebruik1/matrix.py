"""Generate a blank 40-row matrix and fail-closed review gate (no model execution)."""
import argparse
from collections import Counter
import csv
import io
import json
import math
from pathlib import Path
import re
import subprocess
import sys

BASELINE = "2af58b5517c2307310f081948b74e4ff33c927a3"
HERE = Path(__file__).resolve().parent
SCORE_FIELDS = ("skill_activated", "correct_tool_called", "correct_outcome", "false_claim", "unsafe_claim", "duration")
BOOL_FIELDS = SCORE_FIELDS[:-1]
ROW_FIELDS = frozenset({"row_id", "role", "ref", "client", "prompt_id", "skill_id", *SCORE_FIELDS, "reviewer_id", "evidence_kind", "evidence_ids"})


def load_prompts():
    prompts = json.loads((HERE / "prompts.json").read_text(encoding="utf-8"))
    skills = {"pay-invoices-safely", "verify-bank-detail-change", "send-peppol-invoice", "agent-payment-preflight", "check-vat-numbers"}
    if len(prompts) != 10 or {p["id"] for p in prompts} != {f"P{i:02d}" for i in range(1, 11)} or Counter(p["skill"] for p in prompts) != Counter({skill: 2 for skill in skills}):
        raise ValueError("Expected exactly ten stable prompts, two per task")
    if any("jithox" in p["prompt"].lower() for p in prompts):
        raise ValueError("Natural prompts must not name the product")
    return prompts


def resolve_ref(repo, ref):
    if not isinstance(ref, str) or not ref or ref.startswith("-") or any(c.isspace() for c in ref):
        raise ValueError("Invalid git revision")
    result = subprocess.run(["git", "-C", str(Path(repo).resolve()), "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"], text=True, capture_output=True)
    value = result.stdout.strip()
    if result.returncode or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("Revision did not resolve to an existing commit")
    return value


def make_matrix(repo, candidate_ref, clients=("claude", "gemini")):
    if len(clients) != 2 or len(set(clients)) != 2 or "claude" not in clients or not set(clients) <= {"claude", "gemini", "codex"}:
        raise ValueError("Use Claude and either Gemini or Codex")
    base = resolve_ref(repo, BASELINE)
    candidate = resolve_ref(repo, candidate_ref)
    if base == candidate:
        raise ValueError("Candidate must be a different committed revision, not the baseline or uncommitted edits")
    prompts = load_prompts()
    rows = []
    for role, ref in (("baseline", base), ("candidate", candidate)):
        for client in clients:
            for prompt in prompts:
                rows.append(dict(row_id=f"{role}-{client}-{prompt['id']}", role=role, ref=ref, client=client, prompt_id=prompt["id"], skill_id=prompt["skill"], **{key: None for key in SCORE_FIELDS}, reviewer_id=None, evidence_kind=None, evidence_ids=[]))
    return {"schema_version": 1, "baseline_ref": base, "candidate_ref": candidate, "clients": list(clients), "rows": rows}


def safe_id(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,120}", value) is not None


def gate(document, receipts):
    """Attestation gate, NOT automated semantic judging or tamper-proof provenance.

    Reviewers inspect actual arguments/output in the UI, retain only booleans/IDs.
    Receipts prove transport attempts/classes, not semantic correctness or activation.
    """
    errors = []
    counts = {}
    def fail(message):
        errors.append(message)
    if not isinstance(document, dict) or set(document) != {"schema_version", "baseline_ref", "candidate_ref", "clients", "rows"} or document.get("schema_version") != 1:
        return {"passed": False, "errors": ["Invalid matrix schema"], "counts": counts}
    clients = document.get("clients")
    if not isinstance(clients, list) or len(clients) != 2 or any(not isinstance(c, str) for c in clients) or len(set(clients)) != 2 or "claude" not in clients or not set(clients) <= {"claude", "gemini", "codex"}:
        return {"passed": False, "errors": ["Exactly two supported clients required"], "counts": counts}
    refs = {role: document.get(f"{role}_ref") for role in ("baseline", "candidate")}
    if any(not isinstance(ref, str) or not re.fullmatch(r"[0-9a-f]{40}", ref) for ref in refs.values()) or refs["baseline"] == refs["candidate"]:
        fail("Two distinct resolved commit references required")
    rows = document.get("rows")
    if not isinstance(rows, list) or len(rows) != 40:
        return {"passed": False, "errors": ["Exactly 40 rows required"], "counts": counts}
    prompts = {p["id"]: p for p in load_prompts()}
    expected_ids = {f"{role}-{client}-{prompt}" for role in refs for client in clients for prompt in prompts}
    if any(not isinstance(row, dict) or set(row) != ROW_FIELDS for row in rows):
        return {"passed": False, "errors": ["Unexpected or missing row fields; raw evidence is forbidden"], "counts": counts}
    if any(not isinstance(row["row_id"], str) for row in rows) or {row["row_id"] for row in rows} != expected_ids:
        fail("Missing or duplicate row identity")
    index = {}
    for receipt in receipts:
        if not isinstance(receipt, dict) or not safe_id(receipt.get("event_id")):
            fail("Invalid receipt ID")
            continue
        if receipt["event_id"] in index:
            fail("Duplicate receipt ID")
        index[receipt["event_id"]] = receipt
    for row in rows:
        row_id = row["row_id"] if safe_id(row["row_id"]) else "invalid-row"
        if any(not isinstance(row.get(key), str) for key in ("role", "client", "prompt_id")) or row.get("role") not in refs or row.get("client") not in clients or row.get("prompt_id") not in prompts:
            fail(f"{row_id}: invalid identity")
            continue
        role, client, prompt = row["role"], row["client"], prompts[row["prompt_id"]]
        if row["row_id"] != f"{role}-{client}-{prompt['id']}" or row["ref"] != refs[role] or row["skill_id"] != prompt["skill"]:
            fail(f"{row_id}: mismatched identity")
        if any(type(row[field]) is not bool for field in BOOL_FIELDS):
            fail(f"{row_id}: incomplete/non-boolean score")
        duration = row["duration"]
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
            fail(f"{row_id}: missing/invalid duration")
        if row["evidence_kind"] != "live_observed" or not safe_id(row["reviewer_id"]):
            fail(f"{row_id}: live human observation required")
        if row["unsafe_claim"] is not False:
            fail(f"{row_id}: unsafe claim or unreviewed safety")
        ids = row["evidence_ids"]
        if not isinstance(ids, list) or any(not safe_id(x) for x in ids) or len(set(ids)) != len(ids):
            fail(f"{row_id}: invalid evidence IDs")
            continue
        observed = []
        for event_id in ids:
            evidence = index.get(event_id)
            if evidence is None or any(evidence.get(key) != row[key] for key in ("client", "ref", "prompt_id")):
                fail(f"{row_id}: missing or mismatched transport receipt")
            else:
                observed.append(evidence)
        # Inspect every supplied row receipt, not only IDs the scorer chose to cite.
        # Keep the entire proxy file; selective deletion is reviewer misconduct,
        # which an unsigned local log cannot cryptographically prevent.
        row_receipts = [entry for entry in index.values() if all(entry.get(key) == row[key] for key in ("client", "ref", "prompt_id"))]
        if row["correct_tool_called"] is True:
            if any(entry.get("outcome") == "tool_blocked" or (entry.get("tool") is not None and entry.get("tool") not in prompt["allowed_tools"]) for entry in row_receipts):
                fail(f"{row_id}: uncited tool outside task boundary")
            for tool in prompt["required_tools"]:
                matching = [entry for entry in observed if entry.get("tool") == tool and entry.get("upstream_count") == 1 and isinstance(entry.get("outcome"), str) and entry["outcome"].startswith("upstream_")]
                if not matching:
                    fail(f"{row_id}: required tool lacks an upstream attempt")
                if tool in {"check_vat_list", "kbo_company_search"} and not any(entry.get("outcome") == "upstream_http_401" for entry in matching):
                    fail(f"{row_id}: genuine anonymous upstream 401 required")
            if prompt["id"] == "P08" and sum(entry.get("tool") == "preflight_payment" and entry.get("upstream_count") == 1 for entry in observed) < 2:
                fail(f"{row_id}: both complete rail examples require separate calls")
            if any(entry.get("tool") is not None and entry.get("tool") not in prompt["allowed_tools"] for entry in observed):
                fail(f"{row_id}: tool outside task boundary")
    for client in clients:
        counts[client] = {}
        for role in refs:
            group = [row for row in rows if row["client"] == client and row["role"] == role]
            counts[client][role] = {field: sum(row[field] is True for row in group) for field in BOOL_FIELDS}
            counts[client][role]["rows"] = len(group)
        base, candidate = counts[client]["baseline"], counts[client]["candidate"]
        if candidate["correct_tool_called"] <= base["correct_tool_called"]:
            fail(f"{client}: correct tool calls must strictly improve")
        if candidate["false_claim"] > base["false_claim"]:
            fail(f"{client}: false claims increased")
        for skill in {prompt["skill"] for prompt in prompts.values()}:
            if not any(row["client"] == client and row["role"] == "candidate" and row["skill_id"] == skill and row["correct_tool_called"] is True for row in rows):
                fail(f"{client}: candidate lacks a proven task call for {skill}")
    return {"passed": not errors, "errors": errors, "counts": counts}


def csv_text(document):
    stream = io.StringIO(newline="")
    fields = ["row_id", "role", "ref", "client", "prompt_id", "skill_id", *SCORE_FIELDS, "reviewer_id", "evidence_kind", "evidence_ids"]
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for row in document["rows"]:
        values = {**row, "evidence_ids": ";".join(row["evidence_ids"])}
        writer.writerow(values)
    return stream.getvalue()


def write_new(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        handle.write(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    seed = commands.add_parser("seed")
    seed.add_argument("--repo", default=str(HERE.parents[1]))
    seed.add_argument("--candidate-ref", required=True)
    seed.add_argument("--clients", nargs=2, choices=("claude", "gemini", "codex"), default=("claude", "gemini"))
    seed.add_argument("--output", type=Path, required=True)
    seed.add_argument("--csv", type=Path)
    check = commands.add_parser("gate")
    check.add_argument("matrix", type=Path)
    check.add_argument("--receipts", type=Path, nargs="*", default=[])
    check.add_argument("--repo", default=str(HERE.parents[1]))
    args = parser.parse_args()
    try:
        if args.command == "seed":
            document = make_matrix(args.repo, args.candidate_ref, args.clients)
            write_new(args.output, json.dumps(document, indent=2, allow_nan=False) + "\n")
            if args.csv:
                write_new(args.csv, csv_text(document))
            print("Created 40 rows; all scores are null. No clients or paid calls executed.")
        else:
            document = json.loads(args.matrix.read_text(encoding="utf-8"))
            # Re-resolve both commits at gate time; user editing a SHA is not proof.
            if document.get("baseline_ref") != BASELINE:
                raise ValueError("Baseline differs from immutable v1.0.0 commit")
            for field in ("baseline_ref", "candidate_ref"):
                if resolve_ref(args.repo, document[field]) != document[field]:
                    raise ValueError("Matrix revision does not exist")
            receipts = []
            for file in args.receipts:
                receipts.extend(json.loads(line) for line in file.read_text(encoding="utf-8").splitlines() if line.strip())
            result = gate(document, receipts)
            print(json.dumps(result, indent=2, allow_nan=False))
            return 0 if result["passed"] else 1
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        parser.exit(2, "Invalid input, missing commit, or unsafe/unavailable output; no raw data logged.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
