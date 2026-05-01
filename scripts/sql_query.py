"""SQL query runner (read-only) over an SSH tunnel.

Constraints (security, by design):
  - Only the named templates in scripts/sql_templates/ can be run.
  - The routine prompt cannot inject ad-hoc SQL — it picks a template name and
    supplies typed parameters.
  - All parameters are bound via pyodbc's `?` placeholder mechanism, never
    string-substituted into the SQL.
  - The DB user (SQL_USER / SQL_PASS_RO) MUST be a read-only role on the
    server side; this script does not attempt to enforce that itself.

Auth via env vars / routine secrets:
  SSH_HOST            — bastion hostname
  SSH_PORT            — default 22
  SSH_USER            — bastion user
  SSH_PRIVATE_KEY     — PEM contents (NOT a path); we materialize it to a temp file
  SQL_HOST            — target SQL server hostname (private, behind bastion)
  SQL_PORT            — default 1433
  SQL_USER            — read-only DB user
  SQL_PASS_RO         — read-only DB password
  SQL_DATABASE        — initial database (templates may use USE in the future)

Usage:
  python sql_query.py --template health-check
  python sql_query.py --template account-lookup --param search="acme"

Templates may declare typed parameters in a leading comment block:
  -- @param search:str
  -- @param account_id:int
The runner enforces that only declared params are accepted, with the right type.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

TEMPLATES_DIR = Path(__file__).parent / "sql_templates"
PARAM_DECL_RE = re.compile(r"^--\s*@param\s+([A-Za-z_]\w*):(str|int|bool)\s*$", re.MULTILINE)
PARAM_PLACEHOLDER_RE = re.compile(r":(?P<name>[A-Za-z_]\w*)")


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
    """Returns (sql, declared_params:{name: type})."""
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
    """Replace :name placeholders with ? and return positional args in order."""
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
def ssh_tunnel(local_port: int) -> Iterator[None]:
    """Open an SSH local-forward to SQL_HOST:SQL_PORT for the lifetime of the block."""
    if shutil.which("ssh") is None:
        die("ssh client not found in PATH")

    pem = env_required("SSH_PRIVATE_KEY")
    key_file = tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False)
    try:
        key_file.write(pem)
        key_file.close()
        os.chmod(key_file.name, 0o600)

        sql_host = env_required("SQL_HOST")
        sql_port = env_int("SQL_PORT", 1433)
        ssh_host = env_required("SSH_HOST")
        ssh_port = env_int("SSH_PORT", 22)
        ssh_user = env_required("SSH_USER")

        cmd = [
            "ssh",
            "-i", key_file.name,
            "-p", str(ssh_port),
            "-N",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ExitOnForwardFailure=yes",
            "-o", "ServerAliveInterval=15",
            "-L", f"{local_port}:{sql_host}:{sql_port}",
            f"{ssh_user}@{ssh_host}",
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            # Wait until the local forward is accepting connections (max 10s)
            deadline = time.time() + 10
            while time.time() < deadline:
                if proc.poll() is not None:
                    err = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
                    die(f"ssh tunnel exited early: {err.strip()}")
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.3)
                    try:
                        s.connect(("127.0.0.1", local_port))
                        break
                    except OSError:
                        time.sleep(0.2)
            else:
                die("ssh tunnel did not become ready within 10s")
            yield
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    finally:
        try:
            os.unlink(key_file.name)
        except OSError:
            pass


def run_query(sql: str, params: list[Any], local_port: int) -> dict:
    try:
        import pyodbc  # type: ignore
    except ImportError:
        die("pyodbc is required (pip install pyodbc; system needs the MS ODBC Driver 18)")

    db = env_required("SQL_DATABASE")
    user = env_required("SQL_USER")
    pw = env_required("SQL_PASS_RO")
    conn_str = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server=tcp:127.0.0.1,{local_port};"
        f"Database={db};"
        f"UID={user};PWD={pw};"
        "Encrypt=yes;TrustServerCertificate=yes;"
        "Connection Timeout=10;"
        # This client is read-only by intent. Server-side role enforcement is the source of truth.
        "ApplicationIntent=ReadOnly;"
    )
    with pyodbc.connect(conn_str, autocommit=True, readonly=True) as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        if cur.description is None:
            return {"columns": [], "rows": [], "rowcount": cur.rowcount}
        cols = [c[0] for c in cur.description]
        rows = [list(r) for r in cur.fetchmany(500)]  # hard cap
        # Coerce non-JSON-serializable types
        for row in rows:
            for i, v in enumerate(row):
                if hasattr(v, "isoformat"):
                    row[i] = v.isoformat()
        return {"columns": cols, "rows": rows, "rowcount": cur.rowcount, "truncated": cur.fetchone() is not None}


def main() -> int:
    p = argparse.ArgumentParser(description="Run a vetted read-only SQL template over an SSH tunnel.")
    p.add_argument("--template", required=True, help="Template name (without .sql).")
    p.add_argument(
        "--param",
        action="append",
        default=[],
        help="key=value parameter for the template. Repeatable.",
    )
    p.add_argument("--local-port", type=int, default=15433, help="Local SSH-forwarded port.")
    p.add_argument("--list", action="store_true", help="List available templates and exit.")
    args = p.parse_args()

    if args.list:
        for f in sorted(TEMPLATES_DIR.glob("*.sql")):
            print(f.stem)
        return 0

    sql, declared = load_template(args.template)

    supplied: dict[str, str] = {}
    for kv in args.param:
        if "=" not in kv:
            die(f"--param must be key=value, got {kv!r}")
        k, v = kv.split("=", 1)
        supplied[k] = v

    bound_sql, args_list = bind_params(sql, declared, supplied)

    with ssh_tunnel(args.local_port):
        result = run_query(bound_sql, args_list, args.local_port)

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
