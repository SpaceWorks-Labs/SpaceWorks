"""Decision #86: the merged event-website write path keeps both designs' guarantees.

Pages: journalled reservations, copy-on-write overrides, session identities and the
reserve/replay engine. Events programme: fresh actor authority, declared scope
preparation, pre-allocated page IDs, fenced programme and design steps on clone, and
refusal when the page changed after preparation.
"""

import pytest
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.events import services_clone, website_preparation
from apps.events.models import Event
from apps.events.models_website import EventPage, EventPageAsset
from apps.events.services_clone import duplicate_event
from apps.events.services_website import save_content
from apps.events.website_projection import project
from apps.makerspaces.models_page_cleanup import PublicPageObjectCleanup as Cleanup
from apps.makerspaces.website_asset_journal import pending_bytes
from tests.events.website_helpers import section, session
from tests.public_pages.l1c_storage import object_store, upload, inherit  # noqa: F401

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def prepared_ids(monkeypatch):
    """Record every page ID the preparation layer pre-allocates."""
    seen = []
    real = website_preparation._prepare

    def record(target, actor):
        prepared = real(target, actor)
        seen.append(prepared.prepared_page_id)
        return prepared

    monkeypatch.setattr(website_preparation, "_prepare", record)
    return seen


def test_first_upload_creates_the_page_at_its_preallocated_id_and_journals_it(event_owner, object_store, prepared_ids):
    space, actor, event = event_owner
    assert not EventPage.objects.filter(event=event).exists()
    asset = upload(event, actor)
    page = EventPage.objects.get(event=event)
    # Both passes of the reserve/replay engine reuse the one pre-allocated ID.
    assert prepared_ids == [page.pk]
    assert asset.page_id == page.pk and asset.object_key in object_store.private
    # The journal reservation names the same page and was charged exactly once on commit.
    job = Cleanup.objects.get(object_key=asset.object_key)
    assert job.page_id == page.pk and job.storage_accounted
    space.refresh_from_db()
    assert pending_bytes(space.pk) == 0 and space.storage_bytes_used == asset.size_bytes


def test_a_page_changed_after_preparation_is_refused_before_any_bytes(event_owner, object_store, monkeypatch):
    _, actor, event = event_owner
    upload(event, actor)
    real = website_preparation._prepare

    def stale(target, actor):
        prepared = real(target, actor)
        prepared.page_source = ("changed-since-preparation",)
        return prepared

    monkeypatch.setattr(website_preparation, "_prepare", stale)
    assets, jobs = EventPageAsset.objects.count(), Cleanup.objects.count()
    object_store.calls.clear()
    with pytest.raises(ValidationError, match="website changed"):
        upload(event, actor, revision=project(event)["revision"])
    assert not [call for call in object_store.calls if call[1] in {"put", "copy"}]
    assert EventPageAsset.objects.count() == assets and Cleanup.objects.count() == jobs


def test_a_deactivated_actor_is_refused_before_reserving_bytes(event_owner, object_store):
    _, actor, event = event_owner
    type(actor).objects.filter(pk=actor.pk).update(is_active=False)
    # The request still carries the stale, active instance.
    assert actor.is_active
    with pytest.raises(PermissionDenied):
        upload(event, actor)
    assert not object_store.private and not Cleanup.objects.exists()
    assert not EventPage.objects.filter(event=event).exists()


def test_cow_save_keeps_session_identities_and_bumps_the_event_version(event_owner, object_store, prepared_ids):
    _, actor, event = event_owner
    series = inherit(event)
    speaker = upload(series, actor)
    save_content(series, actor=actor, data={"revision": project(series)["revision"],
        "sections": [section("speaker", "speaker", asset_id=speaker.pk)],
        "sessions": [session(event, speakers=["speaker"])]})
    version = Event.objects.get(pk=event.pk).version
    inherited = project(event)
    prepared_ids.clear()
    save_content(event, actor=actor, data=inherited)
    own = EventPage.objects.get(event=event)
    assert prepared_ids == [own.pk]
    # Copy-on-write: the override owns copied speaker bytes and an aliased session identity.
    copied = own.sessions.get().speaker_links.get().speaker
    assert copied.page_id == own.pk and copied.asset_id != speaker.pk
    assert own.session_aliases.get().identity_id == own.sessions.get().identity_id
    assert Event.objects.get(pk=event.pk).version == version + 1


def test_duplicate_runs_fenced_programme_and_design_steps_inside_the_cow_clone(event_owner, object_store, monkeypatch):
    space, actor, event = event_owner
    source = upload(event, actor)
    save_content(event, actor=actor, data={"revision": project(event)["revision"],
        "sections": [section(asset_id=source.pk)], "sessions": []})
    calls = {"fences": [], "programme": [], "designs": 0}
    from apps.events.contracts import clone_registration
    from apps.events.certificates import clone_designs
    real_fences, real_programme, real_designs = (
        services_clone.fences, clone_registration.copy_programme_locked, clone_designs.copy_designs_locked)

    def fences(**kwargs):
        calls["fences"].append(kwargs)
        return real_fences(**kwargs)

    def programme(*args, **kwargs):
        context = [value for value in (*args, *kwargs.values()) if hasattr(value, "event_id")]
        calls["programme"].append(context[0].event_id if context else None)
        return real_programme(*args, **kwargs)

    def designs(*args, **kwargs):
        calls["designs"] += 1
        return real_designs(*args, **kwargs)

    monkeypatch.setattr(services_clone, "fences", fences)
    monkeypatch.setattr(clone_registration, "copy_programme_locked", programme)
    monkeypatch.setattr(clone_designs, "copy_designs_locked", designs)
    clone = duplicate_event(event, actor=actor)
    page = EventPage.objects.get(event=clone)
    copied = page.assets.get()
    # Pages: the clone owns new private bytes; the source keeps its own.
    assert copied.object_key != source.object_key
    assert {source.object_key, copied.object_key} <= set(object_store.private)
    assert page.sections.get().asset_id == copied.pk
    # Events programme: every pass is fenced on the host tenant, and the final pass
    # copies the programme into the committed clone after its design step.
    assert calls["fences"] and all(space.pk in fence["tenant_ids"] for fence in calls["fences"])
    assert calls["programme"][-1] == clone.pk and calls["designs"] >= 1
