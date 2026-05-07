---
name: dd-monitors
description: List, search, and inspect Datadog monitors and alerts. TRIGGER when the user asks "what's firing", "is the X monitor alerting", "show me all alerts for service Y", or wants to read a monitor's query/threshold/notification config.
user_invocable: true
---

# dd-monitors — Datadog monitor and alert inspection

## When to use

- "Anything firing right now?"
- "Is the latency monitor for `tables-fields` alerting?"
- "Show me all monitors tagged `service:tables-fields`."
- "What's the threshold on monitor 12345678?"
- "Why did this page fire?" -> get_monitor.py --id <id> --summary

Pre-req: `dd-setup` complete.

## Tools

| Script | Purpose |
|---|---|
| `scripts/list_monitors.py` | Search monitors by name, tag, and/or overall state. Returns trimmed JSON: id, name, type, status, tags, last_triggered_ts, query (truncated), UI URL. Uses `/api/v1/monitor/search` under the hood for real state filtering. |
| `scripts/get_monitor.py` | Full details for one monitor by ID. `--summary` trims to the triage-relevant fields including failing groups and last-triggered timestamps. Uses `/api/v1/monitor/{id}`. |

## Standard triage flow

1. **What's on fire?**
   ```bash
   python .claude/skills/dd-monitors/scripts/list_monitors.py --state Alert --state "No Data" --top 100
   ```
2. **Filter to a service or area:**
   ```bash
   python .claude/skills/dd-monitors/scripts/list_monitors.py \
     --tag service:tables-fields --tag env:prod --state Alert
   ```
3. **Read the monitor:**
   ```bash
   python .claude/skills/dd-monitors/scripts/get_monitor.py --id 12345678 --summary
   ```
   The summary shows the trigger query, the threshold, which groups are failing, and last-triggered timestamps. From there:
   - Re-run the query in `dd-metrics` to see the current value.
   - Pull the matching logs in `dd-logs` for the failing window.

## Conventions

- **State names are case-sensitive**: `Alert`, `Warn`, `No Data`, `OK`, `Ignored`, `Skipped`, `Unknown`. Pass them exactly as shown; the CLI wraps them for the search DSL.
- **`--tag` is repeatable.** e.g. `--tag service:foo --tag env:prod`. Tags match the monitor's `tags` array (the tags applied to the monitor itself), not scope tags inside the monitor's query. Most SRE monitors are tagged by service/env so this is what you want.
- **Pagination**: `--top` = page size (max 1000), `--page` = page index. If `count == top`, there are probably more.
- **Muted ≠ silenced forever** — in `get_monitor.py --summary`, `muted: true` means there's a downtime active. The full `silenced` map shows scope.
- **Why not `/api/v1/monitor`?** That endpoint's `group_states` param filters *groups within* each returned monitor, not monitors by overall state — so `--state Alert` would silently return OK monitors. Search does proper state filtering.

## Gotchas

- **`--name` is substring**, not exact. `--name latency` matches "Tables-Fields p99 latency", "DB query latency", etc.
- **No data is not OK** — `No Data` means the monitor's query returned nothing. Often a worse signal than `Alert` (your service may have stopped reporting). Always include `--state "No Data"` alongside `Alert` during triage.
- **Last-triggered timestamps are unix seconds** — convert with `date -d @<ts>` or eyeball them.
- **The web URL** in the JSON output is a clickable pivot — hand it to the user verbatim.

## What this skill does NOT do

- No monitor mutations: no create, edit, delete, mute, unmute, resolve. Read-only by design (the App key only has `monitors_read`). To act on a monitor, use the Datadog UI.
- No SLO inspection — that's a separate API surface (`/api/v1/slo`). Add a script if/when needed.
- No notification routing inspection beyond what `get_monitor.py --summary` shows in the `message` field.
