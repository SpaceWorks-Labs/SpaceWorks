"""Decision 345(b): the eraser processing notice, the member's opt-out, the notice version on each request, staff and
bulk requests skipping opted-out members, and the privacy page section."""
import pytest

from apps.audit.models import AuditLog
from apps.card_designs import cutouts, eraser_notice, extras
from apps.card_designs.models import CardHolderExtras, CardPhotoCutout, CardPhotoEraserOptOut
from apps.card_designs.photo_batch_apply import _eraser_code
from tests.l3_local.helpers import client

from .test_cutouts import _answer, _own_url, _setup, _staff_url

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def no_broker(monkeypatch):
    monkeypatch.setattr("apps.card_designs.tasks.dispatch_cutout", lambda cutout_id: None)


def test_members_see_the_notice_and_each_request_stores_its_version(monkeypatch, store, original_photo):
    _space, sm, user, card = _setup("en-notice")
    _answer(monkeypatch)
    body = client(user).get(_own_url(card)).json()
    assert body["notice_version"] == eraser_notice.NOTICE_VERSION and "background-removal" in body["notice"]
    assert body["opted_out"] is False
    assert client(user).post(_own_url(card), {"consent": True}, format="json").status_code == 202
    assert CardPhotoCutout.objects.get().notice_version == eraser_notice.NOTICE_VERSION


def test_opting_out_deletes_the_cutout_and_staff_and_bulk_requests_skip_the_member(monkeypatch, store, original_photo):
    _space, sm, user, card = _setup("en-optout")
    _answer(monkeypatch)
    cutouts.run(cutouts.request(sm, "member_card", card).pk)
    assert CardPhotoCutout.objects.exists()
    response = client(user).put(_own_url(card), {"opted_out": True}, format="json")
    assert response.status_code == 200 and response.json()["opted_out"] is True
    assert not CardPhotoCutout.objects.exists()
    assert cutouts.photo_variant_bytes("member_card", card, "cutout") is None  # the original prints
    refused = client(sm).post(_staff_url(card), {}, format="json")
    assert refused.status_code == 400 and not CardPhotoCutout.objects.exists()
    assert client(sm).get(_staff_url(card)).json()["opted_out"] is True
    with pytest.raises(eraser_notice.OptedOut) as error:
        cutouts.request(sm, "member_card", card)
    assert _eraser_code(error.value) == "eraser_opted_out"
    assert AuditLog.objects.filter(action="card.photo_eraser_opted_out").exists()


def test_opting_back_in_allows_requests_again(monkeypatch, store, original_photo):
    _space, sm, user, card = _setup("en-optin")
    _answer(monkeypatch)
    client(user).put(_own_url(card), {"opted_out": True}, format="json")
    assert client(user).put(_own_url(card), {"opted_out": False}, format="json").json()["opted_out"] is False
    assert client(sm).post(_staff_url(card), {}, format="json").status_code == 202
    assert AuditLog.objects.filter(action="card.photo_eraser_opted_in").exists()


def test_the_opt_out_is_its_own_row_and_survives_clearing_the_printed_extras(monkeypatch, store, original_photo):
    _space, sm, user, card = _setup("en-extras")
    extras.write(user, "member_card", card, opted_in=True, blood_group="O+")
    eraser_notice.set_opt_out(user, "member_card", card, True)
    extras.write(user, "member_card", card, opted_in=False)
    assert not CardHolderExtras.objects.filter(member_card=card).exists()
    row = CardPhotoEraserOptOut.objects.get(member_card=card)
    assert row.notice_version == eraser_notice.NOTICE_VERSION and eraser_notice.opted_out("member_card", card)
    eraser_notice.set_opt_out(user, "member_card", card, False)
    assert not CardPhotoEraserOptOut.objects.exists()


def test_the_opt_out_travels_with_the_space_and_is_in_the_members_own_export(monkeypatch, store, original_photo):
    from apps.data_export.datasets import DATASET_SPECS
    from apps.data_export.subject_selectors import subject_query
    from apps.tenant_migration.catalog_l3 import PROJECTED_LABELS
    space, _sm, user, card = _setup("en-export")
    eraser_notice.set_opt_out(user, "member_card", card, True)
    label = "card_designs.CardPhotoEraserOptOut"
    assert label in PROJECTED_LABELS and label in DATASET_SPECS
    assert list(subject_query(CardPhotoEraserOptOut, user, space.pk)) == [CardPhotoEraserOptOut.objects.get()]
    from tests.l3_local.helpers import member
    other, _membership = member(space, "someone-else")
    assert not subject_query(CardPhotoEraserOptOut, other, space.pk).exists()


def test_another_member_cannot_opt_someone_out(monkeypatch, store, original_photo):
    from tests.l3_local.helpers import member
    space, _sm, _user, card = _setup("en-other")
    other, _membership = member(space, "other")
    assert client(other).put(_own_url(card), {"opted_out": True}, format="json").status_code == 404
    assert not CardPhotoEraserOptOut.objects.exists()


def test_the_privacy_page_carries_the_notice_only_while_the_eraser_can_run():
    from rest_framework.test import APIClient
    space, _sm, _user, _card = _setup("en-privacy")
    url = "/api/v1/discover/legal/privacy/"
    body = APIClient().get(url, {"space": space.slug}).json()
    assert "background removal" in body["markdown"].lower()
    assert "background removal" not in APIClient().get(url).json()["markdown"].lower()  # no space: no notice
    space.enabled_features = [key for key in space.enabled_features if key != "cards.photo_cutout"]
    space.save(update_fields=["enabled_features"])
    assert "background removal" not in APIClient().get(url, {"space": space.slug}).json()["markdown"].lower()
