#!/usr/bin/env python3
"""Parse Slack message dumps from the Slack MCP `slack_read_channel` "detailed"
format and emit the schema used by `docs/messages/<YYYY-MM-DD>/<slug>.jsonl`.

The MCP returns text formatted like:

    === Message from <Display Name> (<UID>) at YYYY-MM-DD HH:MM:SS TZ ===
    Message TS: <epoch.us>
    <body...optionally many lines...>

Bodies often end with `*Sent using* <@U0A5HQER5QQ|Claude>`. We strip that footer
when present so the captured body is the human-meaningful payload.

Usage:
    python scripts/backfill_slack_messages.py \
        --input <path-to-mcp-dump.txt-or-stdin> \
        --slug triage-bot-health \
        --channel-id C0B0Q3KHC07 \
        --channel-name '#triage-bot-health' \
        --recipient '#triage-bot-health'

Pass `--apply` to write JSONL files; default is dry-run printing to stdout.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MESSAGES_ROOT = REPO_ROOT / "docs" / "messages"

MSG_HEADER = re.compile(
    r"=== Message from .*? \((?P<uid>[UW][A-Z0-9]+)\) at (?P<dt>[\d-]+ [\d:]+) (?P<tz>[A-Z]+) ===\s*\n"
    r"Message TS: (?P<ts>[\d.]+)\s*\n"
)
SENT_USING_FOOTER = re.compile(r"\n?\*Sent using\* <@[^>]+>\s*$")

# Map TZ short names to fixed UTC offset minutes for parsing the header datetime.
# (The Slack MCP gives local-tz times in headers but the `Message TS:` field is
# epoch — we always prefer ts for the canonical value, only using the header for
# sanity-check during dry-run.)
TZ_OFFSETS = {"EDT": -4 * 60, "EST": -5 * 60, "UTC": 0, "PDT": -7 * 60, "PST": -8 * 60}


def classify_message_type(body: str, default: str) -> str:
    """Heuristic-classify a message body into one of the prompt's message_type
    enum values. Defaults to whatever caller provides (depends on channel)."""
    b = body.lower()
    if ":bar_chart:" in body or "stability-review" in b and "committed" in b:
        return "stability-summary"
    if ":large_yellow_circle:" in body or ":large_green_circle:" in body or ":warning: triage-bot" in b:
        return "health-status"
    if ":rotating_light:" in body or "needs human" in b or "needs-human" in b:
        return "needs-human"
    if "proposed_kb_entry" in b or "kb proposal" in b or "false alarm" in b:
        return "kb-proposal"
    if "known issue" in b or "recurrence" in b:
        return "known-issue"
    if "clear fix" in b or "suggested fix" in b:
        return "new-fix"
    return default


def parse_dump(text: str) -> list[dict]:
    """Parse the MCP dump text and return a list of message dicts."""
    out = []
    matches = list(MSG_HEADER.finditer(text))
    for i, m in enumerate(matches):
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        body = SENT_USING_FOOTER.sub("", body).strip()
        ts_epoch = float(m.group("ts"))
        ts_iso = datetime.fromtimestamp(ts_epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        date = datetime.fromtimestamp(ts_epoch, tz=timezone.utc).strftime("%Y-%m-%d")
        out.append(
            {
                "ts": ts_iso,
                "ts_epoch": ts_epoch,
                "uid": m.group("uid"),
                "date": date,
                "body": body,
            }
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="path to MCP dump text file, or '-' for stdin")
    ap.add_argument("--slug", required=True, help="filename slug, e.g. triage-bot-health, self-dm")
    ap.add_argument("--channel-id", required=True)
    ap.add_argument("--channel-name", required=True)
    ap.add_argument("--recipient", required=True)
    ap.add_argument("--default-message-type", default="other")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    if args.input == "-":
        text = sys.stdin.read()
    else:
        text = Path(args.input).read_text(encoding="utf-8")

    # If input is a JSON-wrapped MCP file (list of {type, text}), unwrap.
    text_stripped = text.lstrip()
    if text_stripped.startswith("[") or text_stripped.startswith("{"):
        try:
            data = json.loads(text)
            if isinstance(data, list) and data and isinstance(data[0], dict) and "text" in data[0]:
                text = "".join(item.get("text", "") for item in data)
            elif isinstance(data, dict) and "messages" in data:
                text = data["messages"]
            elif isinstance(data, dict) and "text" in data:
                text = data["text"]
        except json.JSONDecodeError:
            pass

    # If the text itself contains an embedded {"messages": "..."} envelope, peel it.
    if text.lstrip().startswith('{"messages"'):
        try:
            text = json.loads(text).get("messages", text)
        except json.JSONDecodeError:
            pass

    msgs = parse_dump(text)
    print(f"parsed {len(msgs)} messages", file=sys.stderr)

    by_date: dict[str, list[dict]] = {}
    for m in msgs:
        line = {
            "ts": m["ts"],
            "channel_id": args.channel_id,
            "channel_name": args.channel_name,
            "recipient": args.recipient,
            "message_type": classify_message_type(m["body"], args.default_message_type),
            "alert_hash": None,
            "thread_ts": None,
            "body": m["body"],
        }
        by_date.setdefault(m["date"], []).append(line)

    # Sort each day's lines chronologically (Slack returns newest-first).
    for date in by_date:
        by_date[date].sort(key=lambda x: x["ts"])

    if args.apply:
        for date, lines in by_date.items():
            out_dir = MESSAGES_ROOT / date
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{args.slug}.jsonl"
            with out_path.open("a", encoding="utf-8") as fh:
                for line in lines:
                    fh.write(json.dumps(line, ensure_ascii=False) + "\n")
            print(f"wrote {len(lines)} lines to {out_path}", file=sys.stderr)
    else:
        for date, lines in sorted(by_date.items()):
            for line in lines:
                print(json.dumps(line, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
