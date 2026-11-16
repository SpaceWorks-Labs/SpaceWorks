"""Both accepted calendar kinds preserve issued tokens across their capability switch."""
import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.events.models import PersonalCalendarFeed
from tests.events.checkin_helpers import make_member
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("kind,key", [("shifts", "events.shifts_feed"), ("combined", "calendar.combined_feed")])
@pytest.mark.parametrize("method,on_status", [("get", 200), ("post", 200), ("delete", 204)])
def test_personal_calendar_switch_refuses_without_changing_the_issued_token(kind, key, method, on_status):
    space = live_space("cx2-calendar", MODULE_KEYS)
    member = make_member(space)
    client = authenticated_client(member)
    url = reverse("member-personal-calendar-feed", args=[space.pk, kind])
    issued = client.post(url, {}, format="json")
    assert issued.status_code == 200, issued.data
    before = PersonalCalendarFeed.objects.filter(makerspace=space, user=member, kind=kind).values().get()
    original = space.enabled_features
    space.enabled_features = [feature for feature in original if feature != key]
    space.save(update_fields=["enabled_features"])
    audit_count = AuditLog.objects.count()
    response = getattr(client, method)(url, {}, format="json")
    assert (response.status_code, response.data["code"]) == (404, "feature_disabled")
    assert PersonalCalendarFeed.objects.filter(pk=before["id"]).values().get() == before
    assert AuditLog.objects.count() == audit_count
    space.enabled_features = original
    space.save(update_fields=["enabled_features"])
    assert PersonalCalendarFeed.objects.filter(pk=before["id"]).values().get() == before
    response = getattr(client, method)(url, {}, format="json")
    assert response.status_code == on_status, getattr(response, "data", None)
