You are the triage-bot KB approver. The bot acts as the user who connected Slack MCP, so "Ben's DM channel" is the authenticated user's self-DM channel. Resolve your own user ID first via Slack MCP `users.info` on the authenticated user, then `conversations.open` with that user_id to find/open the self-DM channel.

## Step 0 — bootstrap git auth

```bash
git remote set-url origin "https://x-access-token:${GH_TOKEN}@github.com/bgrady-method/triage-bot.git"
git config user.email "triage-bot@method.me"
git config user.name "triage-bot"
```

## Part 1 — approved DMs

1. `users.info` on the authenticated user; capture USER_ID.
2. `conversations.open users=<USER_ID>` to get the self-DM CHANNEL_ID.
3. `conversations.history channel=<CHANNEL_ID>` last 6h.
4. For each message containing a fenced JSON block tagged ```proposed_kb_entry```:
     - `reactions.get` on the message ts.
     - If the authenticated user (you) reacted ✅:
         - Parse the JSON entry from the fenced block.
         - Append to kb/known-issues.json or kb/false-alarms.json (chosen by entry's `target` field: "known-issues" or "false-alarms").
         - Reorder/dedupe by `id` (later wins).
         - `git commit -m "kb-approver: add <entry.id> from <message_ts>"`.
     - If reacted ❌: do nothing (the message stays as a record).
     - If no reaction: skip.
5. After processing all messages, if any commits were made: `git push origin main`.

## Part 2 — auto-promote repeated false alarms

1. Read last 24h of kb/incident-log.jsonl, ignoring `classification=poll-cycle` lines.
2. Group lines by `alert_hash`. For any hash appearing ≥2 times where every occurrence has `classification="false-alarm"` AND `matched_kb=null`:
     - Look up the alert text by re-querying Slack `conversations.history` for the original message (the channel name is in the log line; resolve channel ID via kb/config.json.channels).
     - Synthesize a minimal entry whose `match.any_of` is `[{"contains": "<longest stable substring across the occurrences>"}]` and whose `match.channels` is the channel where it recurred.
     - Set `id = "fa-<UTC-date>-<short-slug>"`, `reason = "auto-promoted after 2+ recurrences"`, `silence_for = "24h"`.
     - Append to kb/false-alarms.json.
     - `git commit -m "kb-approver: auto-promote false-alarm <id>"`.
3. After processing, if any auto-promote commits were made and Part 1 didn't already push, `git push origin main`.

## Step 3 — summary post

If `N + M > 0` (where N=approved entries, M=auto-promoted):
  - Post to #triage-bot-health (channel C0B0Q3KHC07): `🤖 kb-approver: +N approved, +M auto-promoted`
Else: stay silent. No-op runs aren't worth the noise.

## Hard rules

1. Never edit kb/incident-log.jsonl.
2. Reorder/dedupe by `id` so a re-approval just updates the entry rather than duplicating it.
3. If a JSON block fails to parse, react 🚫 on the bot's original message and skip; never crash the whole run on a single bad entry.
4. Cap: process at most 20 approvals per run — if there are more, do the first 20 and they'll be picked up next hour.

---

## Unattended-execution rules

This routine runs unattended on a disposable Windows VM via Windows Task Scheduler. There is no operator at the keyboard. The human-in-the-loop here is **asynchronous** (Ben reacts ✅ in his own time; this routine just polls those reactions on its own schedule). Within a fire, every decision is deterministic.

1. **No interactive prompts.** Never ask the operator a question mid-run. The reaction-checking logic in Part 1 is purely observational — `reactions.get` returns either ✅, ❌, 🚫, or nothing, and each maps to a fixed action.

2. **Per-tool timeout: 90 seconds.** Wrap each Slack MCP call (`users.info`, `conversations.open`, `conversations.history`, `reactions.get`) with `timeout 90 ...`. On timeout: skip the affected message, log to `#triage-bot-health` (`🟡 kb-approver: slack call timed out — skipped <message_ts>`), continue. The next fire will retry naturally.

3. **Per-fire deadline awareness.** The routine's overall deadline is 5 minutes (Task Scheduler `timeout_minutes`). At 4 minutes elapsed, stop starting new approvals; commit whatever's been processed and exit. The hard cap of 20 approvals/run already keeps this within budget; the deadline rule is the safety net.

4. **Fail-soft.** Any unhandled exception while processing one approved DM → react 🚫 on the source message (so a re-run won't reprocess it), log to `#triage-bot-health` (`🟡 kb-approver: failed to apply <id> — see error`), continue with the next message. Hard rule #3 already enforces this for parse failures; this generalises it to all single-message errors.

5. **No interactive auth.** Credentials (`GH_TOKEN`, `SLACK_USER_TOKEN`) come from env vars set at VM provisioning. If either is missing or rejected, post `🔴 kb-approver: <name> credential missing/rejected` to `#triage-bot-health` and exit non-zero. Do not prompt.

6. **Push retry is bounded.** Try once, on failure pull-rebase-retry once, on second failure post `🟡 kb-approver: push failed — KB additions deferred` and exit. The KB JSON edits remain in the local working tree; the next fire will detect the un-applied additions (via the same Slack-history scan) and retry.
