"""Member certification notices and type-scoped staff notices."""
from django.utils import timezone

from apps.accounts import rbac
from apps.hardware_requests.notifications_p2 import content, fanout, revision
from apps.integrations.destinations import NotificationScope
from apps.integrations.email_templates import render
from apps.integrations.email_templates_registry_helpers import bag
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.hardware_requests.notifications_p2 import safe_adapter
from apps.makerspaces.local_time import to_local
from .models import CertificationGrant, CertificationType

KIND = "machines.certification"
DIGEST = "machines.certification_summary"


def version(grant):
    return revision(grant.granted_at, grant.expires_at, grant.revoked_at, grant.membership_id)


def staff_allowed(envelope, type_id):
    if envelope.audience != "staff" or envelope.recipient_id is None:
        return True
    from apps.accounts.models import User
    from .access import can_create_machine
    from .models import MachineType
    actor = User.objects.filter(pk=envelope.recipient_id).first()
    machine_type = MachineType.objects.filter(pk=type_id).first()
    return bool(actor and machine_type and can_create_machine(actor, envelope.makerspace_id, machine_type))


def eligible(envelope):
    rows = rbac.scope_notification_policy(CertificationGrant.objects.all(),
        makerspace_id=envelope.makerspace_id, field="certification_type__makerspace_id")
    grant = rows.select_related("membership", "certification_type__machine_type", "granted_by", "revoked_by").filter(
        pk=envelope.source_id, membership__makerspace_id=envelope.makerspace_id,
        membership__status="active", membership__receives_notifications=True,
        certification_type__is_active=True).first()
    if grant is None or version(grant) != envelope.revision:
        return False
    if envelope.event in {"expiring", "expired"}:
        from .reminders_certifications import eligible_grants, reminder_time
        if not eligible_grants(envelope.makerspace).filter(pk=grant.pk).exists():
            return False
        due = reminder_time(envelope.makerspace, grant, envelope.event)
        if due is None or due > timezone.now() or (grant.expires_at <= timezone.now()) != (envelope.event == "expired"):
            return False
    elif envelope.event in {"granted", "revoked"}:
        from .access import can_create_machine
        sender = grant.revoked_by if envelope.event == "revoked" else grant.granted_by
        if sender is None or not can_create_machine(sender, envelope.makerspace_id, grant.certification_type.machine_type):
            return False
    if envelope.audience == "requester":
        return envelope.recipient_id == grant.membership.user_id
    return staff_allowed(envelope, grant.certification_type.machine_type_id)


@safe_adapter
def notify(grant, event, *, include_staff=True):
    certification, space = grant.certification_type, grant.certification_type.makerspace
    expiry = to_local(space, grant.expires_at).isoformat() if grant.expires_at else ""
    context = {"makerspace": bag(name=space.name), "event_name": event,
               "subject": bag(id=grant.pk, name=certification.name[:160], expires_at=expiry)}
    staff = render(space, "certifications", "staff", event, context)
    if event in {"expiring", "expired"}:
        own = content(render(space, "certifications", "requester", event, context))
    else:
        own = {"subject": f"Certification {event}",
               "text": f"Your certification {certification.name[:160]}: {event}. Expiry: {expiry}."}
    own["link"] = f"/m/{space.slug}/member"
    return fanout(space=space, feature="certifications", stream="certifications",
        event=event, kind=KIND, source=grant.pk, version=version(grant), subject=grant,
        owner=grant.membership.user, own=own, staff=content(staff) if include_staff else None,
        scope=NotificationScope(machine_type=certification.machine_type_id),
        context={"certification_grant_id": grant.pk})


def eligible_digest(envelope):
    from .reminders_certification_digest import counts
    source = rbac.scope_notification_policy(CertificationType.objects.all(),
        makerspace_id=envelope.makerspace_id).filter(pk=envelope.source_id, is_active=True).first()
    if source is None or source.machine_type_id != envelope.scope.get("machine_type_id"):
        return False
    if envelope.context.get("day") != to_local(envelope.makerspace, timezone.now()).date().isoformat():
        return False
    type_id = envelope.scope.get("machine_type_id")
    return envelope.audience == "staff" and counts(envelope.makerspace, type_id, timezone.now()) > 0 and staff_allowed(envelope, type_id)


@safe_adapter
def notify_digest(space, reminder, message):
    type_id, day = reminder.subject.split(":", 1)
    certification = rbac.scope_notification_policy(CertificationType.objects.all(),
        makerspace_id=space.pk).filter(machine_type_id=int(type_id), is_active=True).order_by("pk").first()
    if certification is None:
        return None
    return fanout(space=space, feature="certifications", stream="certifications", event="expiring",
        kind=DIGEST, source=certification.pk, version=revision(type_id, day), subject=certification,
        staff={"subject": message.title, "text": message.body}, scope=NotificationScope(machine_type=int(type_id)),
        context={"day": day})


def register():
    register_source(KIND, NotificationSource(eligible))
    register_source(DIGEST, NotificationSource(eligible_digest, render_digest))


def render_digest(envelope):
    from .reminders_certification_digest import counts
    count = counts(envelope.makerspace, envelope.scope["machine_type_id"], timezone.now())
    return {"subject": "Expiring certifications",
            "text": f"{count} certification(s) expire soon; review and renew training."}
