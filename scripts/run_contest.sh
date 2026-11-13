#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
umask 077
: "${ARENA_ORIGIN:?Set ARENA_ORIGIN to the URL students will use, e.g. http://192.168.1.10:8000}"
export ARENA_DATA="${ARENA_DATA:-$PWD/var}"
export ARENA_ORIGIN
exec python3 -m arena --data "$ARENA_DATA" serve --host 0.0.0.0 --port "${PORT:-8000}" --with-worker --slots "${SLOTS:-6}"
