"""A Supabase shared-pooler login is `role.projectref`; the SQL role the grants target is `role`.

Both host orchestration entry points carry their own copy of the mapping (they run as privileged
one-shots outside the app), so both are pinned here against the same cases.
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
POOLER = "aws-0-eu-central-1.pooler.supabase.com"


def load(name):
    spec = importlib.util.spec_from_file_location(f"host_{name}", ROOT / "backend/scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def credentials(module):
    """bootstrap names it _runtime_credentials, transition _credentials; same contract."""
    return getattr(module, "_runtime_credentials", None) or module._credentials


@pytest.fixture(params=["bootstrap_host_orchestration", "transition_host_orchestration"])
def orchestration(request):
    return load(request.param)


@pytest.mark.parametrize("url,role", [
    (f"postgres://spaceworks_app.abcdefgh:secret@{POOLER}:5432/postgres?sslmode=require", "spaceworks_app"),
    (f"postgresql://postgres.abcdefgh:secret@{POOLER}:5432/postgres?sslmode=require", "postgres"),
    ("postgres://spaceworks_app:secret@db.abcdefgh.supabase.co:5432/postgres?sslmode=require", "spaceworks_app"),
    ("postgres://spaceworks_app:secret@db:5432/makerspace", "spaceworks_app"),
    # Dotted names are only split behind the shared pooler.
    ("postgres://app.team:secret@db.example.com:5432/x", "app.team"),
])
def test_wire_login_maps_to_the_sql_role_the_grants_target(orchestration, url, role):
    assert credentials(orchestration)(url) == (role, "secret")


def test_pooler_login_without_a_project_suffix_is_kept_as_is(orchestration):
    role, _ = credentials(orchestration)(f"postgres://spaceworks_app:secret@{POOLER}:5432/postgres")
    assert role == "spaceworks_app"


def test_percent_encoded_password_is_decoded_and_the_login_still_maps(orchestration):
    url = f"postgres://spaceworks_app.abcdefgh:p%40ss%2Fword@{POOLER}:5432/postgres"
    assert credentials(orchestration)(url) == ("spaceworks_app", "p@ss/word")


@pytest.mark.parametrize("url", ["mysql://u:p@h/db", "postgres://nouser@h/db", "postgres://u@h/db"])
def test_a_url_without_user_and_password_is_refused(orchestration, url):
    with pytest.raises(RuntimeError):
        credentials(orchestration)(url)
