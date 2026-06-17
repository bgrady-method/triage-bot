# Per-channel investigation order

Each alert channel has a different upstream and a different signal-to-noise profile. The routine prompt branches on `channel_name` from the alert payload to pick the right starting playbook. `swat` and `team-incident-response` are *incident-response* channels and share identical handling (investigate, self-DM only, never post).

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

**NEVER POST TO #swat.** No thread replies, no top-level posts, no reactions. SWAT is a human-incident-response channel; the bot adds noise there. All investigation output for swat alerts goes to Ben's self-DM, exactly like the other alert channels.

**Investigation order:**
1. Run Datadog + ES in parallel, widest plausible window (`now-1h` minimum).
2. Pull recent deploys (`git log --since="1 hour ago"` on the cloned target service repo, if mentioned).
3. SQL health-check on the named customer DB if applicable.
4. DM Ben a structured summary with all source permalinks and evidence links.

**Bias:** never auto-PR from SWAT. Always `needs-human`. The bot is a silent research assistant for swat — observes, investigates, DMs Ben. Never writes to the channel.

## #team-incident-response

**Source:** incident-response coordination channel (`C0B6233UN4S`). Mixes a Monitoring bot's automated SWAT investigation posts (CPU/host runbooks, etc.) with human coordination messages naming services for rollback / root-cause.

**Treat exactly like #swat** — it is the second incident-response channel. **NEVER POST** (no thread replies, no top-level posts, no reactions); all output goes to Ben's self-DM. Bypass the suppression/escalation cap (humans are watching). Always `needs-human`; never auto-PR.

**Investigation order:** same as #swat. Additionally, read the human coordination thread (per prompt step 4.0a) for `'rolling back X'` / `'reverting X'` pointers — treat engineer-named targets as strong priors to verify with mechanism evidence, not proof.

## Posting locations summary

| Channel | Where the bot replies |
|---|---|
| `alert-frontend-errors` | Self-DM (bot acts as Ben via Slack MCP) |
| `alert-runtime-monitoring` | Self-DM |
| `alert-system` | Self-DM |
| `swat` | Self-DM (same as other alert channels). **Never post to #swat itself** — no thread replies, no top-level posts. |
| `team-incident-response` | Self-DM (incident-response channel, same handling as #swat). **Never post to #team-incident-response itself** — no thread replies, no top-level posts. |
| `triage-bot-health` | Heartbeat + failure summaries + cycle deferrals |
