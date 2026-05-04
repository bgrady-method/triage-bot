"""Service-dependency-matrix drift checker.

Compares the dependency cells declared in
`references/architecture/service-dependency-matrix.md`
against the actual backing-store wiring found in each service's
`appsettings*.json` / `Web.config` / `.csproj` files.

Two modes:
  --local <ROOT>   Scan sibling-cloned repos at <ROOT>/<svc>/ (maintainer
                   machine; pass C:/MethodDev or /workspace).
  --gh             Fetch each service's config files via `gh api` from
                   github.com/methodcrm/<svc>. Used by the cloud routine
                   where per-service repos aren't cloned.

For each row in the matrix, the script reports:
  - declared:  the H/S/A/? cells we found in the matrix
  - observed:  the backing stores actually wired in the repo's config
  - DRIFT:     declared-but-not-observed and observed-but-not-declared

The script does NOT determine H/S/A severity from config — only presence.
That decision still belongs to a human reading per-service CLAUDE.md.

Usage:
  python scripts/dep_drift_check.py --local C:/MethodDev
  python scripts/dep_drift_check.py --gh
  python scripts/dep_drift_check.py --gh --service ms-email-api  # one row only
  python scripts/dep_drift_check.py --gh --strict                # exit 1 on drift

No external deps. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MATRIX_PATH = REPO_ROOT / "references" / "architecture" / "service-dependency-matrix.md"

# Backing-store column → list of regex patterns whose presence in a repo's
# appsettings*.json / Web.config / .csproj implies the service depends on
# that store. Patterns are case-sensitive unless wrapped in (?i).
STORE_PATTERNS: dict[str, list[str]] = {
    "SQL":      [r"(?i)\bSql_c\d\b",
                 r"(?i)\bMasterDatabaseConnection",
                 r"Server=[^;\"]+;\s*Database=",
                 r"(?i)\bSqlConnection\b",
                 r"(?i)\bSqlServer\b"],
    "Mongo":    [r"mongodb://",
                 r"mongodb\+srv://",
                 r"(?i)\bMongoClient\b",
                 r"(?i)\bConnectionStrings.*Mongo",
                 r"(?i)\bConnectionOptions.*Mongo"],
    "Redis":    [r"(?i)\bConnectionStrings.*Redis",
                 r"(?i)\bConnectionOptions.*Redis",
                 r"(?i)StackExchange\.Redis",
                 r"(?i)\bAddRedisCache\b",
                 r"(?i)\bRedis2\b"],
    "RabbitMQ": [r"amqp://",
                 r"(?i)\bConnectionStrings.*RabbitMQ",
                 r"(?i)\bConnectionOptions.*RabbitMQ",
                 r"(?i)\bMassTransit",
                 r"(?i)\brabbitmq\b"],
    # ES = Elasticsearch as a *runtime data store* (search, indexing).
    # Serilog.Sinks.Elasticsearch is excluded — it's a log sink, present on
    # nearly every service, and not what the matrix's ES column tracks.
    "ES":       [r"(?i)\bElasticClient\b",
                 r"(?i)\bIElasticClient\b",
                 r"(?i)\bNEST\.Client",
                 r"(?i)\bAddElasticsearch\b"],
    "S3":       [r"(?i)\bIAmazonS3\b",
                 r"(?i)AWSSDK\.S3",
                 r"(?i)\bAmazon\.S3\b",
                 r"\bs3://"],
}

# Files within a repo to scan. Globs interpreted by Path.rglob.
CONFIG_GLOBS = ["appsettings*.json", "Web.config", "Web.*.config", "*.csproj"]

# Repos to fetch via `gh api`. Mirror the matrix's row labels (collapsed by
# repo — runtime-core is one repo even though the matrix splits its hosts).
# Each entry is the methodcrm/* repo name.
GH_REPOS = [
    "ms-gateway-api", "ms-authentication-api", "ms-identity-api", "oauth2",
    "runtime-core", "ms-search-api", "ms-tables-fields-api",
    "ms-account-api", "ms-tags-api", "ms-preferences-api", "ms-documents-api",
    "ms-email-api", "ms-scheduler-api", "ms-support-api", "ms-analytics-api",
    "qbo-sync-api",
    "ms-reminder-agent", "legacy-email-agent", "legacy-authentication-api",
]

# Map matrix row labels → GH repo name (when they differ).
ROW_TO_REPO = {
    "ms-search-api (a.k.a. Method.Search)":         "ms-search-api",
    "runtime-core (Runtime.Core.Api)":              "runtime-core",
    "runtime-core (Designer.Core.Api)":             "runtime-core",
    "runtime-core (Runtime.Core.Subscriber)":       "runtime-core",
    "runtime-core (AppUpdate.Agent)":               "runtime-core",
    "runtime-core (Apps.Api 5200)":                 "runtime-core",
    "runtime-core (AI.Core.Api)":                   "runtime-core",
    "runtime-core (EDA.Orchestrator.Api)":          "runtime-core",
    "oauth2 (IdentityServer4)":                     "oauth2",
    "qbo-webhooks-api":                             "qbo-sync-api",  # same repo
    "ms-email-api ⚠️":                              "ms-email-api",
    "ms-scheduler-api ❓":                           "ms-scheduler-api",
}


def parse_matrix(matrix_md: str) -> dict[str, dict[str, str]]:
    """Parse the backing-stores table from service-dependency-matrix.md.

    Returns: {service_label: {store_name: cell_value}} where cell_value is
    one of "H", "S", "A", "?", "" (blank).
    """
    rows: dict[str, dict[str, str]] = {}
    in_table = False
    headers: list[str] = []
    for line in matrix_md.splitlines():
        stripped = line.strip()
        if stripped.startswith("## Backing stores"):
            in_table = True
            continue
        if in_table and stripped.startswith("##"):
            break
        if not in_table or not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not cells or all(not c for c in cells):
            continue
        if not headers:
            if cells[0].lower().startswith("service"):
                headers = cells
            continue
        if cells[0].startswith(":") or set(cells[0]) <= set("-: "):
            continue
        svc = cells[0]
        if not svc:
            continue
        rows[svc] = {}
        for col, val in zip(headers[1:], cells[1:]):
            rows[svc][col] = val
    return rows


def _read_file_local(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None


def scan_repo_local(repo_root: Path) -> set[str]:
    """Scan a sibling-cloned repo's config files. Return observed stores."""
    observed: set[str] = set()
    for glob in CONFIG_GLOBS:
        for f in repo_root.rglob(glob):
            # Skip junk
            parts = {p.lower() for p in f.parts}
            if parts & {"node_modules", "bin", "obj", ".git", "packages"}:
                continue
            text = _read_file_local(f)
            if text is None:
                continue
            for store, patterns in STORE_PATTERNS.items():
                if store in observed:
                    continue
                for pat in patterns:
                    if re.search(pat, text):
                        observed.add(store)
                        break
    return observed


def _gh_list_files(repo: str, paths_to_try: list[str]) -> list[str]:
    """List candidate config files in methodcrm/<repo> via gh api."""
    found: list[str] = []
    for p in paths_to_try:
        try:
            res = subprocess.run(
                ["gh", "api", f"repos/methodcrm/{repo}/contents/{p}", "--jq", ".[].path // .path"],
                capture_output=True, text=True, timeout=30,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return []
        if res.returncode != 0:
            continue
        for line in res.stdout.splitlines():
            line = line.strip()
            if line and (line.endswith(".json") or line.endswith(".config") or line.endswith(".csproj")):
                found.append(line)
    return found


def _gh_get_file(repo: str, path: str) -> str | None:
    """Fetch a file's content from methodcrm/<repo>."""
    try:
        res = subprocess.run(
            ["gh", "api", f"repos/methodcrm/{repo}/contents/{path}", "--jq", ".content"],
            capture_output=True, text=True, timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if res.returncode != 0:
        return None
    import base64
    raw = res.stdout.strip().replace("\n", "")
    try:
        return base64.b64decode(raw).decode("utf-8", errors="ignore")
    except Exception:
        return None


def scan_repo_gh(repo: str) -> set[str]:
    """Fetch a methodcrm/<repo>'s config files via gh api. Return observed stores."""
    observed: set[str] = set()
    # Try common locations first; rglob equivalent isn't cheap via gh.
    candidates = [
        "appsettings.json", "appsettings.Development.json", "appsettings.Production.json",
        "Web.config",
        "API/appsettings.json", "API/appsettings.Development.json", "API/Web.config",
        "src/appsettings.json", "src/Web.config",
    ]
    # Also try discovering via search/code API (one HTTP call per filename per repo).
    # `-f` URL-encodes spaces correctly; `+` would be doubly-encoded.
    for filename in ("appsettings.json", "Web.config"):
        try:
            res = subprocess.run(
                ["gh", "api", "-X", "GET", "search/code",
                 "-f", f"q=filename:{filename} repo:methodcrm/{repo}",
                 "--jq", ".items[].path"],
                capture_output=True, text=True, encoding="utf-8", timeout=30,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            break
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                line = line.strip()
                if line and "test" not in line.lower() and "spec" not in line.lower():
                    candidates.append(line)

    seen: set[str] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        text = _gh_get_file(repo, path)
        if text is None:
            continue
        for store, patterns in STORE_PATTERNS.items():
            if store in observed:
                continue
            for pat in patterns:
                if re.search(pat, text):
                    observed.add(store)
                    break
    return observed


def declared_stores(cells: dict[str, str]) -> set[str]:
    """Stores that the matrix says this service uses (any of H/S/A/?)."""
    return {store for store, val in cells.items() if val in {"H", "S", "A", "?"}}


def report_drift(svc: str, declared: set[str], observed: set[str]) -> tuple[bool, str]:
    """Return (has_drift, formatted_report)."""
    declared_only = declared - observed - {"OAuth2/Auth"}  # OAuth2 isn't grep-detectable here
    observed_only = observed - declared
    has_drift = bool(declared_only or observed_only)

    # Strip emoji annotations from the matrix row label for clean console output.
    label = re.sub(r"[☀-➿\U0001F000-\U0001FFFF]", "", svc).strip()
    lines = [f"=== {label} ==="]
    lines.append(f"  declared: {', '.join(sorted(declared)) or '(none)'}")
    lines.append(f"  observed: {', '.join(sorted(observed)) or '(none)'}")
    if declared_only:
        lines.append(f"  DRIFT -- declared but not observed: {', '.join(sorted(declared_only))}")
    if observed_only:
        lines.append(f"  DRIFT -- observed but not declared: {', '.join(sorted(observed_only))}")
    if not has_drift:
        lines.append("  OK")
    return has_drift, "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--local", metavar="ROOT", help="Scan sibling repos under ROOT (e.g. C:/MethodDev or /workspace).")
    grp.add_argument("--gh", action="store_true", help="Fetch repos via `gh api` from github.com/methodcrm/.")
    ap.add_argument("--service", help="Limit scan to one service (matrix row label, exact match).")
    ap.add_argument("--strict", action="store_true", help="Exit non-zero if any drift is found.")
    args = ap.parse_args()

    if not MATRIX_PATH.exists():
        print(f"matrix not found: {MATRIX_PATH}", file=sys.stderr)
        return 2
    rows = parse_matrix(MATRIX_PATH.read_text(encoding="utf-8"))
    if not rows:
        print(f"matrix parsed empty — table format may have changed", file=sys.stderr)
        return 2

    any_drift = False
    for svc, cells in rows.items():
        if args.service and args.service != svc:
            continue
        repo = ROW_TO_REPO.get(svc, svc)
        # Strip annotations like ⚠️ ❓ for repo lookup
        repo = re.sub(r"\s*[⚠️❓]\s*$", "", repo).strip()
        if args.local:
            repo_root = Path(args.local) / repo
            if not repo_root.is_dir():
                print(f"=== {svc} ===\n  SKIP — {repo_root} not found")
                continue
            observed = scan_repo_local(repo_root)
        else:
            observed = scan_repo_gh(repo)

        declared = declared_stores(cells)
        drift, report = report_drift(svc, declared, observed)
        any_drift = any_drift or drift
        print(report)

    if args.strict and any_drift:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
