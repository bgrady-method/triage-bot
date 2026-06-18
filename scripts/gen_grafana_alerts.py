#!/usr/bin/env python3
"""
gen_grafana_alerts.py — deterministic generator: kb/slo-catalog.json -> alerting/grafana/*.json

Reads the SLO catalog (the source of truth) and emits Grafana *unified-alerting*
provisioning payloads, one file per SLO, plus the contact point and notification
policy. Pure / offline / no network — output is committed and PR-reviewable.
`scripts/grafana_provision.py apply` resolves datasource NAMES -> uids and the
folder name -> folderUID against the live instance, then PUTs each rule.

Design: references/architecture/alerting-system-design.md
This is a SEPARATE track from the triage-bot escalation_score machinery.

Conventions baked in:
  * Every rule carries labels {slo, severity, owner, pager:"triage-bot"} so the
    notification policy can route the whole set to one contact point.
  * owner is INERT TEXT in annotations (no @-mention) per the standing rule.
  * Rules land in the "SLO" folder so they never collide with the ~40 existing rules.
  * Burn-rate rules require BOTH the long and short window to breach (precision +
    fast reset), matching the multi-window multi-burn-rate design.

Usage:
  python scripts/gen_grafana_alerts.py            # write alerting/grafana/*.json
  python scripts/gen_grafana_alerts.py --check     # generate in-memory, fail on drift, write nothing
"""
import argparse, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "kb", "slo-catalog.json")
OUTDIR = os.path.join(ROOT, "alerting", "grafana")

WINDOW_SECONDS = {"5m": 300, "30m": 1800, "1h": 3600, "2h": 7200, "6h": 21600,
                  "10m": 600, "15m": 900, "24h": 86400, "3d": 259200}


def load_catalog():
    with open(CATALOG, encoding="utf-8") as f:
        return json.load(f)


def secs(w):
    if w not in WINDOW_SECONDS:
        raise SystemExit(f"unknown window '{w}' — add it to WINDOW_SECONDS")
    return WINDOW_SECONDS[w]


def base_labels(slo, severity):
    return {"slo": slo["id"], "severity": severity, "owner": slo["owner"]["team"],
            "pager": "triage-bot"}


def annotations(slo, summary):
    # owner_team is INERT text — never an @-mention.
    return {"summary": summary, "owner_team": slo["owner"]["team"],
            "slo": slo["id"], "journey": slo["journey"], "runbook": slo["runbook"]}


def es_count_query(ref, datasource_name, lucene, window):
    """A single-bucket ES count over `window` -> one number (reduced by 'last')."""
    return {
        "refId": ref,
        "relativeTimeRange": {"from": secs(window), "to": 0},
        "datasourceUid": datasource_name,  # resolved name->uid at apply time
        "model": {
            "refId": ref,
            "query": lucene,
            "alias": "",
            "metrics": [{"id": "1", "type": "count"}],
            "bucketAggs": [],  # no date histogram -> single number
            "timeField": "@timestamp",
        },
    }


def influxql_query(ref, datasource_name, influxql, window):
    return {
        "refId": ref,
        "relativeTimeRange": {"from": secs(window), "to": 0},
        "datasourceUid": datasource_name,
        "model": {"refId": ref, "query": influxql, "rawQuery": True, "resultFormat": "time_series"},
    }


def promql_query(ref, datasource_name, promql, window):
    return {
        "refId": ref,
        "relativeTimeRange": {"from": secs(window), "to": 0},
        "datasourceUid": datasource_name,
        "model": {"refId": ref, "expr": promql, "instant": True},
    }


def expr_math(ref, expression):
    return {"refId": ref, "datasourceUid": "__expr__",
            "model": {"refId": ref, "type": "math", "expression": expression}}


def expr_reduce(ref, input_ref, reducer="last"):
    return {"refId": ref, "datasourceUid": "__expr__",
            "model": {"refId": ref, "type": "reduce", "reducer": reducer, "expression": input_ref}}


def expr_threshold(ref, input_ref, gt):
    return {"refId": ref, "datasourceUid": "__expr__",
            "model": {"refId": ref, "type": "threshold", "expression": input_ref,
                      "conditions": [{"evaluator": {"type": "gt", "params": [gt]}}]}}


def rule(uid, title, data, condition, for_, labels, annos):
    return {
        "uid": uid, "title": title, "condition": condition, "data": data,
        "noDataState": "OK", "execErrState": "Error", "for": for_,
        "labels": labels, "annotations": annos, "ruleGroup": uid, "isPaused": False,
    }


def gen_availability(slo, ladder_by_tier):
    """Multi-window multi-burn-rate ES rules. budget = 1 - target."""
    budget = round(1.0 - slo["target"], 6)
    ds = slo["datasource"]["error"]
    out = []
    for tier_name in slo.get("ladder_tiers", []):
        t = ladder_by_tier[tier_name]
        thr = round(t["burn"] * budget, 8)
        lw, sw = t["long_window"], t["short_window"]
        data = [es_count_query("ERR_L", ds, slo["queries"]["error"], lw),
                es_count_query("TOT_L", ds, slo["queries"]["total"], lw),
                expr_reduce("EL", "ERR_L"), expr_reduce("TL", "TOT_L")]
        if sw:
            data += [es_count_query("ERR_S", ds, slo["queries"]["error"], sw),
                     es_count_query("TOT_S", ds, slo["queries"]["total"], sw),
                     expr_reduce("ES", "ERR_S"), expr_reduce("TS", "TOT_S")]
            expr = f"(${{EL}}/(${{TL}}+1) > {thr}) && (${{ES}}/(${{TS}}+1) > {thr})"
        else:
            expr = f"${{EL}}/(${{TL}}+1) > {thr}"
        data += [expr_math("BURN_RAW", expr), expr_threshold("BURN", "BURN_RAW", 0)]
        summary = (f"{slo['id']} {slo['journey']}: error budget burning >= {t['burn']}x "
                   f"over {lw}" + (f"+{sw}" if sw else "") + f" (target {slo['target']}, {t['action']}).")
        out.append(rule(f"{slo['id'].lower()}-{tier_name}",
                        f"{slo['id']} {slo['journey']} — {tier_name} burn ({t['severity']})",
                        data, "BURN", t["for"],
                        base_labels(slo, t["severity"]), annotations(slo, summary)))
    return out


def gen_latency(slo, ladder_by_tier):
    """Latency(-and-errors): a p95 threshold rule (InfluxDB or Prometheus) + any error burn rules (ES)."""
    out = []
    q = slo.get("queries", {})
    sustain = slo.get("sustain", "10m")
    thr = slo.get("threshold_ms", slo.get("target_p95_ms"))
    if "influxql_p95" in q:
        ds = slo["datasource"]["metric"]
        data = [influxql_query("P95", ds, q["influxql_p95"], sustain),
                expr_reduce("R", "P95", "max"), expr_threshold("COND", "R", thr)]
        out.append(rule(f"{slo['id'].lower()}-latency",
                        f"{slo['id']} {slo['journey']} — p95 latency (P1)",
                        data, "COND", sustain, base_labels(slo, "P1"),
                        annotations(slo, f"{slo['id']} {slo['journey']}: p95 > {thr}ms sustained {sustain}.")))
    elif "promql_p95" in q:
        ds = slo["datasource"]["metric"]
        data = [promql_query("P95", ds, q["promql_p95"], sustain),
                expr_reduce("R", "P95", "max"), expr_threshold("COND", "R", thr)]
        out.append(rule(f"{slo['id'].lower()}-latency",
                        f"{slo['id']} {slo['journey']} — p95 latency (P1)",
                        data, "COND", sustain, base_labels(slo, "P1"),
                        annotations(slo, f"{slo['id']} {slo['journey']}: p95 > {thr}ms sustained {sustain}.")))
    # error burn rules (only when the SLO declares an ES error/total query + ladder tiers)
    if slo.get("ladder_tiers") and "error" in q and "total" in q:
        out += gen_availability(slo, ladder_by_tier)
    return out


def gen_absolute(slo):
    out = []
    a = slo["absolute"]
    if "count_gte" in a:  # ES absolute error count (low traffic)
        ds = slo["datasource"]["error"]
        data = [es_count_query("C", ds, slo["queries"]["error"], a["window"]),
                expr_reduce("R", "C"), expr_threshold("COND", "R", a["count_gte"] - 1)]
        summary = f"{slo['id']} {slo['journey']}: >= {a['count_gte']} failures in {a['window']}."
    else:  # InfluxDB absolute value threshold (e.g. backlog age)
        ds = slo["datasource"]["metric"]
        ql = next(v for k, v in slo["queries"].items() if k.startswith("influxql"))
        data = [influxql_query("V", ds, ql, a["window"]),
                expr_reduce("R", "V", "max"), expr_threshold("COND", "R", a["value_gt"])]
        summary = f"{slo['id']} {slo['journey']}: value > {a['value_gt']} {a.get('unit','')} over {a['window']}."
    out.append(rule(f"{slo['id'].lower()}-absolute",
                    f"{slo['id']} {slo['journey']} — {a['severity']}",
                    data, "COND", a["window"],
                    base_labels(slo, a["severity"]), annotations(slo, summary)))
    return out


def gen_leading_indicator(slo):
    """F1/F2 style: explicit per-alert specs in slo['alerts']."""
    out = []
    ds = slo["datasource"]["metric"]
    for al in slo["alerts"]:
        ql = slo["queries"][al["query"]]
        if al["kind"] == "no_data":
            data = [influxql_query("HB", ds, ql, al["window"]),
                    expr_reduce("R", "HB", "count"), expr_threshold("COND", "R", 0)]
            # NoData fires this rule: invert via noDataState=Alerting
            r = rule(f"{al['name']}", f"{slo['id']} {al['name']} ({al['severity']})",
                     data, "COND", al["window"],
                     base_labels(slo, al["severity"]),
                     annotations(slo, f"{al['name']}: no datapoints in {al['window']} (heartbeat lost)."))
            r["noDataState"] = "Alerting"
            out.append(r)
        else:  # threshold
            sustain = al.get("sustain", al.get("window", "5m"))
            data = [influxql_query("V", ds, ql, sustain),
                    expr_reduce("R", "V", "max"), expr_threshold("COND", "R", al["value_gt"])]
            labels = base_labels(slo, al["severity"])
            if al.get("inhibited_by"):
                labels["inhibited_by"] = al["inhibited_by"]
            out.append(rule(f"{al['name']}", f"{slo['id']} {al['name']} ({al['severity']})",
                            data, "COND", sustain, labels,
                            annotations(slo, f"{al['name']}: value > {al['value_gt']} sustained {sustain}.")))
    return out


def generate(cat):
    ladder = {t["tier"]: t for t in cat["meta"]["burn_ladder"]}
    files = {}
    for slo in cat["slos"]:
        kind = slo["kind"]
        if kind == "availability":
            rules = gen_availability(slo, ladder)
        elif kind in ("latency", "latency_and_errors"):
            rules = gen_latency(slo, ladder)
        elif kind in ("absolute_errors", "absolute_saturation"):
            rules = gen_absolute(slo)
        elif kind == "leading_indicator":
            rules = gen_leading_indicator(slo)
        else:
            raise SystemExit(f"{slo['id']}: unknown kind '{kind}'")
        files[f"{slo['id']}.json"] = {
            "folder": cat["meta"]["grafana_folder"],
            "slo": slo["id"], "build_status": slo.get("build_status"),
            "needs_probe": slo.get("needs_probe", False),
            "rules": rules,
        }
    # contact point + notification policy (delivery objects)
    files["_contact-point.json"] = {
        "name": cat["meta"]["contact_point"],
        "type": "slack",
        "settings_note": "recipient = #triage-bot-health channel. NO @-mentions in the template. "
                         "Webhook/token supplied at apply time from env, never committed.",
        "message_template": "{{ .CommonLabels.slo }} [{{ .CommonLabels.severity }}] {{ .CommonAnnotations.summary }} "
                            "(owner: {{ .CommonLabels.owner }}) runbook: {{ .CommonAnnotations.runbook }}",
    }
    files["_notification-policy.json"] = {
        "note": "Route everything labelled pager=triage-bot to the triage-bot-health contact point. "
                "Per-owner / XMatters routing is documented in the design doc for later — not active.",
        "route": {"receiver": cat["meta"]["contact_point"],
                  "matchers": ["pager=triage-bot"],
                  "group_by": ["slo"], "group_wait": "30s", "group_interval": "5m", "repeat_interval": "4h"},
        "inhibition": "A firing gateway-avail rule (SLO-2 parent) suppresses SLO-3/4/5 child notifications; "
                      "rabbitmq-consumer-lag is suppressed while subscriber-heartbeat fires.",
    }
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail on drift; write nothing")
    args = ap.parse_args()
    cat = load_catalog()
    files = generate(cat)
    os.makedirs(OUTDIR, exist_ok=True)
    drift = False
    for name, obj in files.items():
        path = os.path.join(OUTDIR, name)
        new = json.dumps(obj, indent=2, sort_keys=False) + "\n"
        old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
        if args.check:
            if old != new:
                drift = True
                print(f"DRIFT: {name}")
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new)
            print(f"wrote alerting/grafana/{name}  ({len(obj.get('rules', []))} rules)" if "rules" in obj
                  else f"wrote alerting/grafana/{name}")
    if args.check and drift:
        sys.exit(1)
    if args.check:
        print("OK — no drift")


if __name__ == "__main__":
    main()
