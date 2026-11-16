"""O-B4: the staff verify panel (uniform 404), desk print-face, bulk jobs from the register filter."""
import io

import pytest
from PIL import Image

from apps.audit.models import AuditLog
from apps.card_designs import job_targets_filter, tokens
from apps.makerspaces import member_card_services as services
from apps.makerspaces.models import MemberCard, MemberCardSettings
from tests.l3_local.helpers import card_space, client, manager, member

pytestmark = pytest.mark.django_db


def _card_with_token(space, sm, name="member"):
    MemberCardSettings.objects.update_or_create(makerspace=space, defaults={"public_verify": True})
    _user, membership = member(space, name)
    card = services.issue_card(sm, membership)
    return card, tokens.live("member_card", card).token


def test_staff_panel_lists_actions_and_everything_else_is_a_uniform_404():
    space, other = card_space("vs-one"), card_space("vs-two")
    sm = manager(space)
    _card, token = _card_with_token(space, sm)
    ok = client(sm).get(f"/api/v1/admin/card-verifications/{token}/staff")
    assert ok.status_code == 200
    assert "revoke_card" in {a["key"] for a in ok.json()["actions"]}
    assert token not in str(AuditLog.objects.filter(action="card_verification.staff_viewed").latest("pk").meta)
    outsider = client(manager(other, "out"))
    for bad in (token, "x" * 43, "short"):
        assert outsider.get(f"/api/v1/admin/card-verifications/{bad}/staff").status_code == 404
    user, _membership = member(space, "plain")
    assert client(user).get(f"/api/v1/admin/card-verifications/{token}/staff").status_code == 404


def test_print_face_is_a_300_dpi_png_audited_once_per_card_and_gated_by_its_switch():
    space = card_space("pf-on", features=("membership.card_desk_print",))
    sm = manager(space)
    card, _ = _card_with_token(space, sm)
    response = client(sm).get(f"/api/v1/admin/member-cards/{card.pk}/print-face?side=front&stock=4x6")
    assert response.status_code == 200 and response["Content-Type"] == "image/png"
    image = Image.open(io.BytesIO(response.content))
    assert image.size == (round(101.6 * 300 / 25.4), round(152.4 * 300 / 25.4))
    client(sm).get(f"/api/v1/admin/member-cards/{card.pk}/print-face?side=back")
    card.refresh_from_db()
    assert card.print_count == 1
    assert client(sm).get(f"/api/v1/admin/member-cards/{card.pk}/print-face?stock=nope").status_code == 400
    off = card_space("pf-off")
    off_card, _ = _card_with_token(off, manager(off))
    assert client(manager(off, "m2")).get(f"/api/v1/admin/member-cards/{off_card.pk}/print-face").status_code == 404


def test_bulk_job_can_select_cards_from_the_register_filter():
    space = card_space("bj-filter")
    sm = manager(space)
    people = [member(space, name)[1] for name in ("ana", "ben")]
    for membership in people:
        services.issue_card(sm, membership)
    ids = job_targets_filter.resolve(sm, space, {"q": "ana"})
    assert list(MemberCard.objects.filter(pk__in=ids).values_list("membership_id", flat=True)) == [people[0].pk]
    assert len(job_targets_filter.resolve(sm, space, {})) == 2
    with pytest.raises(Exception):
        job_targets_filter.resolve(sm, space, {"bogus": "1"})
