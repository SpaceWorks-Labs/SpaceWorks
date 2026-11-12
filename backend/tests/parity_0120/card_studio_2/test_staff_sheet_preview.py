"""Staff ID cards get the same first-sheet preview as member, programme and event cards (decision 344(b))."""
import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.card_designs import staff_card_services
from apps.makerspaces.models import MakerspaceMembership, MemberCardSettings
from tests.l3_local.helpers import card_space, client, custom_staff, manager, member

pytestmark = pytest.mark.django_db(transaction=True)


def _space(slug):
    space = card_space(slug, features=("membership.staff_cards",))
    MemberCardSettings.objects.update_or_create(makerspace=space, defaults={"public_verify": True})
    return space


def test_the_first_staff_sheet_previews_and_is_audited_by_count():
    space = _space("cs2-staff-preview")
    sm = manager(space)
    user = custom_staff(space, ("technician",), "tech")
    staff_card_services.issue(sm, MakerspaceMembership.staff_tracks.get(makerspace=space, user=user))
    response = client(sm).post(reverse("admin-staff-card-job-preview", kwargs={"makerspace_id": space.pk}),
                               {"paper": "a4"}, format="json")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1 and body["sheets"] == 1 and body["front"].startswith("data:image/png;base64,")
    log = AuditLog.objects.get(action="card_job.previewed", makerspace=space)
    assert log.meta["scope"] == "staff_cards" and log.meta["count"] == 1


def test_a_member_cannot_preview_staff_sheets():
    space = _space("cs2-staff-preview-rbac")
    user, _membership = member(space)
    response = client(user).post(reverse("admin-staff-card-job-preview", kwargs={"makerspace_id": space.pk}), {}, format="json")
    assert response.status_code in (403, 404)
