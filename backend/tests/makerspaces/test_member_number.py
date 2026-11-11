"""X12 member numbers (gapless, fixed, patterned), X13 record fields and X16 titles."""
import pytest
from django.urls import reverse
from rest_framework.exceptions import ValidationError

from apps.makerspaces.membership_activation import _activate_membership
from apps.makerspaces.membership_number import display_number, formatted, validate_pattern
from apps.makerspaces.membership_plan_services import create_term
from apps.makerspaces.models import MakerspaceRole
from tests.makerspaces.l4_helpers import features_off, features_on, member, plan, space_with_manager
from tests.return_helpers import authenticated_client, make_user

pytestmark = pytest.mark.django_db


def _join(space, slug):
    user = make_user(slug, access_status="active", email_verified_at="2026-01-01T00:00:00Z")
    role = MakerspaceRole.objects.get(makerspace=space, slug="member")
    return _activate_membership(user, space, user, role, source="open")


def test_numbers_are_gapless_per_space_and_survive_rejoin():
    space, _manager = space_with_manager("mn-gapless")
    first, second = _join(space, "mn-a"), _join(space, "mn-b")
    assert (first.member_number, second.member_number) == (1, 2)
    assert first.source == "join"
    first.status = "revoked"
    first.save()
    role = MakerspaceRole.objects.get(makerspace=space, slug="member")
    again = _activate_membership(first.user, space, first.user, role, source="open")
    assert again.member_number == 1


def test_term_holders_get_a_number_without_changing_their_source():
    space, manager = space_with_manager("mn-term")
    membership = member("mn-term", space)
    create_term(manager, membership, plan(space))
    membership.refresh_from_db()
    assert membership.member_number == 1 and membership.source == ""


def test_patterns():
    assert formatted(42, "") == "0042"
    assert formatted(42, "TNK-{number:5}") == "TNK-00042"
    assert formatted(7, "{year}/{number}", 2026) == "2026/7"
    for bad in ("TNK", "{number}{number}", "A<{number}>"):
        with pytest.raises(ValidationError):
            validate_pattern(bad)


def test_pattern_setting_needs_member_numbers():
    space, manager = space_with_manager("mn-setting")
    client = authenticated_client(manager)
    url = reverse("admin-membership-admission", args=[space.pk])
    assert client.patch(url, {"member_number_pattern": "TNK-{number:4}"}, format="json").status_code == 403
    features_on(space, "member_numbers")
    assert client.patch(url, {"member_number_pattern": "TNK-{number:4}"}, format="json").status_code == 200
    membership = member("mn-shown", space)
    create_term(manager, membership, plan(space))
    membership.refresh_from_db()
    assert display_number(membership) == "TNK-0001"


def test_record_fields_validate_gstin_and_stay_out_of_audit():
    space, manager = space_with_manager("mn-record")
    membership = member("mn-record", space)
    client = authenticated_client(manager)
    url = reverse("admin-membership-record", args=[membership.pk])
    assert client.get(url).status_code == 404
    features_on(space, "records")
    bad = client.put(url, {"state_code": "29", "gstin": "NOTAGSTIN"}, format="json")
    assert bad.status_code == 400
    mismatch = client.put(url, {"state_code": "27", "gstin": "29ABCDE1234F1Z5"}, format="json")
    assert mismatch.status_code == 400
    ok = client.put(url, {"state_code": "29", "gstin": "29abcde1234f1z5", "staff_notes": "Pays by UPI"}, format="json")
    assert ok.status_code == 200, ok.content
    assert ok.json()["gstin"] == "29ABCDE1234F1Z5"
    from apps.audit.models import AuditLog
    entry = AuditLog.objects.get(action="membership.record_updated")
    assert "29ABCDE1234F1Z5" not in str(entry.meta) and "UPI" not in str(entry.meta)


def test_titles_are_display_only_with_one_primary():
    space, manager = space_with_manager("mn-titles")
    membership = member("mn-titles", space)
    client = authenticated_client(manager)
    list_url = reverse("admin-membership-titles", args=[space.pk])
    assert client.post(list_url, {"name": "Treasurer"}, format="json").status_code == 404
    features_on(space, "titles")
    treasurer = client.post(list_url, {"name": "Treasurer", "colour": "citron"}, format="json").json()
    mentor = client.post(list_url, {"name": "Mentor"}, format="json").json()
    assert client.post(list_url, {"name": "Purple", "colour": "#800080"}, format="json").status_code == 400
    assign = reverse("admin-membership-title-assignments", args=[membership.pk])
    client.post(assign, {"title_id": treasurer["id"], "primary": True}, format="json")
    rows = client.post(assign, {"title_id": mentor["id"], "primary": True}, format="json").json()
    assert [row["title"]["name"] for row in rows if row["is_primary"]] == ["Mentor"]
    from apps.accounts import rbac
    assert not rbac.can(membership.user, rbac.Action.MANAGE_MEMBERS, space.pk)
    features_off(space, "titles")
    assert client.get(assign).status_code == 404
