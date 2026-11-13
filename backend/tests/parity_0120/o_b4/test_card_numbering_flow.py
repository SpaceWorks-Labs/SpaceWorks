"""O-B4: numbers come from the published scheme, freeze on the card, skip taken ones and never block activation."""
import pytest
from rest_framework.test import APIRequestFactory

from apps.audit.models import AuditLog
from apps.card_designs import designs, numbering, resolution
from apps.card_designs.models_numbering import CardNumberScheme
from apps.card_designs.views_title_cards import _write
from apps.makerspaces import member_card_services as services
from apps.makerspaces.models import MemberCard, MemberCardSettings
from tests.l3_local.helpers import card_space, manager, member

pytestmark = pytest.mark.django_db
SWITCH = "membership.card_numbering"


def _space(slug):
    return card_space(slug, features=(SWITCH,))


def _publish_default(space, sm, prefix="TNK", pattern="{PREFIX}-{YYYY}-{SEQ:4}"):
    request = APIRequestFactory().put("/", {"prefix": prefix, "pattern": pattern}, format="json")
    request.user, request.data = sm, {"prefix": prefix, "pattern": pattern}
    _write(request, space, None)
    row, _ = resolution.get_or_create(space, "member_cards", actor=sm)
    designs.publish(sm, row)


def test_draft_numbering_is_not_live_until_the_design_publishes():
    space = _space("nb-draft")
    sm = manager(space)
    _user, membership = member(space)
    CardNumberScheme.objects.create(makerspace=space, draft_prefix="TNK", draft_pattern="{PREFIX}{SEQ:3}")
    card = services.issue_card(sm, membership)
    assert card.number_text == ""  # legacy display until published


def test_published_scheme_numbers_new_cards_in_order_and_freezes_the_number():
    space = _space("nb-live")
    sm = manager(space)
    _publish_default(space, sm)
    first = services.issue_card(sm, member(space, "a")[1])
    second = services.issue_card(sm, member(space, "b")[1])
    assert first.number_text.startswith("TNK-") and first.number_text.endswith("-0001")
    assert second.number_text.endswith("-0002")
    kept = services.reissue_card(sm, first, reason="lost")
    assert kept.number_text == first.number_text
    assert AuditLog.objects.filter(action="card_number_scheme.published", makerspace=space).exists()


def test_taken_numbers_are_skipped_and_exhaustion_is_a_typed_409():
    space = _space("nb-skip")
    sm = manager(space)
    _publish_default(space, sm, prefix="", pattern="N{SEQ}")
    _user, other = member(space, "x")
    MemberCard.objects.create(makerspace=space, membership=other, card_number=900, number_text="N1")
    card = services.issue_card(sm, member(space, "y")[1])
    assert card.number_text == "N2"
    scheme = CardNumberScheme.objects.get(makerspace=space)
    scheme.pattern = "ZZ"  # no SEQ: every attempt yields the same text
    scheme.save()
    MemberCard.objects.create(makerspace=space, membership=None, card_number=9001, number_text="ZZ")
    with pytest.raises(numbering.CardNumberExhausted):
        numbering.next_number(member(space, "z")[1], scheme)


def test_auto_issue_never_undoes_activation_when_numbering_is_exhausted():
    space = _space("nb-auto")
    MemberCardSettings.objects.update_or_create(makerspace=space, defaults={"auto_issue": True})
    CardNumberScheme.objects.create(makerspace=space, pattern="ZZ", prefix="")
    MemberCard.objects.create(makerspace=space, membership=None, card_number=1, number_text="ZZ")
    _user, membership = member(space)
    assert services.auto_issue(membership.pk) is None
    assert AuditLog.objects.filter(action="member_card.auto_issue_skipped", makerspace=space).exists()


def test_new_cards_start_with_the_space_name_default_and_existing_spaces_stay_off():
    space = card_space("nb-name")
    sm = manager(space)
    MemberCardSettings.objects.update_or_create(makerspace=space, defaults={"verify_show_name": True})
    assert services.issue_card(sm, member(space, "a")[1]).verify_show_name is True
    MemberCardSettings.objects.filter(makerspace=space).update(verify_show_name=False)
    assert services.issue_card(sm, member(space, "b")[1]).verify_show_name is False


def test_numbering_is_gated_by_its_switch():
    space = card_space("nb-off")  # switch off
    sm = manager(space)
    CardNumberScheme.objects.create(makerspace=space, pattern="{SEQ:3}", prefix="")
    assert services.issue_card(sm, member(space)[1]).number_text == ""
