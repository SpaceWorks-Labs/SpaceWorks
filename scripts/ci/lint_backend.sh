#!/usr/bin/env bash
# Backend error lint: syntax errors, undefined names, redefinitions and repeated dict
# keys. Not style -- the full rule set stays a local editor config (ruff.toml is
# gitignored), so this runs --isolated with the rules spelled out here. Shared by the
# Checks workflow and .githooks/pre-push. Takes about two seconds.
#
# config/settings.py merges its section modules into globals(), which static analysis
# cannot follow, so undefined-name is ignored in that one file.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)/backend"

version=0.17.4
args=(check --isolated --select E9,F63,F7,F82,F811,F601
  --per-file-ignores "config/settings.py:F821"
  apps config scripts manage.py)

if python -m ruff --version 2>/dev/null | grep -qx "ruff $version"; then
  python -m ruff "${args[@]}"
elif command -v pipx >/dev/null 2>&1; then
  pipx run "ruff==$version" "${args[@]}"
else
  echo "ruff $version is needed: python -m pip install ruff==$version" >&2
  exit 1
fi
