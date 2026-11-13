#!/usr/bin/env bash
# Release-gate rehearsal of the one-line installer (decisions 220a, 232). Run by hand before a
# release push; it is not part of CI and needs a Docker host with privileged containers:
#
#   bash scripts/ci/install-rehearsal.sh            # Linux, macOS, or Windows Git Bash
#
# It packs THIS working tree (tracked + untracked, not ignored) and the old release ref,
# starts a privileged ubuntu:24.04 container that runs its own dockerd (Docker-in-Docker;
# the Alpine docker:dind image is not a supported installer distribution) and inside it:
#   1. builds the backend/frontend images of this tree into a local registry and serves
#      both trees as published GitHub releases from an offline HTTPS fixture
#      (scripts/ci/install_rehearsal_fixture.py) - no release is fetched from the network; the
#      fixture serves the release ASSETS (install.sh, bundle tarball, SHA256SUMS) built by
#      scripts/release-assets.sh; cosign is not installed on the rehearsal host, so only the
#      checksum is verified (the signature path needs a real release);
#   2. Full: `curl .../releases/latest/download/install.sh | sh` non-interactively (dry run first), health, idempotent
#      re-run, refused --frontend change, uninstall;
#   3. API-only (own-proxy HTTPS): the same, and no website container;
#   4. installs the old release (0.9.3) exactly as its own installer finished, records
#      data, upgrades to this tree with the release installer, checks the data survived, then checks
#      install.sh --version <old> and update.sh --version <old> both refuse the downgrade.
# Base images, apt packages and (by default) the published old images still come from the
# network. Memory: REHEARSAL_MEMORY caps the container (default 8g, which needs a Docker Desktop VM
# of >= 10 GiB; the frontend build and one running stack peak near 5 GiB). On an 8 GiB VM use
# REHEARSAL_MEMORY=6g and run ONE scenario per invocation (the build cache persists, so reruns are fast):
#   REHEARSAL_MEMORY=6g REHEARSAL_SCENARIOS=full bash scripts/ci/install-rehearsal.sh   # then api, then upgrade
# Disk: about 40 GiB free; build caches persist in the volume spaceworks-rehearsal-docker
# (REHEARSAL_CLEAN=1 removes it afterwards). Expect 30-60 minutes on a first run.
# Settings: REHEARSAL_OLD_REF (origin/codex/release-0.9.3), REHEARSAL_OLD_VERSION
# (0.9.3-main.29.c1f9518a5eed), REHEARSAL_OLD_IMAGES (pull|build), REHEARSAL_SCENARIOS
# ("full api upgrade"). Exit status 0 only when every check passed.
set -euo pipefail
OLD_REF="${REHEARSAL_OLD_REF:-origin/codex/release-0.9.3}"
OLD_VERSION="${REHEARSAL_OLD_VERSION:-0.9.3-main.29.c1f9518a5eed}"
REPO=SpaceWorks-Labs/SpaceWorks
REG=localhost:5000
FIXTURE=/rehearsal/install_rehearsal_fixture.py
LOGS=/var/log/rehearsal
FAILURES=0

host_main() {
  local root work mount status=0
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  for tool in docker git tar; do command -v "$tool" >/dev/null || { echo "$tool is required." >&2; exit 64; }; done
  [[ "$(git -C "$root" show "$OLD_REF:VERSION" | tr -d '[:space:]')" == "${OLD_VERSION%%-main.*}" ]] \
    || { echo "$OLD_REF does not carry VERSION ${OLD_VERSION%%-main.*}." >&2; exit 64; }
  work="$(mktemp -d)"
  trap 'rm -rf -- "$work"' EXIT
  echo "Packing the working tree and $OLD_REF..."
  git -C "$root" ls-files -z -co --exclude-standard | while IFS= read -r -d '' file; do
    [[ -f "$root/$file" && ! -L "$root/$file" ]] && printf '%s\0' "$file"
  done > "$work/local.list"
  tar -C "$root" --null -T "$work/local.list" -czf "$work/local.tar.gz"
  git -C "$root" ls-files -s > "$work/local.modes"
  git -C "$root" archive --format=tar.gz -o "$work/old.tar.gz" "$OLD_REF"
  cp "$root/scripts/ci/install-rehearsal.sh" "$root/scripts/ci/install_rehearsal_fixture.py" "$work/"
  mount="$work"
  if command -v cygpath >/dev/null 2>&1; then mount="$(cygpath -w "$work")"; export MSYS_NO_PATHCONV=1; fi
  docker run --rm --privileged --name spaceworks-rehearsal --memory "${REHEARSAL_MEMORY:-8g}" \
    -v "$mount:/rehearsal:ro" -v spaceworks-rehearsal-docker:/var/lib/docker \
    -e REHEARSAL_OLD_VERSION="$OLD_VERSION" -e REHEARSAL_OLD_IMAGES="${REHEARSAL_OLD_IMAGES:-pull}" \
    -e REHEARSAL_SCENARIOS="${REHEARSAL_SCENARIOS:-full api upgrade}" \
    ubuntu:24.04 bash /rehearsal/install-rehearsal.sh inside || status=$?
  [[ "${REHEARSAL_CLEAN:-0}" != 1 ]] || docker volume rm spaceworks-rehearsal-docker >/dev/null
  exit "$status"
}

check() {
  local label="$1"; shift
  if "$@"; then echo "PASS  $label"; else echo "FAIL  $label"; FAILURES=$((FAILURES + 1)); fi
}

# Run a step with its output in $LOGS/<name>.log; show the tail when it fails.
logged() {
  local name="$1" status=0; shift
  "$@" > "$LOGS/$name.log" 2>&1 || status=$?
  ((status == 0)) || { echo "--- $name exited $status; last lines of $LOGS/$name.log:"; tail -n 40 "$LOGS/$name.log"; }
  return "$status"
}

wait_http() {  # url [curl args...]
  local url="$1" _; shift
  for _ in $(seq 1 40); do curl -fsS -o /dev/null "$@" "$url" 2>/dev/null && return 0; sleep 3; done
  return 1
}

prepare_host() {
  export DEBIAN_FRONTEND=noninteractive
  mkdir -p "$LOGS"
  logged apt bash -c 'apt-get update && apt-get install -y --no-install-recommends ca-certificates curl git \
    python3 openssl docker.io docker-buildx docker-compose-v2 iproute2 tar gzip util-linux'
  dockerd > "$LOGS/dockerd.log" 2>&1 &
  for _ in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 2; done
  docker info >/dev/null 2>&1 || { tail -n 30 "$LOGS/dockerd.log"; echo 'dockerd did not start (is the container privileged?).'; exit 1; }
  mkdir -p /fixture/local /fixture/old
  tar -C /fixture/local -xzf /rehearsal/local.tar.gz
  tar -C /fixture/old -xzf /rehearsal/old.tar.gz
  OLD_RUN="$(sed -E 's/.*-main\.([0-9]+)\..*/\1/' <<< "$OLD_VERSION")"
  NEW_RUN=$((OLD_RUN + 100))
  NEW_SPEC="/fixture/local:$NEW_RUN::/rehearsal/local.modes"
  OLD_SPEC="/fixture/old:$OLD_RUN:${OLD_VERSION##*.}"
  NEW_VERSION="$(python3 "$FIXTURE" version "$NEW_SPEC")"
  [[ "$(python3 "$FIXTURE" version "$OLD_SPEC")" == "$OLD_VERSION" ]] || { echo "Cannot serve $OLD_VERSION from the old tree."; exit 1; }
  echo "Rehearsing $OLD_VERSION -> $NEW_VERSION"
}

build_images() {  # tree version
  local tree="$1" version="$2" target=()
  ! grep -q ' AS release' "$tree/backend/Dockerfile" || target=(--target release)
  logged "build-backend-$version" docker buildx build --load "${target[@]}" \
    --build-context cloud_tooling="$tree" --build-arg BUILD_GIT_DESCRIBE="$version" \
    -t "$REG/spaceworks-backend:$version" "$tree/backend"
  logged "build-frontend-$version" docker buildx build --load -t "$REG/spaceworks-frontend:$version" "$tree/frontend"
}

publish_images() {
  docker rm -f rehearsal-registry >/dev/null 2>&1 || true  # left over from an earlier run in the cached volume
  docker run -d --name rehearsal-registry -p 127.0.0.1:5000:5000 -v rehearsal-registry:/var/lib/registry registry:2 >/dev/null
  build_images /fixture/local "$NEW_VERSION"
  local image pulled=1
  if [[ "${REHEARSAL_OLD_IMAGES:-pull}" == pull ]]; then
    for image in spaceworks-backend spaceworks-frontend; do
      docker pull "ghcr.io/spaceworks-labs/$image:$OLD_VERSION" >/dev/null 2>&1 \
        && docker tag "ghcr.io/spaceworks-labs/$image:$OLD_VERSION" "$REG/$image:$OLD_VERSION" || pulled=0
    done
  fi
  [[ "${REHEARSAL_OLD_IMAGES:-pull}" == pull && "$pulled" == 1 ]] || build_images /fixture/old "$OLD_VERSION"
  for image in spaceworks-backend spaceworks-frontend; do
    for version in "$NEW_VERSION" "$OLD_VERSION"; do logged "push-$image-$version" docker push "$REG/$image:$version"; done
  done
  # Every install below records these image names in its .env, so updates pull from here too.
  export MAKERSPACE_BACKEND_IMAGE="$REG/spaceworks-backend" MAKERSPACE_FRONTEND_IMAGE="$REG/spaceworks-frontend"
}

start_release_fixture() {
  local tls=/fixture/tls
  mkdir -p "$tls"
  openssl req -x509 -newkey rsa:2048 -nodes -days 2 -subj /CN=spaceworks-rehearsal-ca \
    -addext basicConstraints=critical,CA:TRUE -addext keyUsage=critical,keyCertSign,cRLSign \
    -keyout "$tls/ca.key" -out "$tls/ca.crt" 2>/dev/null
  openssl req -newkey rsa:2048 -nodes -subj /CN=api.github.com -keyout "$tls/leaf.key" -out "$tls/leaf.csr" 2>/dev/null
  printf 'subjectAltName=DNS:api.github.com,DNS:raw.githubusercontent.com,DNS:github.com\nextendedKeyUsage=serverAuth\n' > "$tls/ext"
  openssl x509 -req -in "$tls/leaf.csr" -CA "$tls/ca.crt" -CAkey "$tls/ca.key" -CAcreateserial -days 2 \
    -extfile "$tls/ext" -out "$tls/leaf.crt" 2>/dev/null
  cp "$tls/ca.crt" /usr/local/share/ca-certificates/spaceworks-rehearsal.crt
  update-ca-certificates >/dev/null
  echo '127.0.0.1 api.github.com raw.githubusercontent.com github.com' >> /etc/hosts
  python3 "$FIXTURE" serve --cert "$tls/leaf.crt" --key "$tls/leaf.key" --repo "$REPO" \
    --release "$NEW_SPEC" --release "$OLD_SPEC" > "$LOGS/fixture.log" 2>&1 &
  wait_http "https://api.github.com/repos/$REPO/releases" || { tail -n 30 "$LOGS/fixture.log"; echo 'Release fixture did not start.'; exit 1; }
}

# The release installer piped into sh exactly like the documented one-liner, no terminal.
pipe_install() {  # name dir args...
  local name="$1" dir="$2"; shift 2
  logged "$name" env SPACEWORKS_DIR="$dir" SPACEWORKS_OPS_HOST_DIR="/var/lib/sw-$(basename "$dir")/ops" \
    SPACEWORKS_HOST_STATE_DIR="/var/lib/sw-$(basename "$dir")/host" REPO="$REPO" \
    sh -c 'curl -fsSL "https://github.com/$REPO/releases/latest/download/install.sh" | sh -s -- "$@"' install "$@" < /dev/null
}

# The old raw-main path: the repository install.sh is a stub that fetches the release installer.
pipe_legacy_stub() {  # name dir args...
  local name="$1" dir="$2"; shift 2
  logged "$name" env SPACEWORKS_DIR="$dir" SPACEWORKS_OPS_HOST_DIR="/var/lib/sw-$(basename "$dir")/ops" \
    SPACEWORKS_HOST_STATE_DIR="/var/lib/sw-$(basename "$dir")/host" \
    bash -c 'cat /fixture/local/install.sh | bash -s -- "$@"' install "$@" < /dev/null
}

answers() {  # file json-object-body
  (umask 077; printf '{"schema_version":1,"confirmed":true,"answers":{%s}}\n' "$2" > "$1")
}

compose_in() { (cd "$1" && shift && bash scripts/spaceworks-compose.sh bundled "$@"); }

remove_install() {  # dir
  local dir="$1"
  check "$(basename "$dir"): uninstall --purge-local-data" logged "uninstall-$(basename "$dir")" \
    bash "$dir/scripts/uninstall.sh" --purge-local-data --confirm "DELETE-LOCAL-DATA:$(basename "$dir")"
  docker ps -aq --filter label=com.docker.compose.project | xargs -r docker rm -f >/dev/null
  docker volume ls -q | { grep -vx rehearsal-registry || true; } | xargs -r docker volume rm -f >/dev/null
  docker network prune -f >/dev/null
  rm -rf -- "$dir" "/var/lib/sw-$(basename "$dir")"
}

version_is() { [[ "$(tr -d '[:space:]' < "$1/.spaceworks-version")" == "$2" ]]; }
no_website_container() { ! docker ps --format '{{.Image}}' | grep -q spaceworks-frontend; }
refused() { ! "$@" && grep -qi "$EXPECT" "$LOGS/$2.log"; }

fresh_scenario() {  # full|api
  local mode="$1" dir="/opt/sw-$1" file="/root/answers-$1.json" frontend=full health=(http://127.0.0.1/api/v1/health/)
  local body='"ORG_NAME":"Rehearsal Org","MSNAME":"Rehearsal Space","ADMINEMAIL":"owner@example.org","ADMINPASS":"Rehearsal-Pass-1234"'
  if [[ "$mode" == api ]]; then
    frontend=api-only
    body+=',"HTTPS_MODE":"3","PUBLIC_DOMAIN":"api.rehearsal.test"'
    health=(http://127.0.0.1:8080/api/v1/health/ -H 'Host: api.rehearsal.test' -H 'X-Forwarded-Proto: https')
  fi
  answers "$file" "$body"
  check "$mode: dry run succeeds" pipe_install "dry-$mode" "$dir" --dry-run --non-interactive --answers-file "$file" --frontend "$frontend"
  check "$mode: dry run wrote nothing" test ! -e "$dir"
  [[ "$mode" != full ]] || check "full: legacy raw-main stub runs the release installer" pipe_legacy_stub "stub-full" "$dir"     --dry-run --non-interactive --answers-file "$file" --frontend "$frontend"
  check "$mode: curl install.sh | sh (non-interactive)" pipe_install "install-$mode" "$dir" --non-interactive --answers-file "$file" --frontend "$frontend"
  check "$mode: installed $NEW_VERSION" version_is "$dir" "$NEW_VERSION"
  check "$mode: API health" wait_http "${health[@]}"
  if [[ "$mode" == full ]]; then check "full: website answers" wait_http http://127.0.0.1/
  else check "api: no website container" no_website_container; fi
  check "$mode: re-run is an idempotent update" pipe_install "rerun-$mode" "$dir" --non-interactive
  check "$mode: version unchanged after re-run" version_is "$dir" "$NEW_VERSION"
  local other=api-only; [[ "$frontend" == full ]] || other=full
  EXPECT='frontend mode' check "$mode: --frontend change refused" refused pipe_install "switch-$mode" "$dir" --non-interactive --frontend "$other"
  remove_install "$dir"
}

snapshot() {  # dir -> one JSON line of durable facts
  local code='import json; from django.apps import apps; from django.contrib.auth import get_user_model as U
M = apps.get_model("makerspaces", "Makerspace")
print("SNAPSHOT" + json.dumps({"users": U().objects.count(), "admin": U().objects.filter(username="admin").exists(),
      "spaces": sorted(M.objects.values_list("slug", flat=True))}))'
  { compose_in "$1" run --rm --no-deps -T backend --role management python manage.py shell -c "$code" 2>/dev/null \
    || compose_in "$1" exec -T backend python manage.py shell -c "$code"; } | sed -n 's/^SNAPSHOT//p' | tail -n 1
}

same_data() {  # before after: users never drop, admin and makerspaces kept
  python3 -c 'import json, sys
b, a = (json.loads(v) for v in sys.argv[1:])
sys.exit(not (a["users"] >= b["users"] and a["admin"] and a["spaces"] == b["spaces"] and b["spaces"]))' "$1" "$2"
}

upgrade_scenario() {
  local dir=/opt/sw-upgrade before after key
  mkdir -m 700 "$dir"
  tar -C "$dir" -xzf /rehearsal/old.tar.gz
  # The 0.9.3 installer copied its release, ran setup.sh on confirmed answers, then wrote the marker.
  (umask 077; for key in HOSTING_MODEL=1 RUN_FRONTEND=1 SITE_ORIGINS= PLATFORM_DOMAIN= PUBLIC_DOMAIN= TLS_EMAIL= \
      HTTPS_MODE=1 SHAPE=1 STORAGE=1 WEBHOST=localhost MSNAME=Rehearsal\ Space MS_SUBDOMAIN=rehearsal-space \
      SPACEWORKS_EDITION=makerspace MSPROFILE=recommended REQUEST_ACCESS=accounts ADMINUSER=admin \
      ADMINEMAIL=owner@example.org ADMINPASS=Rehearsal-Pass-1234 GEN_PASS=0 GOOGLE_WEB_CLIENT_ID= \
      STRIPE_SECRET_KEY= STRIPE_WEBHOOK_SECRET= STRIPE_DEFAULT_CURRENCY=usd SPACEWORKS_REPOSITORY="$REPO" \
      INSTALL_RUNNER=N S3_ENDPOINT= S3_REGION=us-east-1 PRIVATE_BUCKET=evidence IMAGE_BUCKET=public-images \
      S3_ACCESS_KEY= S3_SECRET_KEY= IMAGE_BASE_URL= PRESIGN_METHOD=post ANSWERS_CONFIRMED=yes; do
    printf '%s=%q\n' "${key%%=*}" "${key#*=}"; done > "$dir/.spaceworks-answers")
  check "upgrade: $OLD_VERSION installed" logged install-old env SPACEWORKS_OPS_HOST_DIR=/var/lib/sw-sw-upgrade/ops \
    SPACEWORKS_HOST_STATE_DIR=/var/lib/sw-sw-upgrade/host SPACEWORKS_INSTALL_REPOSITORY_PINNED=1 \
    SPACEWORKS_REPOSITORY="$REPO" MAKERSPACE_IMAGE_TAG="$OLD_VERSION" bash -c "cd '$dir' && bash setup.sh" < /dev/null
  rm -f -- "$dir/.spaceworks-answers"; printf '%s\n' "$OLD_VERSION" > "$dir/.spaceworks-version"
  check "upgrade: old API health" wait_http http://127.0.0.1/api/v1/health/
  before="$(snapshot "$dir")"; echo "      data before: ${before:-none}"
  check "upgrade: dry run plans the update" pipe_install dry-upgrade "$dir" --dry-run --non-interactive
  check "upgrade: dry run kept $OLD_VERSION" version_is "$dir" "$OLD_VERSION"
  check "upgrade: curl install.sh | sh upgrades" pipe_install upgrade "$dir" --non-interactive
  check "upgrade: now $NEW_VERSION" version_is "$dir" "$NEW_VERSION"
  check "upgrade: new API health" wait_http http://127.0.0.1/api/v1/health/
  after="$(snapshot "$dir")"; echo "      data after:  ${after:-none}"
  check "upgrade: data survived" same_data "${before:-null}" "${after:-null}"
  EXPECT='forward-only' check "downgrade: installer --version refused" refused \
    pipe_install downgrade-install "$dir" --non-interactive --version "$OLD_VERSION"
  EXPECT='Refusing release downgrade' check "downgrade: update.sh --version refused" refused \
    logged downgrade-update bash "$dir/scripts/update.sh" --force --no-module-changes --version "$OLD_VERSION"
  check "downgrade: still $NEW_VERSION and healthy" bash -c "[[ \$(tr -d '[:space:]' < '$dir/.spaceworks-version') == '$NEW_VERSION' ]] && curl -fsS -o /dev/null http://127.0.0.1/api/v1/health/"
  remove_install "$dir"
}

inside_main() {
  prepare_host
  publish_images
  start_release_fixture
  local scenario
  for scenario in ${REHEARSAL_SCENARIOS:-full api upgrade}; do
    case "$scenario" in full|api) fresh_scenario "$scenario" ;; upgrade) upgrade_scenario ;; esac
  done
  ((FAILURES == 0)) && echo 'Rehearsal passed.' || echo "Rehearsal FAILED: $FAILURES check(s); logs in $LOGS."
  ((FAILURES == 0))
}

case "${1:-host}" in
  host) host_main ;;
  inside) inside_main ;;
  *) echo 'Usage: bash scripts/ci/install-rehearsal.sh' >&2; exit 64 ;;
esac
