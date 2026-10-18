#!/usr/bin/env bash
# Noninteractive inputs are data. They never pass through source/eval or argv.
load_noninteractive_answers() {
  local path="$1" transport key value
  [[ ${BASH_VERSINFO[0]} -ge 4 ]] || { echo 'Modern Bash 4.4+ is required.' >&2; return 64; }
  declare -gA INPUT_ANSWERS=() INPUT_USED=()
  transport="$(mktemp)" || return
  chmod 600 "$transport"
  python3 "$ROOT/scripts/installer/private_files.py" secure "$transport" || { rm -f -- "$transport"; return 64; }
  if ! python3 "$ROOT/scripts/installer/answers.py" "$path" > "$transport"; then
    rm -f -- "$transport"; return 64
  fi
  while IFS= read -r -d '' key && IFS= read -r -d '' value; do
    INPUT_ANSWERS["$key"]="$value"
  done < "$transport"
  rm -f -- "$transport"
  SETUP_NON_INTERACTIVE=1
}

check_unused_answers() {
  local key
  [[ "${SETUP_NON_INTERACTIVE:-0}" == 1 ]] || return 0
  for key in "${!INPUT_ANSWERS[@]}"; do
    [[ -n "${INPUT_USED[$key]:-}" ]] || { echo "Unknown or inapplicable answer: $key" >&2; return 64; }
  done
}
