#!/usr/bin/env bash
# V side of the I/M bootstrap/migration contract. Values contain identity, no credentials.
admit_privileged_target() {
  local directory="$1" proof name oid identity
  proof="$("${COMPOSE[@]}" exec -T "$APP_SERVICE" python -c \
    "$(cat "$directory/restore-database-identity.py")" --active-proof)" || return
  proof="${proof//$'\r'/}"
  IFS='|' read -r name oid identity <<< "$proof"
  [[ "$name" =~ ^[A-Za-z_][A-Za-z0-9_$]{0,62}$ && "$oid" =~ ^[1-9][0-9]*$ \
     && "$identity" =~ ^[0-9a-f]{8}-([0-9a-f]{4}-){3}[0-9a-f]{12}$ \
     && "$proof" == "$name|$oid|$identity" ]] || return 1
  export SPACEWORKS_PRIVILEGED_TARGET_NAME="$name"
  export SPACEWORKS_PRIVILEGED_TARGET_OID="$oid"
  export SPACEWORKS_PRIVILEGED_TARGET_UUID="$identity"
  export SPACEWORKS_PRIVILEGED_TARGET_REQUIRED=1
}
