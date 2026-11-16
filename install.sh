#!/bin/sh
# Compatibility entry point. Older documentation points here:
#   curl -fsSL https://raw.githubusercontent.com/SpaceWorks-Labs/SpaceWorks/main/install.sh | bash
# The installer is now a release asset; this stub downloads the latest one and runs it,
# passing every option through. The whole body is one function so a truncated download
# runs nothing.
main() {
  set -eu
  repo="${SPACEWORKS_REPOSITORY:-SpaceWorks-Labs/SpaceWorks}"
  case $repo in */*) ;; *) echo "Invalid SPACEWORKS_REPOSITORY." >&2; exit 64 ;; esac
  command -v curl >/dev/null 2>&1 || { echo 'curl is required.' >&2; exit 1; }
  tmp=$(mktemp "${TMPDIR:-/tmp}/.spaceworks-install.XXXXXX")
  trap 'rm -f -- "$tmp"' EXIT
  curl -fsSL --proto '=https' --tlsv1.2 --retry 3 -o "$tmp" \
    "https://github.com/$repo/releases/latest/download/install.sh" \
    || { echo 'Could not download the SpaceWorks installer from the latest release.' >&2; exit 1; }
  sh "$tmp" "$@"
}
main "$@"
