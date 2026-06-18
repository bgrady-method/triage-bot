# KB → OpenSRE integration — design & conversion plan

> **Status:** proposed (design doc only — no integration code is built yet).
> **Owner:** triage-bot maintainers.
> **Scope decision:** one-way feed of the triage-bot knowledge base into a self-hosted
> [OpenSRE](https://opensre.in/) instance, KB remaining the source of truth.

## 1. Summary & honest framing

This document plans an **additive, one-way integration** that feeds the triage-bot
knowledge base (`kb/*`) into an [OpenSRE](https://github.com/swapnildahiphale/OpenSRE)
instance. The flat-file KB **remains the source of truth**; every existing consumer
(`scripts/match_kb.py`, `prompt.md`, the routines) keeps working unchanged. The
integration is a **standalone** component that can fail without affecting triage.

**Read this before anything else — OpenSRE reality check.** Research of the public
project (v1.0.0, April 2026, **public alpha**) found:

- **No supported KB-import API.** No inbound webhooks (PagerDuty/Datadog/etc.), no
  documented Neo4j bulk loader, no episodic-memory import endpoint.
- **The knowledge graph is Kubernetes-centric** (`KubernetesCluster`, `KubernetesPod`,
  `KubernetesDeployment`, … node labels; `DEPENDS_ON`/`ROUTES_TO` edges). Method runs
  IIS/.NET on EC2 — **not** Kubernetes — so OpenSRE's native topology model does not fit
  our services.
- **The only supported ingress is `POST /investigate`** — a real-time, one-alert-at-a-time
  trigger that runs the LLM agent (SSE-streamed, ~900 s timeout each) and *generates* an
  investigation. Completed investigations are stored as **episodic memory** (PostgreSQL).
- Team/ownership config lives in an internal `config_service` (PostgreSQL) with no public
  import schema.

**Chosen mechanism (accepted trade-off):** seed OpenSRE's **episodic memory** by
**replaying historical incidents through `POST /investigate`**. Consequences, stated
plainly:

- We seed **episodic memory**, *not* the Neo4j topology graph. Ownership/SLO/config data
  therefore becomes **prompt context** on each replay, **not** graph nodes. "Feed all six
  `kb/` files into the graph" is only partially achievable — documented as a limitation,
  not a defect.
- Replay is **best-effort against an alpha API** and incurs **real LLM cost + wall-clock**
  (one agent run per incident). The design rate-limits, defaults to dry-run, and makes the
  large `incident-log.jsonl` backfill opt-in.

If OpenSRE later ships a real bulk-import / graph-loader API, the transport adapter
(§2) is the only piece that changes.

## 2. Target architecture

**A standalone `opensre/` Python package + a `scripts/opensre_replay.py` CLI shim + a new
`routines/opensre-sync.yaml` routine.** It is **not** inlined into the triage cycle —
failure isolation is the top requirement, and this mirrors how `heartbeat` and
`stability-review` are already separate routines rather than steps inside `triage.yaml`.

- The package reads `kb/*` **read-only** and POSTs to OpenSRE over the network. It
  **never writes back to any `kb/` file**, so it cannot corrupt the source of truth.
- Proposed layout:

  ```
  opensre/
    __init__.py
    config.py        # reads kb/config.json "opensre" block + os.environ
    io.py            # the ONLY KB reader; always encoding="utf-8"
    mappers/
      known_issues.py
      false_alarms.py
      incident_log.py
      ownership.py     # slo-catalog.owner + config.critical_path_services (+ ownership.md later)
      slos.py
      accounts.py
    transport/
      base.py          # Adapter ABC: investigate(payload), health()
      rest.py          # POST /investigate over SSE (urllib) — live
      dryrun.py        # writes payloads to logs/opensre/, networks nothing — DEFAULT
    replay.py          # orchestrator: load → map → build payload → adapter → record state
    state.py           # logs/opensre/replay-state.json (per-key content hashes)
  scripts/opensre_replay.py   # thin CLI: python scripts/opensre_replay.py [--dry-run] [--backfill|--incremental] [--only known-issues]
  ```

**Reuse these existing canonical patterns** (do not reinvent):

| Pattern source | What to copy |
|---|---|
| `scripts/tool_health.py` | Pluggable checks; never-crash try/except → `_ok`/`_fail`/`_skipped` result dicts; `--check`; exit codes 0/1/2. Also: **add a `check_opensre()` here** (§7). |
| `scripts/grafana_provision.py` | stdlib `urllib` REST adapter; auth from env in priority order; **dry-run by default, explicit `--commit` to write**; never print secrets. |
| `scripts/gen_grafana_alerts.py` | Deterministic `kb/*.json → output/*.json` transform with a `--check` drift mode — the model for the Phase-0 offline payload builder. |
| `scripts/slack_send.py` | `load_config()` shape for reading `kb/config.json`; the "never print the token" guard. |

**Encoding guard (confirmed real trap).** All KB reads go through `opensre/io.py` using
`encoding="utf-8"`. `kb/known-issues.json` contains a non-cp1252 byte; on Windows the
default cp1252 decode raises `UnicodeDecodeError`. Every existing KB consumer already
passes `encoding="utf-8"` — match that.

## 3. Replay payload design (`POST /investigate`)

- **Endpoint:** `POST {OPENSRE_BASE_URL}/investigate` (sre-agent service, default port
  `8001`). Response is **Server-Sent Events** (`thought` / `tool_start` / `tool_end` /
  `result`). The client must consume the stream to completion with a per-call timeout
  (default 900 s).
- **Body:** `{"prompt": "<string>", "thread_id": "<stable-id>"}`. OpenSRE's
  `_parse_alert_from_prompt()` deserializes any JSON it finds in the prompt into an alert
  object of shape `{name, service, severity, timestamp, description}`.
- **Curated-knowledge preamble.** Because `/investigate` *runs* an investigation rather
  than importing a record, each prompt leads with a clearly-marked
  **`RESOLVED HISTORICAL INCIDENT`** block carrying our curated `diagnosis` (root cause),
  `playbook` (resolution), and `fix_status`, followed by the JSON alert object. The intent
  is that the memory extractor stores **our** confirmed knowledge rather than a fresh
  (possibly wrong) live guess.
- **Fidelity caveat.** Seeding curated knowledge this way is **best-effort** — it depends
  on OpenSRE's LLM-based memory extractor. Replays should run against the **local instance
  with no prod tool access**, so the agent leans on the supplied resolution instead of
  attempting (and failing) a live investigation.

Example prompt body:

```
RESOLVED HISTORICAL INCIDENT (seeding episodic memory; do not investigate live systems)
Root cause: <diagnosis>
Resolution / playbook: <playbook>
Fix status: <fix_status>   Occurrences: <occurrences>   References: <references>

{"name": "<title>", "service": "<service>", "severity": "<sev>",
 "timestamp": "<last_seen>", "description": "<title> — see root cause above"}
```

## 4. Per-artifact mapping (all six files + corpora)

| KB artifact | Treatment under the replay model |
|---|---|
| `kb/known-issues.json` (67 entries) | **Primary replay set.** One replay → one episodic-memory episode. Upsert key `id` (`ki-*`). `title`→alert `name`; `match.channels` / SLO measurement point → `service`; `diagnosis`/`playbook`/`fix_status`/`references` → the curated preamble. |
| `kb/incident-log.jsonl` (~4,060 lines, 2.3 MB) | **Opt-in** (`backfill_incident_log`, default **off**). Replay only non-operational lines — exclude `classification` ∈ {`poll-cycle`,`heartbeat`} and null `alert_hash` (that removes most of the volume). Key = `alert_hash`; `matched_kb` ties the episode to its known-issue; `classification`/`owning_team`/`score_breakdown` ride along as context. |
| `kb/false-alarms.json` (empty today) | Replay as "known-benign / resolution = suppress" episodes so OpenSRE learns noise patterns. Simplest mapper — validates the pipeline on the empty-array case (sync zero episodes, no error). |
| Ownership: `references/architecture/ownership.md` + `slo-catalog.json.slos[].owner.team` + `config.json.critical_path_services` | **Context injection, not graph import.** Enrich each payload's `service`/`severity`/owning-team. Derive the core ownership from the *structured* feeds (SLO owners + critical-path list); treat `ownership.md`'s markdown tables as later enrichment only (needs a table parser; live webhooks are redacted there). |
| `kb/account-tiers.json` (only `_default`/`_schema` today) | Enrich impact/severity context in payloads. **Never export seat counts** — the file forbids storing them (`account_impact.py` queries them live). |
| `kb/slo-catalog.json` | Source of `journey`/`service`/`owner` context; optionally a handful of "SLO-breach exemplar" episodes. `datasource`/`queries`/`webhook_id` are operational — skip. |
| `kb/config.json.channels` | **Not exported** — internal Slack routing, and `swat`/`team-incident-response` are write-forbidden channels. |
| `docs/investigations/*.md`, `docs/messages/**` | Investigation bodies can enrich replay prompts (Phase 2+). Slack message archives are out of scope. |

## 5. Sync semantics & idempotency

- **Backfill** (`--backfill`): replay every in-scope item once — **rate-limited and
  resumable** (state file below).
- **Incremental** (`--incremental`): diff the KB against the last replayed commit
  (`git diff --name-only <last-sha>..HEAD -- kb/` — the same freshness probe
  `heartbeat.yaml` already uses) and replay only changed items; plus a periodic cron
  safety net (~6 h) to catch anything missed.
- **State / dedup:** `logs/opensre/replay-state.json` (under the already-gitignored
  `logs/`) records `{key → {content_sha, thread_id, ts, status}}`. If an item's
  `content_sha` is unchanged, **skip the replay entirely** — this both prevents
  episodic-memory **duplicate pollution** and avoids redundant, expensive agent runs.
  Stable keys reuse existing ids: `ki-*`, `fa-*`, `alert_hash`.
- **Strictly one-way.** OpenSRE is never read during triage in this scope (that is the
  out-of-scope Phase 4). Nothing reads OpenSRE state back into `kb/`.

## 6. Config & secrets (mirror the existing split)

Non-secret toggles in `kb/config.json`; secrets in `.env` + the routine `secrets:` block.

Add an `opensre` block to `kb/config.json` (parallels the existing `stability_review`
block):

```json
"opensre": {
  "enabled": false,
  "dry_run": true,
  "transport": "dryrun",
  "replay_known_issues": true,
  "backfill_incident_log": false,
  "exclude_operational_log_lines": true,
  "max_replays_per_run": 25,
  "per_investigate_timeout_s": 900,
  "concurrency": 1,
  "comment": "One-way KB->OpenSRE episodic-memory feed via POST /investigate replay. enabled=false keeps the sync routine inert. dry_run/transport=dryrun builds payloads to logs/opensre/ and networks nothing. base_url + api_key come from .env (OPENSRE_BASE_URL, OPENSRE_API_KEY), never stored here."
}
```

Secrets (gitignored `.env` + declared in `routines/opensre-sync.yaml` `secrets:`):

- `OPENSRE_BASE_URL`
- `OPENSRE_API_KEY` (Bearer / `x-sandbox-jwt` if the instance enables auth)
- Local instance also needs LLM provider creds (`OPENROUTER_API_KEY` / `NVIDIA_API_KEY`)
  — separate cost and secret, only on the host running OpenSRE.

`opensre/config.py` reads the block via the `load_config()` shape from `slack_send.py`.
If `OPENSRE_BASE_URL`/`OPENSRE_API_KEY` are unset, the adapter reports **`skipped`**, not
`fail` — exactly as `tool_health.py` treats unset DD/ELK creds. The token is never logged.

## 7. Failure isolation & observability

- **Standalone routine** with its own `timeout_minutes` and cron — cannot consume triage's
  30-minute budget or spend cap.
- **Dry-run default.** `transport: "dryrun"` writes the exact payloads it *would* POST to
  `logs/opensre/<date>/payloads/*.json` and networks nothing. Going live is a deliberate
  config flip (`dry_run: false`, `transport: "rest"`) — same gating philosophy as
  `grafana_provision.py apply` requiring `--commit`.
- **Never crash.** `replay.py` wraps every mapper and every adapter call in try/except that
  converts exceptions to a `_fail`-style result dict (copy `tool_health.py`). Exit codes:
  0 all-ok/skipped, 1 partial failure, 2 config/internal error.
- **Heartbeat integration.** Add `check_opensre()` (`GET {OPENSRE_BASE_URL}/health`) to
  `scripts/tool_health.py` `CHECKS`/`CHECK_FN` so OpenSRE shows up in the existing
  heartbeat tool table and the `🟡 tools degraded` path — no new alert surface.
- **Run summary to disk, not Slack.** Each run writes `logs/opensre/<date>/run.json`
  (`{read, replayed, skipped, failed, sha}`). Optionally post a one-liner to
  `#triage-bot-health` **only** on fail/degraded (mirrors `pir-ingest`'s silent-on-nothing).

## 8. Rollout phases

| Phase | Scope | In scope now? |
|---|---|---|
| **0 — Offline payload builder + dry-run** | `opensre/mappers/*` + `transport/dryrun.py` + `replay.py` build `/investigate` payloads for all in-scope files to `logs/opensre/`. Pure/offline. Start with `false-alarms` (trivial) + `slo-catalog` (clean JSON), then `known-issues`, then `incident-log`. | **YES** |
| **1 — Stand up local OpenSRE** | docker-compose (Neo4j 7475/7688, Postgres 5433, config-svc 8081, LiteLLM 4001, sre-agent 8001, web 3002) + LLM creds; implement `transport/rest.py` (SSE); confirm one sample `/investigate` round-trips and stores an episode. | **YES (gated on infra)** |
| **2 — Backfill replay** | `--backfill`: known-issues first; incident-log opt-in via `backfill_incident_log`; rate-limited + resumable. | **YES** |
| **3 — Incremental sync routine** | `routines/opensre-sync.yaml`, git-diff-driven + periodic cron, `dry_run` flipped off, heartbeat check live. | **YES (steady state)** |
| **4 — Triage queries OpenSRE memory** | Triage reads OpenSRE episodic memory to enrich classification. | **EXPLICITLY OUT OF SCOPE** (architecture kept forward-compatible — replay stays one-way today). |

## 9. Verification

- **Phase 0 (no instance):** payload count == in-scope record count (67 known-issues
  today); every payload is valid JSON; assert utf-8 reads (no `UnicodeDecodeError`); a
  `--check` mode re-runs the mapping and fails on drift from committed expected counts.
- **Phase 1:** one sample replay yields a `result` SSE event; an episode row appears in the
  PostgreSQL episodic-memory store; a similar-alert lookup retrieves it (OpenSRE similarity
  weights: alert-type 0.5 / service 0.3 / resolved 0.2).
- **Phase 2:** episode count == replayed count; **re-running backfill replays 0 items**
  (idempotency proof via `replay-state.json`); spot-check 3 `ki-*` episodes carry the
  curated root-cause/resolution text.
- **Phase 3:** add one test `ki-*` entry on a branch → incremental replays **exactly one**;
  heartbeat shows `opensre ✓`.
- **Continuous canary:** the heartbeat `opensre` check + per-run `run.json` give an ongoing
  read-vs-replayed-vs-skipped-vs-failed reconciliation signal.

## 10. Risks & open questions

1. **Alpha API instability** — `/investigate` request/response shape may change; isolated
   behind `transport/rest.py` so confirming/adapting changes one file.
2. **Replay cost & time** — ~900 s/agent run; 67 known-issues (+ optional incident-log) is
   real LLM spend and wall-clock. Mitigations: serial/low `concurrency`,
   `max_replays_per_run`, dry-run first, exclude operational log lines, opt-in incident-log
   backfill.
3. **Fidelity** — `/investigate` investigates rather than imports; curated-knowledge
   seeding is best-effort via the memory extractor (mitigated by the RESOLVED-incident
   preamble and a prod-tool-less local instance).
4. **k8s-centric graph** — replay seeds Postgres **episodic memory**, not the Neo4j
   topology graph; ownership/SLO/config cannot populate the graph cleanly. This is a
   limitation of the chosen mechanism, accepted in the scoping decision.
5. **Episodic-memory duplication** — `replay-state.json` + content-hash dedup + stable
   `thread_id`.
6. **Secrets** — `OPENSRE_API_KEY` never logged or committed; non-secret toggles only in
   `kb/config.json`.
7. **Auth model** (`x-sandbox-jwt`) — confirm whether the self-hosted dev instance requires
   it before Phase 1.
8. **Routine cloud-sync drift** — routines are inline snapshots that don't auto-re-read the
   repo; document the "edit YAML, commit, sync to claude.ai/code/routines" step like the
   other routines. `routines/opensre-sync.yaml` stays the source of truth.

## 11. Files the integration would create / modify

> Described here for the implementation phase — **not** created by this design doc.

- **New:** `opensre/` package (per §2), `scripts/opensre_replay.py`,
  `routines/opensre-sync.yaml`.
- **Modified:** `kb/config.json` (+`opensre` block), `scripts/tool_health.py`
  (+`check_opensre`), `.env` (+`OPENSRE_*`, local only). `logs/` is already gitignored.
- **Reuse references:** `scripts/tool_health.py`, `scripts/grafana_provision.py`,
  `scripts/gen_grafana_alerts.py`, `scripts/slack_send.py` (`load_config` + never-print-
  token), `prompt.md` (the `grep -F '"alert_hash"'` idempotency precedent).

## Appendix — OpenSRE deployment reference (for Phase 1)

docker-compose services and host ports observed in the public repo:

| Service | Host port | Purpose |
|---|---|---|
| PostgreSQL | 5433 | config + episodic memory |
| Config Service | 8081 | team config, tokens, audit |
| Neo4j | 7475 (browser), 7688 (bolt) | knowledge graph |
| LiteLLM proxy | 4001 | LLM provider abstraction |
| SRE Agent | 8001 | investigation engine (`POST /investigate`) |
| Web UI | 3002 | admin console |

Key env: `DATABASE_URL`, `NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD`, `LITELLM_BASE_URL`,
`OPENROUTER_API_KEY`/`NVIDIA_API_KEY`, `LLM_MODEL`, `AGENT_TIMEOUT_SECONDS` (900 default),
and optional `SLACK_BOT_TOKEN`/`SLACK_APP_TOKEN`. License: Apache-2.0. Status: public alpha
— API may evolve.

Sources: <https://opensre.in/>, <https://github.com/swapnildahiphale/OpenSRE>
(`docs/ARCHITECTURE.md`, `sre-agent/server.py`, `sre-agent/memory/integration.py`,
`sre-agent/tools/neo4j_semantic_layer.py`, `docker-compose.yml`).
