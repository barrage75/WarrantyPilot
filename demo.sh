#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if ! command -v uv >/dev/null 2>&1; then
  printf '%s\n' 'Outil manquant : uv. Installation : https://docs.astral.sh/uv/' >&2
  exit 1
fi
export PYTHONUTF8=1
exec uv run --project backend python scripts/demo.py "$@"
