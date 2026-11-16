"""Account-less booking mail retains live lifecycle authority through retries."""
from apps.accounts import rbac
from apps.integrations.delivery_content import render as set_content
from apps.integrations.delivery_sources import DeliverySource, register

KIND = "bookings.guest_mailbox"


def prepare(log):
    from .models import Booking
    from .notifications import requester_content, requester_enabled
    from apps.integrations.email_templates_fablab import bookings_context
    from apps.integrations.email_templates_registry_fablab_defaults import BOOKINGS_REQUESTER_BODIES
    from apps.integrations.recipients import has_selection, requester_selected
    from apps.makerspaces.platform import module_enabled
    from apps.makerspaces.servability import is_servable
    row = rbac.scope_notification_policy(Booking.objects.all(), makerspace_id=log.makerspace_id,
        field="space__makerspace_id").select_related("space__makerspace").filter(pk=log.source_id).first()
    if (row is None or row.member_id is not None or row.is_house or log.audience != "requester"
            or str(row.calendar_sequence) != log.source_metadata.get("revision")
            or row.status != log.source_metadata.get("status") or not row.email
            or row.email != log.to_email or not requester_enabled(row, log.event)):
        return False
    space = row.space.makerspace
    if not is_servable(space) or not module_enabled(space, "bookings"):
        return False
    if has_selection(space, "bookings", log.event) and not requester_selected(space, "bookings", log.event):
        return False
    content = requester_content(row, log.event, bookings_context(row, log.event,
        next_steps=BOOKINGS_REQUESTER_BODIES.get(log.event, "")))
    set_content(log, to_email=row.email, subject=content["subject"], text_body=content["text"],
                html_body=content["html"])
    return True


def register_guest_mailbox():
    register(KIND, DeliverySource(prepare, digestible=False))
