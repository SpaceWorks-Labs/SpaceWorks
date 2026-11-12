"""D314c cut-out jobs: switch, consent, RBAC, retry, typed failures, derived storage, purge, the limit and the resolver."""
import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.card_designs import cutouts
from apps.card_designs.image_adapter.errors import AdapterError
from apps.card_designs.models import CardPhotoCutout, PlatformImageAdapter
from tests.l3_local.helpers import card_space, client, issue, manager, member

from .conftest import clear_photo, cutout_png, set_photo

pytestmark = pytest.mark.django_db
SWITCH = "cards.photo_cutout"
PHOTO_KEY = "member-cards/1/original"


@pytest.fixture(autouse=True)
def no_broker(monkeypatch):
    monkeypatch.setattr("apps.card_designs.tasks.dispatch_cutout", lambda cutout_id: None)


def _platform_provider():
    row = PlatformImageAdapter()
    row.provider_url = "https://eraser.example.org"
    row.set_secret("s" * 24)
    row.save()


def _setup(slug, *, switch=True, provider=True, extra=()):
    space = card_space(slug, features=((SWITCH, *extra) if switch else ()))
    if provider:
        _platform_provider()
    sm = manager(space)
    user, membership = member(space)
    card = issue(space, membership, by=sm)
    set_photo(card, PHOTO_KEY)
    return space, sm, user, card


def _staff_url(card):
    return reverse("admin-member-card-photo-cutout", args=[card.pk])


def _own_url(card):
    return reverse("member-card-photo-cutout", kwargs={"kind": "member_card", "card_id": card.pk})


def _answer(monkeypatch, result=None, error=None):
    def fake(config, data, content_type):
        if error:
            raise error
        return result or (cutout_png(), 40, 60)
    monkeypatch.setattr(cutouts.client, "remove_background", fake)


def test_switch_off_is_404_everywhere():
    _space, sm, user, card = _setup("co-off", switch=False)
    assert client(sm).get(_staff_url(card)).status_code == 404
    assert client(sm).post(_staff_url(card), {}, format="json").status_code == 404
    assert client(user).post(_own_url(card), {"consent": True}, format="json").status_code == 404
    assert not CardPhotoCutout.objects.exists()


def test_staff_queue_run_and_choose(monkeypatch, store, original_photo):
    _space, sm, _user, card = _setup("co-staff")
    _answer(monkeypatch)
    response = client(sm).post(_staff_url(card), {}, format="json")
    assert response.status_code == 202 and response.json()["state"] == "queued"
    row = CardPhotoCutout.objects.get()
    assert row.requested_by == sm and not row.by_holder and row.source_key == PHOTO_KEY
    assert cutouts.run(row.pk) is None
    row.refresh_from_db()
    assert row.state == "done" and row.cutout_key in store and row.provider_scope == "platform"
    assert row.cutout_key.startswith("card-cutouts/") and row.cutout_key != PHOTO_KEY
    card.refresh_from_db()
    assert card.photo_object_key == PHOTO_KEY  # the original is never touched
    shown = client(sm).get(_staff_url(card)).json()
    assert shown["state"] == "done" and shown["use"] == "original" and shown["image_url"]
    assert client(sm).patch(_staff_url(card), {"use": "cutout"}, format="json").json()["use"] == "cutout"
    assert cutouts.photo_variant_bytes("member_card", card, "auto") == store[row.cutout_key]
    assert cutouts.photo_variant_bytes("member_card", card, "original") is None
    actions = set(AuditLog.objects.values_list("action", flat=True))
    assert {"card.photo_cutout_requested", "card.photo_cutout_done", "card.photo_cutout_choice"} <= actions


def test_the_resolver_returns_nothing_until_chosen_and_never_for_a_stale_cutout(monkeypatch, store, original_photo):
    _space, sm, _user, card = _setup("co-resolve")
    _answer(monkeypatch)
    row = cutouts.request(sm, "member_card", card)
    cutouts.run(row.pk)
    assert cutouts.photo_variant_bytes("member_card", card, "auto") is None  # not chosen yet
    assert cutouts.photo_variant_bytes("member_card", card, "cutout") is not None
    card.photo_object_key = "member-cards/1/replaced"
    card.save(update_fields=["photo_object_key"])
    assert cutouts.photo_variant_bytes("member_card", card, "cutout") is None
    assert cutouts.status("member_card", card)["state"] == "stale"


def test_a_member_must_consent_and_can_only_act_on_their_own_card(monkeypatch, store, original_photo):
    space, _sm, user, card = _setup("co-member")
    _answer(monkeypatch)
    assert client(user).post(_own_url(card), {}, format="json").status_code == 400
    assert not CardPhotoCutout.objects.exists()
    assert client(user).post(_own_url(card), {"consent": True}, format="json").status_code == 202
    row = CardPhotoCutout.objects.get()
    assert row.by_holder and row.consent_at is not None
    other_user, other_membership = member(space, "other")
    other_card = issue(space, other_membership, by=manager(space, "m2"))
    assert client(other_user).get(_own_url(card)).status_code == 404
    assert client(other_user).post(_own_url(card), {"consent": True}, format="json").status_code == 404
    assert other_card.pk != card.pk


def test_staff_without_card_authority_and_other_tenants_get_404(monkeypatch, store, original_photo):
    _space, _sm, user, card = _setup("co-rbac")
    _answer(monkeypatch)
    assert client(user).post(_staff_url(card), {}, format="json").status_code in (403, 404)
    other = card_space("co-rbac-other", features=(SWITCH,))
    assert client(manager(other, "x")).post(_staff_url(card), {}, format="json").status_code in (403, 404)
    assert not CardPhotoCutout.objects.exists()


def test_no_provider_and_no_photo_are_refused_with_typed_errors():
    _space, sm, _user, card = _setup("co-none", provider=False)
    response = client(sm).post(_staff_url(card), {}, format="json")
    assert response.status_code == 400 and "eraser" in str(response.json()).lower()
    _platform_provider()
    clear_photo(card)
    assert client(sm).post(_staff_url(card), {}, format="json").status_code == 400


def test_retryable_failures_back_off_then_fail_typed(monkeypatch, store, original_photo):
    _space, sm, _user, card = _setup("co-retry")
    _answer(monkeypatch, error=AdapterError("unavailable"))
    row = cutouts.request(sm, "member_card", card)
    assert cutouts.run(row.pk) == cutouts.BACKOFF_SECONDS[0]
    row.refresh_from_db()
    assert row.state == "queued" and row.error_code == "unavailable" and row.attempts == 1
    for _ in range(cutouts.MAX_ATTEMPTS - 1):
        cutouts.run(row.pk)
    row.refresh_from_db()
    assert row.state == "failed" and row.error_code == "unavailable"
    assert AuditLog.objects.filter(action="card.photo_cutout_failed", meta__error_code="unavailable").exists()


def test_a_final_provider_error_fails_at_once_and_a_rerun_replaces_the_row(monkeypatch, store, original_photo):
    _space, sm, _user, card = _setup("co-final")
    _answer(monkeypatch, error=AdapterError("no_subject_found"))
    row = cutouts.request(sm, "member_card", card)
    assert cutouts.run(row.pk) is None
    row.refresh_from_db()
    assert row.state == "failed" and row.error_code == "no_subject_found" and row.attempts == 1
    _answer(monkeypatch)
    again = cutouts.request(sm, "member_card", card)
    assert again.pk != row.pk and CardPhotoCutout.objects.count() == 1


def test_discard_and_original_removal_purge_the_derived_object(monkeypatch, store, original_photo,
                                                               django_capture_on_commit_callbacks):
    _space, sm, _user, card = _setup("co-purge")
    _answer(monkeypatch)
    row = cutouts.request(sm, "member_card", card)
    cutouts.run(row.pk)
    key = CardPhotoCutout.objects.get().cutout_key
    with django_capture_on_commit_callbacks(execute=True):
        assert client(sm).delete(_staff_url(card)).status_code == 200
    assert not CardPhotoCutout.objects.exists() and key not in store
    row = cutouts.request(sm, "member_card", card)
    cutouts.run(row.pk)
    key = CardPhotoCutout.objects.get().cutout_key
    from apps.makerspaces import member_card_storage
    monkeypatch.setattr(member_card_storage, "_release", lambda *a, **k: None)
    with django_capture_on_commit_callbacks(execute=True):
        member_card_storage.delete_photo(card)
    assert not CardPhotoCutout.objects.exists() and key not in store


def test_deleting_the_card_cascades_and_releases_the_object(monkeypatch, store, original_photo,
                                                            django_capture_on_commit_callbacks):
    _space, sm, _user, card = _setup("co-cascade")
    _answer(monkeypatch)
    row = cutouts.request(sm, "member_card", card)
    cutouts.run(row.pk)
    key = CardPhotoCutout.objects.get().cutout_key
    with django_capture_on_commit_callbacks(execute=True):
        card.delete()
    assert not CardPhotoCutout.objects.exists() and key not in store


def test_the_monthly_limit_refuses_only_a_new_job(monkeypatch, store, original_photo):
    space, sm, _user, card = _setup("co-limit")
    _answer(monkeypatch)
    space.resource_limit_overrides = {"photo_cutout_jobs_monthly": 1}
    space.save(update_fields=["resource_limit_overrides"])
    row = cutouts.request(sm, "member_card", card)
    cutouts.run(row.pk)
    response = client(sm).post(_staff_url(card), {}, format="json")
    assert response.status_code == 409 and response.json()["code"] == "photo_cutout_jobs_monthly_quota_reached"
    # What exists keeps working: reading, choosing and discarding are never limited.
    assert client(sm).get(_staff_url(card)).json()["state"] == "done"
    assert client(sm).patch(_staff_url(card), {"use": "cutout"}, format="json").status_code == 200


def test_a_queued_job_for_the_same_photo_is_not_counted_twice(monkeypatch, store, original_photo):
    _space, sm, _user, card = _setup("co-dupe")
    first = cutouts.request(sm, "member_card", card)
    assert cutouts.request(sm, "member_card", card).pk == first.pk
    assert CardPhotoCutout.objects.count() == 1


def test_a_staff_card_uses_its_member_cards_photo(monkeypatch, store, original_photo):
    space, sm, _user, card = _setup("co-staffcard", extra=("membership.staff_cards",))
    from apps.card_designs.models_staff_cards import StaffCard
    staff = StaffCard.objects.create(makerspace=space, membership=card.membership, card_number=1)
    assert cutouts.owner("staff_card", staff) == ("member_card", card)
    _answer(monkeypatch)
    row = cutouts.request(sm, "staff_card", staff)
    assert row.member_card_id == card.pk and row.staff_card_id is None


def test_settings_secrets_never_leave_the_server_in_the_status(monkeypatch, store, original_photo):
    _space, sm, _user, card = _setup("co-status")
    body = str(client(sm).get(_staff_url(card)).json())
    assert "s" * 24 not in body and "eraser.example.org" not in body
