"""Reports retain saved views and their event/member source rows across real gates."""
from urllib.parse import urlencode
from datetime import timedelta
from django.utils import timezone

import pytest
from django.urls import reverse

from apps.events.models import EventRegistration
from apps.operations.models import SavedView
from tests.accounts.account_factories import make_staff
from tests.events.checkin_helpers import make_event
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.modules.switch_matrix_object_helpers import client_for
from tests.operations.test_saved_report_views import payload
from tests.payments.account_helpers import make_payer
from tests.payments.switch_helpers_cx11b_p2 import route_cycle

pytestmark = [pytest.mark.django_db, pytest.mark.area_reports, pytest.mark.area_events]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["reports.saved_views", "reports", "membership"])
def test_saved_report_restores_same_preference_and_subject_after_switch(native, key):
    space = live_space("p2-saved-report", MODULE_KEYS)
    actor = make_staff(space, username="p2-saved-report-owner", access_status="active")
    row = SavedView.objects.create(makerspace=space, owner=actor, entity="report", name="Retained report",
                                    state=payload()["state"])
    url = f"/api/v1/admin/makerspaces/{space.pk}/saved-report-views/{row.pk}"
    route_cycle(space, client_for(actor, space, native), {"saved": row}, key, url,
        off=(404, "feature_disabled" if "." in key else "module_disabled"),
        check=lambda response: assert_saved(response, row))


def assert_saved(response, row):
    assert response.data["id"] == row.pk and response.data["state"] == row.state


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("report,key", [("event-registrations", "reports.event_exports"),
                                        ("event-attendance-pdf", "reports.event_pdf")])
@pytest.mark.parametrize("gate", ["feature", "reports", "events"])
def test_event_report_restores_same_event_and_registration_with_money_rail_off(native, report, key, gate):
    space = live_space("p2-event-report", set(MODULE_KEYS) - {"payments"})
    actor = make_staff(space, username="p2-event-report-manager", access_status="active")
    event = make_event(space, starts_at=timezone.now() - timedelta(days=2),
                       ends_at=timezone.now() - timedelta(days=1))
    person = make_payer("p2-event-report-person", space)
    row = EventRegistration.objects.create(event=event, member=person, name="Retained attendee", status="registered")
    pdf = report.endswith("pdf")
    url = reverse("report-export" if pdf else "analytics-generic", args=[space.pk, report])
    query = {"subject_kind": "event", "subject_id": event.pk}
    if pdf:
        query["format"] = "pdf"
    key = key if gate == "feature" else gate
    # 224c/226g: this PDF includes payee money. Device grants are refused
    # before source gates in every state; browser sessions still prove the export.
    session_only = native and pdf
    response = route_cycle(space, client_for(actor, space, native), {"event": event, "registration": row},
        key, url + "?" + urlencode(query), on=(403, "full_session_required") if session_only else (200, None),
        off=(403, "full_session_required") if session_only else
            (404, "feature_disabled" if gate == "feature" else "module_disabled"))
    if pdf and not session_only:
        assert response["Content-Type"] == "application/pdf" and response.content.startswith(b"%PDF")
