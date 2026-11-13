#!/usr/bin/env bash
# Operator entry point; no secrets are stored in this script.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
umask 077
command="${1:-help}"
if (( $# )); then shift; fi
case "$command" in
  init) exec python3 -m arena init "$@" ;;
  doctor) exec python3 -m arena doctor "$@" ;;
  teams) exec python3 scripts/create_teams.py "$@" ;;
  team) exec python3 scripts/create_team.py "$@" ;;
  cards) exec python3 scripts/export_login_cards.py "$@" ;;
  run) if (( $# )); then echo "Set PORT, SLOTS and ARENA_ORIGIN as environment variables." >&2; exit 2; fi; exec bash scripts/run_contest.sh ;;
  backup) exec python3 scripts/backup_contest.py "$@" ;;
  help|-h|--help) echo "Usage: bash scripts/contest.sh {init|doctor|teams N|team USER NAME|cards CSV|run|backup --stopped --output DIR} [options]" ;;
  *) echo "Unknown command. Run: bash scripts/contest.sh help" >&2; exit 2 ;;
esac
