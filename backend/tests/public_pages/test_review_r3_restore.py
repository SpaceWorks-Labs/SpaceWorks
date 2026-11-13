"""Round 3: restore inverses and effective tenant storage accounting."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.apps import apps
from django.db import DatabaseError, connection, transaction

from apps.backup.public_page_verification import verify_public_pages
from apps.backup.build_errors import BackupBuildError
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.models_profiles import MemberProfile
from apps.makerspaces.public_page_contract import empty_document
from tests.events.collab_helpers import make_member

pytestmark = pytest.mark.django_db(transaction=True)


def member_reference(kind, space, event):
    from apps.events.website_revisions import working_document
    from apps.organizations.models import Organization
    membership = MakerspaceMembership.objects.get(makerspace=space, user=make_member(space))
    profile = MemberProfile.objects.create(membership=membership)
    app, name = {"makerspace": ("makerspaces", "MakerspacePublicPage"),
                 "organization": ("organizations", "OrganizationPublicPage"),
                 "event": ("events", "EventPage")}[kind]
    Page = apps.get_model(app, name)
    Revision = apps.get_model(app, name + "Revision")
    Member = apps.get_model(app, name + "RevisionMember")
    if kind == "organization":
        page = Page.objects.create(organization=Organization.objects.create(name="Global", slug="r3-global"))
    else:
        page = Page.objects.create(makerspace=space, **({"event": event} if kind == "event" else {}))
    slot = str(uuid4())
    editorial = empty_document(kind)
    editorial["sections"].append({"id": str(uuid4()), "type": "team", "enabled": True,
        "payload": {"title": "Team", "entries": [
            {"id": slot, "kind": "member", "member_slot_id": slot, "role": "Host"}]}})
    document = working_document(page) if kind == "event" else editorial
    if kind == "event":
        document["editorial_document"] = editorial
    with transaction.atomic():
        revision = Revision.objects.create(page=page, document=document,
            **({"source_anchor_start": event.starts_at} if kind == "event" else {}))
        link = Member.objects.create(revision=revision, slot=slot, profile=profile)
    Member.objects.filter(pk=link.pk).update(profile=None)  # Actual backup projection.
    return Member, link, profile


@pytest.mark.parametrize("override", [None, -1, "default"])
def test_unlimited_tenant_assets_verify_without_incrementing_counter(event_owner, settings, monkeypatch, override):
    from apps.events.models_website import EventPage, EventPageAsset
    from apps.events.services_website import save_content
    from apps.makerspaces import limits
    from apps.makerspaces.models_public_pages import MakerspacePublicPage, MakerspacePublicPageAsset
    monkeypatch.setattr(limits, "is_self_host", lambda: False)
    settings.MANAGED_RESOURCE_LIMITS = {"storage": None if override == "default" else 1000}
    space, actor, event = event_owner
    space.resource_limit_overrides = {} if override == "default" else {"storage": override}
    space.save(update_fields=["resource_limit_overrides"])
    page = MakerspacePublicPage.objects.create(makerspace=space)
    MakerspacePublicPageAsset.objects.create(page=page, size_bytes=10, alt_text="Maker image",
        object_key=f"pages/makerspaces/{space.pk}/{page.pk}/r3.webp")
    save_content(event, actor=actor, data={"revision": 0, "sections": [], "sessions": []})
    event_page = EventPage.objects.get(event=event)
    EventPageAsset.objects.create(page=event_page, size_bytes=20, alt_text="Event image",
        object_key=f"events/website/{space.pk}/{event_page.pk}/r3.webp")
    limits.add_storage(space, 30)
    space.refresh_from_db()
    # Owner rule 261: bytes are counted for every space (unlimited ones too); an unlimited space is never refused.
    assert space.storage_bytes_used == 30
    assert verify_public_pages()["assets"] == 1
    # Finite tenants must still account for both maker and event bytes. Other
    # domains may add to the counter; the verifier never requires subtotal equality.
    space.resource_limit_overrides = {"storage": 1000}
    space.save(update_fields=["resource_limit_overrides"])
    # Review r5: a counter below the page bytes is a legitimate state (bytes uploaded
    # while unlimited were never counted; free_storage clamps at zero). Warn only.
    for charged in (0, 10, 29):
        type(space).objects.filter(pk=space.pk).update(storage_bytes_used=charged)
        verify_public_pages()
    for charged in (30, 40):
        type(space).objects.filter(pk=space.pk).update(storage_bytes_used=charged)
        verify_public_pages()
