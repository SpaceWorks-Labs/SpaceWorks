#!/usr/bin/env bash
# Build the installer assets of one release into OUT_DIR (run by the release workflow):
#   install.sh                     the standalone installer (scripts/installer/standalone-install.sh)
#   spaceworks-<version>.tar.gz    the deploy bundle: exactly the host files the installer needs
#   release.json                   {"version", "commit"} for the tooling inside the bundle
#   SHA256SUMS                     checksums of the three files above (signed by the workflow)
# Usage: bash scripts/release-assets.sh <version> <40-hex commit> <out-dir>
set -euo pipefail
version="${1:?version}"; commit="${2:?commit}"; out="${3:?out dir}"
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+-main\.[0-9]+\.[0-9a-f]{12}$ ]] || { echo "Bad version: $version" >&2; exit 64; }
[[ "$commit" =~ ^[0-9a-f]{40}$ && "$commit" == "${version##*.}"* ]] || { echo "Commit does not match the version suffix." >&2; exit 64; }
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
source scripts/install-host-bundle.sh
host_bundle_files
for relative in "${HOST_BUNDLE_FILES[@]}" scripts/installer/standalone-install.sh; do
  [[ -f "$relative" ]] || { echo "Missing bundle file: $relative" >&2; exit 1; }
done
[[ "$(tr -d '[:space:]' < VERSION)" == "${version%%-main.*}" ]] || { echo 'VERSION differs from the release version.' >&2; exit 1; }
mkdir -p "$out"
stage="$(mktemp -d)"; trap 'rm -rf -- "$stage"' EXIT
name="spaceworks-$version"
mkdir "$stage/$name"
printf '%s\n' "${HOST_BUNDLE_FILES[@]}" | tar -cf - -T - | tar -xf - -C "$stage/$name"
tar -C "$stage" --sort=name --owner=0 --group=0 --numeric-owner -czf "$out/$name.tar.gz" "$name"
cp scripts/installer/standalone-install.sh "$out/install.sh"
printf '{"version": "%s", "commit": "%s"}\n' "$version" "$commit" > "$out/release.json"
(cd "$out" && sha256sum install.sh "$name.tar.gz" release.json > SHA256SUMS)
echo "Built release assets in $out:"; ls -l "$out"
