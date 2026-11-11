import pytest
from django.db import connection

from apps.tenant_rls import capabilities, report, role_contract

PROBE = "spaceworks_rls_probe"


def _reset():
    role_contract.reset_cache()
    capabilities.reset_sampling()
    report.reset_sampling()


@pytest.fixture
def probe(settings):
    """Force RLS on for a superuser test run: bound statements SET LOCAL ROLE to a narrow role."""
    from apps.tenant_rls.sync import sync
    settings.TENANT_RLS_PROBE_ROLE = PROBE
    settings.TENANT_RLS_MODE = "auto"
    _reset()
    result = sync()
    yield result
    _reset()


@pytest.fixture
def spaces(db):
    from apps.makerspaces.models import Makerspace
    return (Makerspace.objects.create(name="RLS A", slug="rls-a"),
            Makerspace.objects.create(name="RLS B", slug="rls-b"))


@pytest.fixture
def boxes(spaces):
    from apps.boxes.models import Box
    a, b = spaces
    return Box.objects.create(makerspace=a, label="A box"), Box.objects.create(makerspace=b, label="B box")


def labels():
    from apps.boxes.models import Box
    return sorted(Box.objects.filter(label__in=["A box", "B box"]).values_list("label", flat=True))


def setting(name):
    """Read a GUC with a raw cursor (never through the RLS wrapper)."""
    with connection.cursor() as cursor:
        cursor.cursor.execute("SELECT coalesce(current_setting(%s, true), '')", [name])
        return cursor.cursor.fetchone()[0]
