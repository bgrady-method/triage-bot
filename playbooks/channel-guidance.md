# Per-channel investigation order

Each of the four alert channels has a different upstream and a different signal-to-noise profile. The routine prompt branches on `channel_name` from the alert payload to pick the right starting playbook.

## #alert-frontend-errors

**Source:** Datadog RUM + Sentry-style frontend exception aggregator.

**Investigation order:**
1. ES first — `playbooks/es-investigate.md` Step 2 with `query=fields.Exception:"<type>"`. Frontend exceptions land in ES via the JS error pipeline.
2. Datadog RUM second — query `@error.message:"<msg>"` to confirm browser-side cardinality (how many users affected).
3. **Skip APM.** Frontend traces don't go through APM.
4. If a stack trace points at a file, `git grep` the cloned `apps/m-one` repo for the line.

**Bias:** these alerts are usually `new-with-clear-fix` (single null guard, missing default value) or `needs-human` (a regression Ben needs to assess). Rarely false alarms — frontend RUM is configured to only alert on real user-facing errors.

## #alert-runtime-monitoring

**Source:** Datadog monitors on backend services (latency, error rate, request rate, custom metrics).

**Investigation order:**
1. `playbooks/dd-investigate.md` Step 1 (firing monitors) — the alert text usually quotes the monitor; pull its `query` field for ground truth.
2. `playbooks/dd-investigate.md` Step 3 (golden signals vs baseline).
3. APM (Step 4) for a representative trace.
4. ES only as confirmation if exception details are needed.
5. SQL via `scripts/sql_query.py` only if hypotheses include a data state question (e.g. health-check on a specific account DB).

**Bias:** highest false-alarm rate of the four channels (noisy monitors). Build the KB here aggressively — many entries will be `false-alarm` with `silence_for: "24h"`.

## #alert-system

**Source:** mixed. Infrastructure events (RabbitMQ queue depth, Redis health, AWS notifications), some application alerts that don't fit the runtime category.

**Investigation order:**
1. Read alert text carefully — the source is encoded in the text more than in the channel.
2. If RabbitMQ / Redis / infra: skip ES + APM, go straight to Datadog metrics for the relevant component.
3. If application: parallel Datadog + ES (Steps 1-2 of each playbook).
4. SQL if the alert mentions a specific DB, account, or storage system.

**Bias:** tilted toward `needs-human` because the upstream is heterogeneous and KB pattern matching is harder. If you can't classify with confidence ≥ 0.85, default to `needs-human` regardless of the run-count gate.

## #swat

**Source:** human-posted P0/P1 incident posts. Sometimes structured (XMatters), often free-form ("API is down for customer X").

**Investigation order:**
1. **Post in-thread, don't DM.** SWAT means a human is already engaged; the bot's job is to gather context fast and put it where the responder can see it. Use `chat.postMessage` with `thread_ts` set to the alert's `ts`.
2. Run Datadog + ES in parallel, widest plausible window (`now-1h` minimum).
3. Pull recent deploys (`git log --since="1 hour ago"` on the cloned target service repo, if mentioned).
4. SQL health-check on the named customer DB if applicable.
5. Output a structured summary in the thread, not a DM.

**Bias:** never auto-PR from SWAT. Always `needs-human`. The bot is a research assistant in this channel, nothing more.

## Posting locations summary

| Channel | Where the bot replies |
|---|---|
| `alert-frontend-errors` | Self-DM (bot acts as Ben via Slack MCP) |
| `alert-runtime-monitoring` | Self-DM |
| `alert-system` | Self-DM |
| `swat` | **Thread reply on the alert itself** (not a DM) — slow in v0.5 (up to 60 min) but still the right surface |
| `triage-bot-health` | Heartbeat + failure summaries + cycle deferrals |
