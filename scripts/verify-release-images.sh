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

native_platform=$(docker version --format '{{.Server.Os}}/{{.Server.Arch}}')
case "$native_platform" in
  linux/amd64|linux/arm64) ;;
  *) echo "Unsupported verification platform: $native_platform" >&2; exit 2 ;;
esac

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
  if [[ "$package" == spaceworks-backend ]]; then
    if ! docker run --rm --platform "$native_platform" --user 0:0 --entrypoint python "$image" \
      /app/scripts/install_producer_capability.py --help; then
      echo "::error::Published backend installer smoke check failed: ${image}" >&2
      failed=1
    fi
  fi
done

exit "$failed"
