#!/usr/bin/env bash
# Frontend mode: Full (web app + API) or API-only (backend for mobile apps and integrations).
# The installed dotenv records it once as SPACEWORKS_RUN_FRONTEND=yes|no; compose, update,
# rollback and the control-plane switch already read that key, so no second key is written.
# `--frontend full|api-only` or SPACEWORKS_FRONTEND=full|api-only pre-answers the question.

frontend_mode_answer() {
  case "$1" in
    full) printf '1' ;;
    api-only) printf '2' ;;
    *) return 64 ;;
  esac
}

# Sets RUN_FRONTEND from the preset. Returns 1 when there is no preset (ask the question).
frontend_preset() {
  local preset="${SPACEWORKS_FRONTEND:-}" answer given
  [[ -n "$preset" ]] || return 1
  answer="$(frontend_mode_answer "$preset")" || { echo 'Use --frontend full or --frontend api-only (SPACEWORKS_FRONTEND).' >&2; return 64; }
  # A noninteractive answers file may also name RUN_FRONTEND; it must agree with the preset.
  if [[ "${SETUP_NON_INTERACTIVE:-0}" == 1 && -n "${INPUT_ANSWERS[RUN_FRONTEND]+present}" ]]; then
    given="${INPUT_ANSWERS[RUN_FRONTEND]}"
    [[ "$given" == "$answer" ]] || { echo 'RUN_FRONTEND in the answers file disagrees with --frontend.' >&2; return 64; }
    INPUT_USED[RUN_FRONTEND]=1
  fi
  RUN_FRONTEND="$answer"
}

frontend_mode_label() {
  [[ "$1" == 1 ]] && printf 'Full (web app + API)' || printf 'API-only (no web app on this server)'
}
