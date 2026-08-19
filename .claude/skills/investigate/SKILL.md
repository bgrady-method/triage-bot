---
name: investigate
description: >
  Run one alert / root-cause group through the triage bot's deterministic, read-only
  investigation pipeline and emit a structured evidence bundle (KB match + recurrence
  verification, channel routing, Datadog monitors/logs, Elasticsearch aggregations,
  account impact, partial escalation score). Use when triaging a Slack alert, reproducing
  a past incident's investigation, or ad-hoc probing "what does the bot see for this alert".
  Read-only: it gathers evidence and computes signals — it never sends, commits, or classifies.
user_invocable: true
---

# investigate — deterministic investigation orchestrator

This skill wraps [`scripts/investigate.py`](../../../scripts/investigate.py): the mechanical
stages of `prompt.md` steps 2–7 run in fixed order by shelling out to the already-wired
read-only scripts, producing one **evidence bundle** the model then reasons over.

**It gathers; it does not decide.** The genuine-judgment stages (root-cause hypothesis,
final 4-bucket classification) and every side effect (Slack send, KB write, git commit)
stay with the routine/model. The orchestrator itself makes no write, no send, no commit.

## Hard rules (do not break)
- **Read-only — Hard rule #3.** Every wrapped call is a query (`dd_search.py`, `es_search.py`,
  `account_impact.py`, `match_kb.py`). Never pass a `--commit`/write path; never mutate DD/ES.
- **Scoring is partial by design.** `score` combines mechanically-derivable signals with any
  the model supplies via `--signals-json`. The bundle lists `model_supplied_signals_still_needed`
  — the model must finish scoring and own the classification. Scoring logic lives in
  [`scripts/score.py`](../../../scripts/score.py) (unit-tested; single source of truth).
- **Only four signals are still model-supplied** (2026-07-15): `deployed_within_2h`, `metric`,
  `operator_engaged`, `swat_thread_mentions`. The last two need a Slack channel read, which is
  MCP-only — this orchestrator shells out to Python and has no MCP access, so only the model can
  see them. Everything else derivable from disk (`novel`, `monitor_fire_count`, `monitor_dm_count`,
  `monitor_fires_today`, `recent_post_same_kb_24h`) is now derived in `derive_history_signals`.
  **Why it matters:** four of the five *inhibition* signals used to sit in the model-supplied list.
  An absent signal contributes nothing and inhibition is negative, so an un-supplemented run scored
  systematically **high — biased toward sending**. Pass `--monitor-id` to enable the monitor-history
  signals; without it they're omitted rather than assumed zero.
- **Two send guards are enforced elsewhere.** `#swat`/`#team-incident-response` blocking and
  the `@`-mention ban (Hard rule #13) are enforced by the PreToolUse hook
  `.claude/hooks/guard_slack_send.py`, not here.

## Pipeline (fixed order — matches the DD/ES playbooks)

| Stage | Wraps | Produces |
|---|---|---|
| `hash` | `alert_hash.py` | idempotency key |
| `kb-match` | `match_kb.py` (false-alarms → known-issues) | matched entry / null |
| `kb-verify` | `kb_to_es_query.py` + `es_search.py` / `dd_search.py` | fresh recurrence hit count (>0 gate) |
| `route` | `playbooks/channel-guidance.md` map | `dd-first` / `es-first` / `both` |
| `dd` | `dd_search.py monitors` (always first) + error-log sample | firing monitors, error sample |
| `es` | `es_search.py aggregate` × `Level`/`Exception`/`Error`.keyword | first-sweep buckets |
| `impact` | `account_impact.py` | per-tenant active users + tiers |
| `score` | `score.py` (imported) | partial `escalation_score` + decision preview |

Drill-down doctrine (what to do *inside* the DD/ES stages) is shared with Method's `mtd`
plugin: `references/incident/datadog-playbook.md` (monitors → logs → metrics → traces) and
`references/incident/elasticsearch-playbook.md` (aggregate → drill → expand by `RequestId`),
plus this repo's `playbooks/dd-investigate.md` / `playbooks/es-investigate.md`. Always read
the full `Exception` + `message` on 2–3 samples before concluding (es-investigate Step 3.5).

## Usage

```bash
# Full pipeline for a live alert (JSON bundle):
python scripts/investigate.py --channel C063V5HTTFU --ts 1720000000.001 \
  --service runtime-core-api --text "<alert text>" --group-size 3 --distinct-channels 2

# Human-readable summary:
python scripts/investigate.py --channel alert-system --ts <ts> --text "<...>" --format md

# Only some stages (e.g. re-confirm a known-issue recurrence):
python scripts/investigate.py --channel alert-system --ts <ts> --text "<...>" \
  --stages kb-match,kb-verify

# Feed model-derived signals the orchestrator can't observe (deploy timing, novelty, etc.):
python scripts/investigate.py --channel <c> --ts <ts> --accounts acme,globex \
  --signals-json model_signals.json
```

`--channel` accepts a channel **ID or name** (resolved via `kb/config.json.channels`).
`--accounts` is comma-separated; omit it to skip the impact stage. Windows default to
`now-65m` (`--window-min`). `.env` is auto-loaded from the repo root, so the skill works
ad-hoc; under the routine runner the exported environment wins.

## What this skill does NOT do
- No sending, no committing, no KB writes — the routine does those after reading the bundle.
- No final classification or confidence — those are model judgment (`playbooks/classification.md`).
- No monitoring writes — for Datadog dashboards use `datadog-dashboards`; for Grafana alerts
  use `grafana-alerting` (the only sanctioned monitoring write path).
