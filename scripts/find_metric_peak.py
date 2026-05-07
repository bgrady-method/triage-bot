"""Locate a metric peak, auto-widening backward when the window started mid-recovery.

Wraps `scripts/dd_search.py metric`. Detects the case where the queried window
caught the tail end of an incident — `last < threshold` but `max > threshold`
and the first samples are already declining. In that case, widens the window
backward (up to 4×) and re-queries until the peak is centered or the window
cap is hit.

Output: JSON to stdout with `peak_unix_s`, `peak_value`, `widened` (bool),
`final_from_unix_s`, `final_to_unix_s`, plus the original DD response under
`response`. Errors: JSON to stderr + non-zero exit.

See Bob R-4 / rule R4 in `kb/metric-baselines.md` cross-references.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DD_SEARCH = os.path.join(SCRIPT_DIR, "dd_search.py")


def die(msg: str, code: int = 1) -> None:
    json.dump({"error": msg}, sys.stderr)
    sys.stderr.write("\n")
    sys.exit(code)


def _run_dd_search(query: str, from_s: int, to_s: int) -> dict:
    proc = subprocess.run(
        [sys.executable, DD_SEARCH, "metric", "--query", query, "--from-unix", str(from_s), "--to-unix", str(to_s)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        die(f"dd_search.py metric failed (exit {proc.returncode}): {proc.stderr.strip()}", code=2)
    return json.loads(proc.stdout)


def _series_points(series: list[dict]) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for s in series:
        for ts_ms, val in s.get("pointlist") or s.get("sample_points") or []:
            if val is not None:
                pts.append((ts_ms / 1000.0, float(val)))
    pts.sort(key=lambda p: p[0])
    return pts


def _peak(pts: list[tuple[float, float]]) -> tuple[float, float] | None:
    if not pts:
        return None
    return max(pts, key=lambda p: p[1])


def _last(pts: list[tuple[float, float]]) -> float | None:
    return pts[-1][1] if pts else None


def _is_mid_recovery(pts: list[tuple[float, float]], threshold: float) -> bool:
    """Heuristic: window started mid-recovery when the tail is below threshold,
    the max is above threshold, and the early samples are higher than the mid samples
    (i.e. already coming down at window start)."""
    if len(pts) < 6:
        return False
    last_v = pts[-1][1]
    max_v = max(p[1] for p in pts)
    if not (last_v < threshold <= max_v):
        return False
    first_third_avg = sum(p[1] for p in pts[: len(pts) // 3]) / max(1, len(pts) // 3)
    middle_third = pts[len(pts) // 3 : 2 * len(pts) // 3]
    middle_third_avg = sum(p[1] for p in middle_third) / max(1, len(middle_third))
    return first_third_avg > middle_third_avg


def _peak_in_first_quarter(pts: list[tuple[float, float]]) -> bool:
    """If the peak sits in the leading edge of the window, we still haven't seen
    the rising side — keep widening backward."""
    if not pts:
        return False
    peak_ts, _ = max(pts, key=lambda p: p[1])
    span = pts[-1][0] - pts[0][0]
    if span <= 0:
        return False
    return (peak_ts - pts[0][0]) / span < 0.25


def find_peak(query: str, from_s: int, to_s: int, threshold: float, max_widen: int) -> dict:
    original_from, original_to = from_s, to_s
    widened = False
    last_response: dict[str, Any] = {}
    for attempt in range(max_widen + 1):
        last_response = _run_dd_search(query, from_s, to_s)
        series = last_response.get("series") or []
        pts = _series_points(series)
        peak = _peak(pts)
        if not peak:
            return {
                "peak_unix_s": None,
                "peak_value": None,
                "widened": widened,
                "widen_iterations": attempt,
                "final_from_unix_s": from_s,
                "final_to_unix_s": to_s,
                "original_from_unix_s": original_from,
                "original_to_unix_s": original_to,
                "threshold": threshold,
                "reason": "no data points returned",
                "response": last_response,
            }
        if attempt == max_widen:
            break
        if not _is_mid_recovery(pts, threshold) and not _peak_in_first_quarter(pts):
            break
        widened = True
        span = to_s - from_s
        from_s = from_s - span
    peak_ts, peak_val = peak
    return {
        "peak_unix_s": int(peak_ts),
        "peak_value": peak_val,
        "widened": widened,
        "widen_iterations": attempt,
        "final_from_unix_s": from_s,
        "final_to_unix_s": to_s,
        "original_from_unix_s": original_from,
        "original_to_unix_s": original_to,
        "threshold": threshold,
        "last_value": _last(pts),
        "max_value": max(p[1] for p in pts),
        "response": last_response,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Find a metric peak, auto-widening when the window started mid-recovery.")
    p.add_argument("--query", required=True, help='Datadog metric query, e.g. "p95:trace.aspnet_core.request{service:runtime-core-api,env:prod}".')
    p.add_argument("--from-unix", required=True, type=int, help="Initial window start (unix seconds). Typically the alert window's padded_from_unix_s.")
    p.add_argument("--to-unix", required=True, type=int, help="Initial window end (unix seconds).")
    p.add_argument("--threshold", required=True, type=float, help="Monitor threshold or chosen comparison value (the script uses this to detect mid-recovery).")
    p.add_argument("--max-widen", type=int, default=2, help="Max times to double the window backward. Default 2 (final window up to 4× the initial). Cap at 4.")
    p.add_argument("--pretty", action="store_true")
    args = p.parse_args()
    if args.max_widen > 4:
        die("--max-widen cannot exceed 4")
    out = find_peak(args.query, args.from_unix, args.to_unix, args.threshold, args.max_widen)
    json.dump(out, sys.stdout, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
