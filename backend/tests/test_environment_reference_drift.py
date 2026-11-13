"""Every environment variable the backend reads is documented (cloud lane).

`settings_policy.ENV_SURFACE` is already pinned to exactly what the code reads
(`test_env_surface_drift.py`). At `b7c2ee93` 167 of its 247 names appeared in no doc at all,
so an operator had nowhere to look up `SECURE_SSL_REDIRECT`, `INFRA_HOSTS` or any rate
limit. `docs/environment-reference.md` is the complete list, and this keeps it complete in
both directions.
"""

import re
from pathlib import Path

from apps.backup.settings_policy import ENV_SURFACE, HOST_ONLY_POLICIES

DOC = Path(__file__).resolve().parents[2] / "docs" / "environment-reference.md"
REFERENCE_DOCS = (
    DOC,
    DOC.with_name("environment-reference-delivery.md"),
    DOC.with_name("environment-operations.md"),
)


ROW = re.compile(r"^\| `([A-Z0-9_]+)` \|", re.M)
# Stale since 459865dd (R3 AG1): the reference now also documents keys backend Python never
# reads -- Compose host settings, frontend build/container settings and keys removed in
# release 2. Rows in those sections are checked in the opposite direction instead.
NON_BACKEND_SECTIONS = frozenset({
    "Compose host settings", "Frontend build and container settings", "Removed in release 2",
    "Removed in 0.12.0",
})
# Set by manage.py / WSGI / ASGI / Celery bootstrap; the env-surface scanner discards it on purpose.
BOOTSTRAP_ONLY = frozenset({"DJANGO_SETTINGS_MODULE"})


def _rows_by_section():
    rows = {}
    for path in REFERENCE_DOCS:
        for chunk in re.split(r"^## ", path.read_text(encoding="utf-8"), flags=re.M):
            title = chunk.split("\n", 1)[0].strip()
            rows.setdefault(title, set()).update(ROW.findall(chunk))
    return rows


def _documented():
    return set().union(*(names for title, names in _rows_by_section().items()
                         if title not in NON_BACKEND_SECTIONS))


def _non_backend_rows():
    return set().union(*(names for title, names in _rows_by_section().items() if title in NON_BACKEND_SECTIONS))


def test_every_environment_variable_is_in_the_reference():
    missing = sorted(set(ENV_SURFACE) - _documented())
    assert not missing, (
        f"docs/environment-reference.md does not document {missing}. Add a row in the "
        f"right section with its default and what it is for."
    )


def test_the_reference_lists_nothing_the_backend_does_not_read():
    # Host-only rows have explicit exclusions, not fictitious backend env reads.
    assert set(ENV_SURFACE).isdisjoint(HOST_ONLY_POLICIES)
    stale = sorted(_documented() - set(ENV_SURFACE) - set(HOST_ONLY_POLICIES) - BOOTSTRAP_ONLY)
    assert not stale, f"docs/environment-reference.md documents {stale}, which nothing reads"
    assert _non_backend_rows(), "the Compose/frontend/removed sections were not found"
    read_after_all = sorted(_non_backend_rows() & set(ENV_SURFACE))
    assert not read_after_all, (
        f"docs/environment-reference.md lists {read_after_all} as Compose-only, frontend-only or "
        f"removed, but the backend reads them; move each row to the section for what it does"
    )


def test_the_production_compose_file_passes_the_observability_opt_ins():
    """Documented but inert: no compose service uses env_file, so a value in `.env`
    only reaches Django through an explicit `environment:` entry."""
    import yaml

    root = DOC.parents[1]
    for name in ("docker-compose.prod.yml", "docker-compose.cloud.yml"):
        document = yaml.safe_load((root / name).read_text(encoding="utf-8"))
        backend = document["services"]["backend"]["environment"]
        for key in ("METRICS_TOKEN", "SENTRY_DSN", "SENTRY_TRACES_SAMPLE_RATE", "SENTRY_ENVIRONMENT"):
            assert key in backend, f"{name} does not pass {key} to the backend"
