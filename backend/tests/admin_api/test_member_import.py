"""G18 / #128 C-13: member import -> pending memberships with emailed invites, accepted by proof."""
import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.makerspaces.membership_services import claim_invitation
from apps.makerspaces.models import ImportedMember, MakerspaceMembership, MembershipRecord, MembershipRequest
from tests.makerspaces.l4_helpers import features_off, features_on, member, plan, space_with_manager
from tests.return_helpers import authenticated_client, make_user

pytestmark = pytest.mark.django_db
CSV = ("Name,Email,Phone,Member Number,Plan,End date,GSTIN,State code\n"
       "Asha,asha@example.test,+91 98765 43210,OLD-1,Monthly,2099-01-31,29ABCDE1234F1Z5,29\n"
       "Dup,asha@example.test,,OLD-2,,,,\n"
       "Bad,not-an-email,,,,,,\n"
       "Ravi,ravi@example.test,,OLD-3,Nope,,,\n"
       "Meera,meera@example.test,,,,,,\n")


def _person(username, email, **extra):
    user = make_user(username, access_status="active")
    # A queryset update: saving a new email through the model clears its verification.
    type(user).objects.filter(pk=user.pk).update(email=email, **extra)
    user.refresh_from_db()
    return user


def _upload(text=CSV, name="members.csv"):
    return SimpleUploadedFile(name, text.encode(), content_type="text/csv")


def _space(slug):
    space, manager = space_with_manager(slug)
    features_on(space, "import")
    plan(space, "Monthly")
    return space, authenticated_client(manager)


def test_preview_is_a_dry_run_with_reasons():
    space, client = _space("imp-preview")
    response = client.post(reverse("admin-member-import-preview", args=[space.pk]), {"file": _upload()}, format="multipart")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["counts"] == {"create": 2, "update": 0, "skip": 3}
    reasons = {row["row"]: row["reason"] for row in body["rows"]}
    assert reasons[3] == "duplicate_email" and reasons[4] == "email_invalid" and reasons[5] == "plan_unknown"
    assert not ImportedMember.objects.exists() and not MembershipRequest.objects.exists()


def test_apply_invites_without_linking_and_record_only_gets_no_invite():
    space, client = _space("imp-apply")
    existing = _person("asha-existing", "asha@example.test")
    response = client.post(reverse("admin-member-import-apply", args=[space.pk]),
                           {"file": _upload(), "record_only_rows": "[6]"}, format="multipart")
    assert response.status_code == 200, response.content
    assert response.json()["counts"]["invited"] == 1 and response.json()["counts"]["record_only"] == 1
    asha = ImportedMember.objects.get(external_number="OLD-1")
    assert asha.status == "invited" and asha.invitation.user_id is None  # never auto-linked (C-13)
    assert not MakerspaceMembership.objects.filter(makerspace=space, user=existing).exists()
    meera = ImportedMember.objects.exclude(pk=asha.pk).get()
    assert meera.status == "record_only" and meera.invitation_id is None
    entry = AuditLog.objects.get(action="membership.imported")
    assert "asha" not in str(entry.meta)


def test_accepting_with_the_verified_email_activates_and_opens_the_imported_term():
    space, client = _space("imp-accept")
    client.post(reverse("admin-member-import-apply", args=[space.pk]), {"file": _upload()}, format="multipart")
    asha = ImportedMember.objects.get(external_number="OLD-1")
    stranger = _person("imp-stranger", "other@example.test", email_verified_at=timezone.now())
    with pytest.raises(Exception):
        claim_invitation(stranger, asha.invitation_id)
    person = _person("imp-asha", "asha@example.test", email_verified_at=timezone.now())
    membership = claim_invitation(person, asha.invitation_id)
    asha.refresh_from_db()
    assert asha.status == "accepted" and membership.source == "import" and membership.member_number
    term = membership.terms.get()
    assert term.price is None and term.ends_at.date().year == 2099
    assert MembershipRecord.objects.get(membership=membership).gstin == "29ABCDE1234F1Z5"


def test_existing_member_and_re_import_update():
    space, client = _space("imp-dedup")
    already = member("imp-dedup", space).user.email
    text = f"Email,Name\n{already},Old\nnew@example.test,New\n"
    client.post(reverse("admin-member-import-apply", args=[space.pk]), {"file": _upload(text)}, format="multipart")
    again = client.post(reverse("admin-member-import-preview", args=[space.pk]),
                        {"file": _upload("Email,Name\nnew@example.test,Renamed\n")}, format="multipart").json()
    assert again["counts"]["update"] == 1
    first = client.post(reverse("admin-member-import-preview", args=[space.pk]), {"file": _upload(text)}, format="multipart")
    assert first.json()["rows"][0]["reason"] == "already_member"


def test_xlsx_is_parsed_on_the_server():
    import openpyxl
    space, client = _space("imp-xlsx")
    book = openpyxl.Workbook()
    book.active.append(["Email", "Name"])
    book.active.append(["x1@example.test", "Xavier"])
    data = io.BytesIO()
    book.save(data)
    upload = SimpleUploadedFile("members.xlsx", data.getvalue())
    body = client.post(reverse("admin-member-import-preview", args=[space.pk]), {"file": upload}, format="multipart").json()
    assert body["counts"]["create"] == 1


def test_off_switch_is_a_404():
    space, client = _space("imp-off")
    features_off(space, "import")
    response = client.post(reverse("admin-member-import-preview", args=[space.pk]), {"file": _upload()}, format="multipart")
    assert response.status_code == 404
