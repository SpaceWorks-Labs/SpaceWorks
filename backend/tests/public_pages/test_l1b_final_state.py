from uuid import uuid4
import pytest
from django.db import connection, IntegrityError, transaction
from apps.events.models_website import EventPage
from apps.events.models_website_revisions import EventPageRevision
from apps.events.website_revisions import save_draft
from apps.makerspaces.models_public_pages import MakerspacePublicPage, MakerspacePublicPageRevision
from apps.makerspaces.public_page_contract import empty_document
from apps.makerspaces.models import Makerspace

pytestmark = pytest.mark.django_db(transaction=True)


def flush_constraints():
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_raw_sql_page_shell_and_revision_cycle_accepts_only_final_owned_pointer(page_owner):
    owner, _ = page_owner
    revision_id = uuid4()
    with transaction.atomic():
        page = MakerspacePublicPage.objects.create(makerspace=owner)
        # The pointer may precede its referenced revision within the transaction.
        with connection.cursor() as cursor:
            cursor.execute("UPDATE makerspaces_makerspacepublicpage SET draft_revision_id=%s WHERE id=%s",
                           [revision_id, page.pk])
        MakerspacePublicPageRevision.objects.create(pk=revision_id, page=page, document=empty_document("makerspace"))
        flush_constraints()
    page.refresh_from_db()
    assert page.draft_revision_id == revision_id


@pytest.mark.parametrize("wrong_owner", [False, True])
def test_raw_sql_final_pointer_rejects_dangling_or_foreign_revision(page_owner, wrong_owner):
    owner, _ = page_owner
    page = MakerspacePublicPage.objects.create(makerspace=owner)
    revision_id = uuid4()
    if wrong_owner:
        other = Makerspace.objects.create(name="Other page", slug="final-other")
        other_page = MakerspacePublicPage.objects.create(makerspace=other)
        MakerspacePublicPageRevision.objects.create(pk=revision_id, page=other_page, document=empty_document("makerspace"))
    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("UPDATE makerspaces_makerspacepublicpage SET draft_revision_id=%s WHERE id=%s",
                       [revision_id, page.pk])
        flush_constraints()
    page.refresh_from_db()
    assert page.draft_revision_id is None


def test_raw_event_release_requires_both_owned_pointers(event_owner):
    space, _, event = event_owner
    page = EventPage.objects.create(makerspace=space, event=event)
    with pytest.raises(IntegrityError), transaction.atomic():
        EventPage.objects.filter(pk=page.pk).update(released=True)
        flush_constraints()
    with transaction.atomic():
        revision = save_draft(page)
        EventPage.objects.filter(pk=page.pk).update(released=True, published_revision=revision)
        flush_constraints()
    page.refresh_from_db()
    assert page.released and page.published_revision_id == page.draft_revision_id


def test_raw_revision_mutation_cannot_rewrite_publication(event_owner):
    space, _, event = event_owner
    with transaction.atomic():
        page = EventPage.objects.create(makerspace=space, event=event)
        revision = save_draft(page)
    with pytest.raises(IntegrityError), transaction.atomic():
        EventPageRevision.objects.filter(pk=revision.pk).update(document={})
