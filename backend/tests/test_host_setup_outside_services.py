"""Hybrid self-hosting (decision 239): outside database, Redis, storage and email, local by default.

Real bash and static Compose YAML; no Docker daemon, no network.
"""
import importlib.util
import os
import subprocess
import sys
import types

import pytest
import yaml

from tests.test_host_setup_questions_behavior import BASH, ROOT, defaults, question_tail, questionnaire, quick_answers

pytestmark = pytest.mark.skipif(not BASH, reason="requires bash")

SUPABASE_DIRECT = "postgresql://postgres:pw@db.abcd.supabase.co:5432/postgres?sslmode=require"
SUPABASE_SESSION = "postgresql://postgres.abcd:pw@aws-0-eu.pooler.supabase.com:5432/postgres?sslmode=require"
SUPABASE_TRANSACTION = "postgresql://postgres.abcd:pw@aws-0-eu.pooler.supabase.com:6543/postgres?sslmode=require"


def bash(script, **env):
    return subprocess.run([BASH, "-c", "set -uo pipefail\nsource scripts/installer/outside-services.sh\n" + script],
                          cwd=ROOT, env={**os.environ, **env}, text=True, capture_output=True, timeout=30)


# --- Compose overlays ---------------------------------------------------------------------------

def services_depending_on(name):
    prod = yaml.safe_load((ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8"))
    return {key for key, service in prod["services"].items() if name in (service.get("depends_on") or {})}


@pytest.mark.parametrize("overlay,dependency,disabled", [
    ("compose.external-db.yml", "db", "database-disabled"),
    ("compose.external-redis.yml", "redis", "redis-disabled"),
    ("compose.external-storage.yml", "createbuckets", "storage-disabled"),
])
def test_each_overlay_parks_its_service_and_drops_every_dependency_on_it(overlay, dependency, disabled):
    text = (ROOT / "docker" / overlay).read_text(encoding="utf-8")
    document = yaml.safe_load(text.replace("!reset null", "null"))
    assert document["services"][dependency]["profiles"] == [disabled]
    # Removed key by key (!reset), never by replacing the map, so the overlays stack in any order.
    assert "depends_on: !override" not in text
    for service in services_depending_on(dependency):
        assert dependency in (document["services"][service]["depends_on"]), service


def test_external_database_overlay_gives_one_shot_jobs_the_owner_login():
    text = (ROOT / "docker/compose.external-db.yml").read_text(encoding="utf-8")
    for service in ("orchestration-init", "migrate", "orchestration-ready"):
        block = text.split(f"  {service}:\n")[1].split("\n  ")[0:3]
        assert "SPACEWORKS_MAINTENANCE_DATABASE_URL" in "\n".join(block)
    # Resident services keep the pointer's narrow runtime login: the owner URL never reaches them.
    for service in ("backend", "live", "worker", "beat"):
        assert "SPACEWORKS_MAINTENANCE_DATABASE_URL" not in text.split(f"  {service}:\n")[1].split("\n  ")[0]


def layers(root, env_text, layer="none"):
    (root / ".env").write_text(env_text, newline="\n")
    script = 'ROOT="$PWD"; source scripts/compose-deployment.sh; COMPOSE_FILES=(); append_deployment_layers "$1" "$ROOT" || exit $?; ' \
             'printf "%s\\n" "$DEPLOYMENT_SUFFIX" "${COMPOSE_FILES[@]}"'
    return subprocess.run([BASH, "-c", script, "x", layer], cwd=root, text=True, capture_output=True, timeout=30,
                          env={**os.environ, "SPACEWORKS_STATIC_ENV_FILE": str(root / ".env")})


def test_selectors_add_overlays_in_a_fixed_order_and_default_to_none(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "compose-deployment.sh").write_text((ROOT / "scripts/compose-deployment.sh").read_text(encoding="utf-8"), newline="\n")
    none = layers(tmp_path, "SPACEWORKS_RUN_FRONTEND='yes'\n")
    assert none.returncode == 0 and none.stdout.strip() == ""
    result = layers(tmp_path, "SPACEWORKS_STORAGE='external'\nSPACEWORKS_DATABASE='external'\nSPACEWORKS_REDIS='external'\n")
    suffix, *files = result.stdout.splitlines()
    assert suffix == "-external-storage-external-db-external-redis"
    assert [f.rsplit("/", 1)[1] for f in files] == [
        "compose.external-storage.yml", "compose.external-db.yml", "compose.external-redis.yml"]
    bad = layers(tmp_path, "SPACEWORKS_DATABASE='sqlite'\n")
    assert bad.returncode == 64 and "SPACEWORKS_DATABASE must be bundled or external" in bad.stderr


# --- URL rules -----------------------------------------------------------------------------------

@pytest.mark.parametrize("url,ok,fragment", [
    (SUPABASE_DIRECT, True, ""),
    (SUPABASE_SESSION, True, ""),
    (SUPABASE_TRANSACTION, False, "transaction-pooler"),
    ("postgres://u:p@ep-x-pooler.eu-central-1.aws.neon.tech/db?sslmode=require", False, "transaction-pooler"),
    ("postgresql://postgres:pw@db.abcd.supabase.co:5432/postgres", False, "sslmode=require"),
    ("postgres://u:p@10.0.0.5/db", True, ""),
    ("postgres://u:p@w@host/db?sslmode=require", False, "percent-encode"),
    ("mysql://u:p@host/db", False, "postgresql://"),
])
def test_database_url_rules(url, ok, fragment):
    result = bash('db_url_problem "$URL"', URL=url)
    assert (result.returncode == 0) == ok, result.stdout
    assert fragment in result.stdout
    assert "pw" not in result.stdout  # the URL, with its password, is never echoed back


def test_pooler_detection_asks_for_a_direct_url():
    assert bash('db_url_is_pooler "$URL"', URL=SUPABASE_SESSION).returncode == 0
    assert bash('db_url_is_pooler "$URL"', URL=SUPABASE_DIRECT).returncode == 1


def test_runtime_login_is_derived_and_a_supabase_pooler_keeps_its_project_suffix():
    direct = bash('derive_runtime_database_url "$URL" spaceworks_app SECRET', URL=SUPABASE_DIRECT).stdout
    pooled = bash('derive_runtime_database_url "$URL" spaceworks_app SECRET', URL=SUPABASE_SESSION).stdout
    assert direct == "postgres://spaceworks_app:SECRET@db.abcd.supabase.co:5432/postgres?sslmode=require"
    assert pooled == "postgres://spaceworks_app.abcd:SECRET@aws-0-eu.pooler.supabase.com:5432/postgres?sslmode=require"


def test_redis_rules_require_tls_off_network_and_celery_certificate_mode():
    assert bash('redis_url_problem "redis://default:p@x.upstash.io:6379"').returncode == 1
    assert bash('redis_url_problem "redis://default:p@10.0.0.9:6379"').returncode == 0
    assert bash('redis_url_problem "rediss://default:p@x.upstash.io:6379"').returncode == 0
    assert bash('normalize_redis_url "rediss://d:p@h:6379"').stdout == "rediss://d:p@h:6379?ssl_cert_reqs=required"
    assert bash('normalize_redis_url "rediss://d:p@h:6379?x=1"').stdout == "rediss://d:p@h:6379?x=1&ssl_cert_reqs=required"
    assert bash('normalize_redis_url "redis://redis:6379/0"').stdout == "redis://redis:6379/0"


# --- Questionnaire and dotenv --------------------------------------------------------------------

def test_default_install_is_all_local_and_records_it(tmp_path):
    result = questionnaire(tmp_path, defaults(), write=True)
    assert result.returncode == 0, result.stderr
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "SPACEWORKS_DATABASE='bundled'" in env and "SPACEWORKS_REDIS='bundled'" in env
    assert "SPACEWORKS_MAINTENANCE_DATABASE_URL" not in env and "CELERY_BROKER_URL" not in env
    assert "Outside services: database local; Redis local" in result.stdout
    assert not (tmp_path / "storage-config").exists()


def test_quick_setup_stays_all_local_and_asks_no_outside_question(tmp_path):
    result = questionnaire(tmp_path, quick_answers(), write=True, quick=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("]: ") == 16  # unchanged by the outside-services step
    assert "outside database" not in result.stdout and "Outside services (optional)" not in result.stdout
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "SPACEWORKS_DATABASE='bundled'" in env and "SPACEWORKS_STORAGE='bundled'" in env


def test_the_owners_hybrid_example_writes_every_outside_setting_privately(tmp_path):
    # model, website, HTTPS (own proxy), domain | R2 | gate=yes | Supabase session pooler + direct URL |
    # Upstash | SMTP (Resend) | control panel (no), org, space, MFA, providers
    answers = ["", "", "3", "api.example.org",
               "2", "https://acc.r2.cloudflarestorage.com", "", "auto", "sw-private", "sw-public", "AKIA", "r2-secret",
               "https://img.example.org", "limited",
               "y",
               "2", SUPABASE_SESSION, SUPABASE_DIRECT,
               "2", "rediss://default:tok@x.upstash.io:6379",
               "2", "smtp.resend.com", "587", "resend", "re_key", "Y", "noreply@example.org", "N",
               "", "Test Organization", "My Lab", "", ""] + question_tail()
    result = questionnaire(tmp_path, answers, write=True)
    assert result.returncode == 0, result.stderr
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    for line in (
        "SPACEWORKS_DATABASE='external'", "SPACEWORKS_REDIS='external'", "SPACEWORKS_STORAGE='external'",
        "SPACEWORKS_MAINTENANCE_DATABASE_URL='" + SUPABASE_DIRECT.replace("postgresql:", "postgres:") + "'",
        "DATABASE_CONNECTION_MODE='session'", "MANAGED_POSTGRES='True'",
        "CELERY_BROKER_URL='rediss://default:tok@x.upstash.io:6379?ssl_cert_reqs=required'",
        "STORAGE_CAPABILITIES_FILE='/run/spaceworks-storage/capabilities.json'", "STORAGE_PRESIGN_METHOD='put'",
        "EMAIL_HOST='smtp.resend.com'", "EMAIL_USE_TLS='True'",
    ):
        assert line in env, line
    runtime = [line for line in env.splitlines() if line.startswith("SPACEWORKS_DATABASE_RUNTIME_URL=")][0]
    assert "spaceworks_app.abcd:" in runtime and "aws-0-eu.pooler.supabase.com:5432" in runtime
    assert "\"presign_methods\":[\"put\"]" in (tmp_path / "storage-config/capabilities.json").read_text(encoding="utf-8")
    for secret in ("r2-secret", "re_key", "tok@x.upstash", "pw@"):
        assert secret not in result.stdout, secret


def test_a_transaction_pooler_is_refused_at_the_prompt_and_asked_again(tmp_path):
    answers = ["", "", "3", "api.example.org", "", "y", "2", SUPABASE_TRANSACTION, SUPABASE_DIRECT,
               "1", "1", "", "Test Organization", "My Lab", "", ""] + question_tail()
    result = questionnaire(tmp_path, answers, write=True)
    assert result.returncode == 0, result.stderr
    assert "transaction-pooler address" in result.stdout
    assert "6543" not in (tmp_path / ".env").read_text(encoding="utf-8")


def test_pointer_starts_from_the_outside_runtime_url(tmp_path):
    env = tmp_path / "static.env"
    env.write_text("SPACEWORKS_DATABASE='external'\nSPACEWORKS_DATABASE_RUNTIME_URL='postgres://spaceworks_app:S3cret@h.example.org:5432/d?sslmode=require'\n")
    out = subprocess.run([sys.executable, str(ROOT / "scripts/bundled-database-url.py"), str(env)], text=True, capture_output=True)
    assert out.stdout.strip() == "postgres://spaceworks_app:S3cret@h.example.org:5432/d?sslmode=require"
    env.write_text("SPACEWORKS_DATABASE='external'\n")
    assert subprocess.run([sys.executable, str(ROOT / "scripts/bundled-database-url.py"), str(env)], capture_output=True).returncode != 0


# --- Connection checks ---------------------------------------------------------------------------

def probe(monkeypatch, **env):
    for key, value in env.items():
        monkeypatch.setenv("SW_PROBE_" + key, value)
    spec = importlib.util.spec_from_file_location("probe_external", ROOT / "scripts/installer/probe-external.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_psycopg2(monkeypatch, version_num, *, ssl=True, can_create_role=True, extensions=("pgcrypto", "pg_trgm"), tables=0):
    class Cursor:
        def __init__(self):
            self.rows = []

        def execute(self, sql, *args):
            if "server_version_num" in sql:
                self.rows = [(str(version_num),)]
            elif "pg_stat_ssl" in sql:
                self.rows = [(ssl,)]
            elif "rolcreaterole" in sql:
                self.rows = [(can_create_role,)]
            elif "pg_available_extensions" in sql:
                self.rows = [(name,) for name in extensions]
            elif "count(*)" in sql:
                self.rows = [(tables,)]
            else:
                self.rows = []

        def fetchone(self):
            return self.rows[0]

        def fetchall(self):
            return self.rows

    class Connection:
        def cursor(self):
            return Cursor()

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    module = types.ModuleType("psycopg2")
    module.Error = Exception
    module.connect = lambda *a, **k: Connection()
    extensions_module = types.ModuleType("psycopg2.extensions")
    extensions_module.parse_dsn = lambda url: {"host": "db.example.org"}
    monkeypatch.setitem(sys.modules, "psycopg2", module)
    monkeypatch.setitem(sys.modules, "psycopg2.extensions", extensions_module)


@pytest.mark.parametrize("kwargs,fragment", [
    ({"version_num": 150004}, "PostgreSQL 15"),
    ({"version_num": 170002, "ssl": False}, "not encrypted"),
    ({"version_num": 170002, "can_create_role": False}, "owner login"),
    ({"version_num": 170002, "extensions": ("pgcrypto",)}, "pg_trgm"),
])
def test_database_check_names_the_problem_and_the_fix(monkeypatch, kwargs, fragment):
    module = probe(monkeypatch, DB_URL="postgres://o:p@db.example.org/d?sslmode=require")
    fake_psycopg2(monkeypatch, **kwargs)
    with pytest.raises(module.Fail) as error:
        module.check_database()
    assert fragment in str(error.value) and "Fix:" in str(error.value)
    assert "p@db" not in str(error.value)


def test_database_check_requires_an_empty_database_on_first_install(monkeypatch):
    module = probe(monkeypatch, DB_URL="postgres://o:p@db.example.org/d?sslmode=require", EXPECT_EMPTY="1")
    fake_psycopg2(monkeypatch, 170002, tables=3)
    monkeypatch.setattr(module.Path, "is_file", lambda self: True)
    with pytest.raises(module.Fail, match="already contains tables"):
        module.check_database()


def test_redis_check_reports_unreachable_without_the_url(monkeypatch):
    module = probe(monkeypatch, REDIS_URL="rediss://default:secret@h.example.org:6379")
    redis = types.ModuleType("redis")

    class Redis:
        @staticmethod
        def from_url(*args, **kwargs):
            raise OSError("refused secret")
    redis.Redis = Redis
    monkeypatch.setitem(sys.modules, "redis", redis)
    with pytest.raises(module.Fail) as error:
        module.check_redis()
    assert "secret" not in str(error.value) and "Fix:" in str(error.value)
