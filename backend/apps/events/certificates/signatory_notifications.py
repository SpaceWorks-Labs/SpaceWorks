"""Ask a signatory to approve a certificate design: a navigation notice, never the design itself."""
from django.db import transaction

from apps.integrations.notification_links import local_link
from apps.integrations.notification_outbox import emit

SOURCE = "events.certificate_signature"
EVENT = "certificate_signature_requested"


def notify(event_id):
    from apps.events.models import Event
    from apps.notifications.inbox import eligible_owner
    from .signatory_commands import pending_for
    from .signatory_models import EventCertificateSignatory
    event = Event.objects.select_related("makerspace").get(pk=event_id)
    space = event.makerspace
    people = set(EventCertificateSignatory.objects.filter(event=event, member__isnull=False)
                 .values_list("member_id", flat=True))
    for member_id in people:
        if not eligible_owner(space, member_id):
            continue
        from apps.accounts.models import User
        member = User.objects.get(pk=member_id)
        for item in pending_for(member, space.pk):
            if item["event_id"] != event.pk or item["approved"]:
                continue
            with transaction.atomic():
                emit(makerspace=space, recipient=member, feature="events", stream="events", event=EVENT,
                     audience="member", source_kind=SOURCE, source_id=str(item["signatory_id"]),
                     revision=str(item["template_revision_id"]),
                     dedup_key=f"ev:cert-sign:{item['signatory_id']}:{item['template_revision_id']}",
                     context={"event_id": event.pk, "signatory_id": item["signatory_id"],
                              "template_revision_id": item["template_revision_id"]},
                     rendered={"subject": "A certificate design needs your approval",
                               "text": (f"Certificates for {event.title} print your signature. Review the design "
                                        "and approve it so they can be issued."),
                               "html": "", "link": local_link(space, "member")})


def eligible(envelope):
    """Deliver only while the request is still live: approval on, signatory still this person, not approved."""
    from apps.events.models import Event
    from apps.makerspaces.platform import module_enabled
    from apps.makerspaces.servability import is_servable
    from .signatories import approval_required, design_status
    from .signatory_models import EventCertificateSignatory
    from apps.events.models_certificate_templates import EventCertificateTemplateRevision
    context = envelope.context or {}
    event = Event.objects.select_related("makerspace").filter(pk=context.get("event_id")).first()
    if event is None or event.makerspace_id != envelope.makerspace_id or not is_servable(event.makerspace):
        return False
    if not module_enabled(event.makerspace, "events") or not approval_required(event):
        return False
    signatory = EventCertificateSignatory.objects.filter(pk=context.get("signatory_id"), event=event,
                                                         member_id=envelope.recipient_id).first()
    revision = EventCertificateTemplateRevision.objects.filter(pk=context.get("template_revision_id"),
                                                               event=event).first()
    if signatory is None or revision is None:
        return False
    return any(item["slot"] == signatory.slot and not item["approved"] for item in design_status(event, revision))
