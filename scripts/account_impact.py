"""Account-impact lookup: given a list of account names, find each one's tenant
DB on the right Method SQL cluster, then count active users (per-TenantId,
multi-tenancy-aware) inside that DB. Returns JSONL on stdout — one line per
input account — so the bot can consume incrementally and the order matches the
input.

Used by the triage routine's step 4.3 to populate the "Affected accounts"
section of the investigation report and to feed the `active_users_affected`
signal into the step 7 escalation score (replacing the old distinct-account
count). See `prompt.md` step 4.3 and `docs/kb-curation.md` for context.

Edge cases (each returned as a status code, not an exception, so a partial
batch doesn't abort):
  - ok                  : resolved and user-count succeeded.
  - not_found           : no row in AlocetSystem.dbo.CustomerMethodAccount on
                          any AlocetSystem-bearing cluster we tried. Bot may
                          retry with a subdomain spelling.
  - ambiguous           : multiple rows match — wrapper returns `candidates`
                          and the bot picks the most-likely.
  - inactive_account    : registry shows IsActive=0; user-count contributes 0.
  - tenant_unreachable  : registry said DB X exists on cluster C, but connect
                          to that DB failed (cluster down, DB renamed, etc.).
  - schema_unknown      : tenant DB reachable but `spiderSecurity` missing.
  - error               : uncategorised; includes `error_message`.

Cluster routing: AlocetSystem lives on multiple clusters (per
`scripts/sql_templates/account-lookup.sql` — C1/C3/C4/C5; C2 hosts accounts but
no AlocetSystem). We fan out lookups across every cluster whose env var is set
(`SQL_HOST_PROD1..5`); clusters without env vars are silently skipped and
reported in the per-result `clusters_unconfigured` array so the bot knows the
coverage was partial.

Usage:
  python scripts/account_impact.py --accounts ramexteriorsinc,prestonhardware
  python scripts/account_impact.py --accounts mvwd --pretty   # indented JSON

Exits 0 even when some accounts fail. Exits 2 only on usage error or
fully-fatal failure (no clusters available, no SSH at all).
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SQL_QUERY = REPO_ROOT / "scripts" / "sql_query.py"
TIERS_FILE = REPO_ROOT / "kb" / "account-tiers.json"
ALOCETSYSTEM_CLUSTERS = ("prod1", "prod3", "prod4", "prod5")  # per account-lookup.sql; prod2 has accounts but no AlocetSystem


def _run_sql(connection: str, template: str, params: dict[str, str] | None = None, database: str | None = None) -> dict[str, Any]:
    """Run sql_query.py as a subprocess. Returns parsed JSON, or {'error': '...'}."""
    cmd = [sys.executable, str(SQL_QUERY), "--connection", connection, "--template", template]
    for k, v in (params or {}).items():
        cmd.extend(["--param", f"{k}={v}"])
    if database:
        cmd.extend(["--database", database])
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=60)
    except subprocess.TimeoutExpired:
        return {"error": f"sql_query.py timed out on {connection}/{template}"}
    if p.returncode != 0:
        return {"error": (p.stderr or p.stdout).strip()[:500]}
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError as e:
        return {"error": f"sql_query.py returned non-JSON: {e}; stdout head: {p.stdout[:200]}"}


def _load_tiers() -> dict[str, dict]:
    if not TIERS_FILE.exists():
        return {}
    try:
        return json.loads(TIERS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _lookup_account_on_cluster(account: str, cluster: str) -> dict[str, Any]:
    """Query AlocetSystem.dbo.CustomerMethodAccount on one cluster. Returns
    raw sql_query.py result with cluster annotation."""
    result = _run_sql(cluster, "account-lookup", {"search": account})
    result["_cluster"] = cluster
    return result


def _row_to_dict(cols: list[str], row: list[Any]) -> dict[str, Any]:
    return dict(zip(cols, row))


def _resolve_account(account: str, available_clusters: list[str]) -> tuple[str, list[dict], list[str]]:
    """Returns (status, matched_rows, clusters_unconfigured).
    Status is one of: 'ok', 'not_found', 'ambiguous'.
    matched_rows is a list of {cluster, ...row_fields}."""
    clusters_unconfigured = [c for c in ALOCETSYSTEM_CLUSTERS if c not in available_clusters]
    matches: list[dict] = []
    with cf.ThreadPoolExecutor(max_workers=len(available_clusters)) as ex:
        futs = {ex.submit(_lookup_account_on_cluster, account, c): c for c in available_clusters}
        for fut in cf.as_completed(futs):
            r = fut.result()
            if "error" in r:
                continue  # cluster down or unauthenticated; move on
            cols = r.get("columns") or []
            for row in r.get("rows") or []:
                d = _row_to_dict(cols, row)
                d["_cluster"] = r["_cluster"]
                # exact-match preference: bot can later filter
                if d.get("DatabaseName", "").lower() == account.lower() or \
                   d.get("DisplayName", "").lower() == account.lower() or \
                   d.get("Subdomain", "").lower() == account.lower():
                    d["_exact_match"] = True
                else:
                    d["_exact_match"] = False
                matches.append(d)

    if not matches:
        return "not_found", [], clusters_unconfigured

    # Prefer exact matches when present.
    exact = [m for m in matches if m.get("_exact_match")]
    if exact:
        if len(exact) == 1:
            return "ok", exact, clusters_unconfigured
        # Multiple exact matches — vanishingly rare but possible if same name on multiple clusters
        return "ambiguous", exact, clusters_unconfigured

    if len(matches) == 1:
        return "ok", matches, clusters_unconfigured

    return "ambiguous", matches[:5], clusters_unconfigured  # cap candidate list


def _user_count(cluster: str, tenant_db: str) -> dict[str, Any]:
    """Returns one of: {'status': 'ok', 'tenants': [...], 'totals': {...}},
    {'status': 'tenant_unreachable', 'error': '...'},
    {'status': 'schema_unknown', 'error': '...'}."""
    r = _run_sql(cluster, "account-active-users", database=tenant_db)
    if "error" in r:
        err = r["error"].lower()
        if "spidersecurity" in err and ("invalid object" in err or "does not exist" in err):
            return {"status": "schema_unknown", "error": r["error"]}
        return {"status": "tenant_unreachable", "error": r["error"]}
    cols = r.get("columns") or []
    rows = r.get("rows") or []
    tenants = []
    total_active = 0
    total_licensed = 0
    for row in rows:
        d = _row_to_dict(cols, row)
        try:
            active = int(d.get("active_users") or 0)
            licensed = int(d.get("licensed_active_users") or 0)
        except (TypeError, ValueError):
            active = 0
            licensed = 0
        total_active += active
        total_licensed += licensed
        tenants.append({
            "tenant_id": d.get("TenantId"),
            "total_users": d.get("total_users"),
            "active_users": active,
            "licensed_active_users": licensed,
        })
    return {"status": "ok", "tenants": tenants, "total_active_users": total_active, "total_licensed_active_users": total_licensed}


def _resolve_one(account: str, available_clusters: list[str], tiers: dict[str, dict]) -> dict[str, Any]:
    out: dict[str, Any] = {"account": account}
    status, matches, clusters_unconfigured = _resolve_account(account, available_clusters)

    if clusters_unconfigured:
        out["clusters_unconfigured"] = clusters_unconfigured

    if status == "not_found":
        out["status"] = "not_found"
        return out

    if status == "ambiguous":
        out["status"] = "ambiguous"
        out["candidates"] = [
            {
                "company_account": m.get("DatabaseName"),
                "display_name": m.get("DisplayName"),
                "subdomain": m.get("Subdomain"),
                "is_active": bool(m.get("IsActive")),
                "subscription_status": m.get("SubscriptionStatus"),
                "cluster": m.get("_cluster"),
            }
            for m in matches
        ]
        return out

    # status == 'ok'
    match = matches[0]
    tenant_db = match.get("DatabaseName") or account
    cluster = match.get("_cluster")
    is_active = bool(match.get("IsActive"))
    out["cluster"] = cluster
    out["tenant_db"] = tenant_db
    out["is_active_account"] = is_active
    out["subscription_status"] = match.get("SubscriptionStatus")

    # Most accounts won't be in account-tiers.json — only special-cased ones.
    # Everything else inherits `_default.tier` (which the seed file sets to
    # "unknown", contributing 0 to the escalation score).
    default_tier = (tiers.get("_default") or {}).get("tier", "unknown")
    tier_entry = (
        tiers.get(tenant_db)
        or tiers.get(account)
        or tiers.get(match.get("Subdomain") or "")
    )
    if tier_entry:
        out["tier"] = tier_entry.get("tier", default_tier)
        out["tier_source"] = "account-tiers.json"
    else:
        out["tier"] = default_tier
        out["tier_source"] = "default"

    if not is_active:
        out["status"] = "inactive_account"
        out["tenants"] = []
        out["total_active_users"] = 0
        out["total_licensed_active_users"] = 0
        return out

    uc = _user_count(cluster, tenant_db)
    if uc["status"] != "ok":
        out["status"] = uc["status"]
        out["error_message"] = uc.get("error")
        return out

    out["status"] = "ok"
    out["tenants"] = uc["tenants"]
    out["total_active_users"] = uc["total_active_users"]
    out["total_licensed_active_users"] = uc["total_licensed_active_users"]
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--accounts", required=True, help="Comma-separated list of account names / subdomains / DB names to look up.")
    p.add_argument("--pretty", action="store_true", help="Pretty-print each JSON output instead of one-per-line.")
    args = p.parse_args()

    accounts = [a.strip() for a in args.accounts.split(",") if a.strip()]
    if not accounts:
        json.dump({"error": "--accounts must contain at least one name"}, sys.stderr)
        sys.stderr.write("\n")
        return 2

    # Figure out which clusters we can actually query (env var present).
    available = [c for c in ALOCETSYSTEM_CLUSTERS if os.environ.get(_host_env(c))]
    if not available:
        json.dump({"error": "no AlocetSystem-bearing cluster configured (SQL_HOST_PROD1/3/4/5 all unset)"}, sys.stderr)
        sys.stderr.write("\n")
        return 2

    tiers = _load_tiers()
    for account in accounts:
        result = _resolve_one(account, available, tiers)
        if args.pretty:
            json.dump(result, sys.stdout, indent=2)
            sys.stdout.write("\n")
        else:
            json.dump(result, sys.stdout)
            sys.stdout.write("\n")
        sys.stdout.flush()
    return 0


def _host_env(cluster: str) -> str:
    """Map cluster friendly name → its expected SQL_HOST_* env var. Mirrors
    sql_query.CONNECTIONS but kept local so we don't have to import."""
    return {"prod1": "SQL_HOST_PROD1", "prod2": "SQL_HOST_PROD2", "prod3": "SQL_HOST_PROD3",
            "prod4": "SQL_HOST_PROD4", "prod5": "SQL_HOST_PROD5"}[cluster]


if __name__ == "__main__":
    raise SystemExit(main())
