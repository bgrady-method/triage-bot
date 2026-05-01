"""MongoDB query runner (read-only) over an SSH tunnel.

Mirrors the connection model in `method-db-tools/scripts/mongo_safety.py`
(URI from connections.json, mongosh subprocess), adapted for the cloud
routine: pymongo instead of mongosh, SSH tunnel instead of direct VPN.

Read-only by design:
  - Only `find`, `aggregate`, `count_documents`, `distinct` are exposed.
  - `--account` selects the database (mirrors the skill's `<uri>/<account>`
    pattern from mongo_safety.py:262).
  - Hard cap of 100 docs per result (mirrors mongo_tier_policies.production.default_limit).
  - Server-side query timeout 30s (mirrors mongo_tier_policies.production.query_timeout_seconds).
  - Blocked databases (admin, config, local) are rejected up-front, mirroring
    mongo_tier_policies.production.blocked_databases.

Auth via env vars / routine secrets:
  SSH_HOST / SSH_PORT / SSH_USER / SSH_PASS    — bastion (same as sql_query.py)
  MONGO_URI_<NAME>                              — full mongo URI for connection NAME
                                                  (e.g. MONGO_URI_WAREHOUSE,
                                                   MONGO_URI_RETAIL, MONGO_URI_DELTA, ...)

The URI's host:port is the *remote* target of the SSH tunnel. The script extracts
host:port from the URI, opens a tunnel, then reconnects via pymongo through the
local forwarded port (rewriting the host portion of the URI to 127.0.0.1:<local-port>).

Usage:
  python mongo_query.py --connection warehouse --account 12345 --op find \\
    --collection users --filter '{"email":"a@b.com"}'
  python mongo_query.py --connection warehouse --account 12345 --op count \\
    --collection users --filter '{}'
  python mongo_query.py --list
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from typing import Any, Iterator
from urllib.parse import urlparse, urlunparse

BLOCKED_DATABASES = {"admin", "config", "local"}
DEFAULT_LIMIT = 100
TIMEOUT_SECONDS = 30


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


def list_connections() -> dict[str, str]:
    """Discover available connections from MONGO_URI_* env vars."""
    return {
        k[len("MONGO_URI_"):].lower(): v
        for k, v in os.environ.items()
        if k.startswith("MONGO_URI_") and v
    }


def split_mongo_uri(uri: str) -> tuple[str, int, str]:
    """Pull (host, port, uri-with-host-replaced-by-placeholder) from a Mongo URI.

    `urlparse` doesn't natively understand mongodb:// hosts with auth + port +
    path the way pymongo does, so this is a small careful split.
    """
    parsed = urlparse(uri)
    if parsed.scheme not in ("mongodb", "mongodb+srv"):
        die(f"unsupported mongo URI scheme: {parsed.scheme!r}")
    if "," in (parsed.netloc or ""):
        die("multi-host mongodb URIs (replica-set lists in URI) not supported by the tunnel layer")

    host = parsed.hostname
    if not host:
        die(f"could not parse host from {uri!r}")
    port = parsed.port or 27017
    return host, port, uri


def rewrite_uri_to_local(uri: str, local_port: int) -> str:
    """Replace the host:port in a mongo URI with 127.0.0.1:<local_port>."""
    parsed = urlparse(uri)
    userinfo = ""
    if parsed.username is not None:
        userinfo = parsed.username
        if parsed.password is not None:
            userinfo += f":{parsed.password}"
        userinfo += "@"
    new_netloc = f"{userinfo}127.0.0.1:{local_port}"
    return urlunparse(parsed._replace(netloc=new_netloc))


@contextmanager
def ssh_tunnel(remote_host: str, remote_port: int) -> Iterator[int]:
    try:
        from sshtunnel import SSHTunnelForwarder  # type: ignore
    except ImportError:
        die("sshtunnel required (pip install sshtunnel paramiko)")

    forwarder = SSHTunnelForwarder(
        (env_required("SSH_HOST"), env_int("SSH_PORT", 22)),
        ssh_username=env_required("SSH_USER"),
        ssh_password=env_required("SSH_PASS"),
        remote_bind_address=(remote_host, remote_port),
        set_keepalive=15,
    )
    forwarder.start()
    try:
        yield forwarder.local_bind_port
    finally:
        forwarder.stop()


def run_query(uri: str, account: str, op: str, collection: str, filter_: dict, projection: dict | None,
              sort: list | None, limit: int) -> dict:
    try:
        from pymongo import MongoClient  # type: ignore
    except ImportError:
        die("pymongo required (pip install pymongo)")

    client = MongoClient(uri, serverSelectionTimeoutMS=10_000, socketTimeoutMS=TIMEOUT_SECONDS * 1000)
    try:
        db = client[account]
        col = db[collection]
        if op == "find":
            cur = col.find(filter_, projection or None)
            if sort:
                cur = cur.sort(sort)
            cur = cur.limit(limit)
            docs = [_clean_doc(d) for d in cur]
            return {"op": "find", "count": len(docs), "docs": docs, "truncated_to": limit}
        if op == "count":
            n = col.count_documents(filter_, maxTimeMS=TIMEOUT_SECONDS * 1000)
            return {"op": "count", "count": n}
        if op == "distinct":
            field = filter_.get("$field") or filter_.get("field")
            if not field:
                die('distinct requires `--filter \'{"field":"<fieldname>"}\'`')
            actual_filter = {k: v for k, v in filter_.items() if k not in ("field", "$field")}
            values = col.distinct(field, actual_filter)
            return {"op": "distinct", "field": field, "values": values[:limit], "truncated_to": limit}
        if op == "aggregate":
            pipeline = filter_.get("pipeline")
            if not isinstance(pipeline, list):
                die('aggregate requires `--filter \'{"pipeline":[{"$match":{...}}, ...]}\'`')
            # Reject any write stages
            write_stages = {"$out", "$merge"}
            for stage in pipeline:
                if not isinstance(stage, dict):
                    die("each pipeline stage must be a dict")
                if write_stages & set(stage.keys()):
                    die(f"write stages forbidden: {write_stages & set(stage.keys())}")
            pipeline.append({"$limit": limit})
            docs = [_clean_doc(d) for d in col.aggregate(pipeline, maxTimeMS=TIMEOUT_SECONDS * 1000)]
            return {"op": "aggregate", "count": len(docs), "docs": docs, "truncated_to": limit}
        die(f"unknown op: {op}")
    finally:
        client.close()


def _clean_doc(d: dict) -> dict:
    """Make a Mongo document JSON-serializable (ObjectId -> str, datetime -> isoformat)."""
    out = {}
    for k, v in d.items():
        out[k] = _clean_value(v)
    return out


def _clean_value(v: Any) -> Any:
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if isinstance(v, dict):
        return _clean_doc(v)
    if isinstance(v, list):
        return [_clean_value(x) for x in v]
    if hasattr(v, "binary"):  # bson.Binary
        return repr(v)
    # ObjectId, UUID, etc — str() them
    cls = type(v).__name__
    if cls in ("ObjectId", "UUID", "Decimal128"):
        return str(v)
    return v


def main() -> int:
    p = argparse.ArgumentParser(description="Run a read-only Mongo query over an SSH tunnel.")
    p.add_argument("--list", action="store_true", help="List available connections (from MONGO_URI_* env) and exit.")
    p.add_argument("--connection", help="Connection name (e.g. warehouse, retail, delta). Resolves MONGO_URI_<NAME>.")
    p.add_argument("--account", help="Mongo database to query (the Method account / customer DB).")
    p.add_argument("--op", choices=["find", "count", "distinct", "aggregate"])
    p.add_argument("--collection", help="Collection name.")
    p.add_argument("--filter", default="{}", help="JSON filter (find/count/distinct) or {'pipeline':[...]} for aggregate.")
    p.add_argument("--projection", default=None, help="JSON projection for find. Optional.")
    p.add_argument("--sort", default=None, help='JSON list of [field, direction] pairs, e.g. [["createdAt", -1]].')
    p.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = p.parse_args()

    if args.list:
        conns = list_connections()
        if not conns:
            print("(no MONGO_URI_* env vars set)")
        else:
            for name in sorted(conns):
                # Don't print the URI itself — has embedded creds
                print(name)
        return 0

    if not (args.connection and args.account and args.op and args.collection):
        die("--connection, --account, --op, and --collection are all required (use --list to see connections)")

    if args.account.lower() in BLOCKED_DATABASES:
        die(f"database {args.account!r} is in the blocklist")

    uri = os.environ.get(f"MONGO_URI_{args.connection.upper()}")
    if not uri:
        die(f"no MONGO_URI_{args.connection.upper()} env var set")

    try:
        filter_ = json.loads(args.filter)
        projection = json.loads(args.projection) if args.projection else None
        sort = json.loads(args.sort) if args.sort else None
    except json.JSONDecodeError as e:
        die(f"bad JSON in --filter/--projection/--sort: {e}")

    limit = max(1, min(args.limit, DEFAULT_LIMIT))   # cap at DEFAULT_LIMIT regardless of input

    remote_host, remote_port, _ = split_mongo_uri(uri)

    with ssh_tunnel(remote_host, remote_port) as local_port:
        local_uri = rewrite_uri_to_local(uri, local_port)
        result = run_query(local_uri, args.account, args.op, args.collection, filter_, projection, sort, limit)

    result["connection"] = args.connection
    result["account"] = args.account
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
