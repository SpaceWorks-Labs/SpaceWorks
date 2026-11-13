#!/bin/sh
# Usage: sh scripts/bump-version.sh <new-version>
# Updates VERSION, backend/config/settings_schema.py, the OpenAPI snapshot info.version and the
# README badge, and creates docs/release-<new-version>.md from a template when missing.
# Refuses a version that is not strictly higher than the current one. After running it,
# regenerate frontend/src/generated/api.ts if the schema changed (cd frontend && npm run generate:api).
set -eu

new="${1:-}"
root="$(cd "$(dirname "$0")/.." && pwd)"
case "$new" in
  ''|*[!0-9.]*|.*|*.|*..*) echo "usage: bump-version.sh X.Y.Z" >&2; exit 2 ;;
esac
echo "$new" | grep -Eq '^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$' \
  || { echo "error: '$new' is not a semantic version like 1.2.3" >&2; exit 2; }

cd "$root"
old="$(tr -d '[:space:]' < VERSION)"
higher="$(printf '%s\n%s\n' "$old" "$new" | sort -t. -k1,1n -k2,2n -k3,3n | tail -n 1)"
if [ "$old" = "$new" ] || [ "$higher" != "$new" ]; then
  echo "error: $new is not strictly higher than the current VERSION $old" >&2
  exit 1
fi

printf '%s\n' "$new" > VERSION
sed -i.bak "s/\"VERSION\": \"[^\"]*\"/\"VERSION\": \"$new\"/" backend/config/settings_schema.py
# Only the first "version" key in the snapshot is info.version.
sed -i.bak "0,/\"version\": \"[^\"]*\"/s//\"version\": \"$new\"/" frontend/openapi-schema.json
sed -i.bak -e "s#badge/version-[0-9][0-9.]*-#badge/version-$new-#" -e "s#alt=\"Version [0-9][0-9.]*\"#alt=\"Version $new\"#" README.md
rm -f backend/config/settings_schema.py.bak frontend/openapi-schema.json.bak README.md.bak

notes="docs/release-$new.md"
if [ ! -f "$notes" ]; then
  cat > "$notes" <<TEMPLATE
# SpaceWorks $new

Summary of this release in one or two sentences.

## For members and makerspaces

- 

## For administrators and self-hosters

- 
TEMPLATE
  echo "created $notes (fill it in)"
fi
echo "bumped $old -> $new"
py=python3; python3 -c "" >/dev/null 2>&1 || py=python
"$py" scripts/ci/check_version_bump.py --base-version "$old"
