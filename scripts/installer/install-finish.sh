#!/usr/bin/env bash
run_installed() {
  local command="$1" input=/dev/tty script quoted
  [[ "${SETUP_NON_INTERACTIVE:-0}" != 1 ]] || input=/dev/null
  if [[ "$RUN_INSTALLED_AS_ROOT" == 1 ]]; then
    source "$STAGE_DIR/scripts/installer/environment-continuity.sh"
    local preserve_args=()
    preserve_installer_environment
    if [[ -n "$INSTALLER_PRESERVED_NAMES" && ${#RUN_ROOT[@]} -gt 0 ]]; then
      preserve_args+=("--preserve-env=$INSTALLER_PRESERVED_NAMES")
    fi
    ${RUN_ROOT[@]+"${RUN_ROOT[@]}"} "${preserve_args[@]}" bash -c "cd '$INSTALL_DIR' && $command" < "$input"
  elif [[ "$USE_DOCKER_GROUP" == 1 ]]; then
    script="cd '$INSTALL_DIR' && $command"
    quoted="${script//\'/\'\\\'\'}"
    sg docker -c "bash -c '$quoted'" < "$input"
  else
    (cd "$INSTALL_DIR" && bash -c "$command" < "$input")
  fi
}
if [[ "$ACTION" == modules ]]; then
  run_installed 'bash scripts/update.sh --modules-only'
  exit 0
fi
${RUN_ROOT[@]+"${RUN_ROOT[@]}"} chmod 755 "$STAGE_DIR/install.sh" "$STAGE_DIR/scripts/spaceworks-compose.sh"
# Re-entry uses the pinned release's updater/helpers, never an older installed updater.
case "$ACTION" in
  update) update_options="--force --no-module-changes" ;;
  modules) update_options="--modules-only" ;;
  both) update_options="--force --modules" ;;
esac
if [[ "$ACTION" != fresh && "$ACTION" != resume ]]; then
  update_options+=" --version '$VERSION'"
  run_installed "SPACEWORKS_REPOSITORY='$REPOSITORY' SPACEWORKS_UPDATE_INSTALL_DIR='$INSTALL_DIR' bash '$STAGE_DIR/scripts/update.sh' $update_options"
  exit 0
fi
if [[ "$ACTION" == fresh ]]; then
probe_command='source "$ROOT/scripts/installer/compose-capabilities.sh"; probe_compose_capabilities'
probe_image="${MAKERSPACE_BACKEND_IMAGE:-ghcr.io/spaceworks-labs/spaceworks-backend}:$VERSION"
if [[ "$RUN_INSTALLED_AS_ROOT" == 1 ]]; then
  ${RUN_ROOT[@]+"${RUN_ROOT[@]}"} env ROOT="$STAGE_DIR" HOST_CONFIG_IMAGE="$probe_image" bash -c "$probe_command" || die 'Compose cannot apply the required overlays.'
elif [[ "$USE_DOCKER_GROUP" == 1 ]]; then
  ROOT="$STAGE_DIR" HOST_CONFIG_IMAGE="$probe_image" sg docker -c "bash -c '$probe_command'" || die 'Compose cannot apply the required overlays.'
else
  ROOT="$STAGE_DIR" HOST_CONFIG_IMAGE="$probe_image" bash -c "$probe_command" || die 'Compose cannot apply the required overlays.'
fi
if [[ "${EMPTY_INSTALL_DIR:-0}" == 1 ]]; then ${RUN_ROOT[@]+"${RUN_ROOT[@]}"} rmdir -- "$INSTALL_DIR"; fi
parent="$(dirname "$INSTALL_DIR")"
if [[ ! -d "$parent" ]]; then ${RUN_ROOT[@]+"${RUN_ROOT[@]}"} mkdir -p -- "$parent"; CREATED_PARENT=1; fi
# Temporary storage may be on another filesystem; keep answers private during copying.
${RUN_ROOT[@]+"${RUN_ROOT[@]}"} bash -c 'umask 077; mkdir -- "$1"' _ "$INSTALL_DIR"
${RUN_ROOT[@]+"${RUN_ROOT[@]}"} python3 "$STAGE_DIR/scripts/installer/private_files.py" secure-directory "$INSTALL_DIR"
if [[ "$(id -u)" != 0 && ${#RUN_ROOT[@]} -gt 0 ]]; then
  ${RUN_ROOT[@]+"${RUN_ROOT[@]}"} chown "$(id -u):$(id -g)" "$INSTALL_DIR"
fi
run_installed "python3 '$STAGE_DIR/scripts/installer/state.py' prepare --root '$INSTALL_DIR' --repository '$REPOSITORY' --release '$VERSION' --source '$STAGE_DIR'"
fi
copy_phase="$(python3 "$STAGE_DIR/scripts/installer/state.py" status --root "$INSTALL_DIR" --repository "$REPOSITORY" --release "$VERSION")"
if [[ "$copy_phase" == copying ]]; then
  run_installed "python3 '$STAGE_DIR/scripts/installer/state.py' validate-source --root '$INSTALL_DIR' --repository '$REPOSITORY' --release '$VERSION' --source '$STAGE_DIR'"
  run_installed "python3 '$STAGE_DIR/scripts/installer/state.py' restore-answers --root '$INSTALL_DIR' --repository '$REPOSITORY' --release '$VERSION'"
  ${RUN_ROOT[@]+"${RUN_ROOT[@]}"} cp -a -- "$STAGE_DIR/." "$INSTALL_DIR/"
  if [[ "$(id -u)" != 0 && ${#RUN_ROOT[@]} -gt 0 ]]; then
    ${RUN_ROOT[@]+"${RUN_ROOT[@]}"} chown "$(id -u):$(id -g)" "$INSTALL_DIR"
  fi
  run_installed "python3 '$STAGE_DIR/scripts/installer/state.py' phase --root '$INSTALL_DIR' --repository '$REPOSITORY' --release '$VERSION' --phase copied"
fi
if [[ "${SPACEWORKS_DEPLOYMENT_PROFILE:-full}" == free ]]; then
  # The opt-in free profile was confirmed above; setup writes its environment and
  # notice only. No host stack, version marker or managed-file record is created.
  run_installed "SPACEWORKS_DEPLOYMENT_PROFILE=free SPACEWORKS_REPOSITORY='$REPOSITORY' bash setup.sh --non-interactive"
  say "Prepared the free profile in $INSTALL_DIR; follow docs/deploy/cloud-free.md to launch it."
  exit 0
fi
run_installed "SPACEWORKS_INSTALL_REPOSITORY_PINNED=1 SPACEWORKS_REPOSITORY='$REPOSITORY' MAKERSPACE_IMAGE_TAG='$VERSION' bash setup.sh"
${RUN_ROOT[@]+"${RUN_ROOT[@]}"} rm -f -- "$INSTALL_DIR/.spaceworks-answers"
run_installed "printf '%s\\n' '$VERSION' > .spaceworks-version"
run_installed "project_name=\$(bash scripts/spaceworks-compose.sh bundled config --format json | python3 scripts/installer/project-name.py) || exit 1; source scripts/install-host-bundle.sh; host_bundle_files; printf '%s\\n' \"\${HOST_BUNDLE_FILES[@]}\" | python3 scripts/installer/managed-files.py '$INSTALL_DIR' '$INSTALL_DIR/.spaceworks-release.json' \"\$project_name\""
say "Installed SpaceWorks $VERSION in $INSTALL_DIR."
