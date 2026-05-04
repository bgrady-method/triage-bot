"""Mirror the system-design course into references/system-design/.

Source:  https://github.com/benjgrad/learn/tree/main/ai-fluency-platform/content/system-design
Target:  <repo>/references/system-design/

Idempotent: re-running with no upstream changes is a no-op (size + content match).
Parallel: fetches modules with a ThreadPoolExecutor (default 16 workers).

Usage:
    python scripts/sync_course_content.py
    python scripts/sync_course_content.py --workers 8 --force

Exits non-zero if any module fails to fetch (the others still land on disk).
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAW_BASE = (
    "https://raw.githubusercontent.com/benjgrad/learn/main/"
    "ai-fluency-platform/content/system-design"
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET_ROOT = REPO_ROOT / "references" / "system-design"


def fetch(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "triage-bot-course-sync"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def write_if_changed(path: Path, content: bytes, force: bool) -> str:
    """Write content to path. Return one of: 'created', 'updated', 'unchanged'."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        existing = path.read_bytes()
        if existing == content:
            return "unchanged"
        path.write_bytes(content)
        return "updated"
    if path.exists():
        path.write_bytes(content)
        return "updated"
    path.write_bytes(content)
    return "created"


def fetch_one(level_slug: str, module_slug: str, force: bool) -> tuple[str, str, str | None]:
    """Fetch one module JSON. Returns (level_slug, module_slug, error_or_none)."""
    url = f"{RAW_BASE}/{level_slug}/{module_slug}.json"
    target = TARGET_ROOT / level_slug / f"{module_slug}.json"
    try:
        body = fetch(url)
        write_if_changed(target, body, force)
        return (level_slug, module_slug, None)
    except urllib.error.HTTPError as e:
        return (level_slug, module_slug, f"HTTP {e.code}: {url}")
    except urllib.error.URLError as e:
        return (level_slug, module_slug, f"URL error {e.reason}: {url}")
    except OSError as e:
        return (level_slug, module_slug, f"IO error: {e}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workers", type=int, default=16, help="parallel fetchers (default 16)")
    ap.add_argument("--force", action="store_true", help="overwrite even if content unchanged")
    args = ap.parse_args()

    TARGET_ROOT.mkdir(parents=True, exist_ok=True)

    print(f"sync source: {RAW_BASE}")
    print(f"sync target: {TARGET_ROOT}")
    print()

    # Step 1 — fetch the curriculum index
    curriculum_url = f"{RAW_BASE}/curriculum.json"
    try:
        curriculum_bytes = fetch(curriculum_url)
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        print(f"fatal: could not fetch curriculum.json: {e}", file=sys.stderr)
        return 2

    curriculum = json.loads(curriculum_bytes.decode("utf-8"))
    write_if_changed(TARGET_ROOT / "curriculum.json", curriculum_bytes, args.force)
    print(f"curriculum.json: {len(curriculum.get('levels', []))} levels")

    # Step 2 — enumerate (level, module) pairs from the modules dict
    modules_by_level = curriculum.get("modules", {})
    pairs: list[tuple[str, str]] = []
    for level_slug, module_list in modules_by_level.items():
        for m in module_list:
            slug = m.get("slug")
            if not slug:
                continue
            pairs.append((level_slug, slug))

    print(f"modules to fetch: {len(pairs)}")
    print()

    # Step 3 — fetch in parallel
    counters = {"created": 0, "updated": 0, "unchanged": 0, "failed": 0}
    failures: list[str] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(fetch_one, lvl, slug, args.force) for lvl, slug in pairs]
        for fut in concurrent.futures.as_completed(futures):
            lvl, slug, err = fut.result()
            if err:
                counters["failed"] += 1
                failures.append(f"  {lvl}/{slug}: {err}")
                continue
            # Re-stat to classify result (cheaper than threading state)
            target = TARGET_ROOT / lvl / f"{slug}.json"
            # We approximate the classification: every successful write returned a status,
            # but we discarded it for parallel simplicity. Just count total successes here.
            counters["unchanged"] += 1  # sentinel; refined below

    # We can't distinguish created/updated/unchanged after the fact without a second walk,
    # but the user mostly cares about success/failure. Keep the print honest.
    successes = len(pairs) - counters["failed"]
    print(f"fetched: {successes} / {len(pairs)} modules")
    if failures:
        print(f"failures: {counters['failed']}")
        for line in failures:
            print(line, file=sys.stderr)
        return 1

    print()
    print(f"course mirror complete at {TARGET_ROOT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
