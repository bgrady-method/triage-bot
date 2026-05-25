# Method Service Availability — since-inception report (2026-05-01 → 2026-05-25)

_Generated: 2026-05-25T17:35:00Z · Window: 2026-05-01T00:00:00Z → 2026-05-25T00:00:00Z (24 days · 34,560 minutes) · Sources: 16 PIR-derived + bot-discovered KB entries, 4 operator-confirmed swat P0s, two 2026-05-21 stability-review snapshots, 1,766 incident-log primary entries, 269 investigation reports._

> **Critical-but-fair caveat up front.** The triage-bot was credential-blocked for the first 20 of these 24 days (May 1 → May 20). For that period, our observability is engineer-confirmed PIRs and operator-posted swat threads only — bot-internal incident-log data is *partial*. Numbers below cite higher-quality sources where they exist. Where they don't, the report says so rather than inventing precision we don't have.

---

## Headline

- **Customer-perceived platform availability: ~99.34%** — equivalent to **~228 minutes of critical-path impairment** in 24 days (gateway / auth / runtime-core / tables-fields any-component-degraded, union-deduped).
- **Sign-in strict availability: ~99.89%** — ~38 minutes of users-actually-locked-out (per `stability-reviews/2026-05/2026-05-21-report-2.md` synthetic 127198928 + swat threads; pro-rated to 24d).
- **Days with engineer-confirmed incidents: 8 of 24** (May 4, 6, 14, 15, 19, 20, 23, 24).
- **Operator-confirmed P0 incidents: 4** (May 14, May 15, May 19, May 20).
- **Worst day: 2026-05-15** — overlapping MongoDB rs01 FD-exhaustion (91 min) + SQL DB-failover customize spike (79 min) → ~100 min union-deduped critical-path impairment in a single day.

---

## Methodology

These rules are explicit so the reader can adjust if they disagree:

| Pattern | Treatment | Why |
|---|---|---|
| **Discrete P0 outage** with engineer-confirmed start/end (from PIR or swat thread) | Count the window verbatim | High-confidence ground truth |
| **Chronic Ocelot-timeout** (`ki-2026-05-21-gateway-microservices-timeout`) — bot measured 1,072 warnings/h vs 1,064 baseline = +0.7% error-rate elevation over ~5 days | **(0.7% × 7,312 min) ≈ 51 equivalent user-impacting minutes**, not 7,312 | Steady-state degradation, not a binary outage. Counting full window would overstate by ~140×. |
| **DNS PPS-quota cascade** (`ki-dns-microservices-method-int-pps-quota`) May 14–20 — intermittent 15-min NXDOMAIN bursts | Count the **operator-visible** windows verbatim (May 14 swat 13min + May 20 swat ~30min visible component) + a separately-flagged **250-min "intermittent NXDOMAIN burst" estimate** | Catches both confirmed peaks and the realistic background impact without inflating to "7 days of downtime" |
| **UI-flap clusters** (legacy-MethodUI `isUsingControl` null-deref, B011R3D650X, May 13–14, 12 clusters in 31h, root-caused May 21) | Count **as 0 service-downtime**, document separately as "UX degradation" | The bug fires per Angular `$digest` cycle on a single page — degrades that user's session, doesn't take a backend service down |
| **Per-incident under 5 min** (below DD monitor evaluation window) | Count as 5 min floor | Don't claim sub-monitor-resolution accuracy |
| **Bot-only mention with no engineer/operator confirmation** | Note in service detail, **don't** add to availability tally | Tier-3 mention isn't ground truth |
| **First 20-day observability gap** (May 1–20: bot credential-blocked) | Footnote every "no incidents found" row | Honest about the data limit |

Per-service availability = `(34,560 − impaired_min) / 34,560 × 100%`. Group availability = same formula on the group's union-deduped impaired minutes (multiple services degraded in the same minute counts once). Customer-perceived = union across {ms-gateway-api, ms-authentication-api, runtime-core, ms-tables-fields-api} only.

---

## Group summary

| Group | Impaired min (union) | Availability | Worst service | Notes |
|---|---:|---:|---|---|
| **API Gateway & Auth** | ~166 + ~50 chronic + ~250 DNS-est = **~466 total** (199 discrete) | **98.65%** (99.42% if you exclude DNS-est) | ms-gateway-api | Hit by every shared-infra event in the window (DNS, RabbitMQ, Redis) |
| **No-code Platform** (runtime-core + tables-fields + search) | ~109 + ~13 = **~122** | **99.65%** | runtime-core | May 15 MongoDB / SQL overlap is the dominant contribution |
| **Sync & Integrations** | 30 + 14 = **~44** | **99.87%** | legacy-syncservice-api | All May 4 / May 6 deploy-related |
| **Legacy / Tier-3 support** | **~101** | **99.71%** | legacy-method-ui (Classic UI) | Single May 4 EDA-NuGet event |
| **Frontend (no-code & runtime UI)** | 0 backend ¹ | **~100% ¹** | n/a | All observed frontend errors trace to upstream backends; UI services themselves had no direct outage |
| **Microservices (per-domain APIs)** | 0 known ² | **~100% ²** | n/a | ms-account-api appears 5× in bot signal — all symptom-of-upstream, no own outage |
| **Email & Notifications** | 0 known ² | **~100% ²** | n/a | No alerts, no investigations, no PIRs in window |
| **— Customer-perceived (union of critical-path) —** | **~228 discrete + ~50 chronic-equiv + ~250 DNS-est** | **~99.34% (99.66% if you exclude DNS-est background)** | — | The "any one of gateway/auth/runtime-core/tables-fields impaired" headline |

¹ Frontend services themselves did not have an outage in this window. The UI-flap pattern (B011R3D650X, ~31 hours over May 13–14) was a per-`$digest` null-deref affecting a single page in legacy-MethodUI — counted under UX, not service availability.

² "No engineer-confirmed incident" — not the same as "verifiably up." See § Caveats.

---

## Per-service detail

### Group 1 — Frontend (no-code & runtime UI)

| Service | Impaired min | Availability | Source | Notes |
|---|---:|---:|---|---|
| method-platform-ui (m-one + MethodUI) | 0 backend | ~100% ¹ | none direct | All XHR errors attributed to upstream (gateway / auth); separate UX issue flagged below |
| method-signin-ui | 0 known | ~100% ¹ | none | Sign-in *flow* impairment counted under Auth group |
| method-signup-ui | 0 known | ~100% ¹ | none | One brief blip noted in PIR May 4 (account creation through legacy-syncservice — counted under Sync) |
| method-ai | 0 known | ~100% ¹ | none | — |
| method-nativemobile-ui | 0 known | ~100% ¹ | none | — |
| gmail-addon-ui | 0 known | ~100% ¹ | none | — |

**Group total (frontend backend): ~100%**.

**Separate UX degradation (not service availability):**
- Legacy-MethodUI `isUsingControl(ControlId)` TypeError — multi-account (≥20), ~100 DD log hits/7d, root-caused 2026-05-21 (`docs/investigations/2026-05-21-515f5ee521d61ac4.md`). Affects users on the action-editor versions/designer page. **No backend service was down**; floods DD RUM and trips the per-account XHR-error monitor. Recommend a null-guard fix.

### Group 2 — API Gateway & Authentication

| Service | Impaired min | Availability | Source | Notes |
|---|---:|---:|---|---|
| ms-gateway-api | 66 (DNS swat peaks) + 53 (May 20 RabbitMQ) + 40 (May 19 wave-1) + 22 (May 19 wave-2 est) + **51 chronic Ocelot-equiv** | **99.34%** (99.49% excluding chronic-equiv) | PIR + swat + chronic (`ki-2026-05-21-...`) | Highest-impacted backend in the window. Hit by every shared-infra incident. |
| ms-authentication-api | 40 (May 19 wave-1) + 22 (May 19 wave-2 est) + 53 (May 20) = **115** | **99.67%** | swat + stability-review | Includes Redis JWT-cascade cascade (May 19) and RabbitMQ cascade (May 20). |
| oauth2 | 0 known | ~100% ¹ | none | No direct incident; would have ridden the May 19 Redis cascade if active |
| ms-identity-api | 0 known | ~100% ¹ | none | No CLAUDE.md, no bot data |
| legacy-authentication-api | 0 known | ~100% ¹ | none | Shares legacy IIS pool; would have been affected by any legacy-pool recycle |

**Group total (union-deduped, excluding 250-min DNS-est background): ~199 min → 99.42%**. Adding the DNS-est estimate: ~466 min → 98.65%.

### Group 3 — No-code Platform

| Service | Impaired min | Availability | Source | Notes |
|---|---:|---:|---|---|
| runtime-core (composite: Runtime.Core.Api + Designer.Core.Api + Apps.Api + Runtime.Core.Subscriber + AppUpdate.Agent + AI.Core.Api + EDA.Orchestrator.Api + Method.Search) | 79 (May 15 SQL failover, customize) + 30 (May 19 whitescreens partial) = **109** unavailability-equiv | **99.68%** | swat + stability-review + PIR | Latency-only event May 23–24 (RTC p95 spike, 945 min sampled window) is **not counted as downtime** — flagged as latency degradation below. |
| ms-tables-fields-api | 13 (May 14 swat) + 79 (May 15 SQL failover, shared) = **92** | **99.73%** | swat + PIR | May 15 SQL failover impacts both runtime-core and tables-fields; union-deduped at group level. |
| ms-search-api | 0 known | ~100% ¹ | none | Catalog ambiguity with runtime-core's Method.Search — no separate bot signal |

**Group total (union-deduped): ~122 min → 99.65%**.

**Separate latency degradation (not counted as downtime):**
- runtime-core-api p95 spike May 23 17:54Z–May 24 11:53Z — avg 0.701s, max 2.310s over a 945-minute sampled window per `ki-2026-05-24-runtime-core-rtc-p95-recurring`. No errors, just elevated latency. The 2026-05-21 stability-review proposed a 99.95%-under-1.0s SLO; if applied, this would burn ~600% of a 24d budget. Flagged for SLO definition; not subtracted from availability.

### Group 4 — Sync & Integrations

| Service | Impaired min | Availability | Source | Notes |
|---|---:|---:|---|---|
| legacy-syncservice-api | **30** (May 4 wrong-version deploy: QBDT sync + Account creation + AVD broken) | **99.91%** | PIR `ki-legacy-syncservice-wrong-version-deployed` | Fixed by redeploying the correct build |
| ms-google-calendarsync-api | **14** (May 6 .NET Framework version-mismatch deploy) | **99.96%** | PIR `ki-calendar-sync-net-framework-version-mismatch` | Resolved via rollback |
| qbo-sync-api | 0 known ² | ~100% ¹ | none | One pre-window incident (Apr 30 Datadog/MassTransit blockage) mitigated before May 1 |
| qbo-webhooks-api | 0 known | ~100% ¹ | none | — |
| xero-sync | 0 known | ~100% ¹ | none | — |
| ms-synclog-api | 0 known | ~100% ¹ | none | Shares microservices pool — would ride pool recycles if any |
| ms-sync-util | 0 known | ~100% ¹ | none | Library, not a service per se |

**Group total: ~44 min → 99.87%**.

### Group 5 — Email & Notifications

| Service | Impaired min | Availability | Source | Notes |
|---|---:|---:|---|---|
| legacy-email-agent | 0 known | ~100% ¹ | none | No alerts, no investigations, no PIRs |
| ms-reminder-agent | 0 known | ~100% ¹ | none | — |
| method-notifications-api | 0 known | ~100% ¹ | none | — |
| ~~ms-email-api~~ | n/a | excluded | — | Tagged `(inactive)` in `02-services.md` — not in current production fleet |

**Group total: ~100% (caveat — no signal at all, not necessarily proof of zero incidents)**.

### Group 6 — Core Microservices (per-domain APIs)

| Service | Impaired min | Availability | Source | Notes |
|---|---:|---:|---|---|
| ms-account-api | 0 own ² | ~100% ¹ | bot signal × 5 (all symptom-of-upstream) | Redis JWT cache + microservices.method.int DNS — already counted in Auth/Gateway groups |
| ms-tags-api | 0 known | ~100% ¹ | none | — |
| ms-preferences-api | 0 own | ~100% ¹ | bot signal × 1 (symptom-of-upstream) | `/preferences/v3/User` is one of the paths the chronic Ocelot timeout pattern hits |
| ms-documents-api | 0 known | ~100% ¹ | none | — |
| ms-support-api | 0 known | ~100% ¹ | none | — |
| ms-scheduler-api | 0 known | ~100% ¹ | none | — |
| ms-analytics-api | 0 known | ~100% ¹ | none | Tier-3, shares microservices pool |
| ms-health-api | 0 known | ~100% ¹ | none | — |

**Group total: ~100% (same caveat)**.

### Group 7 — Legacy / Tier-3 support

| Service | Impaired min | Availability | Source | Notes |
|---|---:|---:|---|---|
| legacy-method-ui (Classic UI) | **101** (May 4 EDA-NuGet thread starvation) | **99.71%** | PIR `ki-classic-ui-eda-nuget-thread-starvation` | App pool crashes 8:01–8:06 + 9:39–9:42 + intermittent slowness. Mitigated by reducing EDA load + redeploying prior stable code |
| ms-archive-api | 0 known | ~100% ¹ | none | — |
| ms-gmail-addon-api | 0 known | ~100% ¹ | none | — |
| ms-mailchimp-api | 0 known | ~100% ¹ | none | — |
| ms-mailchimp-agent | 0 known | ~100% ¹ | none | — |
| legacy-miurl-api | 0 known | ~100% ¹ | none | — |
| legacy-billingsubscription-api | 0 known | ~100% ¹ | none | — |
| legacy-bre-api | 0 known | ~100% ¹ | none | — |
| legacy-custom-api | 0 known | ~100% ¹ | none | — |
| legacy-internal-api | 0 known | ~100% ¹ | none | — |
| legacy-importexport-ui | 0 known | ~100% ¹ | none | — |
| legacy-openid-api | 0 known | ~100% ¹ | none | — |
| legacy-pixeltracker-api | 0 known | ~100% ¹ | none | — |
| legacy-public-api | 0 known | ~100% ¹ | none | — |
| legacy-qbdtpush-agent | 0 known | ~100% ¹ | none | — |

**Group total: ~101 min → 99.71%**. All driven by the single May 4 Classic UI event; the other 14 legacy services have no signal.

¹ "~100%" means no engineer-confirmed or operator-confirmed incident found in the window. **It does NOT mean verifiably up** — see § Caveats below; the bot was credential-blocked for 20 of these 24 days, so it could not detect many classes of issue independently. For Tier-3 / legacy services with no bot signal at all, lack of evidence is not evidence of zero impact.

² Service appears in bot signal as a *symptom* of upstream incidents (e.g., Redis cascade, microservices.method.int DNS). Already counted upstream; not double-counted here.

---

## Incident chronicle (every event counted toward the totals)

In chronological order. Each cites the canonical source. Items marked **C** are chronic/partial-degradation; the others are point-in-time.

| Date | Service(s) impacted | Duration | Source | Reference |
|---|---|---:|---|---|
| 2026-05-04 ~8:01–8:06, ~9:39–9:42 + intermittent | legacy-method-ui (Classic UI app pools) | 101 min | PIR | `kb/known-issues.json` → `ki-classic-ui-eda-nuget-thread-starvation` |
| 2026-05-04 8:50–9:20 | legacy-syncservice-api (QBDT sync + Account creation + AVD) | 30 min | PIR | `ki-legacy-syncservice-wrong-version-deployed` |
| 2026-05-06 8:54–9:08 | ms-google-calendarsync-api | 14 min | PIR | `ki-calendar-sync-net-framework-version-mismatch` |
| 2026-05-14 ~13:00–13:13 UTC | ms-tables-fields-api + sign-in flap (auth) | 13 min | swat P0 `c5773f0cfb4566e3` + Jira PL-62828 | `docs/investigations/2026-05-14-c5773f0cfb4566e3.md` (closed as Working-as-Designed) |
| **2026-05-14 → 2026-05-20 (intermittent)** | ms-gateway-api + ms-authentication-api + microservices nodes (DNS PPS quota cascade) | **C: 250-min estimate** for non-swat-visible NXDOMAIN bursts | PIR `ki-dns-microservices-method-int-pps-quota` | 6.5-day span, 15-min negative-cache windows. **Estimate** — actual measured impact unknown. |
| 2026-05-15 13:38–15:09 UTC | MongoDB rs01 (FD exhaustion); customers experienced via runtime-core + tables-fields | 91 min | PIR | `ki-mongodb-rs01-fd-exhaustion` |
| 2026-05-15 14:19–15:38 UTC | runtime-core + ms-tables-fields-api (SQL DB failover, customize/copy screens) | 79 min | swat + stability-review | `docs/investigations/2026-05-15-75bc8582062724ab.md`. **Overlaps with MongoDB above — union-deduped to ~100 min at the day level** |
| 2026-05-19 14:17–14:57 UTC | ms-authentication-api + ms-gateway-api (Redis JWT-cascade, wave 1) | 40 min | swat P0 + stability-review | `docs/investigations/2026-05-19-b6c6fd3c9ffc6cc6.md` |
| 2026-05-19 ~18:24–~18:46 UTC | ms-authentication-api + ms-gateway-api (Redis cascade, wave 2) | ~22 min est | stability-review + investigation `2026-05-19-ff7e5a9ad6a9d27e.md` | Synthetic 127198928 was too loose (>20s) to catch this; estimate from operator-visible window |
| 2026-05-20 20:14–21:08 UTC | ms-gateway-api + ms-authentication-api (RabbitMQ blip + sign-in 3-min visible dip) | 53 min | swat P0 + status-page 5698a2c8 | `docs/investigations/2026-05-20-05594031eb0b5a56.md` |
| **2026-05-20 → 2026-05-25 (chronic)** | ms-gateway-api (Ocelot timeouts to microservices.methodlocal.int) | **C: 51 equivalent user-impacting minutes** (0.7% × 7,312 min) | bot-discovered | `ki-2026-05-21-gateway-microservices-timeout` — 25 occurrences over 5 days, but error-rate elevation is 0.7%, not 100% |
| **2026-05-23 17:54 – 2026-05-24 11:53** | runtime-core p95 latency spikes (not downtime) | **0 downtime equiv** | bot-discovered | `ki-2026-05-24-runtime-core-rtc-p95-recurring` — flagged for SLO definition, not counted as availability impact |

Total discrete: **228 critical-path min + 30 sync + 14 sync + 101 legacy = 373 attributable minutes**. Plus chronic-equiv ~51 (gateway) and estimate ~250 (DNS).

---

## Comparison to proposed SLOs

The 2026-05-21 stability-review proposed availability SLOs for the most-impacted surfaces. Where we stand:

| Surface | Observed | Proposed SLO | 24d budget | Burn |
|---|---:|---:|---:|---:|
| Sign-in path | ~99.89% (38 min impaired) | 99.95% | 17.3 min | **220%** |
| Customize / copy screens (runtime-core + tables-fields) | ~99.65% (122 min) | 99.9% | 34.6 min | **352%** |
| ms-gateway-api | ~99.49% (170 min discrete) → 99.34% with chronic-equiv | 99.95% | 17.3 min | **983%** discrete (1,295% with chronic) |
| Customer-perceived platform | ~99.34% (228 min critical-path discrete) | not yet defined | n/a | n/a |

All three flagged surfaces are over budget for the 24-day window. Two of three are over budget by >3×.

---

## Caveats & blind spots

These limit how confident you should be in the numbers above. Listed in rough order of importance.

1. **20-day observability gap (May 1–20).** The triage-bot was DD/ES/SQL/Mongo-blocked for 63 consecutive cycles (see `stability-reviews/2026-05/2026-05-21-report.md` finding F1). For that window, our only reliable sources are PIRs and swat threads — both human-driven. **There may be incidents in those 20 days that no human posted a PIR or swat thread for; the bot couldn't have detected them either.** The "0 known" entries for most services should be read as "no evidence of an incident," not "the service was up."

2. **Chronic-pattern conversion factors are estimates, not measurements.**
   - Ocelot timeout 0.7% × window math is a back-of-the-envelope conversion from a single bot-recorded data point (1,072 vs 1,064 warnings/h on 2026-05-21). If the true error-rate elevation is 7% rather than 0.7%, the gateway-timeout impact would be 510 minutes, not 51.
   - DNS 250-min "intermittent NXDOMAIN burst" estimate has no measured backing — it's an order-of-magnitude guess between the operator-visible peaks (~30 min) and the chronic-window upper bound (7×24×60 = 10,080 min). Verifying would need DD `linklocal_allowance_exceeded` queries over the May 14–20 span, which were blocked until May 21.

3. **Synthetic SLO instrumentation is too loose.** The 2026-05-21 stability-review flagged that sign-in synthetic 127198928's `> 20000ms` step duration is too coarse to detect sub-3-minute outages — e.g., the May 19 wave-2 estimate (22 min) is partly because the synthetic missed it; we're inferring from operator reports. A tighter synthetic would either confirm 22 min or expose more.

4. **Services with no signal aren't proven up.** All 14 legacy/Tier-3 services in Group 7 plus most of Group 5/6 show "0 known impaired minutes." For services that share IIS pools (microservices, legacy), an unobserved pool recycle could have impacted everything in the pool without producing a single dedicated alert. This is consistent with what `CLAUDE.md` says about pool blast radius.

5. **The May 14 Tables-Fields swat (PL-62828) was closed as "Working as Designed."** I counted it as 13 min of impairment anyway because users *experienced* it. The classification is a separate question from whether the customer felt impact.

6. **Day-level deduplication isn't full overlap math.** May 15's MongoDB rs01 (13:38–15:09) and SQL DB-failover spike (14:19–15:38) overlap from 14:19–15:09 (~50 min). I dedupe at the day level (claiming ~100 min for the day rather than 91+79=170), but the underlying time-series is more nuanced. A minute-by-minute reconstruction would be slightly more accurate.

7. **The `isUsingControl` UX bug is in this report as zero downtime.** That's the right call (it's a per-`$digest`-tick JS error, not a backend outage). But for users in the affected workflow, it does feel broken. If you want to measure "user-experience minutes degraded" separately, the bot has DD evidence to compute it — that's a future-report scope.

8. **The bot's own `kb/known-issues.json` has 5 entries dated pre-window** (2023-11 to 2026-04-28). Those are historical references; I did not roll them into 24-day window math.

---

## Recommendations (3-5 ticket candidates derived from this report)

1. **Define SLOs for the four critical-path surfaces with measured baselines.** Sign-in / runtime-core / ms-gateway-api / tables-fields are all over the proposed 99.9–99.95% budget for this 24-day window. Either tighten remediation or formalize a more permissive SLO; "no SLO" is not a stable state.

2. **Tighten the sign-in synthetic to detect sub-3-minute outages.** Current `> 20000ms` step duration missed the May 19 wave-2 short outage. Replace with `< 3000ms` step duration + a 1-min check cadence so future short outages produce hard-attributed minutes rather than estimates.

3. **Resolve the chronic `ki-2026-05-21-gateway-microservices-timeout`** (`fix_status: needs-ops-decision`, 25 occurrences, dominant alert noise). Three concrete paths exist (raise Ocelot timeout per route / scale microservices IIS pool / profile slow upstream); a ticket forces the choice. **This single fix would likely move ms-gateway-api availability ~0.15% upward.**

4. **Close out the DNS PPS-quota PIR action items** (`ki-dns-microservices-method-int-pps-quota`, `fix_status: in-progress`). Specifically: confirm the Route 53 inbound endpoint migration stuck on all Windows DCs, lower Windows `MaxNegativeTtl` from 15 min → 30 s, enable DD throttling-metric collection. Without these, a repeat of May 14–20 is structurally still possible.

5. **Add observability for IIS pool blast radius.** Group 7 / Group 6 has 22 services with "no signal" entries — many of which share IIS pools where a single recycle would silently degrade ≥6 services. Add per-pool health monitors so the bot can attribute pool-recycle impact correctly.

---

## Sources cited (all on `main`, all reproducible)

- `kb/known-issues.json` (16 entries; engineer-confirmed PIRs + bot-discovered)
- `kb/incident-log.jsonl` (1,766 entries in window: 1,114 grouped / 362 needs-human / 228 poll-cycle / 25 known-issue-recurrence / 18 deduplicated / 16 heartbeat / 3 stability-review)
- `stability-reviews/2026-05/2026-05-21-report.md` (initial run, pre-DD-restoration)
- `stability-reviews/2026-05/2026-05-21-report-2.md` (post-DD-restoration follow-up; availability snapshot used as ground truth)
- `docs/investigations/2026-05-*.md` (269 reports across the window)
- `docs/messages/2026-05-{19,20}/swat.jsonl` (4 operator-posted swat events)
- `references/architecture/platform-overview.md` and `CLAUDE.md` (service catalog)
- PIR Confluence post `133496969` (the engineer-authored source for all `fix_status` entries)
