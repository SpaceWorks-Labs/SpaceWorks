#!/usr/bin/env bash
# Use the running installation only to validate data; execute the selected tooling.
handoff_release_bundle() {
  [[ "${SPACEWORKS_SELECTED_BUNDLE_VERSION:-}" != "$version" || "$UPDATE_SCRIPT_DIR" == "$ROOT/scripts" ]] || return 0
  command -v tar >/dev/null 2>&1 || die "tar is required to install the selected host bundle."
  local commit archive stage status
  commit="$(curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
    --connect-timeout 10 --max-time 30 --retry 2 \
    "https://api.github.com/repos/$SPACEWORKS_REPOSITORY/commits/v$version" | \
    "${COMPOSE[@]}" exec -T "$APP_SERVICE" python -c \
    "$(cat "$UPDATE_SCRIPT_DIR/release-host-bundle.py")" commit "${version##*.}")" \
    || die 'Could not prove the selected release commit.'
  commit="$(printf '%s' "$commit" | tr -d '\r\n')"
  [[ "$commit" =~ ^[0-9a-f]{40}$ ]] || die 'Invalid selected release commit.'
  BUNDLE_STAGE="$(mktemp -d "$ROOT/.spaceworks-update.XXXXXX")"
  archive="$BUNDLE_STAGE/release.tar.gz"; stage="$BUNDLE_STAGE/runtime"
  mkdir "$stage"
  curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
    --connect-timeout 10 --max-time 300 --retry 2 --max-filesize 100000000 \
    "https://github.com/$SPACEWORKS_REPOSITORY/archive/$commit.tar.gz" -o "$archive" \
    || die 'Could not download the selected release host bundle.'
  "${COMPOSE[@]}" exec -T "$APP_SERVICE" python -c \
    "$(cat "$UPDATE_SCRIPT_DIR/release-host-bundle.py")" archive "${version%%-main.*}" < "$archive" \
    || die 'Selected release host bundle is invalid; installation was not changed.'
  tar -xzf "$archive" -C "$stage" --strip-components=1 --no-same-owner
  # Validate the complete runtime manifest before executing any downloaded code.
  validate_host_bundle "$stage"
  say "Continuing with host tooling from $SPACEWORKS_REPOSITORY v$version."
  release_update_lock
  if command -v flock >/dev/null 2>&1; then flock -u 8; exec 8>&-; fi
  status=0
  local arguments=(${UPDATE_ARGUMENTS[@]+"${UPDATE_ARGUMENTS[@]}"})
  [[ -n "$REQUESTED_VERSION" ]] || arguments+=(--version "$version")
  SPACEWORKS_SELECTED_BUNDLE_VERSION="$version" SPACEWORKS_REPOSITORY="$SPACEWORKS_REPOSITORY" \
    bash "$stage/scripts/update.sh" "${arguments[@]}" || status=$?
  exit "$status"
}

refuse_release_downgrade() {
  [[ -n "$current" ]] || return 0
  local current_run selected_run index comparison
  local current_base=() selected_base=()
  [[ "$current" =~ ^[0-9]+\.[0-9]+\.[0-9]+-main\.([0-9]+)\.[0-9a-f]{12}$ ]] \
    || die 'Installed version is unrecognized; refusing an unproven upgrade.'
  current_run="${BASH_REMATCH[1]}"
  [[ "$version" =~ -main\.([0-9]+)\. ]] || die 'Invalid selected release.'
  selected_run="${BASH_REMATCH[1]}"
  IFS=. read -ra current_base <<< "${current%%-main.*}"
  IFS=. read -ra selected_base <<< "${version%%-main.*}"
  for index in 0 1 2; do
    comparison="$(compare_release_decimal "${selected_base[index]}" "${current_base[index]}")"
    [[ "$comparison" != -1 ]] || die "Refusing release downgrade: $current -> $version."
    [[ "$comparison" == 0 ]] || break
  done
  [[ "$(compare_release_decimal "$selected_run" "$current_run")" == 1 ]] \
    || die "Refusing release downgrade or conflicting run: $current -> $version. Use the recovery procedure for rollback."
}

compare_release_decimal() {
  local selected_run="$1" current_run="$2"
  # Decimal string comparison avoids overflow and octal interpretation.
  current_run="$(printf '%s' "$current_run" | sed 's/^0*//')"; current_run="${current_run:-0}"
  selected_run="$(printf '%s' "$selected_run" | sed 's/^0*//')"; selected_run="${selected_run:-0}"
  if [[ "$selected_run" == "$current_run" ]]; then
    echo 0
  elif (( ${#selected_run} < ${#current_run} )) || \
    { (( ${#selected_run} == ${#current_run} )) && [[ "$selected_run" < "$current_run" ]]; }; then
    echo -1
  else
    echo 1
  fi
}
