# triage-bot

Slack-alert-triggered investigation routine for Method Integration. **v0.5: pull-mode polling via Slack MCP** (no Slack app, no webhook).

## What it does

Every hour, the routine:

1. Polls `#alert-system`, `#alert-frontend-errors`, `#alert-runtime-monitoring`, and `#swat` via Slack MCP `conversations.history` (last 65 minutes).
2. Computes a stable hash for each new message; skips ones it already triaged (`claude/triage-{hash}` branch exists).
3. Investigates each new message across Datadog, Elasticsearch, the read-only SQL replica, and the cloned Method codebase.
4. Classifies: `false-alarm` / `known-issue-recurrence` / `new-with-clear-fix` / `needs-human`.
5. DMs Ben on Slack with findings + a recommended next step (or thread-replies on the original alert for `false-alarm` and `swat`).
6. Commits its learning to `kb/`.
7. (After ~2 weeks of signal) opens PRs for clear single-file fixes.

The bot acts **as Ben** via Slack MCP OAuth — so DMs are self-DMs, and posts in alert channels show up authored by Ben.

## Architecture

```
        ┌─────────────────────────────────────────────┐
        │  Anthropic cloud routine (cron: 0 * * * *)  │
        │                                             │
        │  for each alert channel:                    │
        │    Slack MCP conversations.history          │
        │    (last 65 min, sorted oldest-first)       │
        │                                             │
        │  for each new message:                      │
        │    - hash → branch lock (idempotent)        │
        │    - KB lookup (literal/regex)              │
        │    - investigate (DD · ES · SQL · code)     │
        │    - classify                               │
        │    - act (DM self / thread-reply / PR)      │
        │    - commit kb/ updates on per-msg branch   │
        └────────────────────┬────────────────────────┘
                             │
        ┌────────────────────┼─────────────────────────┐
        ▼                    ▼                         ▼
 Slack DM to self    triage-bot/kb commits       GitHub PR (v2+)
 (or thread reply)   (one branch per alert)
```

Cloud cron's hourly minimum is the latency floor — alerts in `#swat` may sit up to 60 min before the bot replies. Acceptable for v0.5; we'll add push for `#swat` only if the latency starts hurting.

## Layout

| Path | Purpose |
|---|---|
| `prompt.md` | The routine's prompt — its brain (poll loop + per-message pipeline) |
| `kb/known-issues.json` | Known recurring issues with diagnosis + playbook |
| `kb/false-alarms.json` | Known false-positive patterns with reason |
| `kb/incident-log.jsonl` | Append-only log of every per-message decision and every poll-cycle summary |
| `kb/config.json` | Runtime config (enabled, daily caps, pr_mode, channel IDs, poll window) |
| `scripts/` | Portable Python helpers (KB matcher, DD/ES/SQL search, alert hash) |
| `playbooks/` | Investigation playbooks (DD, ES, classification, channel guidance) |
| `routines/` | Routine YAML configs (triage, heartbeat, kb-approver) |
| `slack-receiver/` | **Parked.** Push-mode receiver (Slack app + Cloudflare Worker). Revive only if you need sub-minute latency for `#swat`. |
| `docs/` | Runbook + KB curation guide |

## Setup

1. **Push this repo** (already done): `https://github.com/bgrady-method/triage-bot`.
2. **Get channel IDs.** In Slack, right-click each of the four alert channels + `#triage-bot-health`, copy the channel ID, paste into `kb/config.json`.
3. **Create the three Anthropic routines** at https://claude.ai/code/routines:
   - `triage` — paste `prompt.md`, configure per `routines/triage.yaml` (cron `0 * * * *`, Slack + GitHub MCPs, the secrets list).
   - `heartbeat` — inline prompt from `routines/heartbeat.yaml`, cron `0 */6 * * *`.
   - `kb-approver` — inline prompt from `routines/kb-approver.yaml`, cron `*/30 * * * *`.
4. **Connect Slack MCP** in each routine. OAuth as Ben — the routine then acts as you.
5. **Add the secrets** (DD/ES/SSH/SQL/GH) to the triage routine.
6. **First run.** Wait for the next hour boundary, or manually trigger the routine. Watch `kb/incident-log.jsonl` on `main` — every cron fire appends a `poll-cycle` summary line.

## Disable in 30 seconds

```json
// kb/config.json
{ "enabled": false }
```

Push. The next routine fire reads this at step 0a and exits silently.

## Status

| Phase | What | Status |
|---|---|---|
| 0.5 | Polling triage via Slack MCP, DM-only | scaffolded — pending routine setup |
| 1.5 | Self-write KB after 2 confirmations | pending |
| 2 | Auto-PR for high-confidence single-file fixes | pending |
| 3 | Add push for `#swat` (revive `slack-receiver/`) | only if latency becomes a problem |

## Owner

Ben Grady — `b.grady@method.me`
