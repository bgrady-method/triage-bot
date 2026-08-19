"""Re-sync the team ownership map from the Mongo warehouse (read-only).

Companion to `scripts/mongo_query.py`. Where mongo_query.py runs ad-hoc reads over an
SSH tunnel, this tool is purpose-built for one job: pull the team / component / project
ownership rows that back `references/architecture/ownership.md` out of the warehouse so
the committed snapshot can be regenerated and reconciled.

WHY two phases (discover -> dump):
  The exact warehouse DB/collection that mirrors AlocetSystem's ReleaseTeam /
  ReleaseComponents / MethodReleaseProject is not known ahead of time. So:
    1. `--discover` inventories databases + collections and flags the candidates by name.
    2. `--dump --collections db:coll,...` exports the chosen collections' rows as JSON.
  The Markdown regeneration of ownership.md happens back in the triage-bot repo from the
  dumped JSON — this script never writes repo files, so it's safe to run anywhere.

READ-ONLY by design (mirrors mongo_query.py):
  - Only `find` / `list_*` / `count_documents` are used. No write ops exist in this file.
  - admin/config/local are skipped.
  - Connects with the URI from MONGO_URI_WAREHOUSE (env). The pasted password lives ONLY
    in your environment / .env — never pass it on the command line, never commit it.

CONNECTION:
  Direct connect by default (the warehouse URI is a directly-reachable host on-network).
  Pass `--tunnel` to instead open an SSH tunnel using SSH_HOST/SSH_PORT/SSH_USER/SSH_PASS
  (same bastion env as mongo_query.py / sql_query.py), for parity with the bot's posture.

USAGE (run on-network, where mongo-warehouse.method.local resolves):
  export MONGO_URI_WAREHOUSE='mongodb://...:...@mongo-warehouse.method.local:27017/?authSource=admin'

  # 1) See what's there — send this output back:
  python scripts/sync_ownership.py --discover

  # 2) Once we know the collections, export the rows — send this output back:
  python scripts/sync_ownership.py --dump \
      --collections 'AlocetSystem:viewReleaseTeam,AlocetSystem:viewReleaseComponents,AlocetSystem:viewMethodReleaseProject'
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from contextlib import contextmanager
from typing import Any, Iterator
from urllib.parse import urlparse, urlunparse

BLOCKED_DATABASES = {"admin", "config", "local"}
# Name fragments that hint a collection carries ownership data. Case-insensitive.
CANDIDATE_PATTERNS = [
    r"releaseteam", r"releasecomponent", r"releaseproject", r"methodrelease",
    r"ownership", r"\bteam", r"\bcomponent", r"\bproject",
]
SAMPLE_DOCS = 3
DUMP_CAP = 5000  # ownership grids are ~10/105/156 rows; this is a generous safety ceiling.


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


# --- value cleaning (mirrors mongo_query.py._clean_doc) ---------------------------------

def _clean_value(v: Any) -> Any:
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if isinstance(v, dict):
        return _clean_doc(v)
    if isinstance(v, list):
        return [_clean_value(x) for x in v]
    if hasattr(v, "binary"):  # bson.Binary
        return repr(v)
    cls = type(v).__name__
    if cls in ("ObjectId", "UUID", "Decimal128"):
        return str(v)
    return v


def _clean_doc(d: dict) -> dict:
    return {k: _clean_value(v) for k, v in d.items()}


# --- connection (direct by default; optional SSH tunnel, like mongo_query.py) -----------

def split_mongo_uri(uri: str) -> tuple[str, int]:
    parsed = urlparse(uri)
    if parsed.scheme not in ("mongodb", "mongodb+srv"):
        die(f"unsupported mongo URI scheme: {parsed.scheme!r}")
    if "," in (parsed.netloc or ""):
        die("multi-host mongodb URIs (replica-set lists in URI) not supported by the tunnel layer")
    host = parsed.hostname
    if not host:
        die(f"could not parse host from URI")
    return host, parsed.port or 27017


def rewrite_uri_to_local(uri: str, local_port: int) -> str:
    parsed = urlparse(uri)
    userinfo = ""
    if parsed.username is not None:
        userinfo = parsed.username
        if parsed.password is not None:
            userinfo += f":{parsed.password}"
        userinfo += "@"
    return urlunparse(parsed._replace(netloc=f"{userinfo}127.0.0.1:{local_port}"))


@contextmanager
def maybe_tunnel(uri: str, use_tunnel: bool) -> Iterator[str]:
    """Yield a connectable URI. With --tunnel, opens an SSH forward and rewrites the host."""
    if not use_tunnel:
        yield uri
        return
    try:
        from sshtunnel import SSHTunnelForwarder  # type: ignore
    except ImportError:
        die("sshtunnel required for --tunnel (pip install sshtunnel paramiko)")
    host, port = split_mongo_uri(uri)
    forwarder = SSHTunnelForwarder(
        (env_required("SSH_HOST"), env_int("SSH_PORT", 22)),
        ssh_username=env_required("SSH_USER"),
        ssh_password=env_required("SSH_PASS"),
        remote_bind_address=(host, port),
        set_keepalive=15,
    )
    forwarder.start()
    try:
        yield rewrite_uri_to_local(uri, forwarder.local_bind_port)
    finally:
        forwarder.stop()


def connect(uri: str):
    try:
        from pymongo import MongoClient  # type: ignore
    except ImportError:
        die("pymongo required (pip install pymongo)")
    return MongoClient(uri, serverSelectionTimeoutMS=10_000, socketTimeoutMS=30_000)


def is_candidate(name: str) -> bool:
    low = name.lower()
    return any(re.search(p, low) for p in CANDIDATE_PATTERNS)


# --- commands ---------------------------------------------------------------------------

def cmd_discover(client) -> dict:
    """Inventory non-system DBs + collections, flag ownership candidates, sample them."""
    out: dict[str, Any] = {"op": "discover", "databases": {}, "candidates": []}
    for dbn in client.list_database_names():
        if dbn in BLOCKED_DATABASES:
            continue
        db = client[dbn]
        try:
            colls = db.list_collection_names()
        except Exception as e:  # permissions, etc.
            out["databases"][dbn] = {"error": str(e)[:150]}
            continue
        out["databases"][dbn] = sorted(colls)
        for c in colls:
            if not is_candidate(c):
                continue
            entry: dict[str, Any] = {"db": dbn, "collection": c}
            try:
                col = db[c]
                entry["count"] = col.count_documents({}, maxTimeMS=20_000)
                entry["sample"] = [_clean_doc(d) for d in col.find({}, limit=SAMPLE_DOCS)]
            except Exception as e:
                entry["error"] = str(e)[:150]
            out["candidates"].append(entry)
    return out


def cmd_dump(client, specs: list[str], filter_: dict) -> dict:
    """Export full rows for each `db:collection` spec (read-only find)."""
    out: dict[str, Any] = {"op": "dump", "collections": {}}
    for spec in specs:
        if ":" not in spec:
            die(f"bad --collections entry {spec!r} — expected db:collection")
        dbn, cn = spec.split(":", 1)
        if dbn in BLOCKED_DATABASES:
            die(f"database {dbn!r} is blocked")
        col = client[dbn][cn]
        docs = [_clean_doc(d) for d in col.find(filter_, limit=DUMP_CAP)]
        out["collections"][spec] = {"count": len(docs), "rows": docs, "capped_at": DUMP_CAP}
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Re-sync team ownership from the Mongo warehouse (read-only).")
    p.add_argument("--discover", action="store_true", help="Inventory DBs/collections and flag ownership candidates.")
    p.add_argument("--dump", action="store_true", help="Export rows for --collections as JSON.")
    p.add_argument("--collections", help="Comma-separated db:collection list to dump (e.g. AlocetSystem:viewReleaseTeam,...).")
    p.add_argument("--filter", default="{}", help="JSON filter for --dump (default: all rows). e.g. '{\"isActive\":true}'.")
    p.add_argument("--tunnel", action="store_true", help="Connect via SSH tunnel (SSH_* env) instead of direct.")
    p.add_argument("--uri-env", default="MONGO_URI_WAREHOUSE", help="Env var holding the mongo URI (default MONGO_URI_WAREHOUSE).")
    args = p.parse_args()

    if not (args.discover or args.dump):
        die("pass --discover or --dump (see --help)")
    if args.dump and not args.collections:
        die("--dump requires --collections db:coll[,db:coll...]")

    uri = os.environ.get(args.uri_env)
    if not uri:
        die(f"{args.uri_env} env var is required (the full mongo URI; never pass the password on the CLI)")

    try:
        filter_ = json.loads(args.filter)
    except json.JSONDecodeError as e:
        die(f"bad JSON in --filter: {e}")

    with maybe_tunnel(uri, args.tunnel) as conn_uri:
        client = connect(conn_uri)
        try:
            # Fail fast with a clear message if the host is unreachable.
            client.admin.command("ping")
            if args.discover:
                result = cmd_discover(client)
            else:
                specs = [s.strip() for s in args.collections.split(",") if s.strip()]
                result = cmd_dump(client, specs, filter_)
        finally:
            client.close()

    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
