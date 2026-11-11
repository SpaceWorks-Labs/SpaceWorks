"""O-B4: the title-cards list and the primary-title reissue (same number, new QR, audited)."""
import pytest

from apps.audit.models import AuditLog
from apps.card_designs import resolution, title_cards, tokens
from apps.makerspaces import member_card_services as services
from apps.makerspaces import membership_titles
from apps.makerspaces.models import MemberCardSettings, MembershipTitle
from tests.l3_local.helpers import card_space, client, manager, member

pytestmark = pytest.mark.django_db


def _title(space, name):
    return MembershipTitle.objects.create(makerspace=space, name=name)


def test_title_cards_report_status_and_live_card_counts():
    space = card_space("tc-list")
    sm = manager(space)
    chair = _title(space, "Chair")
    _title(space, "Treasurer")
    _user, membership = member(space)
    membership_titles.assign(sm, membership, chair, primary=True)
    services.issue_card(sm, membership)
    resolution.get_or_create(space, "member_cards", actor=sm, title=chair)
    rows = {row["title"]: row for row in title_cards.title_rows(space)}
    assert rows["Chair"]["status"] == "draft" and rows["Chair"]["live_cards"] == 1
    assert rows["Treasurer"]["status"] == "inherits" and rows["Treasurer"]["live_cards"] == 0
    response = client(sm).get(f"/api/v1/admin/makerspaces/{space.pk}/card-designs/titles")
    assert response.status_code == 200 and {r["title"] for r in response.json()} == {"Chair", "Treasurer"}


def test_primary_title_change_reissues_the_live_card_when_the_switch_is_on():
    space = card_space("tc-reissue", features=("membership.title_card_reissue",))
    MemberCardSettings.objects.update_or_create(makerspace=space, defaults={"public_verify": True})
    sm = manager(space)
    a, b = _title(space, "A"), _title(space, "B")
    _user, membership = member(space)
    card = services.issue_card(sm, membership)
    old_qr, old_token = services.active_qr(card).payload, tokens.live("member_card", card).token
    membership_titles.assign(sm, membership, a, primary=True)
    card.refresh_from_db()
    assert services.active_qr(card).payload != old_qr and tokens.live("member_card", card).token != old_token
    entry = AuditLog.objects.filter(action="member_card.reissued", makerspace=space).latest("pk")
    assert entry.meta["reason"] == "title_changed"
    again = services.active_qr(card).payload
    membership_titles.assign(sm, membership, a, primary=True)  # no change: no reissue
    assert services.active_qr(card).payload == again
    membership_titles.assign(sm, membership, b, primary=True)
    assert services.active_qr(card).payload != again


def test_no_reissue_when_the_switch_is_off():
    space = card_space("tc-off")
    sm = manager(space)
    _user, membership = member(space)
    card = services.issue_card(sm, membership)
    qr = services.active_qr(card).payload
    membership_titles.assign(sm, membership, _title(space, "A"), primary=True)
    assert services.active_qr(card).payload == qr
