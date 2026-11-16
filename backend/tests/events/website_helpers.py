from datetime import timedelta
from copy import deepcopy

from apps.events.models import EventStaffGrant
from apps.events.models_website import EventPage, EventPageSection
from tests.events.ticketing_helpers import event_space, open_event, account
from tests.events.collab_helpers import make_staff, client_for
from django.db import transaction


@transaction.atomic
def snapshot(page, *, released=None):
    """Fixture publication is explicit; production saves never publish implicitly."""
    from apps.events.website_revisions import save_draft
    revision = save_draft(page)
    if released is not None:
        page.released = released
    if page.released:
        page.published_revision = revision
    page.save(update_fields=["released", "published_revision"])
    return page


@transaction.atomic
def make_page(**values):
    released = values.pop("released", False)
    page = EventPage.objects.create(**values)
    return snapshot(page, released=released)


@transaction.atomic
def make_session(**values):
    from apps.events.models_website import EventSession
    from apps.events.models_website_revisions import EventSessionIdentity, EventSessionAlias
    page = values["page"]
    identity = EventSessionIdentity.objects.create(page=page)
    EventSessionAlias.objects.create(page=page, identity=identity, slug=values["slug"])
    result = EventSession.objects.create(identity=identity, **values)
    snapshot(page)
    return result


@transaction.atomic
def remove_page(page):
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.allow_immutable_delete', true)")
        previous = cursor.fetchone()[0] or ""
        cursor.execute("SET LOCAL app.allow_immutable_delete = 'on'")
    page.delete()
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.allow_immutable_delete', %s, true)", [previous])


def website_fixture(*, released=True):
    space = event_space("website")
    space.enabled_features += ["events.website", "events.embed"]
    space.website_embed_origins = ["https://partner.example"]
    space.save(update_fields=["enabled_features", "website_embed_origins"])
    actor = make_staff(space)
    event = open_event(space)
    page = EventPage.objects.create(makerspace=space, event=event)
    section = EventPageSection.objects.create(page=page, kind="speaker", slug="ada", title="Ada",
                                               body="**Welcome**", visibility="published")
    snapshot(page, released=released)
    return space, actor, event, page, section


def section(slug="intro", kind="intro", **values):
    return {"kind": kind, "slug": slug, "title": slug.title(), "body": "", "url": "",
            "asset_id": None, "visibility": "published", "position": 0, **values}


def session(event, slug="talk", **values):
    return {"slug": slug, "title": slug.title(), "body": "", "starts_at": event.starts_at,
            "ends_at": event.starts_at + timedelta(minutes=30), "track": None, "room": None,
            "speakers": [], "visibility": "published", **values}


def content(page, sections=None, sessions=None):
    return {"revision": page.revision, "sections": sections or [], "sessions": sessions or []}


def grantee(space, event, permission):
    from uuid import uuid4
    user = account(f"website-{permission}")
    issuer = make_staff(space, username=f"website-issuer-{uuid4().hex[:8]}")
    grant = EventStaffGrant.objects.create(makerspace=space, event=event, user=user,
                                            granted_by=issuer, permissions=[permission])
    from apps.events.contributions.models_roles import EventGrantEntitlement
    EventGrantEntitlement.objects.create(event=event, makerspace=space, grant=grant,
        source_kind="manual", permissions=[permission], created_by=issuer)
    return user, grant


def url(event, suffix=""):
    return f"/api/v1/public/{event.makerspace.slug}/events/{event.public_token}/website/{suffix}"


def staff_url(event, suffix=""):
    return f"/api/v1/admin/events/{event.pk}/website/{suffix}"
