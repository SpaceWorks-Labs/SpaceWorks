"""Photo-path fixes found by the CARD-STUDIO-2 audit (decision 344(a)): the cut-out quota cannot be dodged by
re-running or discarding, "Preview as" never reports a cut-out while the switch is off, a replaced photo's stale
cut-out is purged with its storage, and the bulk eraser reasons stay readable."""
import pytest

from apps.card_designs import cards, cutouts
from apps.card_designs.cutout_staleness import purge_if_stale
from apps.card_designs.models import CardPhotoCutout
from apps.card_designs.photo_batch_apply import _eraser_code
from apps.managed_hosting.extra_quota_counters import photo_cutout_jobs_monthly
from .conftest import set_photo
from .test_cutouts import _answer, _setup

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def no_broker(monkeypatch):
    monkeypatch.setattr("apps.card_designs.tasks.dispatch_cutout", lambda cutout_id: None)


def test_a_rerun_and_a_discard_still_count_against_the_monthly_quota(monkeypatch, store, original_photo):
    space, sm, _user, card = _setup("cs2-quota")
    _answer(monkeypatch)
    row = cutouts.request(sm, "member_card", card)
    cutouts.run(row.pk)
    cutouts.discard(sm, "member_card", card)
    assert not CardPhotoCutout.objects.exists()
    assert photo_cutout_jobs_monthly(space) == 1  # the deleted row still counts: the audit trail is append-only
    cutouts.run(cutouts.request(sm, "member_card", card).pk)
    assert photo_cutout_jobs_monthly(space) == 2


def test_preview_as_reports_no_cutout_while_the_switch_is_off(monkeypatch, store, original_photo):
    space, sm, _user, card = _setup("cs2-flags")
    _answer(monkeypatch)
    row = cutouts.request(sm, "member_card", card)
    cutouts.run(row.pk)
    assert cards.cutout_flags("member_card", card)["available"] is True
    space.enabled_features = [key for key in space.enabled_features if key != "cards.photo_cutout"]
    space.save(update_fields=["enabled_features"])
    card.refresh_from_db()
    assert cards.cutout_flags("member_card", card) == {"available": False, "use_cutout": False}


def test_a_replaced_photo_drops_its_stale_cutout(monkeypatch, store, original_photo):
    _space, sm, _user, card = _setup("cs2-stale")
    _answer(monkeypatch)
    cutouts.run(cutouts.request(sm, "member_card", card).pk)
    assert CardPhotoCutout.objects.exists()
    purge_if_stale("member_card", card)  # same photo: kept
    assert CardPhotoCutout.objects.exists()
    set_photo(card, "member-cards/1/replaced")
    purge_if_stale("member_card", card)
    assert not CardPhotoCutout.objects.exists()


def test_bulk_eraser_refusals_keep_a_short_readable_reason():
    from rest_framework.exceptions import NotFound, ValidationError
    from apps.managed_hosting.extra_quotas import ExtraQuotaReached
    assert _eraser_code(ExtraQuotaReached("photo_cutout_jobs_monthly", 1)) == "eraser_limit_reached"
    assert _eraser_code(NotFound()) == "eraser_off"
    refused = ValidationError({"detail": "x"})
    assert _eraser_code(refused).startswith("eraser_") and len(_eraser_code(refused)) <= 32
