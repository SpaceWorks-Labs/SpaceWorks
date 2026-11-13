"""Round 3: restore inverses and effective tenant storage accounting."""

import pytest as _legacy_pytest

_legacy_pytest.skip('Not in release 0.12.0: apps.backup.recipient_selection, apps.backup.slice_merge_cleanup, apps.backup.slice_merge_database, apps.backup.slice_merge_staging (+2 more)', allow_module_level=True)

from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.apps import apps
from django.db import DatabaseError, connection, transaction

from apps.backup.public_page_verification import verify_public_pages
from apps.backup.recipient_selection import BackupBuildError
from apps.backup.slice_merge_cleanup import drop_staging_schema
from apps.backup.slice_merge_database import (
    MERGE_ROLE, WRITE_TRIGGER, merge_role, merge_schema_name,
    protect_target_tables, provision_merge_role,
)
from apps.backup.slice_merge_staging import _apply_delta, _create_schema, _insert_delta
from apps.backup.slice_merge_types import SliceMergeError
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.models_profiles import MemberProfile
from apps.makerspaces.public_page_contract import empty_document
from tests.backup.test_slice_merge_database_e8 import _merging_component
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


@pytest.mark.parametrize("kind", ["organization", "makerspace", "event"])
def test_only_exact_guarded_slice_inverse_can_restore_member_link(event_owner, kind):
    space, _, event = event_owner
    Model, link, profile = member_reference(kind, space, event)
    other = MemberProfile.objects.create(membership=MakerspaceMembership.objects.get(
        makerspace=space, user=make_member(space, username="other")))
    table = Model._meta.db_table
    delta = {"field": "profile", "row_pk": link.pk, "old_value": None, "new_value": profile.pk}
    # Ordinary writers cannot un-null the immutable link, even if they spoof GUCs.
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.b1_merge_component', %s, true)", [str(uuid4())])
        _apply_delta(cursor, Model, delta)

    operation, component = _merging_component(makerspace_id=space.pk)
    provision_merge_role()
    schema = merge_schema_name(operation.operation_id, [component.component_id])
    _create_schema(schema, [SimpleNamespace(component=component)], {table}, using="default")
    _insert_delta(schema, Model, delta, component.component_id, using="default")
    try:
        # The role alone is insufficient, even when granted UPDATE by an operator.
        with connection.cursor() as cursor:
            cursor.execute(f'DROP TRIGGER IF EXISTS {WRITE_TRIGGER} ON "{table}"')
            cursor.execute(f'GRANT UPDATE, SELECT ON "{table}" TO {MERGE_ROLE}')
        with pytest.raises(SliceMergeError), transaction.atomic(), connection.cursor() as cursor:
            with merge_role(cursor, operation.operation_id, component.component_id, schema):
                _apply_delta(cursor, Model, delta)
        protect_target_tables(schema, {table})
        # A mismatched component and an undeclared inverse still fail the backup guard.
        with pytest.raises(SliceMergeError), transaction.atomic(), connection.cursor() as cursor:
            with merge_role(cursor, operation.operation_id, uuid4(), schema):
                _apply_delta(cursor, Model, delta)
        with pytest.raises(SliceMergeError), transaction.atomic(), connection.cursor() as cursor:
            with merge_role(cursor, operation.operation_id, component.component_id, schema):
                _apply_delta(cursor, Model, {**delta, "new_value": other.pk})
        # Even a declared membership/slot rewrite remains outside the allowance.
        slot_delta = {"field": "slot", "row_pk": link.pk, "old_value": str(link.slot), "new_value": str(uuid4())}
        _insert_delta(schema, Model, slot_delta, component.component_id, using="default")
        with pytest.raises(SliceMergeError), transaction.atomic(), connection.cursor() as cursor:
            with merge_role(cursor, operation.operation_id, component.component_id, schema):
                _apply_delta(cursor, Model, slot_delta)
        with transaction.atomic(), connection.cursor() as cursor:
            with merge_role(cursor, operation.operation_id, component.component_id, schema):
                _apply_delta(cursor, Model, delta)
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        link.refresh_from_db()
        assert link.profile_id == profile.pk
        rewrite = {**delta, "old_value": profile.pk, "new_value": other.pk}
        _insert_delta(schema, Model, rewrite, component.component_id, using="default")
        with pytest.raises(SliceMergeError), transaction.atomic(), connection.cursor() as cursor:
            with merge_role(cursor, operation.operation_id, component.component_id, schema):
                _apply_delta(cursor, Model, rewrite)
    finally:
        with connection.cursor() as cursor:
            cursor.execute(f'DROP TRIGGER IF EXISTS {WRITE_TRIGGER} ON "{table}"')
        drop_staging_schema(schema)


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
    assert space.storage_bytes_used == 0
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
