# `routines/` — prompt + scheduling for the four triage-bot runs

This directory holds the source-of-truth prompts and the Windows Task Scheduler XML for the four triage-bot routines. The repo is mid-pivot from Anthropic Cloud Routines to fully local, unattended Claude Code sessions on a disposable Windows VM. See `C:\Users\Benjamin Grady\.claude\plans\i-notice-there-is-lazy-hedgehog.md` for the full plan.

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
| `triage.task.xml` | Windows Task Scheduler export — hourly 07:00–18:00 UTC. Register with `schtasks /Create /XML routines\triage.task.xml /TN "triage-bot\triage" /F`. |
| `heartbeat.task.xml` | Task Scheduler export — every 6h (00/06/12/18 UTC). Same `schtasks /Create /XML` pattern under `\triage-bot\heartbeat`. |
| `kb-approver.task.xml` | Task Scheduler export — every 3h at :45 UTC. Registers as `\triage-bot\kb-approver`. |
| `stability-review.task.xml` | Task Scheduler export — first Tuesday each month at 13:23 UTC. Registers as `\triage-bot\stability-review`. |

## How the new model works

Each routine is one `claude -p` invocation reading its `routines/<name>.prompt.md` file. Scheduled by Windows Task Scheduler via `scripts/invoke-routine.ps1`. No inline-snapshot drift, no manual sync step — `git pull --ff-only` at the start of every fire means the next scheduled run always picks up committed prompt changes.

```powershell
# scripts/invoke-routine.ps1 -Routine <name> does, in order:
#   1. cd C:\MethodDev\triage-bot
#   2. load .env into the process environment
#   3. git pull --ff-only (non-fatal on failure)
#   4. Get-Content routines/<name>.prompt.md | claude -p "" `
#        --output-format json `
#        --permission-mode acceptEdits `
#        2>&1 | Tee-Object -FilePath logs/<name>-<UTC-stamp>.json
#   5. exit with claude's exit code (so Task Scheduler "Last Run Result" is meaningful)
```

### Manual run (smoke test)

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File C:\MethodDev\triage-bot\scripts\invoke-routine.ps1 -Routine heartbeat
Get-Content -Tail 1 (Get-ChildItem C:\MethodDev\triage-bot\logs\heartbeat-*.json |
  Sort-Object LastWriteTime | Select-Object -Last 1)
```

### Inspect / disable a registered task

```powershell
schtasks /Query /TN "triage-bot\triage" /FO LIST /V    # next run + last result
schtasks /Change /TN "triage-bot\triage" /DISABLE       # pause without unregistering
schtasks /Run    /TN "triage-bot\triage"                # fire now (out of band)
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
