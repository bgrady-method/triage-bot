# `routines/` — prompt + scheduling for the four triage-bot runs

This directory holds the source-of-truth prompts and (in PR #2) the Windows Task Scheduler XML for the four triage-bot routines. The repo is mid-pivot from Anthropic Cloud Routines to fully local, unattended Claude Code sessions on a disposable Windows VM. See `C:\Users\Benjamin Grady\.claude\plans\i-notice-there-is-lazy-hedgehog.md` for the full plan.

## What's here

| File | Role |
|---|---|
| `triage.prompt.md` | Hourly alert-channel poll + investigate + DM. Was top-level `prompt.md` (still present during dual-run; this is the canonical copy going forward). |
| `stability-review.prompt.md` | Monthly stability report. Was top-level `stability-review-prompt.md`. |
| `heartbeat.prompt.md` | Every-6h tool-health + spend-cap check. Extracted from `heartbeat.yaml`'s inline `prompt:` block. |
| `kb-approver.prompt.md` | Every-3h merge of Ben-approved KB additions. Extracted from `kb-approver.yaml`'s inline `prompt:` block. |
| `triage.yaml` | **Legacy.** Cloud Routine config. Source of truth for the deployed cloud routine at trig_01A6Vg…EMMw until cutover (PR #4). |
| `stability-review.yaml` | **Legacy.** Cloud Routine config (trig_01CgsB…pQswG). |
| `heartbeat.yaml` | **Legacy.** Cloud Routine config (trig_016cuz…hKaW). |
| `kb-approver.yaml` | **Legacy.** Cloud Routine config (trig_013UVV…7xoq4). |
| `SYNC.md` | **Legacy.** The manual paste-and-save workflow that keeps the cloud-routine inline-snapshot prompts in sync with the source files. Retired in PR #4. |

In PR #2: `*.task.xml` files appear here (Windows Task Scheduler exports for each routine).

## How the new model works

Each routine is one `claude -p` invocation reading its `routines/<name>.prompt.md` file. Scheduled by Windows Task Scheduler. No inline-snapshot drift, no manual sync step — `git pull` at the start of every fire (in `scripts/invoke-routine.ps1`, landing in PR #2) means the next scheduled run always picks up committed prompt changes.

```powershell
# what scripts/invoke-routine.ps1 -Routine triage will do (PR #2):
git pull origin main
Get-Content routines/triage.prompt.md | claude -p "" `
  --output-format json `
  --permission-mode acceptEdits `
  | Tee-Object -FilePath logs/triage-$(Get-Date -Format 'yyyyMMdd-HHmmss').json
```

## Editing prompts

1. Edit `routines/<name>.prompt.md`.
2. Commit + push to `main`.
3. Next scheduled fire on the VM picks it up via `git pull`.

**During the dual-run period** (between PR #3 landing and PR #4 retiring the cloud routines), you also need to follow `SYNC.md` to update the cloud routine's inline snapshot. Once the cloud routines are retired, `SYNC.md` is deleted and step 1+2 above are the only flow.

## Why prompts moved out of the YAMLs

Cloud Routines stored the prompt inline in the YAML (heartbeat, kb-approver) or in a separate `prompt.md` referenced by `prompt_file:` (triage, stability-review). For the unattended-local model, every routine has the same shape: a `.prompt.md` that `claude -p` reads from disk on each fire. The YAMLs become legacy historical artifacts.

## Skill auto-discovery

The prompts can reference skills by name (e.g. "use the `dd-investigate` skill"). Claude Code auto-loads skills from `.claude/skills/` when their description matches the prompt. The vendored skills are:

- `dd-investigate`, `dd-logs`, `dd-monitors`, `dd-metrics`, `dd-apm` — Datadog tooling
- `es-investigate`, `es-logs`, `es-indices` — Elasticsearch / Logstash
- `dd-setup`, `es-setup` — credential bootstrap (used internally by the others)
- `triage-classify`, `triage-channel-route` — repo-specific bucketing + routing
- `stability-five-whys` — repo-specific monthly-review methodology

These are checked into `.claude/skills/`. PR #3 will update the prompt bodies to invoke skills explicitly where they currently `cat playbooks/<file>.md`.
