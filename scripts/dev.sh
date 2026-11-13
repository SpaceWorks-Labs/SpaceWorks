#!/usr/bin/env bash
# The single developer entry point; requires Docker and Bash (Git Bash on Windows).
#   up [args]       Compose up -d; retire live and remove successful one-shots.
#   down [args]     Compose down; volumes persist unless you pass -v.
#   test [args]     Pytest in disposable Postgres/Redis/MinIO; default args: -q.
#   affected [backend|frontend]  Only the tests for what changed (AFFECTED_BASE).
#   hooks           Enable the repo's git hooks (.githooks/pre-push).
#   e2e [args]      Seed the running dev stack; Playwright against a production preview.
#   <other> [args]  Forward verbatim to Compose: logs, exec, run, ps, restart, etc.
# Restart affects long-running services only; up recreates the four one-shots.
# E2E creates a fresh tenant each run; dev.sh down -v wipes the dev database.
# Compose chain: base, machine override if present, then the dev layer.
set -euo pipefail
export MSYS_NO_PATHCONV=1

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
HOST_ROOT="$ROOT"
if command -v cygpath >/dev/null 2>&1; then
  HOST_ROOT="$(cygpath -m "$ROOT")"
fi
files=(-f docker-compose.yml)
[[ ! -f docker-compose.override.yml ]] || files+=(-f docker-compose.override.yml)
files+=(-f docker-compose.dev.yml)
compose() { docker compose "${files[@]}" "$@"; }

up() {
  local failed=0 svc cid result
  local one_shots=(orchestration-init migrate orchestration-ready createbuckets)
  # A failed `up` can leave a one-shot created but never started, and `docker wait` on that
  # blocks forever, so stop here and let compose's own error stand.
  compose up -d "$@"
  if [[ "$(docker inspect -f '{{.State.Running}}' spaceworks-live 2>/dev/null || true)" == true ]]; then
    docker rm -f spaceworks-live
  fi
  for svc in "${one_shots[@]}"; do
    cid="$(compose ps -a -q "$svc")"
    [[ -n "$cid" ]] || continue
    if ! result="$(docker wait "$cid")" || [[ "$result" != 0 ]]; then
      echo "$svc failed; inspect it with: dev.sh logs $svc" >&2
      failed=1
    fi
  done
  [[ "$failed" == 0 ]] || return 1
  compose rm -f "${one_shots[@]}"
}

# The test runner bind-mounts the source, so the image only has to carry what the
# Dockerfile installs: system packages, Python dependencies, fonts and Postgres clients.
# Rebuild only when those inputs change (or with SPACEWORKS_TEST_REBUILD=1). An
# unchanged image skips the ~27 MB context upload and the source-layer rebuild (CJK font
# download, compilemessages, collectstatic) that every source edit used to trigger.
ensure_test_image() {
  local inputs=(Dockerfile requirements.txt scripts/bundle_cjk_fonts.py scripts/verify_printable_runtime.py)
  local hash current
  hash="$(cd "$ROOT/backend" && cat "${inputs[@]}" | sha256sum | cut -c1-16)"
  current="$(docker image inspect -f '{{index .Config.Labels "spaceworks.test-deps"}}' \
    spaceworks-backend 2>/dev/null || true)"
  if [[ "$current" == "$hash" && "${SPACEWORKS_TEST_REBUILD:-0}" != 1 ]]; then
    echo "Test image is current (dependencies $hash); not rebuilding." >&2
    return
  fi
  docker build --label "spaceworks.test-deps=$hash" --tag spaceworks-backend "$HOST_ROOT/backend"
}

# Tests for what changed since a base (AFFECTED_BASE; default: the upstream, else HEAD~1):
# scripts/affected_tests.py picks the pytest files and the frontend sources for
# `vitest related`. Small changes use this; the full suite stays the release gate.
affected() {
  local scope="${1:-all}" sel=()
  if [[ "$scope" == all || "$scope" == backend ]]; then
    mapfile -t sel < <(python "$HOST_ROOT/scripts/affected_tests.py" backend)
    if [[ "${sel[0]:-}" == ALL ]]; then
      echo "Shared backend code changed; running the full backend suite." >&2
      test_suite -q
    elif ((${#sel[@]})); then
      echo "Affected backend tests: ${#sel[@]} file(s)." >&2
      # Hundreds of paths overflow the Windows command-line limit; pytest reads @file arguments.
      printf '%s\n' "${sel[@]}" > "$ROOT/backend/.affected-tests.txt"
      test_suite -q @.affected-tests.txt
    else
      echo "No affected backend tests." >&2
    fi
  fi
  if [[ "$scope" == all || "$scope" == frontend ]]; then
    mapfile -t sel < <(python "$HOST_ROOT/scripts/affected_tests.py" frontend)
    if ((${#sel[@]})); then
      # Batches keep each command line under the Windows limit.
      local i
      for ((i = 0; i < ${#sel[@]}; i += 200)); do
        (cd "$ROOT/frontend" && npx vitest related --run "${sel[@]:i:200}") || return
      done
    else
      echo "No affected frontend sources." >&2
    fi
  fi
}

test_suite() {
  RUN="spaceworks-test-$$-$(date +%s)"
  cleanup() {
    local status=$? containers=()
    set +e
    mapfile -t containers < <(docker ps -aq --filter "label=spaceworks.test=$RUN")
    if ((${#containers[@]})); then docker rm -fv "${containers[@]}" >/dev/null; fi
    docker network rm "$RUN" >/dev/null 2>&1
    exit "$status"
  }
  trap cleanup EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
  # Source is bind-mounted below; dependencies and fonts come from the image.
  ensure_test_image
  docker network create "$RUN" >/dev/null
  docker run -d --name "$RUN-db" --network "$RUN" --network-alias db \
    --label "spaceworks.test=$RUN" --tmpfs /var/lib/postgresql/data \
    -e POSTGRES_USER=makerspace -e POSTGRES_PASSWORD=makerspace \
    -e POSTGRES_DB=makerspace_manager postgres:16 >/dev/null
  docker run -d --network "$RUN" --network-alias redis \
    --label "spaceworks.test=$RUN" redis:7.4.11-alpine >/dev/null
  docker run -d --network "$RUN" --network-alias minio \
    --label "spaceworks.test=$RUN" -e MINIO_ROOT_USER=minioadmin \
    -e MINIO_ROOT_PASSWORD=minioadmin pgsty/silo:RELEASE.2026-09-16T00-00-00Z server /data >/dev/null
  local deadline=$((SECONDS + 60))
  until docker exec "$RUN-db" pg_isready -U makerspace -d makerspace_manager >/dev/null 2>&1; do
    if ((SECONDS >= deadline)); then echo "Test Postgres did not become ready" >&2; return 1; fi
    sleep 1
  done
  docker run --rm --network "$RUN" --label "spaceworks.test=$RUN" \
    --entrypoint /bin/sh pgsty/silo:RELEASE.2026-09-16T00-00-00Z -c '
      # The whole setup retries as one unit: on a busy runner Docker DNS can drop a lookup in the middle of it.
      setup() {
        mc alias set local http://minio:9000 minioadmin minioadmin &&
        mc mb --ignore-existing local/evidence && mc version enable local/evidence &&
        mc anonymous set none local/evidence &&
        mc mb --ignore-existing local/public-images && mc version enable local/public-images &&
        mc anonymous set download local/public-images
      }
      n=0; until setup; do n=$((n + 1)); [ "$n" -ge 30 ] && exit 1; sleep 2; done;
    '
  local key_output keys
  key_output="$(docker run --rm --label "spaceworks.test=$RUN" --entrypoint python spaceworks-backend -c \
    'from cryptography.fernet import Fernet; print(*(Fernet.generate_key().decode() for _ in range(3)), sep="\n")')"
  mapfile -t keys <<< "$key_output"
  local TEST_ENV=(
    -e DATABASE_URL=postgres://makerspace:makerspace@db:5432/makerspace_manager
    -e SECRET_KEY=test-only -e DEBUG=True -e TRUSTED_PROXY_COUNT=0 -e PYTHONDONTWRITEBYTECODE=1
    -e ALLOWED_HOSTS=localhost,127.0.0.1 -e CELERY_BROKER_URL=redis://redis:6379/0
    -e AWS_S3_ENDPOINT_URL=http://minio:9000 -e AWS_S3_PUBLIC_ENDPOINT_URL=http://minio:9000
    -e PUBLIC_IMAGE_BASE_URL=http://minio:9000/public-images
    -e AWS_ACCESS_KEY_ID=minioadmin -e AWS_SECRET_ACCESS_KEY=minioadmin
    -e AWS_STORAGE_BUCKET_NAME=evidence -e PUBLIC_IMAGE_BUCKET=public-images
    -e STORAGE_PRESIGN_METHOD=post -e EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
    -e "API_CLIENT_ENC_KEY=${keys[0]}" -e "AUDIT_MAC_MASTER_KEY=${keys[1]}"
    -e "PII_MASTER_KEY=${PII_MASTER_KEY:-${keys[2]}}"
  )
  # tests/tombstone only runs under an exported TOMBSTONED_APPS profile, so pass it through.
  [[ -z "${TOMBSTONED_APPS:-}" ]] || TEST_ENV+=(-e "TOMBSTONED_APPS=$TOMBSTONED_APPS")
  # A nonempty probe role forces RLS for the X-8 regression.
  [[ -z "${TENANT_RLS_PROBE_ROLE:-}" ]] || TEST_ENV+=(-e "TENANT_RLS_PROBE_ROLE=$TENANT_RLS_PROBE_ROLE")
  (($#)) || set -- -q
  docker run --rm --network "$RUN" --label "spaceworks.test=$RUN" --entrypoint pytest \
    -v "$HOST_ROOT:/workspace" -w /workspace/backend \
    -v "$HOST_ROOT/scripts:/run/spaceworks-privileged-scripts" \
    "${TEST_ENV[@]}" spaceworks-backend -p no:cacheprovider "$@"
}

e2e() {
  local deadline=$((SECONDS + 60)) remaining
  until remaining=$((deadline - SECONDS)) && ((remaining > 0)) && \
    curl -sf --max-time "$remaining" http://localhost:8000/api/v1/health/ >/dev/null && \
    remaining=$((deadline - SECONDS)) && ((remaining > 0)) && \
    curl -sf --max-time "$remaining" http://localhost:5000/ >/dev/null; do
    if ((SECONDS >= deadline)); then
      echo "Dev stack is not ready; start it with: dev.sh up" >&2
      return 1
    fi
    sleep 1
  done
  compose exec -T backend python manage.py seed_e2e --write-json /tmp/e2e-seed.json
  docker cp spaceworks-backend:/tmp/e2e-seed.json "$HOST_ROOT/frontend/e2e/.seed.json"
  e2e_preview "$@"
}

# Playwright runs against a production build (the kiosk service worker exists only
# there), served by `vite preview` behind the same /api proxy so cookies and exact
# Station Origin checks behave as in production. Dev CORS already admits :5173.
e2e_preview() {
  local port="${E2E_PREVIEW_PORT:-5173}" api="${E2E_API_URL:-http://localhost:8000}" preview_pid deadline
  cd "$ROOT/frontend"
  # Playwright is a pinned devDependency; fetch the Chromium build that exact version expects (no-op once present).
  [[ -x ./node_modules/.bin/playwright || -x ./node_modules/.bin/playwright.cmd ]] || npm ci
  npx playwright install chromium
  VITE_API_URL="http://localhost:$port/api" npm run build
  VITE_DEV_PROXY_TARGET="$api" node ./node_modules/vite/bin/vite.js preview     --host localhost --port "$port" --strictPort &
  preview_pid=$!
  trap 'kill "$preview_pid" 2>/dev/null || true; wait "$preview_pid" 2>/dev/null || true' EXIT INT TERM
  deadline=$((SECONDS + 60))
  until curl -sf --max-time 2 "http://localhost:$port/" >/dev/null; do
    if ((SECONDS >= deadline)); then echo "Production preview did not become ready." >&2; return 1; fi
    sleep 1
  done
  E2E_API_URL="$api" E2E_BASE_URL="http://localhost:$port"     E2E_SEED_FILE="$HOST_ROOT/frontend/e2e/.seed.json" npx playwright test "$@"
}

case "${1:-}" in
  up) shift; up "$@" ;;
  down) shift; compose down "$@" ;;
  test) shift; test_suite "$@" ;;
  affected) shift; affected "$@" ;;
  hooks) git config core.hooksPath .githooks && echo "Git hooks enabled (.githooks/pre-push)." ;;
  e2e) shift; e2e "$@" ;;
  *) compose "$@" ;;
esac
