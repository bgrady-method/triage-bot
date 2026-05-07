# DD skill tooling status — bundled `.claude/skills/dd-*` scripts

Working / broken status for the bundled Datadog skill scripts at `C:\MethodDev\triage-bot\.claude\skills\dd-*\scripts\`. **The bot's own `scripts/dd_search.py` is the preferred surface** — it's a thin REST wrapper that doesn't suffer from the bugs below. Reach for the bundled scripts only when `dd_search.py` doesn't cover the surface (notably trace fetching and span search).

> **Use:** before invoking any bundled script, find it below. If `status: broken`, use the workaround. If `status: unverified`, run the smoke-test and update this file.

## Status table

| Script | Status | Last verified | Smoke-test result | Workaround |
|---|---|---|---|---|
| `dd-monitors/get_monitor.py` | **working** | 2026-05-07 | exit 0; valid JSON returned for monitor 115456700 | — |
| `dd-monitors/list_monitors.py` | **working** | 2026-05-07 | exit 0; valid JSON for `--tag env:prod`. **Arg quirk:** must use repeated `--tag` (singular), not `--tags`. `--name` only valid on triggered-monitors page. | use `dd_search.py monitors` to avoid arg quirks |
| `dd-metrics/query_timeseries.py` | **working** | 2026-05-07 | exit 0; valid JSON. **Output footgun:** abbreviates middle samples with `"..."` and persists at >30 KB; use `dd_search.py metric --top-series-by-max` / `--peak-only` instead. | `dd_search.py metric` |
| `dd-metrics/list_dashboards.py` | **working** | 2026-05-07 | exit 0; valid JSON | — |
| `dd-logs/search_logs.py` | **working** | 2026-05-07 | exit 0; valid JSON. **Argparse quirk:** `--sort -timestamp` triggers `expected one argument`; use `--sort=-timestamp` (with `=`). | `dd_search.py logs` |
| `dd-logs/aggregate_logs.py` | **working** (patched 2026-05-07) | 2026-05-07 | post-patch: exit 0; valid JSON. Pre-patch: exit 2 with `400 ... Field 'aggregation' is invalid: Unrecognized parameter`. Fix: `sort` body needed `"type": "measure"` alongside `"aggregation"`. | — |
| `dd-apm/list_services.py` | **working** | 2026-05-07 | exit 0; valid JSON listing 109 services | — |
| `dd-apm/search_spans.py` | **working** (patched 2026-05-07) | 2026-05-07 | post-patch: exit 0; returns spans with full attributes including `host` (the dimension `trace.*` metric facets return as `N/A` — span-level search now compensates). Pre-patch: exit 2 with `400 ... document is missing required top-level members`. Fix: body wrapped in JSON:API `data` envelope (`{"data": {"type": "search_request", "attributes": {...}}}`). | — |
| `dd-apm/get_trace.py` | **working** | 2026-05-07 | exit 0; returned `count: 0` for a known-bad trace ID — no error. Use a real trace_id from `dd_search.py logs` or the DD UI. | — |

## Upstream fixes — applied 2026-05-07

Both bugs caught by smoke-tests have been patched directly in `~/.claude/skills/dd-*/scripts/` (no upstream tracker exists for these user-installed skills).

- `aggregate_logs.py` (`dd-logs/scripts/aggregate_logs.py:70`): added `"type": "measure"` to the `sort` body so DD v2 accepts the `aggregation` key alongside it.
- `search_spans.py` (`dd-apm/scripts/search_spans.py:59-71`): wrapped the request body in the JSON:API `data` envelope: `{"data": {"type": "search_request", "attributes": {filter, page, sort}}}`.

If the skills are ever reinstalled from a fresh source, both patches will need to be re-applied. Re-run the smoke-test recipe after any update to confirm.

## Smoke-test recipe (for re-verification)

From the triage-bot root:

```bash
set -a; . ./.env; set +a
for script in \
  .claude/skills/dd-monitors/scripts/get_monitor.py \
  .claude/skills/dd-monitors/scripts/list_monitors.py \
  .claude/skills/dd-metrics/scripts/query_timeseries.py \
  .claude/skills/dd-metrics/scripts/list_dashboards.py \
  .claude/skills/dd-logs/scripts/search_logs.py \
  .claude/skills/dd-logs/scripts/aggregate_logs.py \
  .claude/skills/dd-apm/scripts/list_services.py \
  .claude/skills/dd-apm/scripts/search_spans.py \
  .claude/skills/dd-apm/scripts/get_trace.py; do
    # Each script has different required args; see Last verified above for the
    # benign query that triggered the smoke-test.
    echo "=== $script ==="
done
```

Re-run after any upstream `.claude/skills/dd-*` update; refresh the table.

## How to grow this file

When a bundled script's behaviour changes (fixed upstream, new arg quirk discovered):
1. Re-run its smoke-test from the recipe above.
2. Update `Status`, `Last verified`, `Smoke-test result`, and `Workaround`.
3. The `kb-approver` routine reviews proposed updates before merging.

Cross-references:
- `kb/metric-baselines.md` — what to query
- `kb/dd-trace-metric-tags.md` — `by {X}` fallback chain
- `kb/logstash-coverage.md` — which services have ES coverage at all
