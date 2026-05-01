# triage-bot

Slack-alert-triggered investigation routine for Method Integration.

## What it does

Every alert in `#alert-system`, `#alert-frontend-errors`, `#alert-runtime-monitoring`, or `#swat`:

1. Hits a Cloudflare Worker (Slack signature verified)
2. The Worker fires a Claude routine with the alert payload
3. The routine investigates across Datadog, Elasticsearch, the read-only SQL replica, and the cloned Method codebase
4. It classifies the alert: `false-alarm` / `known-issue-recurrence` / `new-with-clear-fix` / `needs-human`
5. It DMs Ben on Slack with findings + a recommended next step
6. It commits its learning to `kb/`
7. (After ~2 weeks of signal) it can open PRs for clear single-file fixes

## Architecture

```
Slack alert  ──▶  Cloudflare Worker  ──▶  Routine /fire endpoint
   (4 channels)    (signature verify,        (Anthropic cloud)
                    payload reshape,
                    debounce)                    │
                                                 ▼
                                  ┌──────────────────────────┐
                                  │ Triage routine (1 prompt)│
                                  │  - Hash alert (idempotency)
                                  │  - KB lookup (literal/regex)
                                  │  - Channel-specific playbook:
                                  │    Datadog · ES · SQL · code
                                  │  - Classify
                                  │  - Act (DM Ben; later: PR)
                                  │  - Append to incident-log
                                  └──────────┬───────────────┘
                                             │
                  ┌──────────────────────────┼─────────────────────────┐
                  ▼                          ▼                         ▼
         Slack DM to Ben         Commit to triage-bot/kb        GitHub PR (v2+)
                                 (branch per alert hash)
```

## Layout

| Path | Purpose |
|---|---|
| `prompt.md` | The routine's prompt — its brain |
| `kb/known-issues.json` | Known recurring issues with diagnosis + playbook |
| `kb/false-alarms.json` | Known false-positive patterns with reason |
| `kb/incident-log.jsonl` | Append-only log of every run |
| `kb/config.json` | Runtime config (enabled, daily caps, pr_mode) |
| `scripts/` | Portable Python helpers (KB matcher, DD/ES/SQL search) |
| `playbooks/` | Investigation playbooks (DD, ES, classification, channel guidance) |
| `routines/` | Routine YAML configs (triage, heartbeat, kb-approver) |
| `slack-receiver/` | Cloudflare Worker source + Slack app manifest |
| `docs/` | Runbook + KB curation guide |

## Disable in an emergency

Edit `kb/config.json` on `main`:

```json
{ "enabled": false }
```

Push. The next routine run reads this and exits silently. Or set `pr_mode: "off"` to keep triage but disable PR creation.

## Status

| Phase | What | Status |
|---|---|---|
| 0 | Slack receiver in observation mode (logs to `#triage-bot-debug`) | not started |
| 1 | DM-only triage with KB approval flow | not started |
| 1.5 | Self-write KB after 2 confirmations | not started |
| 2 | Auto-PR for high-confidence single-file fixes | not started |

## Owner

Ben Grady — `b.grady@method.me`
