"""No-store public allowlists and live gates independent of an expired EventPage."""

import re
from urllib.parse import urlsplit

from django.http import Http404
from django.utils import timezone

from apps.events.contracts.providers import ReadPurpose
from apps.events.judging.errors import ProgrammeError
from apps.events.judging.models_results import ResultPublicationState
from apps.events.judging.ports import runtime
from apps.events.models import Event
from apps.makerspaces.editions import public_surface_available
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import is_servable
from .gallery_models import GalleryConsent, GalleryEntryAsset


def public_event(*, request_context, public_token=None, event_id=None, gallery=True):
    rows = Event.objects.select_related("makerspace")
    event = rows.filter(public_token=public_token).first() if public_token else rows.filter(pk=event_id).first()
    if event is None:
        raise Http404
    space = event.makerspace
    if (not event.is_public or event.status not in ("published", "completed") or not is_servable(space)
            or not space.public_site_enabled or not module_enabled(space, "events")
            or not public_surface_available("events")):
        raise Http404
    runtime().require_public_origin(event, request_context)
    runtime().require_programme(event, gallery=gallery)
    return event


def live_entry(entry, *, include_hidden=False):
    if not entry.publication.active:
        raise Http404
    if entry.hidden_at and not include_hidden:
        raise Http404
    snapshot = runtime().snapshot(entry.snapshot_id)
    row = GalleryConsent.objects.filter(event_id=entry.event_id, team_id=snapshot.team_id,
        snapshot_id=entry.snapshot_id, metadata_public=True, metadata_generation=entry.metadata_generation).first()
    if (row is None or snapshot.event_id != entry.event_id or not snapshot.eligible or not snapshot.current):
        raise Http404
    return snapshot, row


def _link(value):
    try:
        parsed = urlsplit(value)
        return bool(len(value) <= 2048 and parsed.scheme == "https" and parsed.hostname and not parsed.username
                    and not parsed.password and not any(ord(c) < 32 or ord(c) == 127 for c in value))
    except (ValueError, TypeError):
        return False


def _member_cards(snapshot):
    cards = []
    for member in snapshot.member_ids:
        card = runtime().public_member_card(event_id=snapshot.event_id, member_id=member, scope="team")
        if (card and isinstance(card.get("handle"), str) and isinstance(card.get("display_name"), str)
                and re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,28}[a-z0-9]", card["handle"])):
            # Derive profile href from the public handle. Never expose membership/actor IDs.
            cards.append({"display_name": str(card["display_name"])[:200], "profile_url": f"/{card['handle']}"})
            photo = card.get("photo_url")
            if isinstance(photo, str) and re.fullmatch(
                    r"/api/v1/public/event-programmes/[a-f0-9-]{36}/member-cards/[a-f0-9-]{36}/photo/", photo):
                cards[-1]["photo_url"] = photo
    return cards


def project_entry(entry):
    snapshot, consent = live_entry(entry)
    expired = bool(snapshot.expires_at and snapshot.expires_at <= timezone.now())
    items = list(consent.items.filter(active=True))
    asset_generations = {i.asset_id: i.generation for i in items if i.asset_id}
    link_generations = {i.link_id: i.generation for i in items if i.link_id}
    assets, links = [], []
    if not expired:
        for item in entry.assets.all():
            if item.asset_id not in snapshot.public_asset_ids or asset_generations.get(item.asset_id) != item.consent_generation:
                continue
            value = runtime().public_asset(event_id=entry.event_id, asset_id=item.asset_id)
            if value["state"] == "expired":
                continue
            if value["state"] != "ready":
                continue
            assets.append({"public_id": str(item.public_id), "mime": value["mime"], "bytes": value["bytes"],
                           "sha256": value["sha256"], "kind": value["kind"],
                           "download_url": f"/api/v1/public/event-programmes/{entry.event.public_token}/gallery/assets/{item.public_id}/"})
        live_links = {link.id: link.url for link in snapshot.public_links}
        links = [{"kind": item.kind, "url": item.url} for item in entry.links.all()
                 if link_generations.get(item.link_id) == item.consent_generation
                 and live_links.get(item.link_id) == item.url and _link(item.url)]
    files_state = "expired" if expired else ("available" if assets or links else "withdrawn")
    return {"public_id": str(entry.public_id), "title": entry.title, "description": entry.description,
            "consent_version": consent.version, "files_state": files_state, "assets": assets, "links": links,
            "members": _member_cards(snapshot), "content_sha256": snapshot.content_sha256}


def asset_download(public_token, public_asset_id, *, request):
    def authorize():
        event = public_event(public_token=public_token, request_context=request)
        item = GalleryEntryAsset.objects.select_related("entry").filter(
            public_id=public_asset_id, entry__event_id=event.pk).first()
        if item is None:
            raise Http404
        snapshot, consent = live_entry(item.entry)
        if not consent.items.filter(asset_id=item.asset_id, active=True, generation=item.consent_generation).exists():
            raise Http404
        if item.asset_id not in snapshot.public_asset_ids:
            raise Http404
        if snapshot.expires_at and snapshot.expires_at <= timezone.now():
            raise ProgrammeError("asset_expired", "These project files have expired.", status=410)
        return item
    item = authorize()
    return runtime().stream_asset(asset_id=item.asset_id, snapshot_id=item.entry.snapshot_id,
        actor_id=None, purpose=ReadPurpose.PUBLIC_GALLERY, request=request, reauthorize=authorize)


def public_results(event):
    state = ResultPublicationState.objects.filter(event=event).select_related("current_announcement__result").first()
    if state is None or not state.current_announcement_id:
        raise Http404
    announcement = state.current_announcement
    awards = []
    for award in announcement.result.awards.select_related("prize").filter(public_requested=True).order_by("prize_id", "rank"):
        snapshot = runtime().snapshot(award.submission_snapshot_id)
        consent = GalleryConsent.objects.filter(event=event, snapshot_id=snapshot.id, metadata_public=True).first()
        if snapshot.current and snapshot.eligible and snapshot.event_id == event.pk and consent:
            awards.append({"prize": award.prize_name, "rank": award.rank, "title": snapshot.title})
    return {"event_id": event.pk, "version": announcement.result.version,
            "published_at": announcement.published_at, "awards": awards}
