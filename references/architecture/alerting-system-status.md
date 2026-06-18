# Alerting system (SLI/SLO/SLA) — progress & handoff

**Last updated:** 2026-06-18 · **Branch:** `alerting-system-grafana` · **PR:** [#5](https://github.com/bgrady-method/triage-bot/pull/5)

This is the pick-up-later doc for the curated SLO alerting work. Design + runbooks live in
[`alerting-system-design.md`](alerting-system-design.md); the source of truth for rules is
[`kb/slo-catalog.json`](../../kb/slo-catalog.json).

> **One-line state (LIVE 2026-06-18, round 2):** **9 alert rules + 2 dashboards** in `Triage Bot / SLO`
> (+ `Triage Bot / SLA` placeholder). All 9 verified **state=inactive / health=ok** (queries evaluate, none
> firing). Every rule routes **directly** to `triage-bot-health` via per-rule `notification_settings` — the
> shared notification policy is **untouched** (hash identical across both rounds). 2 of 6 deferred remain
> (gateway), pending Datadog.

## Live now (deployed) — 9 rules
- **Round 1 (InfluxDB):** `slo-4-errors-fast` (P1), `slo-4-errors-slow` (P2), `slo-4-latency` (P2),
  `slo-5-latency` (P2), `slo-7-errors-slow` (P2).
- **Round 2:**
  - `slo-1-auth-errors` (P2) — **ES** (`Elasticsearch` ds, `_index:method-microservices-authentication-* AND
    level:Error`, ≥5/30m). **Light:** single query, own rule group at **5-min eval** (ES perf guardrail).
  - `slo-8-subscriber-down` (**P1**) — `rabbitmq_queue` `consumers==0` on the live event-consumer queues
    (subscriber down → event processing/cache-invalidation halts).
  - `slo-8-consumer-lag` (P2) — `messages_ready > 1000` on those queues.
  - `f2-dead-lettering` (P2) — `non_negative_difference(messages_ready) > 50/5m` on `*_error` queues (spike, not
    the static backlogs; `publish_rate` is dead so depth-delta is the signal).
- **Dashboards:** `Triage Bot — SLO Overview` (now incl. consumer + DLQ panels), `Triage Bot — SLA (reporting only)`.
- Two P1 rules total (`slo-4-errors-fast`, `slo-8-subscriber-down`) — pager stays quiet.

## Still deferred (no rules emitted — no silent never-fire alerts)
- **SLO-6 designer** → `deferred-no-recent-data`: `viewdesigner_request`/`view_request` have **no data for ~30
  days** (last point 2026-05-19); the designer metric pipeline is dormant. Revive when it resumes.
- **SLO-2 gateway availability / SLO-3 gateway latency** → `deferred-no-datasource`: gateway logs are
  Warning-only (ki-21 noise), no status/duration; no gateway metric. **Datadog HAS the data**
  (`trace.aspnet_core.request.duration{service:ms-gateway-api}`), but Grafana has no Datadog plugin
  (install=server-admin). Path: install the Grafana Enterprise Datadog plugin → build like the rest, OR native
  DD monitors → DD Slack integration to `#triage-bot-health`. (Gateway-down impact already shows via SLO-4/5/7.)

---

> **(historical) Prior one-line state:** design + tooling built; token provisioned; probes done; nothing live —
> superseded by the deployment above.

---

## 1. Goal & guardrails (unchanged)
- A small, curated, **symptom-level SLO** alert set where every page is urgent/important/actionable/real.
- **Separate track** from the triage-bot's `escalation_score`/classification machinery — this *applies* the
  KB's learnings; it does not modify the bot.
- **No `@`-mentions** ever (owning team = inert text). **All notifications → `#triage-bot-health`** for now.
- **Secrets never committed** — repo holds datasource uids + webhook ids only. Tokens/passwords/webhook URLs
  live in `.env`.
- `prompt.md` **Hard Rule #3** (no mutating Datadog/ES) stands — the new write tool talks **only to Grafana**.

## 2. What's DONE
- **Design doc** — `references/architecture/alerting-system-design.md` (7 deliverables + per-SLO runbooks
  `#rb-slo-1 … #rb-f2`).
- **Catalog** — `kb/slo-catalog.json` (8 SLOs + F2, burn ladder, ownership map + 5 gaps). ⚠ queries still use
  *placeholder* schemas — see §5.
- **Generator** — `scripts/gen_grafana_alerts.py` → `alerting/grafana/*.json` (deterministic; `--check` guards
  drift). Currently emits 17 rules.
- **Provisioner** — `scripts/grafana_provision.py` — the **only sanctioned write tool**, Grafana-only,
  token-or-session auth, API-mount auto-detect, **`apply` is dry-run by default** (`--commit` to write).
- **Skill** — `.claude/skills/grafana-alerting/SKILL.md` (force-added; `.claude/` is gitignored).
- **`prompt.md`** — documents the new write tool + Grafana env vars.
- **Grafana service account** — created live: name `triage-bot-alerting`, **id 98**, role **Editor** (your
  `b.grady` Editor role *was* allowed to create it). Its token is in `.env` as **`GRAFANA_TOKEN`** (local only,
  not committed). Use the token, not the SSO password.
- **Live probes** — datasource enumeration + InfluxDB measurement/field/tag probes done (results in §4/§5).

## 3. Verified Grafana environment (so you don't re-discover it)
- **Grafana Enterprise 12.0.1.** Hosts: `grafana.method.me` (API at **root `/api`**) and
  `logstash3.method.me/grafana` (API at **`/grafana/api`**). `GRAFANA_URL` in `.env` is the login page form;
  the provisioner strips `/login` and auto-detects the mount. Session cookie is scoped to `/grafana`.
- **Auth:** `GRAFANA_TOKEN` (preferred) or `GRAFANA_USERNAME`/`GRAFANA_PASSWORD`.
- **Already in production:** ~40 alert rules + 13 contact points. Our rules go in a dedicated **`SLO` folder**
  to avoid collisions.
- **All Slack contact points use incoming-webhook `url`** (not a shared bot token). So we need a per-channel
  webhook for `#triage-bot-health`. An **`XMatters`** contact point already exists (eventual P1 paging — do not
  use until authorized).

## 4. Datasources (verified)
InfluxDB is the metrics backbone (default); Elasticsearch for logs; Prometheus only self-monitors.

| Datasource | uid | Use |
|---|---|---|
| `rtcapi_metrics` | 000000006 | RTC API timing + response codes (SLO-4 screen, SLO-5 action) |
| `approutine_action_metrics` | eeyjtm8tjrshsf | AppRoutine action timing (SLO-5) |
| `syncservice_metrics` | lhFTdmfVk | Sync request timing + error flags (SLO-7) |
| `applogs-es` | T61mv5NMz | App/Serilog logs (SLO-1 auth, SLO-2 gateway, SLO-6 designer) |
| `eda_metrics` | 8CiInx3Sz | **Business** events only — NOT broker telemetry |
| `Prometheus` | nckBUNsnk | Prometheus self-metrics only — no app/gateway/RabbitMQ metrics |

## 5. Probe results → query corrections needed (the key handoff detail)
The catalog's current queries use placeholder measurement/field names that **do not match reality**. Real
schemas (from `SHOW MEASUREMENTS/FIELD KEYS/TAG VALUES`):

| Catalog placeholder | Reality | Action |
|---|---|---|
| `rtc_request.duration_ms` | measurement **`rtcapi_request`**; fields `count,lower,mean,stddev,sum,upper`; tags incl. `response_code` (200…500), `endpoint`, `metric_type=timing` | **No stored p95.** Use `mean`/`upper` for latency; error-ratio from `response_code=~/^5/`. |
| `action_execution.duration_ms` | measurement **`approutine_actions`**; same timing fields; tags incl. `actiontype`,`account` (no `response_code`) | Latency from `mean`/`upper`. Errors would need ES (no code tag here). |
| `sync_queue.oldest_unprocessed_age_s` | measurement **`syncservice_request`**; timing fields; tags **`haserror`(true/false)**, **`statuscode`(200/500)** | **No backlog-age field.** Reframe SLO-7 as a sync **error-rate** (`haserror='true'`). |
| `eda_metrics` subscriber_heartbeat / consumer_lag / `dlq.depth` | measurement **`eda_event`**, field `value`; tags are business (`event_name`=AccountCreated/RecordUpdated/…) | **Not broker telemetry — cannot build SLO-8/F2 here.** |

### Feasibility matrix (post-probe)
| SLO | Status | Notes |
|---|---|---|
| SLO-4 screen load | **buildable** | rtcapi_request: error-ratio (response_code) + latency (mean/upper, p95 approx) |
| SLO-5 action exec | **buildable** | approutine_actions latency (mean/upper); errors need ES |
| SLO-7 QBO sync | **buildable (reframed)** | syncservice_request error-rate via `haserror`/`statuscode`, not backlog |
| SLO-1 sign-in, SLO-2 gateway, SLO-6 designer | **needs ES field confirmation** | depend on `applogs-es`; index pattern + status/service/level field names not yet pinned (mapping is large/multi-index) |
| **SLO-3 gateway latency** | **DEFERRED — no datasource** | no gateway metric in InfluxDB; Prometheus self-only |
| **SLO-8 subscriber/lag, F2 DLQ** | **DEFERRED — no datasource** | `eda_event` is business events; no RabbitMQ telemetry reachable |

## 6. Outstanding work (in order)
1. **[needs user] `#triage-bot-health` webhook** → add `TRIAGE_BOT_HEALTH_WEBHOOK=https://hooks.slack.com/services/…`
   to `.env`. Source: the dedicated **`triage-bot` Slack app** — install `slack-receiver/manifest.json`, then
   Incoming Webhooks → Add to #triage-bot-health (see `slack-receiver/README.md`). The same app's bot token
   (`SLACK_BOT_TOKEN`) is also the triage bot's send identity via `scripts/slack_send.py`.
2. **Rewrite catalog queries** to the §5 schemas; mark SLO-3/8/F2 `build_status: "deferred-no-datasource"`.
3. **Confirm `applogs-es`** index pattern + field names (`grafana_provision.py probe` extended, or `es_search.py
   mapping --index <pattern>`) to finalize SLO-1/2/6.
4. `python scripts/gen_grafana_alerts.py` → regenerate.
5. `python scripts/grafana_provision.py apply` (**dry-run**) → review the create/update diff.
6. `contact-point-ensure --commit` (with the webhook) → `notification-policy-ensure --commit` → **then**
   `apply --commit`. Order matters: without the contact point + routing first, firing rules hit Grafana's
   **default** contact point (unwanted). 
7. `test-fire --rule <uid> --commit` → confirm a message lands in `#triage-bot-health` (owner = inert text).
8. **[decision] deferred SLOs:** to get SLO-3/8/F2 we must *emit* the metrics — a RabbitMQ Prometheus exporter
   (consumer lag, DLQ depth, Subscriber heartbeat) and a gateway request-duration metric. Decide: write a
   "metrics to add" recommendation, or drop these 3 for now.

## 7. Pick-up-later quickstart
```bash
cd /c/MethodDev/triage-bot
git checkout alerting-system-grafana
set -a; . ./.env; set +a                       # needs GRAFANA_URL + GRAFANA_TOKEN (already set)
python scripts/grafana_provision.py health      # confirm reachable (Grafana has had outages)
python scripts/grafana_provision.py probe        # re-resolve schemas if needed
# ...edit kb/slo-catalog.json per §5, then:
python scripts/gen_grafana_alerts.py
python scripts/grafana_provision.py apply         # dry-run; add --commit when ready (after contact point)
```
Env vars: `GRAFANA_URL`, `GRAFANA_TOKEN` (✅ set), `TRIAGE_BOT_HEALTH_WEBHOOK` (⬜ needed for delivery).

## 8. Open questions for the user
- Provide the `#triage-bot-health` webhook (or confirm reuse of an existing Slack app).
- Deferred SLO-3/8/F2: invest in emitting the missing metrics, or drop for now?
- SLO-4/5 latency: accept `mean`/`upper` as the p95 stand-in, or source true p95 elsewhere (e.g. Datadog)?
- Confirm runtime-core cross-team ownership (gap #1) and the DevOps-has-no-webhook gap (gap #2).
