---
name: grafana-alerting
description: >
  Create, preview, and provision Method's curated SLO alert rules in Grafana as code.
  Use when adding/editing/retiring an SLO alert, wiring the #triage-bot-health contact point,
  probing InfluxDB/ES/Prometheus datasource schemas, or applying alerting/grafana/*.json to the
  live Grafana instance. This is the ONLY sanctioned write path to a monitoring platform in this repo.
---

# Grafana alerting-as-code

This skill turns [`kb/slo-catalog.json`](../../../kb/slo-catalog.json) (the source of truth) into Grafana
unified-alerting rules and provisions them. Full design + runbooks:
[`references/architecture/alerting-system-design.md`](../../../references/architecture/alerting-system-design.md).

**This is a separate track from the triage-bot's `escalation_score` / classification machinery.** The bot builds
the KB and investigates; this applies those learnings to a small set of genuinely good alerts.

## Hard rules (do not break)
- **No `@`-mentions.** Owning teams appear as **inert text** in alert annotations (`owner: <Team>`), never as a
  Slack `@user`/`@usergroup`. Matches `prompt.md` Hard Rule #13.
- **One sink for now: `#triage-bot-health`.** Do not route to per-team channels or the `XMatters` contact point
  until the user explicitly authorizes it (the XMatters contact point already exists in Grafana; leave it alone).
- **Grafana-only writes.** `grafana_provision.py` is the only write tool in this repo. It reads InfluxDB/ES/
  Prometheus *through* Grafana datasources — it never mutates Datadog/ES, so `prompt.md` Hard Rule #3 is untouched.
- **Never commit secrets.** Webhook URLs, tokens, passwords stay in `.env` / process env. The repo holds only
  datasource **uids** and webhook **ids**.
- **Don't collide with the 40 existing rules.** Our rules live in the `SLO` Grafana folder.

## Environment
- `GRAFANA_URL` — may be a login page (`…/grafana/login`); the tool strips `/login` and auto-detects the API mount
  (root `/api` on `grafana.method.me`, or `/grafana/api` on `logstash3.method.me`).
- `GRAFANA_TOKEN` — service-account token (preferred). Else `GRAFANA_USERNAME` + `GRAFANA_PASSWORD` (SSO login;
  brittle — cookie scoped to `/grafana`, tied to one user).
- `TRIAGE_BOT_HEALTH_WEBHOOK` — Slack webhook for the contact point (only needed for `contact-point-ensure --commit`).

## Workflow
1. **Probe** (read-only) to resolve `needs_probe`/`🔎` field names in the catalog:
   `python scripts/grafana_provision.py probe`
   (runs `SHOW MEASUREMENTS` on `rtcapi_metrics`/`eda_metrics`/`syncservice_metrics`, etc.). Update
   `kb/slo-catalog.json` query field names to match reality.
2. **Edit the catalog** — add/modify an SLO, its datasource, query, target, ladder tiers, owner, runbook anchor.
3. **Generate** — `python scripts/gen_grafana_alerts.py` (deterministic; rerun with `--check` in CI to detect drift).
4. **Dry-run** — `python scripts/grafana_provision.py apply` (dry-run is the DEFAULT; shows create/update + any
   unresolved datasource names). Resolve datasource NAMES→uids and folder→folderUID happen here.
5. **PR** — commit `kb/slo-catalog.json` + `alerting/grafana/*.json` and open a PR. The set is reviewed like code.
6. **Apply** — on approval: `python scripts/grafana_provision.py apply --commit`.
7. **Contact point + verify** — `contact-point-ensure --commit` (with `TRIAGE_BOT_HEALTH_WEBHOOK`), then
   `test-fire --rule <uid> --commit` to confirm `#triage-bot-health` delivery with owner as inert text.

## Burn-rate model (in `meta.burn_ladder`)
Multi-window multi-burn: a tier fires only when BOTH its long and short window breach `burn × (1−SLO_target)`.
Only fast-burn (14.4× / 6×) is P1; 3× / 1× are P2 tickets. The generator builds, per ES SLO: single-bucket count
queries → `reduce(last)` → `math` burn ratio → `threshold(>0)` condition. Latency SLOs: InfluxQL/PromQL p95 →
`reduce(max)` → `threshold(ms)`.

## Verifying it's safe
- `gen_grafana_alerts.py --check` → no drift.
- `apply` (no `--commit`) writes nothing and lists exactly what would change.
- `grep -rE "<@|<!subteam|@channel|@here" alerting/ references/architecture/alerting-system-design.md` → empty.
- `grep -rE "hooks.slack.com|xmatters.com|GRAFANA_PASSWORD|grafana_session" kb/ references/ alerting/` → empty.
