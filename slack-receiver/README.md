# slack-receiver

Cloudflare Worker that receives Slack Events API payloads and either:

- **Phase 0 (observation):** posts the parsed payload to `#triage-bot-debug` so we can verify the wire shape across all 4 alert channels.
- **Phase 1 (live):** forwards the parsed payload to the Claude routine's `/fire` endpoint with a bearer token.

Switch by setting the `PHASE` env var in `wrangler.toml` (`"0"` or `"1"`).

## Deploy (first time)

```bash
cd slack-receiver
npm install
npx wrangler login

# Required secrets:
npx wrangler secret put SLACK_SIGNING_SECRET    # from Slack app -> Basic Information
npx wrangler secret put SLACK_BOT_TOKEN         # xoxb-... from OAuth & Permissions
npx wrangler secret put ALLOWED_CHANNELS        # C0123,C0456,... (4 alert channel IDs, comma-separated)
npx wrangler secret put DEBUG_CHANNEL_ID        # #triage-bot-debug ID

# Phase 1 only:
npx wrangler secret put ROUTINE_FIRE_URL        # from Anthropic routine config
npx wrangler secret put ROUTINE_FIRE_TOKEN      # from Anthropic routine config

npx wrangler deploy
```

The deploy output prints your Worker URL (e.g. `https://triage-bot-slack-receiver.bgrady.workers.dev`). Paste this URL into the Slack app's **Event Subscriptions → Request URL**. Slack will verify it via the URL handshake — the Worker handles `url_verification` automatically.

## Verifying

1. Send a test message in `#triage-bot-debug` — nothing should happen (the bot's own posts are filtered).
2. Send a test message in one of the four alert channels — within ~1s, a debug post should appear in `#triage-bot-debug` showing the reshaped payload.
3. Check `npx wrangler tail` for live logs of incoming events.

## Switching to Phase 1

After Phase 0 has run for 2–3 days and the alert shapes look good:

```bash
# Edit wrangler.toml: PHASE = "1"
npx wrangler deploy
```

The Worker now forwards to the routine instead of the debug channel.
