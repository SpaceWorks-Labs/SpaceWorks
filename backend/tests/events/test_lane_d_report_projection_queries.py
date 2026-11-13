"""Report hints consume page authority and cache tenant-level audit checks."""

from tests.account_split_g2_helpers import grant_organization_action

from types import SimpleNamespace

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.events.models import EventStaffGrant
from apps.events.serializers_event_authority import event_list_context
from apps.events.serializers_event_details import EventAdminSerializer
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole
from tests.events.test_staff_grant_page_authority import _page_fixture

from tests.fixed_roles.helpers import assign_builtin_roles  # noqa: E402

pytestmark = pytest.mark.django_db


class ReportProjection(EventAdminSerializer):
    class Meta(EventAdminSerializer.Meta):
        fields = ("report_features",)


def report_page(source, *, audit=True):
    space, user, events, _ = _page_fixture(24, source)
    space.enabled_modules = sorted(set(space.enabled_modules) | {"reports"})
    space.enabled_features += ["reports.event_exports", "reports.event_pdf"]
    space.save()
    if source == "grant":
        from tests.events.manual_grant_fixture import update_manual_permissions
        update_manual_permissions(EventStaffGrant.objects.filter(user=user, event__isnull=False),
                                  ["manage_registrations"])
    if audit and source != "tenant":
        grant_organization_action(space, user, "view_audit")
    return space, user, events


@pytest.mark.parametrize("source,audit", [("tenant", True), ("organizer", True),
    ("series_organizer", True), ("grant", True), ("organizer", False),
    ("series_organizer", False), ("grant", False)])
def test_report_projection_query_cost_is_constant_with_reports_enabled(source, audit):
    _, user, events = report_page(source, audit=audit)
    # Decision 248 / EB1: a grantee holding manage_registrations on the event reads its analytics and
    # export without tenant audit; the PDF stays with the managers. Everyone else needs the audit read.
    expected = (["analytics", "exports"] + ([] if source == "grant" else ["pdf"])) if audit or source == "grant" else []
    counts = []
    for size in (1, 24):
        page = events[:size]
        with CaptureQueriesContext(connection) as queries:
            context = event_list_context(SimpleNamespace(user=user), page)
            data = ReportProjection(page, many=True, context=context).data
        counts.append(len(queries))
        assert data == [{"report_features": expected}] * size
    assert counts[0] == counts[1]
    # Detail's fallback must agree with the precomputed list projection.
    assert ReportProjection(events[0], context={"request": SimpleNamespace(user=user)}).data == data[0]


@pytest.mark.parametrize("state", ["no_audit", "no_registration_permission", "restricted",
                                   "password_rotation", "reports_off"])
def test_report_projection_preserves_permission_conjunction_and_active_account_checks(state):
    space, user, events = report_page("grant", audit=state != "no_audit")
    if state == "no_registration_permission":
        from tests.events.manual_grant_fixture import update_manual_permissions
        update_manual_permissions(EventStaffGrant.objects.filter(user=user, event__isnull=False), ["edit_details"])
    elif state == "restricted":
        user.access_status = "restricted"
    elif state == "password_rotation":
        user.must_change_password = True
    elif state == "reports_off":
        space.enabled_modules.remove("reports")
        space.save(update_fields=["enabled_modules"])
    context = event_list_context(SimpleNamespace(user=user), events)
    # Without the audit read a registrations grantee still gets analytics and exports (decision 248),
    # so that state is the one that is not empty; every other state removes the grant's reports.
    expected = ["analytics", "exports"] if state == "no_audit" else []
    assert all(row["report_features"] == expected for row in ReportProjection(events, many=True, context=context).data)
