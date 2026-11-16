"""Event short links: create, regenerate, resolve and the PII-free daily visit counter.

Resolution is exactly the `/e/<uuid>` gate (`website_visibility.resolve`), so an
unlisted event resolves while a private, draft, cancelled, ended, offline or unservable
one returns the same 404 as an unknown or retired code. Visits store one integer per
event per makerspace-local day and nothing about the visitor.
"""

from django.utils.translation import gettext
import logging
import re
import secrets
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import F, Sum
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.makerspaces.local_time import local_now

from . import event_authority
from .event_permissions import PUBLISH_SCHEDULE
from .models import Event
from .models_short_links import EventShortLink, EventShortLinkVisitDay
from .services_write_boundary import event_write

logger = logging.getLogger(__name__)
FEATURE = "events.short_links"
ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
CODE_RE = re.compile(r"^[0-9A-Za-z]{7}$")
BOT_RE = re.compile(r"bot|crawl|spider|preview|facebookexternalhit|whatsapp|slack|telegram|discord|skype|"
                    r"linkedin|embedly|curl|wget|python|headless|lighthouse", re.IGNORECASE)
INSERT_ATTEMPTS = 5


def new_code():
    return "".join(secrets.choice(ALPHABET) for _ in range(7))


def live_link(event):
    return EventShortLink.objects.filter(event=event, retired_at__isnull=True).first()


def _locked(event):
    return Event.objects.select_for_update(of=("self",)).select_related("makerspace").get(pk=event.pk)


def _require(actor, event):
    event_authority.require(actor, event, PUBLISH_SCHEDULE)
    if event.status != Event.Status.PUBLISHED:
        # Only a published event resolves; creating codes for drafts would hand out
        # addresses that cannot open and would block a draft occurrence's removal.
        raise ValidationError({"event": gettext("Publish the event before making a short link.")})


def _insert(event, actor):
    for _attempt in range(INSERT_ATTEMPTS):
        try:
            with transaction.atomic():
                return EventShortLink.objects.create(event=event, makerspace_id=event.makerspace_id,
                                                     code=new_code(), created_by=actor)
        except IntegrityError:
            continue  # A code collision (or a retired code) is never reissued; draw again.
    raise ValidationError({"code": gettext("Could not allocate a short link. Try again.")})


@event_write
def create(event, *, actor):
    """Idempotent: returns the live code when one exists, otherwise makes one."""
    with transaction.atomic():
        locked = _locked(event)
        _require(actor, locked)
        existing = live_link(locked)
        if existing is not None:
            return existing, False
        link = _insert(locked, actor)
        audit.record(actor, "event.short_link.created", makerspace=locked.makerspace, target=locked,
                     meta={"event_id": locked.pk, "code": link.code})
        return link, True


@event_write
def regenerate(event, *, actor):
    """Retire the live code (it 404s at once) and issue a new one in one transaction."""
    with transaction.atomic():
        locked = _locked(event)
        _require(actor, locked)
        current = EventShortLink.objects.select_for_update().filter(
            event=locked, retired_at__isnull=True).first()
        retired_code = None
        if current is not None:
            current.retired_at, current.retired_by = timezone.now(), actor
            current.save(update_fields=("retired_at", "retired_by"))
            retired_code = current.code
        link = _insert(locked, actor)
        audit.record(actor, "event.short_link.regenerated", makerspace=locked.makerspace, target=locked,
                     meta={"event_id": locked.pk, "code": link.code, "retired_code": retired_code})
        return link


def resolve_code(code):
    """The live event behind a code, through the public `/e/<uuid>` gate, or Http404."""
    if not CODE_RE.fullmatch(code or ""):
        raise Http404
    link = EventShortLink.objects.select_related("event").filter(code=code, retired_at__isnull=True).first()
    if link is None:
        raise Http404
    from apps.makerspaces.platform import feature_enabled
    from .website_visibility import resolve
    event = resolve(None, link.event.public_token)
    if not feature_enabled(event.makerspace, FEATURE):
        raise Http404  # Switched off: the code is kept but resolves like an unknown one.
    return event


def is_person_visit(request):
    headers = request.headers
    if headers.get("X-SW-Visit") != "1":
        return False
    if "prefetch" in (headers.get("Sec-Purpose", "") + headers.get("Purpose", "")).lower():
        return False
    return not BOT_RE.search(headers.get("User-Agent", ""))


def record_visit(event, request):
    """Count one person visit; any failure is logged and swallowed, never blocking the page."""
    if not is_person_visit(request):
        return False
    try:
        day = local_now(event.makerspace).date()
        rows = EventShortLinkVisitDay.objects.filter(event=event, day=day)
        if rows.update(count=F("count") + 1):
            return True
        try:
            with transaction.atomic():
                EventShortLinkVisitDay.objects.create(event=event, makerspace_id=event.makerspace_id,
                                                      day=day, count=1)
        except IntegrityError:
            rows.update(count=F("count") + 1)  # A concurrent first visit created the day row.
        return True
    except Exception:
        logger.warning("event_short_link_visit_failed", extra={"event_id": event.pk})
        return False


def visits(event, since=None, *, days=30):
    """Daily series for analytics: `[{"day", "count"}]`, oldest first, zero-filled.

    `since` is a local date; without it the window is the last `days` local days.
    """
    today = local_now(event.makerspace).date()
    start = since or today - timedelta(days=days - 1)
    counts = dict(EventShortLinkVisitDay.objects.filter(event=event, day__gte=start, day__lte=today)
                  .values_list("day", "count"))
    span = (today - start).days + 1
    return [{"day": start + timedelta(days=offset), "count": counts.get(start + timedelta(days=offset), 0)}
            for offset in range(max(span, 0))]


def total_visits(event):
    return EventShortLinkVisitDay.objects.filter(event=event).aggregate(total=Sum("count"))["total"] or 0
