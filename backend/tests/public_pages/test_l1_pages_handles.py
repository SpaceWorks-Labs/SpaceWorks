from django.db import IntegrityError, connection, transaction
from django.utils import timezone
import pytest
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.test import APIRequestFactory
from apps.accounts.models import User
from apps.makerspaces.models import Makerspace
from apps.makerspaces.models_profiles import PublicHandle
from apps.makerspaces.models_public_pages import MakerspacePublicPage, MakerspacePublicPageRevision
from apps.makerspaces.public_page_contract import empty_document
from apps.makerspaces.public_page_errors import PageConflict
from apps.makerspaces import public_page_services as pages
from apps.makerspaces.public_page_access import resolve_handle
from apps.makerspaces.public_profile_access import resolve_public_profile
from apps.makerspaces.public_profile_handles import name_available

pytestmark = pytest.mark.django_db(transaction=True)


def test_virtual_get_does_not_create_and_save_does_not_publish(page_owner):
    space, actor = page_owner
    initial = pages.read_editor("makerspace", space.pk, actor=actor)
    assert initial["version"] == 0 and not MakerspacePublicPage.objects.exists()
    saved = pages.save("makerspace", space.pk, actor=actor, version=0, document=initial["document"])
    assert saved["version"] == 1 and saved["draft_revision_id"] and not saved["published_revision_id"]
    with pytest.raises(PageConflict):
        pages.save("makerspace", space.pk, actor=actor, version=0, document=saved["document"])


def test_namespace_is_shared_and_member_resolver_ignores_tenant_claim(page_owner):
    space, actor = page_owner
    state = pages.change_handle("makerspace", space.pk, actor=actor, version=0, handle="THE.lab")
    assert state["handle"] == "the.lab" and not name_available("the.lab")
    with pytest.raises(NotFound):
        resolve_public_profile("the.lab")
    with pytest.raises(NotFound):
        resolve_handle("the.lab")
    other = Makerspace.objects.create(name="Other", slug="other-lab")
    with pytest.raises(IntegrityError), transaction.atomic():
        PublicHandle.objects.create(makerspace=other, handle="the.LAB", changed_at=timezone.now())


def test_publication_save_then_withdraw_and_cooldown(page_owner):
    space, actor = page_owner
    state = pages.change_handle("makerspace", space.pk, actor=actor, version=0, handle="our.lab")
    state = pages.save("makerspace", space.pk, actor=actor, version=state["version"], document=state["document"])
    state = pages.publish("makerspace", space.pk, actor=actor, version=state["version"], draft_revision_id=state["draft_revision_id"])
    public_id = state["published_revision_id"]
    state = pages.save("makerspace", space.pk, actor=actor, version=state["version"], document=state["document"])
    assert state["published_revision_id"] == public_id != state["draft_revision_id"]
    request = APIRequestFactory().get("/", HTTP_HOST="testserver")
    assert resolve_handle("our.lab", request)[1]["kind"] == "makerspace"
    state = pages.change_handle("makerspace", space.pk, actor=actor, version=state["version"], release=True)
    assert not state["published_revision_id"] and not name_available("our.lab")
    with pytest.raises(NotFound):
        resolve_handle("our.lab", request)
    with pytest.raises(PageConflict):
        pages.change_handle("makerspace", space.pk, actor=actor, version=state["version"], handle="another.lab")


def test_owner_shape_and_same_page_pointer_guards(page_owner):
    space, actor = page_owner
    with pytest.raises(IntegrityError), transaction.atomic():
        PublicHandle.objects.create(handle="no.owner", changed_at=timezone.now())
    page = MakerspacePublicPage.objects.create(makerspace=space)
    other = Makerspace.objects.create(name="Other", slug="pointer-other")
    other_page = MakerspacePublicPage.objects.create(makerspace=other)
    revision = MakerspacePublicPageRevision.objects.create(page=other_page, document=empty_document("makerspace"))
    with pytest.raises(IntegrityError), transaction.atomic():
        MakerspacePublicPage.objects.filter(pk=page.pk).update(draft_revision=revision)
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
    with pytest.raises(IntegrityError), transaction.atomic():
        MakerspacePublicPageRevision.objects.filter(pk=revision.pk).update(document={})


def test_platform_cannot_use_page_services(page_owner):
    space, _ = page_owner
    platform = User.objects.create_superuser(username="page-root", password=None)
    # Decision 115: the platform superadmin edits a makerspace's OWN page like its Space Manager ...
    assert pages.read_editor("makerspace", space.pk, actor=platform)["version"] == 0
    # ... but organization pages are deployment-global and stay owner-only.
    with pytest.raises(PermissionDenied):
        pages.read_editor("organization", space.pk, actor=platform)
