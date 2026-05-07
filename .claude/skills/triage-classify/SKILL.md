---
name: triage-classify
description: "Classify a triage-bot alert investigation into one of four buckets — `false-alarm`, `known-issue-recurrence`, `new-with-clear-fix`, `needs-human` — with a calibrated confidence score. TRIGGER: invoke after gathering investigation evidence (DD/ES/SQL queries, deploy correlation, KB lookup) and before writing the incident-log line and acting. Reads the deterministic rubric in playbooks/classification.md so the same evidence always produces the same label."
allowedTools: [Read]
---

# triage-classify — bucket assignment for a triage-bot alert

This skill is the deterministic decision step the routine runs after Phase-4 investigation and before Phase-7 action. It maps `(evidence, KB hits, confidence)` to one of four buckets per the project rubric.

## When to use

Inside the triage routine, after Phase 4 (Investigation) completes and before Phase 6 (incident-log write). The skill takes the gathered evidence and returns:

- `classification`: one of `false-alarm`, `known-issue-recurrence`, `new-with-clear-fix`, `needs-human`
- `confidence`: float 0..1
- `bug_type` (when `needs-human` or `new-with-clear-fix`): one of `data`, `env`, `code`, `unknown`
- `rationale`: 1-2 sentences explaining the bucket choice

## How

Read `playbooks/classification.md` (relative to repo root). It defines:

1. **The four buckets** — semantics + day-1 action for each.
2. **Day-1 conservative bias** — for the first 50 incident-log lines, default to `needs-human` unless confidence ≥ 0.95 OR a literal/regex KB hit. Read `kb/incident-log.jsonl` line count to evaluate.
3. **Confidence calibration table** — 0.95 / 0.85 / 0.70 thresholds and what each means.
4. **Underlying bug taxonomy** — data / env / code disambiguation rule.
5. **Worked examples** for each bucket.

## Hard rules

1. **Tie-break toward higher-friction.** Between two plausible buckets, choose the one that surfaces more evidence to Ben (`needs-human` over `new-with-clear-fix`; `known-issue-recurrence` over `false-alarm`).
2. **No human prompt.** This decision is fully deterministic from the evidence + rubric. Never ask the user.
3. **Conservative-mode override is mandatory** during the first 50 runs. Don't skip it because the evidence "looks clear" — that's the point of conservative mode.
4. **Write `confidence` to two decimal places** in the incident-log line.

## Reference

The rubric body lives in `playbooks/classification.md` — single source of truth. This skill is a thin wrapper that reminds Claude to follow it. If you're updating the rubric, edit the playbook, not this SKILL.md.
