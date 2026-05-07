"""Detect cluster-wide infra blips on a Datadog trace dependency.

Runs two metric queries against `dd_search.py metric`:
  1. `sum:trace.<dep>.<errors_metric>{env:<env>} by {service}.as_count()`
  2. `p95:trace.<dep>.<command_metric>{env:<env>} by {service}`

Classifies the window as cluster-wide if at least N services show errors in
the same or adjacent 20-second buckets (N read from kb/config.json
cluster_wide_impact.min_services_for_cluster_wide; default 3).

Output: JSON with `is_cluster_wide`, `affected_services`,
`peak_p95_per_service`, `outage_duration_estimate_sec`. Errors: JSON to
stderr + non-zero exit.

See Bob R-3 / rule R9 in `kb/metric-baselines.md` cross-references.
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
KB_CONFIG = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "kb", "config.json"))


DEPENDENCY_METRICS: dict[str, dict[str, str]] = {
    "redis": {"errors": "trace.redis.command.errors", "p95": "trace.redis.command"},
    "sql_server": {"errors": "trace.sql_server.query.errors", "p95": "trace.sql_server.query"},
    "mongodb": {"errors": "trace.mongodb.query.errors", "p95": "trace.mongodb.query"},
    "http": {"errors": "trace.http.request.errors", "p95": "trace.http.request"},
}


def die(msg: str, code: int = 1) -> None:
    json.dump({"error": msg}, sys.stderr)
    sys.stderr.write("\n")
    sys.exit(code)


def _load_config() -> dict[str, Any]:
    try:
        with open(KB_CONFIG, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def _run_dd_search(query: str, from_s: int, to_s: int) -> dict:
    proc = subprocess.run(
        [sys.executable, DD_SEARCH, "metric", "--query", query, "--from-unix", str(from_s), "--to-unix", str(to_s)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        die(f"dd_search.py metric failed for query {query!r} (exit {proc.returncode}): {proc.stderr.strip()}", code=2)
    return json.loads(proc.stdout)


def _service_from_scope(series: dict) -> str | None:
    scope = series.get("scope") or ""
    for part in scope.split(","):
        if part.startswith("service:"):
            return part[len("service:") :]
    return None


def _bucket_keys(series: dict, bucket_s: int) -> set[int]:
    """Return the set of bucket-start unix-seconds where this series has a non-null value > 0."""
    keys: set[int] = set()
    for ts_ms, val in series.get("pointlist") or series.get("sample_points") or []:
        if val is None or val == 0:
            continue
        ts_s = int(ts_ms / 1000.0)
        keys.add((ts_s // bucket_s) * bucket_s)
    return keys


def _peak(series: dict) -> tuple[int, float] | None:
    pts = [(int(ts_ms / 1000.0), float(val)) for ts_ms, val in series.get("pointlist") or series.get("sample_points") or [] if val is not None]
    if not pts:
        return None
    return max(pts, key=lambda p: p[1])


def _bucket_span_seconds(buckets: set[int], bucket_s: int, adjacent: int) -> int:
    """Largest contiguous run within `adjacent` buckets of slack, expressed in seconds."""
    if not buckets:
        return 0
    sorted_b = sorted(buckets)
    runs: list[list[int]] = [[sorted_b[0]]]
    for b in sorted_b[1:]:
        if b - runs[-1][-1] <= bucket_s * (adjacent + 1):
            runs[-1].append(b)
        else:
            runs.append([b])
    longest = max(runs, key=lambda r: r[-1] - r[0])
    return (longest[-1] - longest[0]) + bucket_s


def check(dep: str, env: str, from_s: int, to_s: int, min_services: int, bucket_s: int, adjacent: int) -> dict:
    if dep not in DEPENDENCY_METRICS:
        die(f"unsupported dep {dep!r}; choose from {sorted(DEPENDENCY_METRICS)}")
    metrics = DEPENDENCY_METRICS[dep]

    err_query = f"sum:{metrics['errors']}{{env:{env}}} by {{service}}.as_count()"
    err_resp = _run_dd_search(err_query, from_s, to_s)

    err_buckets_per_service: dict[str, set[int]] = {}
    for s in err_resp.get("series") or []:
        svc = _service_from_scope(s)
        if not svc:
            continue
        keys = _bucket_keys(s, bucket_s)
        if keys:
            err_buckets_per_service[svc] = keys

    services_with_errors = sorted(err_buckets_per_service)
    is_cluster_wide = len(services_with_errors) >= min_services

    p95_query = f"p95:{metrics['p95']}{{env:{env}}} by {{service}}"
    p95_resp = _run_dd_search(p95_query, from_s, to_s)
    peak_p95_per_service: dict[str, dict[str, float]] = {}
    for s in p95_resp.get("series") or []:
        svc = _service_from_scope(s)
        if not svc:
            continue
        peak = _peak(s)
        if not peak:
            continue
        peak_p95_per_service[svc] = {"peak_unix_s": peak[0], "peak_value_seconds": peak[1]}

    durations = {svc: _bucket_span_seconds(buckets, bucket_s, adjacent) for svc, buckets in err_buckets_per_service.items()}
    outage_duration_estimate_sec = max(durations.values()) if durations else 0

    affected = []
    for svc in services_with_errors:
        affected.append({
            "service": svc,
            "error_buckets": sorted(err_buckets_per_service[svc]),
            "error_window_seconds": durations[svc],
            "peak_p95_seconds": peak_p95_per_service.get(svc, {}).get("peak_value_seconds"),
            "peak_p95_unix_s": peak_p95_per_service.get(svc, {}).get("peak_unix_s"),
        })

    elevated_only_p95 = sorted(
        ({"service": svc, **peak_p95_per_service[svc]} for svc in peak_p95_per_service if svc not in err_buckets_per_service),
        key=lambda d: d["peak_value_seconds"],
        reverse=True,
    )

    return {
        "dependency": dep,
        "env": env,
        "window_unix": {"from": from_s, "to": to_s},
        "config": {"min_services_for_cluster_wide": min_services, "bucket_seconds": bucket_s, "adjacent_bucket_count": adjacent},
        "is_cluster_wide": is_cluster_wide,
        "affected_services_with_errors": affected,
        "elevated_p95_no_errors": elevated_only_p95[:25],
        "outage_duration_estimate_sec": outage_duration_estimate_sec,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Classify a window as cluster-wide infra blip vs service-local.")
    p.add_argument("--dep", required=True, choices=sorted(DEPENDENCY_METRICS), help="Dependency to inspect.")
    p.add_argument("--env", default="prod", help="Datadog env tag value. Default: prod.")
    p.add_argument("--from-unix", required=True, type=int)
    p.add_argument("--to-unix", required=True, type=int)
    p.add_argument("--min-services", type=int, default=None, help="Override kb/config.json cluster_wide_impact.min_services_for_cluster_wide.")
    p.add_argument("--bucket-seconds", type=int, default=None, help="Override kb/config.json cluster_wide_impact.bucket_seconds.")
    p.add_argument("--pretty", action="store_true")
    args = p.parse_args()

    cfg = _load_config().get("cluster_wide_impact", {})
    min_services = args.min_services if args.min_services is not None else int(cfg.get("min_services_for_cluster_wide", 3))
    bucket_s = args.bucket_seconds if args.bucket_seconds is not None else int(cfg.get("bucket_seconds", 20))
    adjacent = int(cfg.get("adjacent_bucket_count", 1))

    out = check(args.dep, args.env, args.from_unix, args.to_unix, min_services, bucket_s, adjacent)
    json.dump(out, sys.stdout, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
