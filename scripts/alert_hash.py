"""Deterministic hash of an alert for idempotency.

Used as the lock key (`claude/triage-{hash}` branch) and as the alert_id in
incident-log.jsonl. Two runs produced by the same Slack message produce the
same hash, so retries / duplicate event-callbacks are absorbed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys


def alert_hash(channel_id: str, ts: str, thread_ts: str | None = None) -> str:
    """sha256 of "channel:ts" — thread_ts wins over ts when present.

    Slack's `ts` is microsecond-precision and stable for the lifetime of the
    message even across edits. `thread_ts` (when set) anchors a reply to its
    parent — we use the parent so all replies in the same thread map to one
    investigation.
    """
    anchor = thread_ts or ts
    blob = f"{channel_id}:{anchor}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]  # 16 hex chars = 64 bits, plenty


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute alert hash from a Slack payload.")
    parser.add_argument("--channel", required=True)
    parser.add_argument("--ts", required=True)
    parser.add_argument("--thread-ts", default=None)
    parser.add_argument(
        "--from-stdin",
        action="store_true",
        help="Read a JSON payload (as forwarded by the Cloudflare Worker) from stdin instead.",
    )
    args = parser.parse_args()

    if args.from_stdin:
        payload = json.load(sys.stdin)
        h = alert_hash(payload["channel_id"], payload["ts"], payload.get("thread_ts"))
    else:
        h = alert_hash(args.channel, args.ts, args.thread_ts)

    print(h)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
