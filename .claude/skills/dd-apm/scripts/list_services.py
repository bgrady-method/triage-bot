#!/usr/bin/env python3
"""List APM services that have reported traffic in a given window.

Discovers services via metric queries (`trace.<integration>.request.hits by {service}`)
rather than the Service Catalog API — that way we only need `metrics_read` + `apm_read`
and don't need `apm_service_catalog_read`.

Different Datadog integrations emit different metric names. By default we query all
common ones and union the results. Override with --metric-prefix if you know yours.

Output: per-service request count and error count across all queried integrations.
"""
from __future__ import annotations

import argparse
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "dd-setup" / "scripts"))
from dd_client import dd_get, parse_time_unix, run_or_exit, print_json  # noqa: E402


DEFAULT_METRIC_PREFIXES = [
    "trace.http.request",
    "trace.web.request",
    "trace.aspnet_core.request",
    "trace.aspnet.request",
    "trace.servlet.request",
    "trace.django.request",
    "trace.express.request",
    "trace.rack.request",
    "trace.rails.request",
    "trace.gin.request",
    "trace.echo.request",
    "trace.fastapi.request",
    "trace.flask.request",
    "trace.node.request",
]


def _aggregate_by_service(series: list[dict]) -> dict[str, float]:
    out: dict[str, float] = {}
    for s in series:
        scope = s.get("scope") or ""
        if not scope.startswith("service:"):
            continue
        name = scope.split(":", 1)[1]
        total = sum(p[1] for p in (s.get("pointlist") or []) if p[1] is not None)
        out[name] = out.get(name, 0.0) + total
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--from", dest="frm", default="now-1h",
                   help="Window start. Default: now-1h")
    p.add_argument("--to", default="now", help="Window end. Default: now")
    p.add_argument("--env", default=None, help="Optional env filter, e.g. 'prod'")
    p.add_argument("--metric-prefix", action="append", default=None,
                   help="Integration prefix(es) to query. Repeatable. "
                        "Default: a list of common ones across languages/frameworks. "
                        "Example: --metric-prefix trace.aspnet_core.request")
    p.add_argument("--top", type=int, default=50,
                   help="Top N services by request count. Default: 50")
    p.add_argument("--verbose", action="store_true",
                   help="Show which metric prefix surfaced each service")
    args = p.parse_args()

    prefixes = args.metric_prefix or DEFAULT_METRIC_PREFIXES
    scope = f"env:{args.env}" if args.env else "*"
    frm = parse_time_unix(args.frm)
    to = parse_time_unix(args.to)

    totals: dict[str, dict] = {}
    provenance: dict[str, set[str]] = {}

    for prefix in prefixes:
        hits_resp = run_or_exit(lambda p=prefix: dd_get("/api/v1/query", params={
            "query": f"sum:{p}.hits{{{scope}}} by {{service}}",
            "from": frm, "to": to,
        }))
        err_resp = run_or_exit(lambda p=prefix: dd_get("/api/v1/query", params={
            "query": f"sum:{p}.errors{{{scope}}} by {{service}}",
            "from": frm, "to": to,
        }))
        hits = _aggregate_by_service(hits_resp.get("series") or [])
        errs = _aggregate_by_service(err_resp.get("series") or [])
        for name, h in hits.items():
            cur = totals.setdefault(name, {"hits": 0.0, "errors": 0.0})
            cur["hits"] += h
            cur["errors"] += errs.get(name, 0.0)
            provenance.setdefault(name, set()).add(prefix)

    rows = []
    for name, v in totals.items():
        h, e = v["hits"], v["errors"]
        row = {
            "service": name,
            "hits": int(h),
            "errors": int(e),
            "error_pct": round(100.0 * e / h, 3) if h else None,
        }
        if args.verbose:
            row["from_metrics"] = sorted(provenance[name])
        rows.append(row)
    rows.sort(key=lambda r: r["hits"], reverse=True)

    print_json({
        "window": f"{args.frm} -> {args.to}",
        "env_filter": args.env,
        "metric_prefixes_queried": prefixes,
        "service_count": len(rows),
        "services": rows[: args.top],
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
