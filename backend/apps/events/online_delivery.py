"""Online/hybrid delivery: the join link and its release rule, plus the venue map link.

The join URL can carry a meeting password, so it is stored as deployment-key Fernet
ciphertext (the same at-rest scheme as integration credentials) and is released ONLY to
a confirmed registrant while `events.online_delivery` is on: the member ticket, their
confirmation email (L2 reads `join_url_for`), and their personal calendar (`.ics` and
feed). It never appears in a public serializer, share card, embed, staff room alert or
audit row. Switching the capability off hides the link everywhere and keeps the data.
"""

from django.utils.translation import gettext
from urllib.parse import quote, urlsplit

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.makerspaces.capability_eligibility import configuration_feature_enabled
from apps.makerspaces.secrets import decrypt_value, encrypt_value

from . import event_authority
from .capacity import CONFIRMED_STATUSES
from .event_permissions import EDIT_DETAILS
from .models import Event
from .services_write_boundary import event_write

FEATURE = "events.online_delivery"
MAX_JOIN_URL = 2000
ONLINE_MODES = (Event.DeliveryMode.ONLINE, Event.DeliveryMode.HYBRID)


def enabled(event):
    # Loaded configuration only: every caller is already behind a servability gate.
    return configuration_feature_enabled(event.makerspace, FEATURE)


def public_mode(event):
    """How people attend, for public cards and chips; None while the switch is off."""
    return event.delivery_mode if enabled(event) else None


def validate_join_url(value):
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) > MAX_JOIN_URL or any(ord(char) < 33 or ord(char) == 127 for char in value):
        raise ValidationError({"join_url": gettext("Use a single https:// link of at most 2000 characters.")})
    try:
        parts = urlsplit(value)
        host = parts.hostname
    except ValueError as exc:
        raise ValidationError({"join_url": gettext("Use a valid https:// link.")}) from exc
    if parts.scheme != "https" or not host or parts.username or parts.password:
        raise ValidationError({"join_url": gettext("Use an https:// link without a username or password.")})
    return value


def stored_join_url(event):
    """Staff-only plaintext; callers must hold EDIT_DETAILS or go through `join_url_for`."""
    return decrypt_value(event.join_url_encrypted) if event.join_url_encrypted else ""


def join_url_for(registration):
    """The join link for this registration, or None when it must not be shown.

    Confirmed registrants only, on a published or completed online/hybrid event, while
    the space has `events.online_delivery` on.
    """
    if registration is None or registration.status not in CONFIRMED_STATUSES:
        return None
    event = registration.event
    if (event.delivery_mode not in ONLINE_MODES
            or event.status not in (Event.Status.PUBLISHED, Event.Status.COMPLETED)
            or not enabled(event)):
        return None
    return stored_join_url(event) or None


def map_url(event):
    """A venue map link for in-person and hybrid events; never for online-only events.

    An external venue's own map link (`venue_map_url`) wins when set; then the host space's map
    link (the event happens at that venue); otherwise a map search for the event location within
    the space's town. None without any of them.
    """
    if enabled(event) and event.delivery_mode == Event.DeliveryMode.ONLINE:
        return None
    if event.venue_map_url:
        return event.venue_map_url
    space = event.makerspace
    if space.map_url:
        return space.map_url
    query = ", ".join(part for part in (event.location.strip(), space.location.strip()) if part)
    return "https://www.openstreetmap.org/search?query=" + quote(query[:255]) if query else None


def refuse_when_off(event, delivery_mode=None, join_url_value=None):
    """404 before any write when a request would change online delivery while it is off."""
    from apps.makerspaces.folded_capabilities import require_capability
    changes_mode = delivery_mode is not None and delivery_mode != event.delivery_mode
    changes_link = join_url_value is not None and validate_join_url(join_url_value) != stored_join_url(event)
    if changes_mode or changes_link:
        require_capability(event.makerspace, FEATURE)


@event_write
def set_online(event, *, actor, delivery_mode=None, join_url_value=None):
    """Change how people attend; audited without ever recording the link itself."""
    from apps.makerspaces.folded_capabilities import require_capability

    with transaction.atomic():
        locked = Event.objects.select_for_update(of=("self",)).select_related("makerspace").get(pk=event.pk)
        event_authority.require(actor, locked, EDIT_DETAILS)
        old_mode, fields = locked.delivery_mode, []
        if delivery_mode is not None and delivery_mode != locked.delivery_mode:
            if delivery_mode not in Event.DeliveryMode.values:
                raise ValidationError({"delivery_mode": gettext("Choose in_person, online or hybrid.")})
            locked.delivery_mode = delivery_mode
            fields.append("delivery_mode")
        if join_url_value is not None:
            cleaned = validate_join_url(join_url_value)
            if cleaned != stored_join_url(locked):
                locked.join_url_encrypted = encrypt_value(cleaned) if cleaned else ""
                fields.append("join_url_encrypted")
        if not fields:
            return locked  # An unchanged echo never needs the switch (the form resends it).
        require_capability(locked.makerspace, FEATURE)
        locked.version += 1
        locked.save(update_fields=[*fields, "version", "updated_at"])
        from .services_calendar import calendar_event_changed
        calendar_event_changed(locked)
        audit.record(actor, "event.delivery_mode_changed", makerspace=locked.makerspace, target=locked,
                     meta={"event_id": locked.pk, "old_mode": old_mode, "new_mode": locked.delivery_mode,
                           "join_url_changed": "join_url_encrypted" in fields,
                           "join_url_set": bool(locked.join_url_encrypted)})
        return locked
