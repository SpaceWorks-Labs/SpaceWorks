"""Semantic validation must run before serving a restored candidate."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.db import connection, transaction

from apps.backup.public_page_verification import verify_public_pages, verify_pointers, verify_references
from apps.backup.build_errors import BackupBuildError
from apps.makerspaces import public_page_services as pages
from apps.makerspaces.public_page_contract import empty_document
from apps.organizations.models import Organization
from apps.organizations.models_public_pages import OrganizationPublicPage, OrganizationPublicPageRevision

pytestmark = pytest.mark.django_db(transaction=True)


def test_valid_tenant_and_global_history_verify_without_publication(page_owner):
    space, actor = page_owner
    pages.save("makerspace", space.pk, actor=actor, version=0, document=empty_document("makerspace"))
    organization = Organization.objects.create(name="Global history", slug="restore-global")
    page = OrganizationPublicPage.objects.create(organization=organization)
    revision = OrganizationPublicPageRevision.objects.create(page=page, document=empty_document("organization"), created_by=actor)
    page.draft_revision = revision
    page.save(update_fields=["draft_revision"])
    report = verify_public_pages()
    assert report["pages"] == 2 and report["revisions"] == 2


def test_post_restore_pointer_verifier_rejects_wrong_owner_even_without_a_trigger():
    class Revisions:
        def filter(self, **_):
            return self
        def exists(self):
            return False
    with pytest.raises(BackupBuildError, match="wrong-owner"):
        verify_pointers(SimpleNamespace(draft_revision_id=uuid4(), published_revision_id=None, revisions=Revisions()))


def test_post_restore_reference_verifier_checks_slot_equality_not_just_count():
    class References:
        def values_list(self, *_args, **_kwargs):
            return [("cover", 2, 1)]
    document = empty_document("makerspace")
    document.update(cover_mode="asset", cover_asset_id=1)
    with pytest.raises(BackupBuildError, match="asset references"):
        verify_references(SimpleNamespace(page_id=1, asset_references=References()), document)


def test_global_quota_is_reproduced_from_retained_and_pending_bytes():
    from apps.organizations.models_public_pages import OrganizationPublicPageStorage
    organization = Organization.objects.create(name="Quota", slug="restore-quota")
    OrganizationPublicPageStorage.objects.create(organization=organization, used_bytes=5)
    with pytest.raises(BackupBuildError, match="global storage"):
        verify_public_pages()


def test_restored_released_schedule_validates_both_working_and_published(event_owner):
    from apps.events.services_website import save_content, set_release
    from apps.events.models_website import EventPage
    from tests.events.website_helpers import session
    _, actor, event = event_owner
    save_content(event, actor=actor, data={"revision": 0, "sections": [], "sessions": [session(event)]})
    page = EventPage.objects.get(event=event)
    set_release(event, actor=actor, released=True, revision=page.revision)
    assert verify_public_pages()["event_pages"] == 1


def test_global_reference_inverse_without_backup_merge_guard_is_rejected(page_owner):
    """Ordinary writers cannot use the guarded slice-restore allowance."""
    from django.db import IntegrityError
    from apps.makerspaces.models_profiles import MemberProfile
    from apps.organizations.models_public_pages import OrganizationPublicPageRevisionMember
    space, actor = page_owner
    from tests.accounts.account_factories import make_membership
    # A member profile hangs off the community row (DB track guard); the page owner is staff, so under
    # one account per person (decision 63) they join as a member too rather than reuse the staff row.
    membership = make_membership(actor, space)
    profile = MemberProfile.objects.create(membership=membership)
    organization = Organization.objects.create(name="Inverse", slug="restore-inverse")
    page = OrganizationPublicPage.objects.create(organization=organization)
    document = empty_document("organization")
    slot = str(uuid4())
    document["sections"].append({"id": str(uuid4()), "type": "team", "enabled": True,
        "payload": {"title": "", "entries": [{"id": slot, "kind": "member", "member_slot_id": slot, "role": ""}]}})
    with transaction.atomic():
        revision = OrganizationPublicPageRevision.objects.create(page=page, document=document)
        link = OrganizationPublicPageRevisionMember.objects.create(revision=revision, profile=profile, slot=slot)
    OrganizationPublicPageRevisionMember.objects.filter(pk=link.pk).update(profile=None)
    with pytest.raises(IntegrityError), transaction.atomic():
        OrganizationPublicPageRevisionMember.objects.filter(pk=link.pk).update(profile=profile)
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
