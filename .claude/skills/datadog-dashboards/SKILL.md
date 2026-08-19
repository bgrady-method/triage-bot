---
name: datadog-dashboards
description: >
  Create, read, clone, update, and delete Datadog dashboards via the v1 dashboard API.
  Use when the user asks to build/inspect/edit/remove a Datadog dashboard or copy widgets
  between dashboards. USER-INVOKED ONLY — writes mutate Datadog, which prompt.md Hard rule #3
  forbids the autonomous triage routine from doing. Reads are always safe; writes are dry-run
  until --commit.
---

# Datadog dashboards

Wraps the Datadog **v1 dashboard API** through `scripts/dd_dashboard.py`. It's the dashboard
companion to the read-only `scripts/dd_search.py` (logs / monitors / metrics / RUM).

## Boundary with Hard rule #3 (read this first)

`prompt.md` Hard rule #3: **"No mutating Datadog or ES. Read-only API calls only."** Dashboard
`create` / `update` / `delete` are Datadog writes — so:

- **The autonomous triage routine must never call the write paths.** It may use `list` / `get`
  to read a dashboard during an investigation; that stays read-only and compliant.
- **Writes are a deliberate, user-invoked action.** Every write is **dry-run by default** and only
  hits the API with an explicit `--commit`. Treat `--commit` like the `grafana-alerting` skill's
  `--commit`: a human chose to run it.

## Auth (same env as dd_search.py)
- `DD_API_KEY`, `DD_APP_KEY` — required for every call (read and write).
- `DD_SITE` — defaults to `datadoghq.com`.

These already live in `.env`. The script reads them from the process environment.

## Commands

| Command | API | Safe? |
|---|---|---|
| `list [--query <substr>] [--summary]` | `GET /api/v1/dashboard` | read-only |
| `get --id <id>` | `GET /api/v1/dashboard/{id}` | read-only |
| `create --file <json> [--commit]` | `POST /api/v1/dashboard` | dry-run until `--commit` |
| `update --id <id> --file <json> [--commit]` | `PUT /api/v1/dashboard/{id}` | dry-run until `--commit` |
| `delete --id <id> [--commit]` | `DELETE /api/v1/dashboard/{id}` | dry-run until `--commit` |

`--file -` reads the JSON definition from stdin. Add `--pretty` to any command for indented JSON.

## Typical workflows

**Read / find a dashboard**
```bash
python scripts/dd_dashboard.py list --summary --query "runtime-core"
python scripts/dd_dashboard.py get --id abc-d3f-ghi --pretty > dash.json
```

**Create a new dashboard**
1. Write a definition file (minimum: `title`, `layout_type`, `widgets`). The easiest start is to
   `get` an existing dashboard, strip `id`/`url`/`author_*`, and edit.
2. Dry-run, then commit:
```bash
python scripts/dd_dashboard.py create --file dash.json            # dry-run: prints what it would POST
python scripts/dd_dashboard.py create --file dash.json --commit   # actually creates; prints new id + url
```

**Edit an existing dashboard (PUT replaces the whole thing)**
```bash
python scripts/dd_dashboard.py get --id abc-d3f-ghi --pretty > dash.json   # fetch full body
# edit dash.json
python scripts/dd_dashboard.py update --id abc-d3f-ghi --file dash.json            # dry-run
python scripts/dd_dashboard.py update --id abc-d3f-ghi --file dash.json --commit   # apply
```
`update` is a full replace — always start from a freshly fetched body so you don't drop widgets.

**Clone**: `get` source → remove `id`/`url`/`author_*` → change `title` → `create`.

**Delete**
```bash
python scripts/dd_dashboard.py delete --id abc-d3f-ghi             # dry-run
python scripts/dd_dashboard.py delete --id abc-d3f-ghi --commit    # gone
```

## Dashboard body shape (ordered layout)
```json
{
  "title": "My dashboard",
  "description": "what it shows",
  "layout_type": "ordered",
  "widgets": [
    {
      "definition": {
        "title": "p95 request duration — tables-fields",
        "type": "timeseries",
        "requests": [
          { "q": "p95:trace.web.request.duration{service:tables-fields,env:prod}", "display_type": "line" }
        ]
      }
    }
  ]
}
```
`layout_type` is `ordered` (auto-stacked; omit per-widget `layout`) or `free` (each widget needs a
`layout: {x,y,width,height}`). Widget `type` values: `timeseries`, `query_value`, `toplist`,
`heatmap`, `table`, `note`, `group`, etc. The metric queries (`q`) are the same ones `dd_search.py
metric` runs, so probe them there first.

## Safety checklist before `--commit`
- Ran the same command without `--commit` and the dry-run summary matches intent.
- For `update`: the body came from a fresh `get` (full replace — no dropped widgets).
- For `delete`: confirmed the `id` via `list --summary` first.
- You (a human) are running it — not the autonomous routine.
