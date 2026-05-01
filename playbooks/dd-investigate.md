# Datadog investigation playbook

Ported from `~/.claude/skills/dd-investigate/SKILL.md`. Local Python helper calls have been replaced with `scripts/dd_search.py` (REST under the hood). Otherwise the order and rationale are identical.

## When to use

When the alert points at a backend service or system signal and you don't yet know which Datadog surface (monitors / logs / metrics / traces) holds the smoking gun. If the alert is already specific (e.g. monitor id quoted in the alert text), skip Step 1 and go straight to Step 4.

## Step 0 — Confirm scope

You must have, before running anything:
1. **Service** — Datadog `service:` tag value. The alert text usually contains it. If absent, derive from the source (e.g. `tables-fields` from a monitor name).
2. **Time window** — when did this start? Default `now-30m` for fresh alerts; use the alert's own timestamp as the upper bound.
3. **Symptom** — alert fired / latency / errors / no-data / customer-report / deploy-related / unknown.

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

Run all three for the affected service and compare to the same window 24h ago. The script takes unix epoch seconds; build with `date -u +%s`.

```bash
NOW=$(date -u +%s); HOUR_AGO=$((NOW - 3600))

# Request rate
python scripts/dd_search.py metric \
  --query "sum:trace.web.request.hits{service:<svc>,env:prod}.as_rate()" \
  --from-unix $HOUR_AGO --to-unix $NOW

# Error rate
python scripts/dd_search.py metric \
  --query "sum:trace.web.request.errors{service:<svc>,env:prod}.as_rate()" \
  --from-unix $HOUR_AGO --to-unix $NOW

# p95 latency by endpoint
python scripts/dd_search.py metric \
  --query "p95:trace.web.request.duration{service:<svc>,env:prod} by {resource_name}" \
  --from-unix $HOUR_AGO --to-unix $NOW
```

What to look for:
- **Cliff** (rate dropped to 0): service down or upstream broken.
- **Step change** (latency doubled at 14:32): deploy / config change near that timestamp.
- **Drift** (errors creeping up): resource exhaustion, leak.

## Step 4 — Pull a representative trace

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
Window:   <start> -> <end>
Firing monitors:
  - <id> <name> (since <ts>)
Symptoms:
  - <golden signal observation, e.g. "p95 4x baseline">
  - <log finding, e.g. "200 errors/min on POST /v1/field, all from web-prod-3">
  - <trace finding, e.g. "75% of latency is in SQL span on customer DB">
Trace IDs preserved: <id1>, <id2>
Likely cause: <hypothesis with confidence 0..1>
Suggested next action: <one of: restart pool / rollback deploy / page DB on-call / file defect / no action — known false alarm>
```

## Conventions

- **Always run Step 1 first** — even if logs are obviously spammy, monitors tell you what *Datadog* thinks is broken, which is a useful prior.
- **Compare to baseline** — single numbers are meaningless. Either re-run the metric for `now-25h .. now-24h` or eyeball whether the timeseries shape is normal.
- **Preserve trace IDs** in the summary. They're the cheapest way for a future investigator to reconstruct what you saw.
- **Don't pivot blindly** — if aggregation shows errors are uniform across hosts, don't waste time on per-host log searches.

## Gotchas

- **`<svc>` placeholder** must match the actual `service:` tag value. If metrics show no data, the service may be tagged differently (`tables-fields-api` vs `tables_fields_api`). The alert text often shows the canonical tag.
- **Monitor names lie.** Read the `query` field, not the name.
- **Telemetry lag** — Datadog ingestion is normally <30s but can spike during incidents. If `now-2m` shows nothing and `now-15m` does, that's a hint, not a fact.
- **Background workers** don't show up in `trace.web.*` metrics. For RabbitMQ consumers / sidekick jobs, use `trace.<integration>.*` or query logs directly.

## Out of scope

- This playbook is read-only. It does not mute monitors, post events, or page anyone.
- It does not replace the Datadog UI for visual exploration. Always include UI URLs in the DM Ben gets.
