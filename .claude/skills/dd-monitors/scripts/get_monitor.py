#!/usr/bin/env python3
"""Get full details for a single Datadog monitor.

Wraps GET /api/v1/monitor/{id}. Returns the full payload by default;
use --summary for a trimmed view of the fields that matter during triage.
"""
from __future__ import annotations

import argparse
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "dd-setup" / "scripts"))
from dd_client import dd_get, run_or_exit, print_json, web_url  # noqa: E402


def _summary(m: dict) -> dict:
    opts = m.get("options", {}) or {}
    state = m.get("state", {}) or {}
    groups = state.get("groups", {}) or {}
    failing = [
        {
            "group": gname,
            "status": g.get("status"),
            "last_triggered_ts": g.get("last_triggered_ts"),
            "last_resolved_ts": g.get("last_resolved_ts"),
            "last_notified_ts": g.get("last_notified_ts"),
        }
        for gname, g in groups.items()
        if g.get("status") in ("Alert", "Warn", "No Data")
    ]
    return {
        "id": m.get("id"),
        "name": m.get("name"),
        "type": m.get("type"),
        "overall_state": m.get("overall_state"),
        "query": m.get("query"),
        "message": (m.get("message") or "")[:1000],
        "tags": m.get("tags"),
        "thresholds": opts.get("thresholds"),
        "evaluation_delay": opts.get("evaluation_delay"),
        "new_host_delay": opts.get("new_host_delay"),
        "no_data_timeframe": opts.get("no_data_timeframe"),
        "notify_no_data": opts.get("notify_no_data"),
        "notify_audit": opts.get("notify_audit"),
        "muted": bool(opts.get("silenced") or {}),
        "silenced": opts.get("silenced"),
        "failing_groups": failing,
        "failing_count": len(failing),
        "url": web_url(f"/monitors/{m.get('id')}"),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--id", required=True, help="Monitor ID (integer)")
    p.add_argument("--summary", action="store_true",
                   help="Print only the triage-relevant fields (default: full payload)")
    args = p.parse_args()

    resp = run_or_exit(
        lambda: dd_get(f"/api/v1/monitor/{args.id}", params={"with_downtimes": "true"})
    )

    print_json(_summary(resp) if args.summary else resp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
