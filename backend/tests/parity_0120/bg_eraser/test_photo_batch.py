"""D314c addendum: bulk card-photo upload matched by file name, reviewed, then applied through the normal photo path."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.card_designs import photo_batch, photo_batch_apply
from apps.card_designs.models import CardPhotoBatch, CardPhotoBatchItem, PlatformImageAdapter
from tests.l3_local.helpers import card_space, client, issue, manager, member

from .conftest import jpeg, set_photo

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def no_broker(monkeypatch):
    monkeypatch.setattr(photo_batch_apply.cutouts, "request", lambda *a, **k: None, raising=False)


def _space(slug, *, switch=False):
    space = card_space(slug, features=("cards.photo_cutout",) if switch else ())
    sm = manager(space)
    cards = {}
    for name, number, printed in (("a", "TNK-0001", "Priya Raman"), ("b", "TNK-0002", "Sam Lee"),
                                  ("c", "TNK-0003", "Sam Lee")):
        _user, membership = member(space, name)
        card = issue(space, membership, by=sm)
        card.number_text, card.printed_name = number, printed
        card.save(update_fields=["number_text", "printed_name"])
        cards[name] = card
    return space, sm, cards


def _url(space, *rest):
    names = {(): "admin-card-photo-batches"}
    return reverse(names[()], args=[space.pk]) if not rest else reverse(rest[0], args=[space.pk, *rest[1:]])


def _create(api, space, **extra):
    body = {"kind": "member_card", "holders_consented": True, **extra}
    return api.post(_url(space), body, format="json")


def _add(api, space, batch_id, *files):
    uploads = [SimpleUploadedFile(name, data) for name, data in files]
    return api.post(_url(space, "admin-card-photo-batch-files", batch_id), {"files": uploads}, format="multipart")


@pytest.fixture
def applied(monkeypatch):
    calls = []
    monkeypatch.setattr("apps.makerspaces.member_card_storage.replace_photo_bytes",
                        lambda actor, card, data: calls.append((actor, card.pk, len(data))) or card)
    return calls


def test_the_holders_must_be_confirmed_as_agreeing(store):
    space, sm, _cards = _space("pb-consent")
    assert _create(client(sm), space, holders_consented=False).status_code == 400
    assert not CardPhotoBatch.objects.exists()


def test_review_table_shows_matched_ambiguous_unmatched_and_has_photo(store):
    space, sm, cards = _space("pb-review")
    set_photo(cards["a"], "member-cards/1/existing")
    api = client(sm)
    batch_id = _create(api, space).json()["id"]
    body = _add(api, space, batch_id, ("TNK-0001.jpg", jpeg()), ("TNK-0002.jpg", jpeg()), ("Sam Lee.png", jpeg()),
                ("IMG_9.jpg", jpeg()), ("broken.jpg", b"not an image")).json()
    by_name = {item["filename"]: item for item in body["items"]}
    assert by_name["TNK-0001"]["status"] == "has_photo" and by_name["TNK-0001"]["decision"] == "keep"
    assert by_name["TNK-0002"]["status"] == "matched" and by_name["TNK-0002"]["decision"] == "apply"
    assert by_name["TNK-0002"]["match_kind"] == "number" and by_name["TNK-0002"]["thumbnail_url"]
    assert by_name["Sam Lee"]["status"] == "ambiguous" and len(by_name["Sam Lee"]["candidates"]) == 2
    assert by_name["IMG_9"]["status"] == "unmatched" and by_name["IMG_9"]["decision"] == "skip"
    assert by_name["broken"]["status"] == "unmatched" and by_name["broken"]["error_code"] == "unreadable_image"
    assert body["file_count"] == 5 and body["eraser_available"] is False


def test_a_second_file_for_one_holder_is_skipped_as_a_duplicate(store):
    space, sm, _cards = _space("pb-dupe")
    api = client(sm)
    batch_id = _create(api, space).json()["id"]
    body = _add(api, space, batch_id, ("TNK-0001.jpg", jpeg()), ("tnk_0001.png", jpeg())).json()
    assert [item["decision"] for item in body["items"]] == ["apply", "skip"]
    assert body["items"][1]["error_code"] == "duplicate_file"


def test_choose_resolves_ambiguous_and_unmatched_and_guards_the_holder(store):
    space, sm, cards = _space("pb-choose")
    api = client(sm)
    batch_id = _create(api, space).json()["id"]
    items = _add(api, space, batch_id, ("Sam Lee.jpg", jpeg()), ("mystery.jpg", jpeg())).json()["items"]
    ambiguous, unknown = items
    choose = lambda item, body: api.patch(_url(space, "admin-card-photo-batch-item", batch_id, item["id"]),  # noqa: E731
                                          body, format="json")
    assert choose(ambiguous, {"holder_id": cards["b"].pk}).json()["items"][0]["status"] == "matched"
    assert choose(unknown, {"holder_id": cards["b"].pk}).status_code == 400  # already chosen for another file
    assert choose(unknown, {"holder_id": 999999}).status_code == 400  # not part of this batch's cards
    assert choose(unknown, {"decision": "apply"}).status_code == 400  # no person yet
    assert choose(unknown, {"holder_id": cards["c"].pk}).json()["items"][1]["decision"] == "apply"
    assert choose(ambiguous, {"decision": "skip"}).json()["items"][0]["decision"] == "skip"


def test_apply_attaches_through_the_normal_photo_path_with_one_audit_row_per_photo(store, applied):
    space, sm, cards = _space("pb-apply")
    api = client(sm)
    batch_id = _create(api, space).json()["id"]
    _add(api, space, batch_id, ("TNK-0001.jpg", jpeg()), ("TNK-0002.jpg", jpeg()), ("nobody.jpg", jpeg()))
    assert api.post(_url(space, "admin-card-photo-batch-apply", batch_id)).status_code == 202
    assert photo_batch_apply.apply_chunk(batch_id) is False
    assert sorted(card_pk for _actor, card_pk, _size in applied) == sorted([cards["a"].pk, cards["b"].pk])
    assert all(actor == sm for actor, _pk, _size in applied)
    batch = CardPhotoBatch.objects.get(pk=batch_id)
    assert (batch.state, batch.applied_count, batch.skipped_count, batch.failed_count) == ("done", 2, 1, 0)
    assert not CardPhotoBatchItem.objects.exclude(file_key="").exists()  # temporary files are deleted
    assert not any(key.startswith("card-photo-batches/") for key in store)
    assert AuditLog.objects.filter(action="card_photo_batch.item_applied").count() == 2
    for action in ("created", "applied", "finished"):
        assert AuditLog.objects.filter(action=f"card_photo_batch.{action}", makerspace=space).count() == 1
    assert api.post(_url(space, "admin-card-photo-batch-apply", batch_id)).status_code == 400  # not applied twice


def test_keep_leaves_an_existing_photo_and_replace_overwrites_it(store, applied):
    space, sm, cards = _space("pb-replace")
    for card in cards.values():
        set_photo(card, "member-cards/1/existing")
    api = client(sm)
    batch_id = _create(api, space).json()["id"]
    items = _add(api, space, batch_id, ("TNK-0001.jpg", jpeg()), ("TNK-0002.jpg", jpeg())).json()["items"]
    api.patch(_url(space, "admin-card-photo-batch-item", batch_id, items[1]["id"]), {"decision": "replace"},
              format="json")
    api.post(_url(space, "admin-card-photo-batch-apply", batch_id))
    photo_batch_apply.apply_chunk(batch_id)
    assert [pk for _a, pk, _s in applied] == [cards["b"].pk]


def test_apply_with_nothing_chosen_is_refused(store, applied):
    space, sm, _cards = _space("pb-nothing")
    api = client(sm)
    batch_id = _create(api, space).json()["id"]
    _add(api, space, batch_id, ("unknown person.jpg", jpeg()))
    assert api.post(_url(space, "admin-card-photo-batch-apply", batch_id)).status_code == 400
    assert not applied


def test_an_apply_chunk_stops_when_the_creator_loses_authority(store, applied, monkeypatch):
    space, sm, _cards = _space("pb-revoked")
    api = client(sm)
    batch_id = _create(api, space).json()["id"]
    _add(api, space, batch_id, ("TNK-0001.jpg", jpeg()))
    api.post(_url(space, "admin-card-photo-batch-apply", batch_id))

    def refuse(*args, **kwargs):
        raise PermissionError
    monkeypatch.setattr(photo_batch_apply.roster, "authorise", refuse)
    photo_batch_apply.apply_chunk(batch_id)
    assert not applied
    assert CardPhotoBatch.objects.get(pk=batch_id).skipped_count == 1


def test_rbac_and_tenant_scoping(store):
    space, sm, _cards = _space("pb-rbac")
    other_space, other_sm, _ = _space("pb-rbac-other")
    batch_id = _create(client(sm), space).json()["id"]
    member_user, _m = member(space, "plain")
    assert client(member_user).post(_url(space), {"kind": "member_card", "holders_consented": True},
                                    format="json").status_code in (403, 404)
    assert client(other_sm).get(_url(space, "admin-card-photo-batch", batch_id)).status_code in (403, 404)
    assert client(other_sm).get(_url(other_space, "admin-card-photo-batch", batch_id)).status_code == 404
    assert client(other_sm).post(_url(space), {"kind": "member_card", "holders_consented": True},
                                 format="json").status_code in (403, 404)


def test_cancel_deletes_the_uploaded_files(store):
    space, sm, _cards = _space("pb-cancel")
    api = client(sm)
    batch_id = _create(api, space).json()["id"]
    _add(api, space, batch_id, ("TNK-0001.jpg", jpeg()))
    assert any(key.startswith("card-photo-batches/") for key in store)
    assert api.delete(_url(space, "admin-card-photo-batch", batch_id)).json()["state"] == "cancelled"
    assert not any(key.startswith("card-photo-batches/") for key in store)
    assert _add(api, space, batch_id, ("TNK-0002.jpg", jpeg())).status_code == 400


def test_expired_batches_lose_their_files(store):
    space, sm, _cards = _space("pb-expiry")
    api = client(sm)
    batch_id = _create(api, space).json()["id"]
    _add(api, space, batch_id, ("TNK-0001.jpg", jpeg()))
    from django.utils import timezone
    CardPhotoBatch.objects.filter(pk=batch_id).update(expires_at=timezone.now())
    photo_batch.purge_expired_batches()
    assert not any(key.startswith("card-photo-batches/") for key in store)
    assert CardPhotoBatch.objects.get(pk=batch_id).state == "cancelled"


def test_remove_backgrounds_needs_the_switch_and_a_provider(store):
    space, sm, _cards = _space("pb-eraser-off")
    assert _create(client(sm), space, remove_backgrounds=True).status_code == 400
    switched, sm2, _ = _space("pb-eraser-nop", switch=True)
    assert _create(client(sm2), switched, remove_backgrounds=True).status_code == 400  # switch on, no provider


def test_the_eraser_follow_up_queues_one_job_per_applied_photo(store, applied, monkeypatch):
    space, sm, cards = _space("pb-eraser", switch=True)
    row = PlatformImageAdapter()
    row.provider_url = "https://eraser.example.org"
    row.set_secret("s" * 24)
    row.save()
    queued = []
    monkeypatch.setattr(photo_batch_apply.cutouts, "request", lambda actor, kind, card, **k: queued.append((kind, card.pk)))
    api = client(sm)
    created = _create(api, space, remove_backgrounds=True).json()
    assert created["remove_backgrounds"] is True and created["eraser_available"] is True
    _add(api, space, created["id"], ("TNK-0001.jpg", jpeg()), ("TNK-0002.jpg", jpeg()))
    api.post(_url(space, "admin-card-photo-batch-apply", created["id"]))
    photo_batch_apply.apply_chunk(created["id"])
    assert sorted(queued) == sorted([("member_card", cards["a"].pk), ("member_card", cards["b"].pk)])


def test_an_eraser_refusal_does_not_undo_the_applied_photo(store, applied, monkeypatch):
    space, sm, cards = _space("pb-eraser-limit", switch=True)
    row = PlatformImageAdapter()
    row.provider_url = "https://eraser.example.org"
    row.set_secret("s" * 24)
    row.save()
    from apps.managed_hosting.extra_quotas import ExtraQuotaReached
    monkeypatch.setattr(photo_batch_apply.cutouts, "request",
                        lambda *a, **k: (_ for _ in ()).throw(ExtraQuotaReached("photo_cutout_jobs_monthly", 1)))
    api = client(sm)
    batch_id = _create(api, space, remove_backgrounds=True).json()["id"]
    _add(api, space, batch_id, ("TNK-0001.jpg", jpeg()))
    api.post(_url(space, "admin-card-photo-batch-apply", batch_id))
    photo_batch_apply.apply_chunk(batch_id)
    item = CardPhotoBatchItem.objects.get()
    assert item.state == "applied" and item.error_code.startswith("eraser_") and len(applied) == 1
