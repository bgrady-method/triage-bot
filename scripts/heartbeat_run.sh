#!/usr/bin/env bash
# Wrapper that finds Python and runs the named script. Needed because the
# bash sandbox sees the WindowsApps python stub instead of the real
# C:\...\Python\Python312\python.exe that invoke-routine.ps1 puts on PATH.
set -euo pipefail

PY="/c/Users/MachineUser/AppData/Local/Programs/Python/Python312/python.exe"
if [[ ! -x "$PY" ]]; then
    echo "ERROR: python not found at $PY" >&2
    exit 2
fi

exec "$PY" "$@"
