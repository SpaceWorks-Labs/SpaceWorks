#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || -z "$1" ]]; then
  echo "Usage: GHCR_OWNER=<owner> $0 <tag>" >&2
  exit 2
fi

tag="$1"
owner="${GHCR_OWNER:-${GITHUB_REPOSITORY_OWNER:-}}"
if [[ -z "$owner" ]]; then
  echo "GHCR_OWNER or GITHUB_REPOSITORY_OWNER must identify the image owner." >&2
  exit 2
fi

failed=0
for package in spaceworks-backend spaceworks-frontend spaceworks-allinone; do
  image="ghcr.io/${owner}/${package}:${tag}"
  echo "Verifying ${image}"
  if ! docker pull "$image"; then
    echo "::error::Published release image cannot be pulled: ${image}" >&2
    failed=1
  elif [[ "$package" == spaceworks-backend ]]; then
    if ! docker run --rm --user 0:0 --entrypoint python "$image" \
      /app/scripts/install_producer_capability.py --help; then
      echo "::error::Published backend installer smoke check failed: ${image}" >&2
      failed=1
    fi
  fi
done

exit "$failed"
