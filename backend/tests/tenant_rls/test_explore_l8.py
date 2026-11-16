import pytest
from django.db import connection

from apps.tenant_rls.policies import build_plans
from apps.tenant_rls.checks import coverage_gaps
from apps.tenant_rls.context import tenant_context, capability_context

pytestmark = pytest.mark.django_db


def test_explore_generation(capsys):
    plans, unresolvable = build_plans()
    gaps = coverage_gaps()
    with capsys.disabled():
        print("\nPLANS", len(plans), "UNRESOLVABLE", len(unresolvable), "GAPS", len(gaps))
        for label, reason in sorted(unresolvable.items()):
            print("UNRES", label, reason)
        for table in gaps[:40]:
            print("GAP", table)
    assert plans


def test_explore_boundary(probe, spaces, capsys):
    from apps.boxes.models import Box
    a, b = spaces
    Box.objects.create(makerspace=a, label="A box")
    Box.objects.create(makerspace=b, label="B box")
    with capsys.disabled():
        print("\nSYNC", len(probe.applied), probe.unchanged, probe.failed)
    assert Box.objects.filter(label__in=["A box", "B box"]).count() == 2
    with tenant_context(a.pk):
        labels = sorted(Box.objects.filter(label__in=["A box", "B box"]).values_list("label", flat=True))
    assert labels == ["A box"]
    with capability_context("backup", label="test"):
        assert Box.objects.filter(label__in=["A box", "B box"]).count() == 2
    assert Box.objects.filter(label__in=["A box", "B box"]).count() == 2


def test_explore_makemigrations_check(capsys):
    from io import StringIO
    from django.core.management import call_command
    out = StringIO()
    try:
        call_command("makemigrations", "--check", "--dry-run", stdout=out)
    finally:
        with capsys.disabled():
            print("\nMAKEMIGRATIONS", out.getvalue()[-3000:])


def test_explore_checks(capsys):
    from django.core.checks import run_checks
    errors = [m for m in run_checks() if m.level >= 40]
    with capsys.disabled():
        for m in errors:
            print("CHECK", m.id, str(m.msg)[:300])
    assert not [m for m in errors if m.id.startswith("tenant_rls")]
