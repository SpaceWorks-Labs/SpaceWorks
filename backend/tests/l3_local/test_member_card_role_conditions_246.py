"""Decision 246: member-card management across every built-in role (issue, reissue, revoke, list), replay and isolation.

Authority is `manage_member_cards`, read from `ROLE_CATALOG`. A refused call must leave no card, no QR
code and no audit row; a card is issued once per live membership; revoke needs a note.
"""
import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.makerspaces import member_card_services as services
from apps.makerspaces.models import MemberCard
from apps.makerspaces.role_catalog import ROLE_BY_SLUG, ROLE_CATALOG
from tests.fixed_roles.helpers import staff_account
from tests.l3_local.helpers import card_space, client, manager, member

pytestmark = pytest.mark.django_db
SLUGS = [role.slug for role in ROLE_CATALOG]


def _allowed(slug):
    return "manage_member_cards" in ROLE_BY_SLUG[slug].granted_actions


def _base(space):
    return f"/api/v1/admin/makerspaces/{space.pk}/member-cards"


@pytest.mark.parametrize("slug", SLUGS)
def test_list_issue_reissue_revoke_follow_manage_member_cards(slug):
    space = card_space(f"mcr-{slug}".replace("_", "-"))
    boss = manager(space)
    _user, membership = member(space, "holder")
    _user2, other_membership = member(space, "second")
    existing = services.issue_card(boss, other_membership)
    actor = client(staff_account(space, f"mcr-actor-{slug}", slug))
    listed = actor.get(_base(space))
    issued = actor.post(f"{_base(space)}/{membership.pk}/issue", {}, format="json")
    reissued = actor.post(f"/api/v1/admin/member-cards/{existing.pk}/reissue", {"reason": "lost"}, format="json")
    revoked = actor.post(f"/api/v1/admin/member-cards/{existing.pk}/revoke", {"note": "Lost and replaced"},
                         format="json")
    if _allowed(slug):
        assert listed.status_code == 200
        assert issued.status_code in (200, 201), issued.content
        assert reissued.status_code == 200, reissued.content
        assert revoked.status_code == 200, revoked.content
    else:
        for refused in (listed, issued, reissued, revoked):
            assert refused.status_code in (403, 404)
        assert not MemberCard.objects.filter(membership=membership).exists()
        existing.refresh_from_db()
        assert existing.revoked_at is None
        assert not AuditLog.objects.filter(makerspace=space, actor__username=f"mcr-actor-{slug}").exists()


def test_a_second_issue_for_the_same_membership_is_refused_and_one_card_stands():
    space = card_space("mcr-twice")
    boss = client(manager(space))
    _user, membership = member(space)
    url = f"{_base(space)}/{membership.pk}/issue"
    assert boss.post(url, {}, format="json").status_code in (200, 201)
    assert boss.post(url, {}, format="json").status_code in (400, 403, 409)
    assert MemberCard.objects.filter(membership=membership, revoked_at__isnull=True).count() == 1
    assert AuditLog.objects.filter(makerspace=space, action="member_card.issued").count() == 1


@pytest.mark.parametrize("body", [{}, {"note": ""}, {"note": "   "}])
def test_revoke_without_a_note_is_a_400_and_the_card_stays_live(body):
    space = card_space("mcr-note")
    boss = manager(space)
    _user, membership = member(space)
    card = services.issue_card(boss, membership)
    assert client(boss).post(f"/api/v1/admin/member-cards/{card.pk}/revoke", body, format="json").status_code == 400
    card.refresh_from_db()
    assert card.revoked_at is None


def test_a_revoked_card_cannot_be_revoked_again_and_a_fresh_card_can_follow():
    space = card_space("mcr-again")
    boss = manager(space)
    _user, membership = member(space)
    card = services.issue_card(boss, membership)
    url = f"/api/v1/admin/member-cards/{card.pk}/revoke"
    assert client(boss).post(url, {"note": "Lost"}, format="json").status_code == 200
    assert client(boss).post(url, {"note": "Lost"}, format="json").status_code in (400, 403, 404, 409)
    assert services.issue_card(boss, membership).pk != card.pk


def test_another_spaces_manager_and_anonymous_cannot_touch_this_spaces_cards():
    mine, theirs = card_space("mcr-iso-a"), card_space("mcr-iso-b")
    boss = manager(mine)
    _user, membership = member(mine)
    card = services.issue_card(boss, membership)
    outsider = client(manager(theirs, "outsider"))
    assert outsider.get(_base(mine)).status_code in (403, 404)
    assert outsider.post(f"/api/v1/admin/member-cards/{card.pk}/revoke", {"note": "x"}, format="json").status_code in (403, 404)
    assert outsider.post(f"/api/v1/admin/member-cards/{card.pk}/reissue", {"reason": "x"}, format="json").status_code in (403, 404)
    anon = APIClient()
    assert anon.get(_base(mine)).status_code in (401, 403)
    card.refresh_from_db()
    assert card.revoked_at is None


def test_a_non_active_membership_cannot_be_issued_a_card_and_the_module_off_hides_the_routes():
    space = card_space("mcr-off")
    boss = client(manager(space))
    _user, membership = member(space)
    type(membership).objects.filter(pk=membership.pk).update(status="suspended")
    refused = boss.post(f"{_base(space)}/{membership.pk}/issue", {}, format="json")
    assert refused.status_code in (400, 403, 409)
    assert not MemberCard.objects.exists()
    space.enabled_modules = sorted(set(space.enabled_modules) - {"membership"})
    space.save(update_fields=["enabled_modules"])
    assert boss.get(_base(space)).status_code in (403, 404)
