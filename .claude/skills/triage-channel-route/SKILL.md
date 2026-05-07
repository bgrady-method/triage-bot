---
name: triage-channel-route
description: "Pick the right investigation order for a triage-bot alert based on the Slack channel it came from. TRIGGER: at the start of Phase 4 (Investigation), once the alert's channel_name is known and before the first DD/ES query. Returns the prescribed tool order, time-window defaults, and posting style (DM vs in-thread reply for swat) per playbooks/channel-guidance.md."
allowedTools: [Read]
---

# triage-channel-route — per-channel investigation order

The four alert channels (`#alert-frontend-errors`, `#alert-runtime-monitoring`, `#alert-system`, `#swat`) have different upstreams and different signal-to-noise profiles. Each gets a different starting playbook.

## When to use

Inside the triage routine, at the start of Phase 4 (Investigation), once the group's `channel_name` is set. Before invoking `dd-investigate` or `es-investigate`, this skill tells you:

- Which playbook(s) to run, in which order
- What time window to use (default vs widened for `#swat`)
- Whether to skip APM (frontend) or skip ES+APM (infra subset of `#alert-system`)
- Posting style: standard self-DM vs in-thread reply (for `#swat`)
- Per-channel classification bias (e.g. `#alert-runtime-monitoring` skews false-alarm; `#alert-system` skews needs-human)

## How

Read `playbooks/channel-guidance.md` (relative to repo root). Each channel has its own section with the investigation-order numbered list and bias notes.

## Hard rules

1. **Don't pick an order that contradicts the channel's playbook.** If the playbook says "ES first" for frontend, don't start with Datadog.
2. **`#swat` is in-thread, never DM.** This is a non-negotiable rule from `prompt.md` Hard Rule #4.
3. **Time window for `#swat` is `now - 1h` minimum.** Other channels use the group's primary alert ts as the start, extended to now if < 15 min.
4. **No human prompt.** Channel routing is fully deterministic.

## Reference

Body of the per-channel rules lives in `playbooks/channel-guidance.md` — single source of truth. This skill is a thin wrapper.
