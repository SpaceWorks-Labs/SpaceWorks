"""The incident RLS exists for: a query that forgets its makerspace filter inside a bound request."""

import pytest

from apps.tenant_rls.context import tenant_context

pytestmark = pytest.mark.django_db


def test_a_forgotten_filter_returns_only_the_bound_tenant(probe, boxes):
    from apps.audit.services import record
    from apps.audit.models import AuditLog
    from apps.boxes.models import Box
    a, b = (box.makerspace for box in boxes)
    record(None, "test.rls_marker", makerspace=b)
    with tenant_context(a.pk):
        assert set(Box.objects.values_list("makerspace_id", flat=True)) == {a.pk}  # no .filter(makerspace=...)
        assert not AuditLog.objects.filter(makerspace=b).exists()
        assert Box.objects.update(label="renamed") == 1
    assert Box.objects.get(pk=boxes[1].pk).label == "B box"


def test_platform_rows_stay_visible_inside_a_binding(probe, boxes):
    from apps.audit.models import AuditLog
    from apps.audit.services import record
    a = boxes[0].makerspace
    record(None, "test.rls_platform_marker", makerspace=None)
    with tenant_context(a.pk):
        assert AuditLog.objects.filter(action="test.rls_platform_marker").exists()
        record(None, "test.rls_platform_inside", makerspace=None)
    assert AuditLog.objects.filter(action="test.rls_platform_inside").exists()
