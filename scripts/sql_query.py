"""SQL query runner (read-only) over an SSH tunnel.

Mirrors the connection model in `method-db-tools/scripts/db_utils.py` (pyodbc +
ApplicationIntent=ReadOnly for production), adding an SSH tunnel layer because
this routine runs from Anthropic's cloud (no VPN, no internal-network access).

Constraints (security, by design):
  - Only the named templates in scripts/sql_templates/ are runnable.
  - The routine prompt cannot inject ad-hoc SQL — it picks a template name and
    supplies typed parameters bound via pyodbc's ? placeholder mechanism.
  - The DB user is `reader`, a read-only account; pyodbc connects with
    ApplicationIntent=ReadOnly. Even if the role were misconfigured, the
    `tier_policies.production.allow_writes_flag: false` check in the skills'
    connections.json (which we mirror in spirit) blocks writes.

Auth via env vars / routine secrets:
  SSH_HOST            — bastion hostname (e.g. hq.method.me)
  SSH_PORT            — bastion port (default 22; Method uses 9433)
  SSH_USER            — bastion user (e.g. b.grady)
  SSH_PASS            — bastion password
  SQL_HOST_PROD1      — prod1 host/IP target of the tunnel (e.g. 172.31.121.125)
  SQL_HOST_PROD2      — prod2 host/IP target of the tunnel (e.g. 172.31.121.225)
  SQL_PORT            — SQL Server port (default 1433)
  SQL_USER            — read-only DB user (e.g. reader)
  SQL_PASS_RO         — read-only DB password
  SQL_DATABASE        — initial database (e.g. AlocetSystem)

Usage:
  python sql_query.py --template health-check
  python sql_query.py --template account-lookup --param search="acme"
  python sql_query.py --template health-check --connection prod2
  python sql_query.py --list
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

TEMPLATES_DIR = Path(__file__).parent / "sql_templates"
PARAM_DECL_RE = re.compile(r"^--\s*@param\s+([A-Za-z_]\w*):(str|int|bool)\s*$", re.MULTILINE)
PARAM_PLACEHOLDER_RE = re.compile(r":(?P<name>[A-Za-z_]\w*)")

CONNECTIONS = {
    "prod1": {"host_env": "SQL_HOST_PROD1", "description": "Production SQL Server 1 (read-only)"},
    "prod2": {"host_env": "SQL_HOST_PROD2", "description": "Production SQL Server 2 (read-only)"},
}


def die(msg: str, code: int = 1) -> None:
    json.dump({"error": msg}, sys.stderr)
    sys.stderr.write("\n")
    sys.exit(code)


def env_required(key: str) -> str:
    v = os.environ.get(key)
    if not v:
        die(f"{key} env var is required")
    return v


def env_int(key: str, default: int) -> int:
    v = os.environ.get(key)
    if not v:
        return default
    try:
        return int(v)
    except ValueError:
        die(f"{key} must be an int, got {v!r}")


def load_template(name: str) -> tuple[str, dict[str, str]]:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        die(f"invalid template name: {name!r}")
    p = TEMPLATES_DIR / f"{name}.sql"
    if not p.exists():
        die(f"unknown template: {name!r} (not found at {p})")
    sql = p.read_text(encoding="utf-8")
    declared = {m.group(1): m.group(2) for m in PARAM_DECL_RE.finditer(sql)}
    return sql, declared


def coerce(value: str, type_: str) -> Any:
    if type_ == "str":
        return value
    if type_ == "int":
        return int(value)
    if type_ == "bool":
        if value.lower() in ("1", "true", "yes"):
            return True
        if value.lower() in ("0", "false", "no"):
            return False
        die(f"bad bool value: {value!r}")
    die(f"unknown type: {type_}")


def bind_params(sql: str, declared: dict[str, str], supplied: dict[str, str]) -> tuple[str, list[Any]]:
    unknown = set(supplied) - set(declared)
    if unknown:
        die(f"undeclared params supplied: {sorted(unknown)}; template declares {sorted(declared)}")

    args: list[Any] = []
    used: set[str] = set()

    def repl(m: re.Match) -> str:
        name = m.group("name")
        if name not in declared:
            die(f"placeholder :{name} in SQL but not declared with -- @param")
        if name not in supplied:
            die(f"missing required param: {name}")
        used.add(name)
        args.append(coerce(supplied[name], declared[name]))
        return "?"

    new_sql = PARAM_PLACEHOLDER_RE.sub(repl, sql)
    missing = set(declared) - used
    if missing:
        die(f"declared params never used in SQL: {sorted(missing)}")
    return new_sql, args


@contextmanager
def ssh_tunnel(remote_host: str, remote_port: int) -> Iterator[int]:
    """Open SSH local-forward to remote_host:remote_port; yield the local port."""
    try:
        from sshtunnel import SSHTunnelForwarder  # type: ignore
    except ImportError:
        die("sshtunnel required (pip install sshtunnel paramiko)")

    forwarder = SSHTunnelForwarder(
        (env_required("SSH_HOST"), env_int("SSH_PORT", 22)),
        ssh_username=env_required("SSH_USER"),
        ssh_password=env_required("SSH_PASS"),
        remote_bind_address=(remote_host, remote_port),
        # local_bind_address omitted -> sshtunnel picks a free local port
        set_keepalive=15,
    )
    forwarder.start()
    try:
        yield forwarder.local_bind_port
    finally:
        forwarder.stop()


def run_query(sql: str, params: list[Any], local_port: int) -> dict:
    try:
        import pyodbc  # type: ignore
    except ImportError:
        die("pyodbc required (pip install pyodbc + Microsoft ODBC Driver 17/18 system package)")

    db = env_required("SQL_DATABASE")
    user = env_required("SQL_USER")
    pw = env_required("SQL_PASS_RO")
    # Driver name matches db_utils.py:72 ("ODBC Driver 17 for SQL Server" for production).
    conn_str = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER=tcp:127.0.0.1,{local_port};"
        f"DATABASE={db};"
        f"UID={user};PWD={pw};"
        "Encrypt=yes;TrustServerCertificate=yes;"
        "Connection Timeout=10;"
        "ApplicationIntent=ReadOnly;"  # mirrors db_utils.py:95
    )
    with pyodbc.connect(conn_str, autocommit=True) as conn:
        # Mirror db_utils.py:98 — query timeout from tier policy (production = 30s)
        conn.timeout = 30
        cur = conn.cursor()
        cur.execute(sql, params)
        if cur.description is None:
            return {"columns": [], "rows": [], "rowcount": cur.rowcount}
        cols = [c[0] for c in cur.description]
        rows = [list(r) for r in cur.fetchmany(500)]   # hard cap mirrors tier_policies.production.max_rows_ceiling
        for row in rows:
            for i, v in enumerate(row):
                if hasattr(v, "isoformat"):
                    row[i] = v.isoformat()
        return {
            "columns": cols,
            "rows": rows,
            "rowcount": cur.rowcount,
            "truncated": cur.fetchone() is not None,
        }


def main() -> int:
    p = argparse.ArgumentParser(description="Run a vetted read-only SQL template over an SSH tunnel.")
    p.add_argument("--template", help="Template name (without .sql).")
    p.add_argument(
        "--connection",
        choices=sorted(CONNECTIONS.keys()),
        default="prod1",
        help="Which production SQL instance to query.",
    )
    p.add_argument(
        "--param",
        action="append",
        default=[],
        help="key=value parameter for the template. Repeatable.",
    )
    p.add_argument("--list", action="store_true", help="List available templates and exit.")
    args = p.parse_args()

    if args.list:
        for f in sorted(TEMPLATES_DIR.glob("*.sql")):
            print(f.stem)
        return 0

    if not args.template:
        die("--template is required (use --list to see options)")

    sql, declared = load_template(args.template)

    supplied: dict[str, str] = {}
    for kv in args.param:
        if "=" not in kv:
            die(f"--param must be key=value, got {kv!r}")
        k, v = kv.split("=", 1)
        supplied[k] = v

    bound_sql, args_list = bind_params(sql, declared, supplied)

    conn_meta = CONNECTIONS[args.connection]
    remote_host = env_required(conn_meta["host_env"])
    remote_port = env_int("SQL_PORT", 1433)

    with ssh_tunnel(remote_host, remote_port) as local_port:
        result = run_query(bound_sql, args_list, local_port)

    result["connection"] = args.connection
    result["remote_host"] = remote_host
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
