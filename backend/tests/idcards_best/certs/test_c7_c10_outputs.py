"""C7-C10: PNG export, share image, holder name opt-in, richer verification, issue plan and issued list."""
from io import BytesIO

import pytest
from PIL import Image
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.events.certificates.lifecycle import render_certificate
from apps.events.certificates.models import EventCertificatePublicationPolicy
from apps.events.contributions.models_roles import EventRoleAssignment
from tests.events.checkin_helpers import make_member, make_staff, register

from .helpers import ended_event, issue

pytestmark = pytest.mark.django_db(transaction=True)


def _rendered(slug):
    space, event = ended_event(slug)
    EventCertificatePublicationPolicy.objects.create(event=event, enabled=True)
    member = make_member(space, display_name="Ada Lovelace")
    row = issue(event, "registration", register(event, member, status="attended").pk, activate=False)
    row = render_certificate(row)
    assert row.status == "active" and len(row.sha256) == 64
    return space, event, member, row


def public_get(path):
    """Public certificate reads are host-checked; ask through the platform's own host."""
    return APIClient().get(path, HTTP_HOST="localhost")


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_holder_list_png_share_image_and_name_opt_in():
    space, event, member, row = _rendered("c7-holder")
    client = _client(member)
    base = f"/api/v1/member/makerspaces/{space.pk}/certificates/"
    listing = client.get(base)
    assert listing.status_code == 200, listing.content
    item = listing.data[0]
    assert item["kind_title"] == "Certificate of attendance" and item["verifiable"] is True and item["holder_name_public"] is False
    png = client.get(f"{base}{row.pk}/png/")
    assert png.status_code == 200 and png["Content-Type"] == "image/png"
    with Image.open(BytesIO(png.content)) as image:
        assert image.size == (3508, 2480)
    share = client.get(f"{base}{row.pk}/share-image/")
    with Image.open(BytesIO(share.content)) as image:
        assert image.size == (1200, 627)
    verify = public_get(f"/api/v1/public/event-certificates/{row.serial}/verify/")
    assert verify.data["recipient_name"] is None and verify.data["sha256"] == row.sha256
    assert verify["X-Robots-Tag"] == "noindex" and verify["Referrer-Policy"] == "no-referrer"
    assert client.post(f"{base}{row.pk}/holder-name/", {"show": True}, format="json").data["holder_name_public"] is True
    assert public_get(f"/api/v1/public/event-certificates/{row.serial}/verify/").data["recipient_name"] == "Ada Lovelace"
    actions = set(AuditLog.objects.filter(makerspace=space).values_list("action", flat=True))
    assert {"event.certificate_png_downloaded", "event.certificate_share_image_downloaded",
            "event.certificate_holder_name_changed"} <= actions
    other = _client(make_member(space, "c7-other"))
    assert other.get(f"{base}{row.pk}/png/").status_code == 404
    assert other.post(f"{base}{row.pk}/holder-name/", {"show": False}, format="json").status_code == 404


def test_public_share_image_follows_verification():
    space, event, member, row = _rendered("c8-share")
    response = public_get(f"/api/v1/public/event-certificates/{row.serial}/share.png")
    assert response.status_code == 200 and response["X-Robots-Tag"] == "noindex"
    card = public_get(f"/api/v1/public/event-certificates/{row.serial}/share/")
    html = card.content.decode()
    assert card.status_code == 200 and "og:image" in html and "share.png" in html and 'content="noindex"' in html
    assert "Ada Lovelace" not in html
    EventCertificatePublicationPolicy.objects.filter(event=event).update(enabled=False)
    assert public_get(f"/api/v1/public/event-certificates/{row.serial}/share.png").status_code == 404
    assert public_get(f"/api/v1/public/event-certificates/{row.serial}/share/").status_code == 404


def test_issue_plan_lists_recipients_skips_and_samples():
    space, event = ended_event("c10-plan")
    staff = make_staff(space)
    attendee = make_member(space, "c10-attendee", display_name="Grace Hopper")
    registration = register(event, attendee, status="attended")
    host = make_member(space, "c10-host", display_name="Host Person")
    EventRoleAssignment.objects.create(event=event, makerspace=space, member=host, role="co_organizer",
                                       origin="staff", state="approved")
    client = _client(staff)
    url = f"/api/v1/admin/events/{event.pk}/certificates/issue-plan/"
    plan = client.post(url, {"groups": ["attendance", "roles"]}, format="json")
    assert plan.status_code == 200, plan.content
    kinds = {(row["kind"], row["name"]) for row in plan.data["recipients"]}
    assert kinds == {("attendance", "Grace Hopper"), ("organiser_thanks", "Host Person")}
    assert plan.data["counts"] == {"attendance": 1, "organiser_thanks": 1}
    sample = client.post(url + "sample.pdf", {key: plan.data["recipients"][0][key] for key in (
        "subject_kind", "subject_id", "kind", "award_id", "result_revision_id")}, format="json")
    assert sample.status_code == 200 and sample.content.startswith(b"%PDF")
    issue(event, "registration", registration.pk)
    again = client.post(url, {"groups": ["attendance"]}, format="json")
    assert again.data["recipients"] == [] and again.data["skipped"][0]["reason"] == "Already has this certificate."
    issued = client.get(f"/api/v1/admin/events/{event.pk}/certificates/issued/")
    assert issued.data["count"] == 1 and issued.data["results"][0]["kind_title"] == "Certificate of attendance"
    assert _client(attendee).post(url, {"groups": ["attendance"]}, format="json").status_code in (403, 404)
