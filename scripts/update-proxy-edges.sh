#!/usr/bin/env bash
# Atomic bundle renames leave individual bind mounts on the old inode. Recreate
# edges even when Compose sees unchanged YAML, on both update and image rollback.
refresh_update_proxy_edges() {
  local layer="${SPACEWORKS_COMPOSE_LAYER:-}" edge=frontend
  if [[ -z "$layer" && -f "$ROOT/.spaceworks-layer" ]]; then
    layer="$(tr -d '[:space:]' < "$ROOT/.spaceworks-layer")"
  fi
  [[ "$(deployment_value SPACEWORKS_RUN_FRONTEND)" != no ]] || edge=api-edge
  "${COMPOSE[@]}" up -d --no-deps --force-recreate "$edge" || return
  if [[ "$layer" == *tls || "$layer" == *saas ]]; then
    "${COMPOSE[@]}" up -d --no-deps --force-recreate caddy || return
  fi
}
