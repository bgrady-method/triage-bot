"""Parse a Datadog monitor URL into a canonical investigation window.

The Slack-pasted alert URL carries the authoritative time window that the
monitor evaluated when it fired. Computing UTC by hand from the millis is a
known footgun (see kb/dd-skill-tooling-status.md / Bob R-5). Always derive the
window via this helper and pass the padded values to dd_search.py / es_search.py.

Input: one URL like
  https://app.datadoghq.com/monitors/115456700?from_ts=1778160500000&to_ts=1778161700000&event_id=...&link_event_ts=1778161400

Output: JSON to stdout. Errors: JSON to stderr + non-zero exit.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from datetime import datetime, timezone


PAD_SECONDS = 30 * 60


def die(msg: str, code: int = 1) -> None:
    json.dump({"error": msg}, sys.stderr)
    sys.stderr.write("\n")
    sys.exit(code)


def _iso_z(unix_s: int | None) -> str | None:
    if unix_s is None:
        return None
    return datetime.fromtimestamp(unix_s, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_unix_s(raw: str | None) -> int | None:
    if raw is None:
        return None
    try:
        n = int(raw)
    except ValueError:
        return None
    # from_ts/to_ts are millis; link_event_ts is seconds. Disambiguate by magnitude:
    # any value > 10^11 is millis (Sat Mar 03 5138 in seconds — never a real timestamp).
    return n // 1000 if n > 10**11 else n


def _monitor_id(path: str) -> int | None:
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2 and parts[-2] == "monitors":
        try:
            return int(parts[-1])
        except ValueError:
            return None
    return None


def parse(url: str) -> dict:
    parsed = urllib.parse.urlparse(url)
    if not parsed.netloc.endswith("datadoghq.com") and not parsed.netloc.endswith("datadoghq.eu"):
        die(f"not a Datadog URL: {url}")
    qs = urllib.parse.parse_qs(parsed.query)

    def first(k: str) -> str | None:
        v = qs.get(k)
        return v[0] if v else None

    monitor_id = _monitor_id(parsed.path)
    from_s = _to_unix_s(first("from_ts"))
    to_s = _to_unix_s(first("to_ts"))
    event_s = _to_unix_s(first("link_event_ts") or first("event_ts"))
    event_id = first("event_id") or first("link_event_id")

    if from_s is None or to_s is None:
        die(f"URL missing from_ts/to_ts query params: {url}")

    padded_from = from_s - PAD_SECONDS
    padded_to = to_s + PAD_SECONDS

    return {
        "monitor_id": monitor_id,
        "event_id": event_id,
        "from_unix_s": from_s,
        "to_unix_s": to_s,
        "event_unix_s": event_s,
        "from_iso_z": _iso_z(from_s),
        "to_iso_z": _iso_z(to_s),
        "event_iso_z": _iso_z(event_s),
        "padded_from_unix_s": padded_from,
        "padded_to_unix_s": padded_to,
        "padded_from_iso_z": _iso_z(padded_from),
        "padded_to_iso_z": _iso_z(padded_to),
        "padding_seconds": PAD_SECONDS,
        "monitor_url": f"{parsed.scheme}://{parsed.netloc}/monitors/{monitor_id}" if monitor_id else None,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Parse a Datadog monitor URL into a canonical UTC window.")
    p.add_argument("url", help="Full Datadog monitor URL with from_ts/to_ts query params.")
    p.add_argument("--pretty", action="store_true")
    args = p.parse_args()
    out = parse(args.url)
    json.dump(out, sys.stdout, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
