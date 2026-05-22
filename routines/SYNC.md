# Routine sync workflow

Each deployed routine at https://claude.ai/code/routines stores its prompt as
an **inline snapshot** captured at create time. That snapshot does **not**
auto-update when the source-of-truth files in this repo (`prompt.md`,
`stability-review-prompt.md`, or the inline `prompt:` blocks in
`routines/*.yaml`) change. Updates require a manual sync.

## Trigger IDs

| Routine          | Trigger ID                          | Source of truth                      | Cron expression           |
|------------------|-------------------------------------|--------------------------------------|---------------------------|
| triage           | `trig_01A6VgYtcZkh567gxCLvEMMw`     | `prompt.md`                          | `0 7-18 * * *` (hourly)   |
| stability-review | `trig_01CgsBZFhq3Tphw4719pQswG`     | `stability-review-prompt.md`         | `23 13 1-7 * 2` (1st Tue) |
| heartbeat        | `trig_016cuzzVZHdEJ3yAVvezhKaW`     | `routines/heartbeat.yaml` (inline)   | `0 */6 * * *` (every 6h)  |
| pir-ingest       | (local only — no cloud routine)     | `routines/pir-ingest.yaml` (inline)  | Task Scheduler Mon 09:15 local weekly |

## Sync workflow when a prompt changes

1. **Edit and commit locally** — change `prompt.md` / `stability-review-prompt.md` / `routines/<name>.yaml`, push to `main`.
2. **Open the routine in claude.ai** — visit `https://claude.ai/code/routines` and click the routine being changed.
3. **Paste the new prompt content** — replace the existing prompt with the latest content from the source-of-truth file.
4. **Save** — the next cron fire uses the new prompt.

Alternative: invoke the `/schedule` skill from a fresh Claude Code session and run `/schedule update <trigger_id>` with the latest prompt content.

## What changes need a sync

A sync is required when you change:
- The body text of the prompt (anything in `prompt.md`, `stability-review-prompt.md`, or the `prompt: |` block of an inline-prompt YAML).
- The MCP connectors attached to the routine.
- The cron schedule.

A sync is **not** required when you change:
- Files the routine reads at runtime — `kb/config.json`, `CLAUDE.md`, `playbooks/*.md`, `references/**/*`, `scripts/**/*`. The routine `cat`s these on each fire from the cloned repo, so changes to them propagate on the next cron without any sync step.
- Files the routine writes — `kb/incident-log.jsonl`, `docs/investigations/`, `docs/messages/`, `stability-reviews/<YYYY-MM>/<YYYY-MM-DD>-report.md`. Same reason.

## Why the gap exists

The deployed routine could in principle read its prompt from the cloned repo on each fire (and the YAML's `prompt_file:` directive hints at that intent), but the routine creation flow snapshots the prompt content into the trigger config so the routine remains runnable even if the repo is unreachable. The trade-off: prompt edits don't propagate without an explicit sync.
