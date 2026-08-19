#!/usr/bin/env python3
"""
investigate.py — deterministic, READ-ONLY investigation orchestrator.

Runs one alert / root-cause group through the mechanical investigation stages in
the fixed order the routine already prescribes (prompt.md steps 2–7 + the DD/ES
playbooks), by shelling out to the existing wired scripts, and prints a single
structured **evidence bundle** (JSON or markdown).

It gathers evidence; it does NOT decide or act. The model reads the bundle and does
the genuine-judgment stages (root-cause hypothesis, final 4-bucket classification)
and every side effect (Slack send, KB write, git commit). This script never sends,
never commits, and never calls a `--commit`/write path — Hard rule #3 holds by
construction.

Stages (skip/select with --stages):
  hash          alert_hash.py                      idempotency key
  kb-match      match_kb.py (false-alarms → known)  matched entry or null
  kb-verify     kb_to_es_query.py + es_search.py    fresh recurrence hit count
  route         channel-guidance.md map             dd-first / es-first / both
  dd            dd_search.py monitors(+logs)        firing monitors, error sample
  es            es_search.py aggregate ×3 (+drill)  Level/Exception/Error buckets
  impact        account_impact.py                   per-tenant active users
  score         score.py (imported)                 partial escalation score

Usage:
  python scripts/investigate.py --channel C063V5HTTFU --ts 1720000000.001 \
      [--thread-ts <ts>] [--text "…"] [--text-file f] [--service runtime-core] \
      [--accounts acme,globex] [--group-size 3] [--distinct-channels 2] \
      [--query "level:ERROR AND service:runtime-core-api"] [--window-min 65] \
      [--signals-json model_signals.json] [--stages hash,kb-match,dd,es,score] \
      [--format json|md]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys

import score as score_mod

# Windows consoles default to cp1252, which cannot encode the arrows/em-dashes
# this module prints. Without this, `--help` dies with UnicodeEncodeError (the
# module docstring contains a literal arrow) and `--format md` dies the same way
# on the score line. Both were live bugs. Guarded: stdout may be replaced by a
# stream without .reconfigure (pytest capture, some CI harnesses).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):  # noqa: PERF203
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
PY = sys.executable
CONFIG = os.path.join(ROOT, "kb", "config.json")
KB_KNOWN = os.path.join(ROOT, "kb", "known-issues.json")
INCIDENT_LOG = os.path.join(ROOT, "kb", "incident-log.jsonl")
KB_FALSE = os.path.join(ROOT, "kb", "false-alarms.json")

ALL_STAGES = ["hash", "kb-match", "kb-verify", "route", "dd", "es", "impact", "score"]


def load_dotenv_into_environ():
    """Populate os.environ from repo-root .env so the wrapped scripts (which read
    os.environ directly, no python-dotenv) work when run ad-hoc. Already-set vars
    win, so the routine runner's exported environment is never overridden."""
    path = os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val

# channel_name -> recommended investigation order (playbooks/channel-guidance.md)
ROUTE = {
    "alert-frontend-errors": "es-first",     # ES first, then DD RUM, skip APM
    "alert-runtime-monitoring": "dd-first",  # DD full pass, ES to confirm
    "alert-system": "both",                  # infra→DD, app→parallel
    "swat": "both-wide",
    "team-incident-response": "both-wide",
}

# Signals the orchestrator genuinely cannot derive — the model must supply these
# (via --signals-json) or accept 0. Surfaced in the bundle for honesty.
#
# Kept deliberately short. Everything derivable from data already on disk is now
# derived below (see derive_history_signals) rather than defaulting to 0.
#
# Why this mattered: four of the five INHIBITION signals used to live in this
# list. Absent signals contribute nothing, and inhibition signals are negative,
# so an un-supplemented run scored systematically HIGH — biased toward sending.
# Reporting that in `model_supplied_signals_still_needed` was honest but did not
# make the score right. Only `operator_engaged` still inhibits from here.
#
# These four cannot be mechanised from this process:
#   deployed_within_2h    — needs Azure DevOps/TFS deploy data; methodcrm/* git
#                           fetch 403s for this token (standing gap).
#   metric                — observed-vs-threshold shape varies per monitor type;
#                           parsing it generically is unreliable enough to be
#                           worse than declaring the gap.
#   operator_engaged      — needs a Slack channel read. This orchestrator shells
#                           out to Python scripts and has NO MCP access; the read
#                           path is MCP-only, so only the model can see it. (Its
#                           availability also flaps per-session — the 15:07Z
#                           triage on 2026-07-15 had it, the 16:03Z heartbeat
#                           did not.)
#   swat_thread_mentions  — same reason: Slack read, MCP-only.
MODEL_SUPPLIED_SIGNALS = [
    "deployed_within_2h", "metric", "operator_engaged", "swat_thread_mentions",
]


def run(cmd, stdin=None, timeout=90):
    """Run a subprocess from the repo root; return {ok, rc, out, err, cmd}."""
    try:
        p = subprocess.run(cmd, cwd=ROOT, input=stdin, capture_output=True,
                           text=True, timeout=timeout)
        return {"ok": p.returncode == 0, "rc": p.returncode,
                "out": p.stdout, "err": p.stderr.strip()[:500],
                "cmd": " ".join(cmd)}
    except Exception as e:  # noqa: BLE001  (timeout, missing interpreter, etc.)
        return {"ok": False, "rc": None, "out": "", "err": f"{type(e).__name__}: {e}",
                "cmd": " ".join(cmd)}


def load_config():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


# ---------------------------------------------------------------------------
# stages — each returns a JSON-serializable dict; never raises
# ---------------------------------------------------------------------------
def stage_hash(ctx):
    cmd = [PY, os.path.join(SCRIPTS, "alert_hash.py"),
           "--channel", ctx["channel_id"], "--ts", str(ctx["ts"])]
    if ctx.get("thread_ts"):
        cmd += ["--thread-ts", str(ctx["thread_ts"])]
    r = run(cmd)
    return {"ok": r["ok"], "alert_hash": r["out"].strip() or None, "raw": r}


def _match_one(kb_path, ctx):
    cmd = [PY, os.path.join(SCRIPTS, "match_kb.py"), "--kb", kb_path,
           "--channel", ctx["channel_name"], "--text", ctx["text"] or ""]
    r = run(cmd)
    entry = None
    if r["out"].strip() and r["out"].strip() != "null":
        try:
            entry = json.loads(r["out"])
        except json.JSONDecodeError:
            entry = None
    return entry, r


def stage_kb_match(ctx):
    """False-alarms first, then known-issues (prompt.md step 3 order)."""
    fa_entry, fa_raw = _match_one(KB_FALSE, ctx)
    if fa_entry:
        return {"ok": True, "kind": "false-alarm", "matched_id": fa_entry.get("id"),
                "entry": fa_entry}
    ki_entry, ki_raw = _match_one(KB_KNOWN, ctx)
    if ki_entry:
        return {"ok": True, "kind": "known-issue", "matched_id": ki_entry.get("id"),
                "entry": ki_entry}
    return {"ok": True, "kind": None, "matched_id": None, "entry": None,
            "raw": {"false_alarms": fa_raw, "known_issues": ki_raw}}


def stage_kb_verify(ctx, kb):
    """Re-confirm a known-issue recurrence in its own evidence_source, this cycle.

    ES-sourced (default): build a query from the entry and aggregate.
    DD-sourced: run the entry's evidence_query as a DD log search.
    """
    entry = (kb or {}).get("entry")
    if not entry or kb.get("kind") != "known-issue":
        return {"ok": True, "skipped": "no known-issue match to verify"}
    src = entry.get("evidence_source", "elasticsearch")
    win = f"now-{ctx['window_min']}m"

    if src in ("datadog_logs", "datadog_apm"):
        q = entry.get("evidence_query")
        if not q:
            return {"ok": True, "evidence_source": src,
                    "note": "entry has no evidence_query; model must verify in DD"}
        r = run([PY, os.path.join(SCRIPTS, "dd_search.py"), "logs",
                 "--query", q, "--from", win, "--to", "now", "--limit", "10"])
        return {"ok": r["ok"], "evidence_source": src, "query": q, "raw": r}

    # elasticsearch / datadog_rum default → derive an ES query from the entry
    qr = run([PY, os.path.join(SCRIPTS, "kb_to_es_query.py"),
              "--kb-id", entry.get("id", ""), "--kb-file", KB_KNOWN])
    query = qr["out"].strip()
    if not qr["ok"] or not query:
        return {"ok": False, "evidence_source": "elasticsearch",
                "error": "kb_to_es_query produced no query", "raw": qr}
    agg = run([PY, os.path.join(SCRIPTS, "es_search.py"), "aggregate",
               "--query", query, "--from", win, "--to", "now",
               "--field", "Error.keyword", "--top", "5"])
    hits, top_buckets = None, None
    try:
        parsed = json.loads(agg["out"]) if agg["out"].strip() else {}
        if isinstance(parsed, dict):
            hits = (parsed.get("total") or {}).get("value")
            top_buckets = parsed.get("buckets")
        elif isinstance(parsed, list):  # bare bucket list
            hits = sum(b.get("doc_count", b.get("count", 0)) for b in parsed)
            top_buckets = parsed
    except json.JSONDecodeError:
        pass
    return {"ok": agg["ok"], "evidence_source": "elasticsearch", "query": query,
            "recurrence_hits": hits, "verified_nonempty": bool(hits),
            "top_buckets": top_buckets, "raw": agg}


def stage_route(ctx):
    order = ROUTE.get(ctx["channel_name"], "both")
    return {"ok": True, "channel": ctx["channel_name"], "recommended_order": order}


def stage_dd(ctx):
    """Always scan monitors first (prompt.md step 4.0); then sample error logs."""
    win = f"now-{ctx['window_min']}m"
    mon = run([PY, os.path.join(SCRIPTS, "dd_search.py"), "monitors",
               "--state", "Alert", "--state", "No Data", "--summary"])
    monitors = None
    try:
        monitors = json.loads(mon["out"]) if mon["out"].strip() else None
    except json.JSONDecodeError:
        pass
    out = {"ok": mon["ok"], "monitors_firing": monitors, "monitors_raw": mon}
    # optional log sample scoped to the service, if one was named
    if ctx.get("service"):
        logs = run([PY, os.path.join(SCRIPTS, "dd_search.py"), "logs",
                    "--query", f"service:{ctx['service']} status:error",
                    "--from", win, "--to", "now", "--limit", "10"])
        out["error_log_sample"] = logs
    return out


def stage_es(ctx):
    """First sweep: aggregate by Level/Exception/Error .keyword (the 3-field rule)."""
    win = f"now-{ctx['window_min']}m"
    query = ctx.get("query") or (f"service:{ctx['service']}" if ctx.get("service") else "*")
    aggs = {}
    for field in ("Level.keyword", "Exception.keyword", "Error.keyword"):
        r = run([PY, os.path.join(SCRIPTS, "es_search.py"), "aggregate",
                 "--query", query, "--from", win, "--to", "now",
                 "--field", field, "--top", "10"])
        if not r["ok"] or not r["out"].strip():
            aggs[field] = {"error": r["err"] or "no output"}
            continue
        try:
            parsed = json.loads(r["out"])
        except json.JSONDecodeError:
            aggs[field] = {"error": "unparseable", "raw": r["out"][:200]}
            continue
        # es_search aggregate returns {total, buckets} (or a bare bucket list)
        if isinstance(parsed, dict):
            aggs[field] = {"total": (parsed.get("total") or {}).get("value"),
                           "buckets": parsed.get("buckets", [])}
        else:
            aggs[field] = {"total": None, "buckets": parsed}
    return {"ok": True, "query": query, "aggregations": aggs,
            "note": "read the full Exception+message on 2-3 samples before concluding "
                    "(es-investigate.md Step 3.5)"}


def stage_impact(ctx):
    if not ctx.get("accounts"):
        return {"ok": True, "skipped": "no --accounts provided"}
    r = run([PY, os.path.join(SCRIPTS, "account_impact.py"),
             "--accounts", ctx["accounts"]])
    rows, active_ok, tiers = [], 0, []
    for line in r["out"].splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows.append(row)
        if row.get("status") == "ok":
            active_ok += int(row.get("total_active_users") or 0)
            if row.get("tier"):
                tiers.append(row["tier"])
    return {"ok": r["ok"], "rows": rows, "active_users_ok_sum": active_ok,
            "tiers": tiers, "raw_err": r["err"]}


def _parse_ts(value):
    """Return an aware UTC datetime, or None if unparseable. Never raises.

    Handles the three shapes that actually occur here:
      - ISO-8601 with Z            — most kb/incident-log.jsonl lines
      - epoch int/float            — some legacy incident-log lines
      - Slack ts as a STRING       — `--ts 1784121195.616799`, the CLI's own format

    That last one matters: Slack ts is not ISO, so treating it as unparseable
    would silently fall back to wall-clock now and compute 30d/7d/today windows
    around the wrong instant when replaying a past alert.
    """
    def _from_epoch(f):
        # < 1e9 is 2001-09-09; no Method alert predates that, so a smaller number
        # is junk rather than a timestamp. Say None instead of silently returning
        # 1970 and quietly skewing every window that depends on it.
        if f < 1e9:
            return None
        try:
            return datetime.datetime.fromtimestamp(f, datetime.timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    if isinstance(value, bool):           # bool is an int subclass — reject first
        return None
    if isinstance(value, (int, float)):
        return _from_epoch(float(value))
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:                                  # Slack ts / epoch-as-string
        return _from_epoch(float(s))
    except ValueError:
        return None


def _iter_incident_log():
    """Yield incident-log dicts. Tolerates the BOM (PowerShell writes utf-8-sig),
    malformed lines, and non-dict records. Never raises."""
    try:
        with open(INCIDENT_LOG, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(rec, dict):
                    yield rec
    except OSError:
        return


# Classifications that can produce an escalation-grade finding. A `false-alarm`
# is deliberately excluded — see _was_posted.
POSTWORTHY_CLASSES = {"needs-human", "known-issue-recurrence", "new-with-clear-fix"}


def _was_posted(rec):
    """Did this fire warrant an escalation-grade finding?

    This feeds monitor_maturity, whose question is "when this monitor fires, is it
    worth telling someone?" So a fire only counts if it BOTH reached a postworthy
    classification AND wasn't suppressed.

    The `false-alarm` exclusion is load-bearing, not pedantry. False-alarm lines
    carry `suppressed_dm: false` (nothing was suppressed — the action was a
    kb-update / thread-reply, not a finding). Counting them as posts inverts the
    signal: monitor 299551472 (ImportSubscriber No Data) is a false alarm on 45 of
    45 recorded fires, and naively reading suppressed_dm scores it dm_rate 0.94 ->
    maturity +1, i.e. the single most trustworthy monitor in the fleet. It is the
    opposite: a monitor that only ever cries wolf earns dm_rate 0.0 -> -2.
    """
    if str(rec.get("classification")) not in POSTWORTHY_CLASSES:
        return False
    if "suppressed_dm" in rec:
        return not rec.get("suppressed_dm")
    return str(rec.get("action") or "").startswith("post")


def derive_history_signals(ctx, bundle):
    """Derive the history-based signals from data already on disk.

    Replaces four MODEL_SUPPLIED_SIGNALS entries that previously defaulted to 0
    and biased the score toward sending. All are read-only counts over
    kb/incident-log.jsonl plus the matched KB entry.

    Semantics match score.py's documented contract:
      monitor_fire_count       fires for this monitor_id in the last 30d
      monitor_dm_count         of those, how many were posted
      monitor_fires_today      this fire's ordinal today (1st fire -> 1)
      novel                    no KB match AND no same-hash alert in the prior 7d
      recent_post_same_kb_24h  this matched_kb was already posted in the last 24h

    Counts are strictly BEFORE this alert's own ts, so a run stays correct
    whether or not the current alert has been logged yet (Hard rule #6 appends
    the log line before side-effects, so on a live cycle it usually has been).
    """
    now = _parse_ts(ctx.get("ts")) or datetime.datetime.now(datetime.timezone.utc)
    monitor_id = ctx.get("monitor_id")
    alert_hash = (bundle.get("hash") or {}).get("alert_hash")
    d30 = now - datetime.timedelta(days=30)
    d7 = now - datetime.timedelta(days=7)
    today = now.date()

    fire_count = dm_count = fires_today = 0
    same_hash_7d = 0

    for rec in _iter_incident_log():
        ts = _parse_ts(rec.get("ts"))
        if ts is None or ts >= now:      # strictly prior events only
            continue
        if monitor_id is not None and rec.get("monitor_id") == monitor_id:
            if ts >= d30:
                fire_count += 1
                if _was_posted(rec):
                    dm_count += 1
            if ts.date() == today:
                fires_today += 1
        if alert_hash and rec.get("alert_hash") == alert_hash and ts >= d7:
            same_hash_7d += 1

    out = {}
    if monitor_id is not None:
        out["monitor_fire_count"] = fire_count
        out["monitor_dm_count"] = dm_count
        out["monitor_fires_today"] = fires_today + 1   # ordinal incl. this fire

    km = bundle.get("kb-match") or {}
    matched_id = km.get("matched_id") if km.get("kind") == "known-issue" else None
    out["novel"] = (matched_id is None) and (same_hash_7d == 0)

    entry = km.get("entry") or {}
    last_notified = _parse_ts(entry.get("last_notified_at"))
    if matched_id and last_notified:
        out["recent_post_same_kb_24h"] = (now - last_notified) < datetime.timedelta(hours=24)

    return out


def stage_score(ctx, bundle):
    """Compute the escalation score from mechanically-derived + model-supplied signals."""
    cfg = ctx["cfg"]
    signals = {}

    km = bundle.get("kb-match") or {}
    if km.get("kind") == "known-issue":
        signals["matched_kb"] = km.get("matched_id")

    svc = ctx.get("service")
    if svc and svc in cfg.get("critical_path_services", []):
        signals["critical_path_service"] = svc

    imp = bundle.get("impact") or {}
    if imp.get("rows") is not None:
        signals["active_users"] = imp.get("active_users_ok_sum", 0)
        signals["account_tiers"] = imp.get("tiers", [])
        signals["accounts_resolved"] = sum(1 for r in imp["rows"] if r.get("status") == "ok")

    signals["group_size"] = ctx.get("group_size", 1)
    signals["distinct_channels"] = ctx.get("distinct_channels", 1)

    # history-based signals derived from kb/incident-log.jsonl + the matched entry
    # (monitor maturity, recency decay, novelty, recent-post-same-kb). These used
    # to default to 0 and skew the score toward sending.
    derived_history = derive_history_signals(ctx, bundle)
    signals.update(derived_history)

    # merge model-supplied signals (they override / add the judgment-derived ones)
    supplied = ctx.get("model_signals") or {}
    signals.update({k: v for k, v in supplied.items() if v is not None})

    result = score_mod.escalation_score(signals, cfg)
    missing = [s for s in MODEL_SUPPLIED_SIGNALS if s not in supplied]
    result["signals_used"] = signals
    result["model_supplied_signals_still_needed"] = missing
    result["decision_preview"] = score_mod.decide_escalation(
        result["score"], ctx["channel_name"], today_post_count=0, cfg=cfg)
    result["note"] = ("PARTIAL — derived from mechanical signals only unless "
                      "--signals-json supplied the rest. Model must finalize.")
    return result


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------
def to_markdown(bundle):
    L = [f"# Investigation bundle — {bundle['input']['channel_name']} "
         f"@ {bundle['input']['ts']}", ""]
    L.append(f"- alert_hash: `{(bundle.get('hash') or {}).get('alert_hash')}`")
    km = bundle.get("kb-match") or {}
    L.append(f"- KB match: **{km.get('kind') or 'none'}**"
             + (f" (`{km.get('matched_id')}`)" if km.get("matched_id") else ""))
    kv = bundle.get("kb-verify") or {}
    if "recurrence_hits" in kv:
        L.append(f"- recurrence verified: {kv.get('verified_nonempty')} "
                 f"({kv.get('recurrence_hits')} hits, {kv.get('evidence_source')})")
    rt = bundle.get("route") or {}
    if rt:
        L.append(f"- recommended order: **{rt.get('recommended_order')}**")
    dd = bundle.get("dd") or {}
    if dd.get("monitors_firing") is not None:
        mf = dd["monitors_firing"]
        L.append(f"- DD monitors firing: {len(mf) if isinstance(mf, list) else mf}")
    imp = bundle.get("impact") or {}
    if imp.get("active_users_ok_sum") is not None and not imp.get("skipped"):
        L.append(f"- active users (status:ok): {imp['active_users_ok_sum']}")
    sc = bundle.get("score") or {}
    if "score" in sc:
        L.append(f"- **escalation score (partial): {sc['score']}** "
                 f"(threshold {sc.get('threshold_hint')}) → "
                 f"{sc.get('decision_preview', {}).get('action')}")
        if sc.get("model_supplied_signals_still_needed"):
            L.append(f"  - model still needs: "
                     f"{', '.join(sc['model_supplied_signals_still_needed'])}")
    L += ["", "_Read-only bundle — no send, no commit. Model finalizes "
          "classification + actions._"]
    return "\n".join(L)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--channel", required=True, help="Channel ID (Cxxxx) or name.")
    ap.add_argument("--ts", required=True, help="Primary alert Slack ts.")
    ap.add_argument("--thread-ts", dest="thread_ts")
    ap.add_argument("--text", help="Alert text (for KB match / query scoping).")
    ap.add_argument("--text-file", help="File to read alert text from (overrides --text).")
    ap.add_argument("--service", help="Named service/repo (for DD scope + critical-path signal).")
    ap.add_argument("--monitor-id", dest="monitor_id", type=int,
                    help="DD monitor id. Enables the monitor-history signals "
                         "(maturity + recency decay) in the score; without it "
                         "those are omitted rather than assumed zero.")
    ap.add_argument("--accounts", help="Comma-separated account names for impact.")
    ap.add_argument("--query", help="ES query scope for the aggregate sweep.")
    ap.add_argument("--group-size", type=int, default=1)
    ap.add_argument("--distinct-channels", type=int, default=1)
    ap.add_argument("--window-min", type=int, default=65)
    ap.add_argument("--signals-json", help="JSON file of model-supplied score signals.")
    ap.add_argument("--stages", default=",".join(ALL_STAGES),
                    help=f"Comma list of stages to run. Default all: {','.join(ALL_STAGES)}")
    ap.add_argument("--format", choices=["json", "md"], default="json")
    a = ap.parse_args()

    load_dotenv_into_environ()
    cfg = load_config()
    chans = cfg.get("channels", {})
    id_to_name = {v: k for k, v in chans.items()}
    # accept either an ID or a name for --channel
    if a.channel in id_to_name:
        channel_id, channel_name = a.channel, id_to_name[a.channel]
    elif a.channel in chans:
        channel_id, channel_name = chans[a.channel], a.channel
    else:
        channel_id, channel_name = a.channel, a.channel  # unknown; pass through

    text = a.text or ""
    if a.text_file:
        try:
            with open(a.text_file, encoding="utf-8") as f:
                text = f.read()
        except OSError as e:
            print(f"warning: could not read --text-file: {e}", file=sys.stderr)

    model_signals = {}
    if a.signals_json:
        try:
            with open(a.signals_json, encoding="utf-8") as f:
                model_signals = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"warning: could not read --signals-json: {e}", file=sys.stderr)

    ctx = {
        "channel_id": channel_id, "channel_name": channel_name,
        "ts": a.ts, "thread_ts": a.thread_ts, "text": text,
        "service": a.service, "monitor_id": a.monitor_id,
        "accounts": a.accounts, "query": a.query,
        "group_size": a.group_size, "distinct_channels": a.distinct_channels,
        "window_min": a.window_min, "model_signals": model_signals, "cfg": cfg,
    }

    want = [s.strip() for s in a.stages.split(",") if s.strip()]
    bundle = {"input": {k: ctx[k] for k in
                        ("channel_id", "channel_name", "ts", "thread_ts", "service",
                         "monitor_id", "accounts", "group_size", "distinct_channels",
                         "window_min")},
              "read_only": True}

    if "hash" in want:
        bundle["hash"] = stage_hash(ctx)
    if "kb-match" in want:
        bundle["kb-match"] = stage_kb_match(ctx)
    if "kb-verify" in want:
        bundle["kb-verify"] = stage_kb_verify(ctx, bundle.get("kb-match"))
    if "route" in want:
        bundle["route"] = stage_route(ctx)
    if "dd" in want:
        bundle["dd"] = stage_dd(ctx)
    if "es" in want:
        bundle["es"] = stage_es(ctx)
    if "impact" in want:
        bundle["impact"] = stage_impact(ctx)
    if "score" in want:
        bundle["score"] = stage_score(ctx, bundle)

    if a.format == "md":
        print(to_markdown(bundle))
    else:
        print(json.dumps(bundle, indent=2, default=str))


if __name__ == "__main__":
    main()
