# Datadog investigation playbook

Ported from `~/.claude/skills/dd-investigate/SKILL.md`. Local Python helper calls have been replaced with `scripts/dd_search.py` (REST under the hood). Otherwise the order and rationale are identical.

## When to use

When the alert points at a backend service or system signal and you don't yet know which Datadog surface (monitors / logs / metrics / traces) holds the smoking gun. If the alert is already specific (e.g. monitor id quoted in the alert text), skip Step 1 and go straight to Step 4.

## Step 0 — Confirm scope

You must have, before running anything:
1. **Service** — Datadog `service:` tag value. The alert text usually contains it. If absent, derive from the source (e.g. `tables-fields` from a monitor name).
2. **Time window** — when did this start? **If the alert text contains a Datadog monitor URL, derive the window from it via `scripts/parse_alert_url.py "<url>"` and use the `padded_from_unix_s` / `padded_to_unix_s` for every subsequent query.** Never compute UTC by hand — millis vs seconds and DST trip-ups are routine. Default `now-30m` only when no URL is available.
3. **Symptom** — alert fired / latency / errors / no-data / customer-report / deploy-related / unknown.

> **Rule R6.** Always derive the window from the alert URL. The orchestrator's hand-math on the 2026-05-07 RTC Screen Load alert was off by 20 minutes; every narrow-window query for that incident missed the true peak. `scripts/parse_alert_url.py` returns `from_iso_z`, `to_iso_z`, `padded_from_unix_s`, `padded_to_unix_s` — pass the unix-second pair to `dd_search.py metric --from-unix / --to-unix`.

## Step 1 — What's already firing?

```bash
python scripts/dd_search.py monitors \
  --tags "service:<svc>,env:prod" \
  --state Alert --state "No Data" --summary
```

Note any monitor IDs that are firing. Their `query` field reveals the dimension being tracked. The `last_triggered_ts` correlates with the alert.

If a monitor is firing on the same signal as the alert: jump to Step 3 (golden signals) for that dimension and Step 4 for matching logs.

If nothing is firing but the alert is real: telemetry may lag, or the issue is below thresholds. Continue to Step 2.

## Step 2 — Where are the errors concentrated?

```bash
python scripts/dd_search.py logs \
  --query "service:<svc> status:error env:prod" \
  --from now-30m --limit 100
```

Eyeball: is one host / one path dominating? If so, focus there. If errors are evenly distributed, the cause is global (config, dependency, deploy).

For 5xx specifically:
```bash
python scripts/dd_search.py logs \
  --query "service:<svc> @http.status_code:[500 TO 599]" \
  --from now-30m --limit 50
```

## Step 3 — Golden signals vs baseline

Run all three for the affected service and compare to the corresponding scope in `kb/metric-baselines.md` (or to the same window 24h ago if no baseline is recorded). The script takes unix epoch seconds — use the `padded_from_unix_s` / `padded_to_unix_s` you derived in Step 0.

> **.NET prefix matters.** Method's services are .NET, instrumented as `trace.aspnet_core.request.*` (not `trace.web.request.*`). For Tier 3 .NET Framework services on the IIS `microservices` pool (`ms-archive-api`, `ms-gmail-addon-api`, `ms-google-calendarsync-api`, etc.), use `trace.aspnet.request.*` instead. See `CLAUDE.md` "Tier 3 .NET Framework microservices" for the full list.

```bash
FROM=<padded_from_unix_s>  # from parse_alert_url.py
TO=<padded_to_unix_s>

# Request rate
python scripts/dd_search.py metric \
  --query "sum:trace.aspnet_core.request.hits{service:<svc>,env:prod}.as_rate()" \
  --from-unix $FROM --to-unix $TO

# Error rate
python scripts/dd_search.py metric \
  --query "sum:trace.aspnet_core.request.errors{service:<svc>,env:prod}.as_rate()" \
  --from-unix $FROM --to-unix $TO

# p95 latency by endpoint
python scripts/dd_search.py metric \
  --query "p95:trace.aspnet_core.request{service:<svc>,env:prod} by {resource_name}" \
  --from-unix $FROM --to-unix $TO
```

What to look for:
- **Cliff** (rate dropped to 0): service down or upstream broken.
- **Step change** (latency doubled at 14:32): deploy / config change near that timestamp.
- **Drift** (errors creeping up): resource exhaustion, leak.

> **Rule R4 / mid-recovery window.** If the p95 timeseries `last` value is at-baseline but `max` is well above the monitor threshold, the window started mid-recovery and the peak is hidden in truncated samples. Re-run via `scripts/find_metric_peak.py --query <...> --from-unix $FROM --to-unix $TO --threshold <monitor-threshold>` — it auto-widens backward (up to 4× the original window) and returns the actual peak timestamp.

## Step 3.5 — Classify the latency anatomy

Before pulling traces or logs, branch on the golden-signal results. The wrong branch wastes ~5–10 turns chasing logs that don't exist or chasing app code for an infra issue.

> **Rule R1 — downstream-latency.** IF `errors.as_rate() == 0` (no series, or `last == 0`) AND `p95 > monitor threshold` AND `hits.as_rate()` is within ±20% of the 1h baseline → the cause is downstream, not in this service. **Skip log search.** Fan out the dependency p95s in parallel:
>
> ```bash
> for METRIC in trace.redis.command trace.sql_server.query trace.mongodb.query trace.http.request; do
>   python scripts/dd_search.py metric \
>     --query "p95:${METRIC}{service:<svc>*,env:prod}" \
>     --from-unix $FROM --to-unix $TO
> done
> ```
>
> For any dependency where `p95 > 10× the baseline in kb/metric-baselines.md` → that's the smoking gun. Move to Step 3.6 (cluster-wide check).

> **Rule R2 — app-error-driven.** IF `errors.as_rate() > 0` AND `p95 > threshold` → app or recent deploy. Pull error logs first (Step 2 query), check 5xx `resource_name` distribution, then check recent deploys ±15 min of spike start.

> **Rule R3 — load-driven.** IF `hits.as_rate()` is >2× the 1h baseline → upstream caller is hammering. Check rate limits, queue saturation, RabbitMQ depth. Do NOT chase per-call latency.

> **Step 4a — when there are no error logs to grab.** If Rule R1 fires (downstream-latency, zero errors), there is no error log with a `trace_id` to pull. Skip Step 4. The actual exception class lives in the DD APM trace tree — open one slow request in the DD UI: `https://app.datadoghq.com/apm/traces?query=service:<svc>%20resource_name:<resource>` with the spike window. Cross-ref `kb/logstash-coverage.md` if the service isn't indexed in ES.

## Step 3.6 — Cluster-wide vs service-local

Before concluding the slow dependency is this service's problem, check whether other services saw the same dependency stall.

```bash
python scripts/check_cluster_wide_impact.py \
  --dep redis \
  --env prod \
  --from-unix $FROM \
  --to-unix $TO
```

Output reports `is_cluster_wide` (true when ≥ N services have errors in same/adjacent buckets — N from `kb/config.json` `cluster_wide_impact.min_services_for_cluster_wide`, default 3), the `affected_services_with_errors` list, the `elevated_p95_no_errors` list, and `outage_duration_estimate_sec`.

> **Rule R9.** If `is_cluster_wide: true` → infra/cluster issue, NOT app-local. Stop chasing this service's code; record the impact radius and proceed to Step 5.

## Step 4 — Pull a representative trace (only if R2/R3 fired)

Take a recent error log, grab its `trace_id`:

```bash
python scripts/dd_search.py logs \
  --query "service:<svc> status:error" --from now-15m --limit 5
```

Datadog returns each event with `attributes.trace_id` (and `attributes.span_id`). Open the trace in the Datadog UI by linking with: `https://app.datadoghq.com/apm/trace/<trace_id>`. (Routine cannot render the UI; share the URL in its DM to Ben.)

If the failing span is in a downstream service, restart from Step 1 with that service.

## Step 5 — Summarize (output for the routine prompt to consume)

```
Incident: <one-line symptom>
Service:  <name>
Window:   <from_iso_z> -> <to_iso_z>   # from parse_alert_url.py
Firing monitors:
  - <id> <name> (since <ts>)
Anatomy: <downstream-latency | app-error-driven | load-driven>
Symptoms:
  - <golden signal observation, e.g. "p95 4x baseline (10.7s vs ~1s)">
  - <dependency observation, e.g. "trace.redis.command p95 1.36s vs 3ms baseline (~400×)">
  - <log finding, e.g. "200 errors/min on POST /v1/field, all from web-prod-3">
  - <trace finding, e.g. "75% of latency is in SQL span on customer DB">
Cluster-wide? <true | false>
  Affected services: <count> (<names>)
  Outage duration: <seconds>
Trace IDs preserved: <id1>, <id2>
Likely cause: <hypothesis with confidence 0..1>
Suggested next action: <one of: restart pool / rollback deploy / page DB on-call / file defect / no action — known false alarm>
```

> **Rule R10 — why-only-this-monitor (cluster-wide events only).** When `is_cluster_wide: true` from Step 3.6, the user wants to know *why this service alarmed and not the others*. Compute `dep_calls_per_request = sum:trace.<dep>.command.hits{service:<svc>} / sum:trace.aspnet_core.request.hits{service:<svc>}` averaged over the spike window. The service with the highest ratio AND no per-call timeout is usually the canonical alarm-trigger. Add a one-liner to the summary, e.g.: "runtime-core-api has ~67 redis calls per inbound request (vs <3 for other affected services); per-call slowdown × volume = biggest tail = first to cross monitor threshold."

> **Observability gap reporter.** When `is_cluster_wide: true` AND `dd_search.py monitors --tags "<dep>"` returns 0 cluster-level monitors, append to the summary: `OBSERVABILITY GAP: no infra-layer monitor exists for <dep>. Customer-symptom monitor(s) caught this incident as a side-effect.` See also `kb/metric-baselines.md` "Coverage gaps".

## Conventions

- **Always run Step 1 first** — even if logs are obviously spammy, monitors tell you what *Datadog* thinks is broken, which is a useful prior.
- **Compare to baseline** — single numbers are meaningless. Either re-run the metric for `now-25h .. now-24h` or eyeball whether the timeseries shape is normal.
- **Preserve trace IDs** in the summary. They're the cheapest way for a future investigator to reconstruct what you saw.
- **Don't pivot blindly** — if aggregation shows errors are uniform across hosts, don't waste time on per-host log searches.

## Gotchas

- **`<svc>` placeholder** must match the actual `service:` tag value. If metrics show no data, the service may be tagged differently (`tables-fields-api` vs `tables_fields_api`). The alert text often shows the canonical tag.
- **Monitor names lie.** Read the `query` field, not the name.
- **Telemetry lag** — Datadog ingestion is normally <30s but can spike during incidents. If `now-2m` shows nothing and `now-15m` does, that's a hint, not a fact.
- **Background workers** don't show up in `trace.aspnet_core.request.*` metrics. For RabbitMQ consumers / sidekick jobs, use `trace.<integration>.*` (e.g. `trace.masstransit.consume`) or query logs directly.
- **Tag presence** — `by {host}` and `by {error.type}` return `<key>:N/A` for several Method trace metrics (notably `trace.redis.command*`). Check `kb/dd-trace-metric-tags.md` before issuing a `by {X}` query and use the documented fallback chain.
- **Bundled dd-* skills can be broken.** The bot's `scripts/dd_search.py` is the preferred surface. Before reaching for `~/.claude/skills/dd-*/scripts/<x>.py`, consult `kb/dd-skill-tooling-status.md`. As of last verification, `dd-apm/search_spans.py` and `dd-logs/aggregate_logs.py` are broken — workarounds documented there.
- **Output too large** — multi-series queries (`by {service}` etc.) overflow the harness's 30 KB inline limit. Add `--top-series-by-max N --peak-only` to `dd_search.py metric` to compact the response.

## Out of scope

- This playbook is read-only. It does not mute monitors, post events, or page anyone.
- It does not replace the Datadog UI for visual exploration. Always include UI URLs in the DM Ben gets.
