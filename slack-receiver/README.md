# triage-bot Slack app

One Slack app (`manifest.json`) serving **two active jobs** plus **one parked job**:

| Job | Status | Mechanism |
|---|---|---|
| Grafana alerting delivery | **active** | Incoming Webhook → `#triage-bot-health` (consumed by the SLO alerting system) |
| triage bot's send identity | **active** | Bot token (`chat:write`/`im:write`) used by `scripts/slack_send.py` |
| Async message trigger | **parked** | Events API → Cloudflare Worker (`worker.js`) → routine `/fire` |

Design tie-in: `references/architecture/alerting-system-design.md` (how the webhook feeds the Grafana contact
point) and `references/architecture/alerting-system-status.md`.

---

## Install (one time)

1. **api.slack.com/apps → Create New App → From manifest** → paste `manifest.json` → create in the Method
   workspace. Installing needs **workspace-admin approval**.
2. **Install to Workspace.**

### Wire job 1 — Grafana alerting delivery
3. **Incoming Webhooks → Add New Webhook to Workspace → `#triage-bot-health`** → copy the
   `https://hooks.slack.com/services/…` URL.
4. Put it in `.env` (never commit): `TRIAGE_BOT_HEALTH_WEBHOOK=https://hooks.slack.com/services/…`
   (later: one webhook per team channel for per-team routing).
5. The alerting system consumes it: `python scripts/grafana_provision.py contact-point-ensure --commit`
   then `... test-fire --commit`.

### Wire job 2 — the bot's send identity
6. **OAuth & Permissions → Bot User OAuth Token (`xoxb-…`)** → `.env`: `SLACK_BOT_TOKEN=xoxb-…`
7. **Invite `@triage-bot`** to `#triage-bot-health` and the 3 public alert channels (`alert-system`,
   `alert-frontend-errors`, `alert-runtime-monitoring`). **Do NOT invite it to `#swat` or
   `#team-incident-response`** — and `scripts/slack_send.py` refuses to post there regardless.
8. Verify: `python scripts/slack_send.py heartbeat --text "triage-bot app online"` → lands in
   `#triage-bot-health` as `triage-bot`.

Secrets (`TRIAGE_BOT_HEALTH_WEBHOOK`, `SLACK_BOT_TOKEN`) live only in `.env` — never in the repo.

---

## Parked: async message trigger (revive later)

Currently the routine **polls** hourly via the Slack MCP (`routines/triage.yaml` cron). To switch to
push-based, sub-minute triggering, revive the Cloudflare Worker in this directory.

1. Re-add the event subscription to `manifest.json` `settings` (Slack requires a live `request_url`, so deploy
   the Worker first, then paste its URL here):
   ```json
   "event_subscriptions": {
     "request_url": "https://<deployed-worker>.workers.dev",
     "bot_events": ["message.channels", "message.groups"]
   }
   ```
   `message.groups` + the dormant `groups:history` scope cover the private `#swat` /
   `#team-incident-response` channels — **read-only; the bot still never posts there.**
2. Deploy the Worker:
   ```bash
   cd slack-receiver && npm install && npx wrangler login
   npx wrangler secret put SLACK_SIGNING_SECRET    # Slack app → Basic Information
   npx wrangler secret put SLACK_BOT_TOKEN         # xoxb-… (same app token)
   npx wrangler secret put ALLOWED_CHANNELS        # comma-separated channel IDs
   npx wrangler secret put DEBUG_CHANNEL_ID        # #triage-bot-debug (Phase 0)
   npx wrangler secret put ROUTINE_FIRE_URL        # Anthropic routine /fire endpoint
   npx wrangler secret put ROUTINE_FIRE_TOKEN      # bearer for /fire
   npx wrangler deploy
   ```
3. Paste the Worker URL into the Slack app's **Event Subscriptions → Request URL** (the Worker auto-handles the
   `url_verification` handshake). `worker.js` runs in two phases via the `PHASE` var: `0` = observe (post the
   reshaped payload to `#triage-bot-debug`), `1` = live (forward to the routine).
4. Switch `routines/triage.yaml` trigger from `cron` to `api` (or run both — keep cron for the safety net and
   fire on-demand for `#swat`), and update `prompt.md` to consume a single firing payload instead of polling.

Why it's worth doing eventually: the Events API payload carries the **block/attachment content** that
Grafana/Datadog post — content the Slack MCP currently can't surface (see
`docs/investigations/2026-06-11-89f3aaafdbeef186.md`).
