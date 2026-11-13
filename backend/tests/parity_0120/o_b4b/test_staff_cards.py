"""O-B4 part 2: staff ID cards -- issue, verify page, separate numbering, lifecycle hooks, switch off, limit."""
import pytest
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.card_designs import staff_card_hooks as hooks
from apps.card_designs import staff_card_numbering, tokens
from apps.card_designs import staff_card_services as services
from apps.card_designs.holders import registered
from apps.card_designs.models import StaffCard
from apps.makerspaces import member_card_services
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole, MemberCardSettings
from tests.l3_local.helpers import card_space, client, custom_staff, manager, member

pytestmark = pytest.mark.django_db(transaction=True)
FEATURES = ("membership.staff_cards",)


def _space(slug, *, auto=False):
    extra = ("membership.staff_cards_auto_issue",) if auto else ()
    space = card_space(slug, features=FEATURES + extra)
    MemberCardSettings.objects.update_or_create(makerspace=space, defaults={"public_verify": True})
    return space


def _staff(space, slugs=("technician",), name="tech"):
    user = custom_staff(space, slugs, name)
    return user, MakerspaceMembership.staff_tracks.get(makerspace=space, user=user)


def _verify(token):
    return APIClient().get(f"/api/v1/public/card-verifications/{token}", HTTP_HOST="testserver")


def test_issue_creates_card_token_and_audit_and_requires_authority():
    space = _space("sc-issue")
    sm = manager(space)
    _user, staff = _staff(space)
    card = services.issue(sm, staff)
    assert card.is_active and card.number_text == "STF-0001" and card.roles == ["technician"]
    assert tokens.live("staff_card", card) is not None
    assert AuditLog.objects.filter(action="staff_card.issued", makerspace=space).exists()
    from django.core.exceptions import PermissionDenied
    with pytest.raises(PermissionDenied):
        services.issue(member(space)[0], staff)


def test_numbering_is_separate_from_member_cards():
    space = _space("sc-number")
    sm = manager(space)
    _u, membership = member(space)
    mcard = member_card_services.issue_card(sm, membership)
    _user, staff = _staff(space)
    card = services.issue(sm, staff)
    assert card.number_text == "STF-0001" and mcard.number_text != card.number_text
    staff_card_numbering.save(space, "TEAM", "{PREFIX}-{YY}-{SEQ:3}")
    _other_user, other = _staff(space, ("handover",), "hand")
    assert services.issue(sm, other).number_text.startswith("TEAM-")
    with pytest.raises(ValidationError):
        staff_card_numbering.validate("TEAM", "{PREFIX}-{UNIT}-{SEQ}")


def test_public_verify_shows_name_staff_roles_and_never_contact_details():
    space = _space("sc-verify")
    sm = manager(space)
    user, staff = _staff(space)
    card = services.issue(sm, staff)
    token = tokens.live("staff_card", card).token
    response = _verify(token)
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True and body["label"].startswith("Staff") and body["holder"]["name"]
    assert user.email not in str(body)
    services.revoke(sm, card)
    assert _verify(token).json()["valid"] is False


def test_staff_access_ending_revokes_the_card():
    space = _space("sc-revoke")
    sm = manager(space)
    _user, staff = _staff(space)
    card = services.issue(sm, staff)
    from apps.accounts import staff_account_lifecycle as lifecycle
    lifecycle.revoke(sm, space.pk, staff.pk, reason="left")
    card.refresh_from_db()
    assert card.revoked_at is not None and card.revoked_reason == "staff_access_ended"


def test_account_suspension_revokes_and_reads_revoked_live():
    space = _space("sc-suspend")
    sm = manager(space)
    user, staff = _staff(space)
    card = services.issue(sm, staff)
    user.access_status = User.AccessStatus.SUSPENDED
    user.save(update_fields=["access_status"])
    assert registered()["staff_card"].standing(StaffCard.objects.get(pk=card.pk)) == "revoked"  # a fresh read, not the cached user
    hooks.after_user_access_changed(sm, user)
    card.refresh_from_db()
    assert card.revoked_at is not None and card.revoked_reason == "account_restricted"


def test_role_change_reissues_same_number_new_token_and_never_blocks(monkeypatch):
    from apps.makerspaces.role_assignments import set_membership_roles
    space = _space("sc-roles")
    sm = manager(space)
    _user, staff = _staff(space)
    card = services.issue(sm, staff)
    old_token = tokens.live("staff_card", card).token
    handover = MakerspaceRole.objects.get(makerspace=space, slug="handover")
    set_membership_roles(makerspace=space, actor=sm, membership=staff, roles=[handover])
    card.refresh_from_db()
    assert card.number_text == "STF-0001" and card.roles == ["handover"]
    assert tokens.live("staff_card", card).token != old_token
    assert AuditLog.objects.filter(action="staff_card.reissued", meta__reason="roles_changed").exists()

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(services, "reissue_locked", boom)
    technician = MakerspaceRole.objects.get(makerspace=space, slug="technician")
    set_membership_roles(makerspace=space, actor=sm, membership=staff, roles=[technician])  # must not raise
    staff.refresh_from_db()
    assert staff.assigned_role_id == technician.pk


def test_auto_issue_on_grant_when_switched_on_and_not_otherwise():
    on, off = _space("sc-auto-on", auto=True), _space("sc-auto-off")
    for space, expected in ((on, 1), (off, 0)):
        _user, staff = _staff(space)
        hooks.after_roles_changed(manager(space), staff)
        assert StaffCard.objects.filter(makerspace=space).count() == expected


def test_switch_off_is_404_and_limit_is_409():
    off = card_space("sc-off")
    assert client(manager(off)).get(f"/api/v1/admin/makerspaces/{off.pk}/staff-cards").status_code == 404
    space = _space("sc-limit")
    sm = manager(space)
    space.resource_limit_overrides = {"staff_cards_issued_monthly": 1}
    space.save(update_fields=["resource_limit_overrides"])
    _u1, one = _staff(space)
    _u2, two = _staff(space, ("handover",), "hand")
    api = client(sm)
    base = f"/api/v1/admin/makerspaces/{space.pk}/staff-cards"
    assert api.post(base, {"membership_id": one.pk}, format="json").status_code == 201
    assert api.post(base, {"membership_id": two.pk}, format="json").status_code == 409
    listing = api.get(base).json()
    assert listing["count"] >= 2 and {row["card"] is not None for row in listing["results"]} >= {True, False}


def test_staff_holder_sees_own_card_in_my_cards():
    space = _space("sc-mine")
    sm = manager(space)
    user, staff = _staff(space)
    services.issue(sm, staff)
    rows = client(user).get("/api/v1/member/cards").json()
    assert [row["kind"] for row in rows] == ["staff_card"] and rows[0]["title"] == "Staff card"
    assert rows[0]["email_available"] is False


def test_staff_design_default_template_has_staff_band_and_no_desk_qr():
    space = _space("sc-design")
    body = client(manager(space)).get(f"/api/v1/admin/makerspaces/{space.pk}/staff-card-design").json()
    assert body["domain"] == "staff_cards"
    layers = body["document"]["front"]["layers"]
    assert "Staff band" in [layer["name"] for layer in layers]
    assert not any(layer["kind"] == "desk_qr" for layer in layers)
