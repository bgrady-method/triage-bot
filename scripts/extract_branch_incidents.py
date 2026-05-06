#!/usr/bin/env python3
"""One-shot extractor: pull alert-specific incident-log lines from every
origin/claude/triage-* branch that aren't already on main, dedupe by
alert_hash, and emit them sorted by ts. Read-only by default; pass
--apply to append to kb/incident-log.jsonl in-place.

Usage:
    python scripts/extract_branch_incidents.py            # dry-run, prints summary
    python scripts/extract_branch_incidents.py --apply    # appends to kb/incident-log.jsonl
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INCIDENT_LOG = REPO_ROOT / "kb" / "incident-log.jsonl"


def run(cmd: list[str], **kwargs) -> str:
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, **kwargs)
    if out.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed: {out.stderr}")
    return out.stdout


def list_triage_branches() -> list[str]:
    raw = run(["git", "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin/claude/triage-*"])
    return [b.strip() for b in raw.splitlines() if b.strip()]


def read_branch_log(ref: str) -> list[dict]:
    try:
        raw = run(["git", "show", f"{ref}:kb/incident-log.jsonl"])
    except RuntimeError:
        return []
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def read_main_log() -> list[dict]:
    out = []
    with INCIDENT_LOG.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="append missing lines to kb/incident-log.jsonl")
    args = ap.parse_args()

    branches = list_triage_branches()
    print(f"discovered {len(branches)} triage branches", file=sys.stderr)

    main_log = read_main_log()
    main_hashes = {entry["alert_hash"] for entry in main_log if entry.get("alert_hash")}
    print(f"main incident-log: {len(main_log)} lines, {len(main_hashes)} with alert_hash", file=sys.stderr)

    by_hash: dict[str, dict] = {}
    skipped_no_hash = 0
    skipped_already_main = 0

    for ref in branches:
        for entry in read_branch_log(ref):
            h = entry.get("alert_hash")
            if not h:
                skipped_no_hash += 1
                continue
            if h in main_hashes:
                skipped_already_main += 1
                continue
            existing = by_hash.get(h)
            if existing is None or entry.get("ts", "") < existing.get("ts", ""):
                by_hash[h] = entry

    new_entries = sorted(by_hash.values(), key=lambda e: e.get("ts", ""))
    print(
        f"unique new alert_hashes: {len(new_entries)}; "
        f"skipped {skipped_no_hash} no-hash, {skipped_already_main} already-on-main",
        file=sys.stderr,
    )

    if args.apply:
        with INCIDENT_LOG.open("a", encoding="utf-8") as fh:
            for entry in new_entries:
                fh.write(json.dumps(entry) + "\n")
        print(f"appended {len(new_entries)} lines to {INCIDENT_LOG}", file=sys.stderr)
    else:
        for entry in new_entries:
            print(json.dumps(entry))

    return 0


if __name__ == "__main__":
    sys.exit(main())
