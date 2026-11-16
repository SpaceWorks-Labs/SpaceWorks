"""Badge/report hints stay constant-cost and never consult tenant VIEW_AUDIT.

The badge hint is event-scoped (manage_registrations); tenant audit access no longer
widens or narrows it.
"""
from tests.events.manual_grant_fixture import create_manual_grant

from tests.events.ticketing_helpers import account
from tests.account_split.sweep_g2_helpers import staff_user
from tests.account_split_g2_helpers import grant_organization_action

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accounts import rbac
from apps.events.models import EventStaffGrant
from apps.events.serializers_event_authority import event_list_context
from apps.events.serializers_event_details import EventAdminSerializer
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole
from tests.events.checkin_helpers import make_event, make_staff
from tests.events.test_staff_grant_page_authority import _page_fixture
from tests.events.ticketing_helpers import event_space

pytestmark = pytest.mark.django_db


class BadgeReportProjection(EventAdminSerializer):
    class Meta(EventAdminSerializer.Meta):
        fields = ("badge_sensitive_fields_allowed", "report_features")


@pytest.mark.parametrize("reports", [True, False])
@pytest.mark.parametrize("source,audit", [("tenant", True), ("grant", True), ("grant", False)])
def test_badge_and_report_query_cost_is_constant_for_200_events(source, audit, reports):
    space, user, events, _ = _page_fixture(200, source)
    modules = set(space.enabled_modules) - {"reports"}
    if reports:
        modules.add("reports")
    space.enabled_modules = sorted(modules)
    space.enabled_features = []
    space.save()
    if source == "grant":
        from tests.events.manual_grant_fixture import update_manual_permissions
        update_manual_permissions(EventStaffGrant.objects.filter(user=user), ["manage_registrations"])
        if audit:
            from tests.fixed_roles.helpers import assign_builtin_roles
            grant_organization_action(space, user, "view_audit")
    counts = []
    for size in (1, 24, 200):
        page = events[:size]
        context = event_list_context(SimpleNamespace(user=user), page)
        with patch.object(rbac, "can", wraps=rbac.can) as check, CaptureQueriesContext(connection) as queries:
            data = BadgeReportProjection(page, many=True, context=context).data
        if not reports:
            assert not any(call.args[1] == rbac.Action.VIEW_AUDIT for call in check.call_args_list)
        # Every source holds manage_registrations, so the badge hint is on regardless of audit. Report hints
        # follow the reports module: the tenant Event Manager and, by decision 248 / EB1, a grantee with
        # manage_registrations on this event both get the event analytics.
        allowed = reports
        assert data == [{"badge_sensitive_fields_allowed": True,
                         "report_features": ["analytics"] if allowed else []}] * size
        counts.append(len(queries))
    assert counts[0] == counts[1] == counts[2]


def test_badge_hint_does_not_check_audit_without_registration_authority():
    _, user, events, _ = _page_fixture(2, "grant")
    context = event_list_context(SimpleNamespace(user=user), events)
    with patch.object(rbac, "can", wraps=rbac.can) as check:
        data = BadgeReportProjection(events, many=True, context=context).data
    assert not any(call.args[1] == rbac.Action.VIEW_AUDIT for call in check.call_args_list)
    assert all(row["badge_sensitive_fields_allowed"] is False for row in data)


def test_badge_hint_follows_event_registration_authority_per_makerspace():
    space, _, events, _ = _page_fixture(1, "tenant")
    user = account("badge-delegated-manager")
    grant_organization_action(space, user, "manage_events")
    other = event_space("badge-audit-other")
    foreign = make_event(other)
    create_manual_grant(makerspace=other, event=foreign, user=user,
                                  granted_by=make_staff(other), permissions=["manage_registrations"])
    page = [events[0], foreign, events[0]]
    context = event_list_context(SimpleNamespace(user=user), page)
    with patch.object(rbac, "can", wraps=rbac.can) as check:
        data = BadgeReportProjection(page, many=True, context=context).data
    assert not any(call.args[1] == rbac.Action.VIEW_AUDIT for call in check.call_args_list)
    # The foreign event's manage_registrations grant now admits custom answers there too.
    assert [row["badge_sensitive_fields_allowed"] for row in data] == [True, True, True]

    from tests.fixed_roles.helpers import assign_builtin_roles
    user = staff_user(space, "badge-event-manager", staff_role="event_manager")
    fresh = event_list_context(SimpleNamespace(user=user), [events[0]])
    assert "manage_registrations" in fresh["event_authority"][(events[0]._meta.label, events[0].pk)][1]
    # An Event-Manager-shaped role (manage_events, no view_audit) may print custom answers.
    assert BadgeReportProjection(events[0], context=fresh).data["badge_sensitive_fields_allowed"] is True
