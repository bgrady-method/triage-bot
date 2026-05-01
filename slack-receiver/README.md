# slack-receiver — PARKED in v0.5

> **This directory is not used in v0.5.** v0.5 polls Slack via MCP from inside the routine, so no separate webhook receiver is needed.
>
> Revive this only if you need sub-minute latency for `#swat` or if daily alert volume exceeds what hourly polling can absorb.

---

## What this would do (when revived)

A Cloudflare Worker that receives Slack Events API payloads and forwards them to a Claude routine's `/fire` endpoint. Two modes via the `PHASE` env var:

- **Phase 0 (observation):** posts the parsed payload to `#triage-bot-debug` so you can verify the wire shape across all 4 alert channels.
- **Phase 1 (live):** forwards to the routine's `/fire` endpoint with a bearer token.

## Reviving (future)

```bash
cd slack-receiver
npm install
npx wrangler login

# Required secrets:
npx wrangler secret put SLACK_SIGNING_SECRET    # from Slack app -> Basic Information
npx wrangler secret put SLACK_BOT_TOKEN         # xoxb-... from OAuth & Permissions
npx wrangler secret put ALLOWED_CHANNELS        # C0123,C0456,... (channel IDs)
npx wrangler secret put DEBUG_CHANNEL_ID        # #triage-bot-debug ID
npx wrangler secret put ROUTINE_FIRE_URL        # from Anthropic routine config
npx wrangler secret put ROUTINE_FIRE_TOKEN      # from Anthropic routine config

npx wrangler deploy
```

The deploy output prints your Worker URL. Paste it into the Slack app's **Event Subscriptions → Request URL**. Slack verifies via the URL handshake — the Worker handles `url_verification` automatically.

You'll also need to switch the triage routine's trigger from `cron` to `api` (in `routines/triage.yaml` and the routine UI), and update the top of `prompt.md` to consume a single firing payload instead of polling.

Push and pull can coexist: keep the cron trigger for the three less-urgent channels, add an api trigger that the Worker fires only for `#swat`.
