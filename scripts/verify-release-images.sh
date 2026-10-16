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
for package in spaceworks-backend spaceworks-frontend; do
  image="ghcr.io/${owner}/${package}:${tag}"
  echo "Verifying ${image}"
  for platform in linux/amd64 linux/arm64; do
    if ! docker pull --platform "$platform" "$image"; then
      echo "::error::Published release image cannot be pulled for $platform: ${image}" >&2
      failed=1
    fi
  done
done

exit "$failed"
