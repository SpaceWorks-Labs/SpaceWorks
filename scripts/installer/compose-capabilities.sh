#!/usr/bin/env bash
probe_compose_capabilities() (
  set -euo pipefail
  local probe
  probe="$(mktemp -d)" || return
  trap 'rm -rf -- "$probe"' EXIT
  printf 'services:\n  probe:\n    image: scratch\n    ports: ["54321:80"]\n    environment: {OLD: value}\n' > "$probe/base.yml" || return
  printf 'services:\n  probe:\n    ports: !reset []\n    environment: !override {ONLY: replacement}\n' > "$probe/overlay.yml" || return
  docker compose -p spaceworks-feature-probe -f "$probe/base.yml" -f "$probe/overlay.yml" \
    config --format json > "$probe/config.json" || return
  if command -v python3 >/dev/null 2>&1; then
    python3 "$ROOT/scripts/installer/compose-capabilities.py" < "$probe/config.json" || return
  else
    docker run --rm -i --network none --read-only --entrypoint python \
      "$HOST_CONFIG_IMAGE" -c "$(cat "$ROOT/scripts/installer/compose-capabilities.py")" < "$probe/config.json" || return
  fi
  local help flag
  help="$(docker compose up --help)" || return
  for flag in --wait --no-deps --force-recreate --remove-orphans; do
    [[ "$help" == *"$flag"* ]] || { echo "Compose up lacks required $flag." >&2; return 64; }
  done
)
