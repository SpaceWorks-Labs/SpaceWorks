"""Member certification notices and type-scoped staff notices."""
from django.utils import timezone
from django.utils.translation import gettext, gettext_noop

from apps.integrations.notification_links import local_link
from apps.accounts import rbac
from apps.hardware_requests.notifications_p2 import content, fanout, revision
from apps.integrations.destinations import NotificationScope
from apps.integrations.email_templates import render
from apps.integrations.email_templates_registry_helpers import bag
from apps.integrations.notification_catalog_sources import event_live
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.hardware_requests.notifications_p2 import safe_adapter
from apps.makerspaces.local_time import to_local
from .models import CertificationGrant, CertificationType

KIND = "machines.certification"
GUEST_KIND = "machines.guest_certification"
GRANT_WORDS = {"granted": gettext_noop("granted"), "revoked": gettext_noop("revoked")}
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
    reminder = envelope.event in {"expiring", "expired"}
    if reminder and not event_live(envelope.makerspace, "certifications", envelope.event):
        return False
    rows = rbac.scope_notification_policy(CertificationGrant.objects.all(),
        makerspace_id=envelope.makerspace_id, field="certification_type__makerspace_id")
    grant = rows.select_related("membership", "certification_type__machine_type", "granted_by", "revoked_by").filter(
        pk=envelope.source_id, membership__makerspace_id=envelope.makerspace_id,
        membership__status="active", membership__receives_notifications=True,
        certification_type__is_active=True).first()
    if grant is None or version(grant) != envelope.revision:
        return False
    if reminder:
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
        what = gettext(GRANT_WORDS.get(event, event))
        own = {"subject": gettext("Certification %(what)s") % {"what": what},
               "text": gettext("Your certification %(name)s: %(what)s. Expiry: %(expiry)s.") % {
                   "name": certification.name[:160], "what": what, "expiry": expiry}}
    own["link"] = local_link(space, "member")
    return fanout(space=space, feature="certifications", stream="certifications",
        event=event, kind=KIND, source=grant.pk, version=version(grant), subject=grant,
        owner=grant.membership.user, own=own, staff=content(staff) if include_staff else None,
        staff_context=context, scope=NotificationScope(machine_type=certification.machine_type_id),
        context={"certification_grant_id": grant.pk})


def eligible_digest(envelope):
    if not event_live(envelope.makerspace, "certifications", "expiring"):
        return False
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
        context={"day": day}, staff_context={"makerspace": bag(name=space.name),
            "event_name": "expiring", "subject": bag(id=certification.pk, name=certification.name[:160], expires_at="")})


def guest_version(grant):
    return revision(grant.granted_at, grant.expires_at, grant.revoked_at)


def eligible_guest(envelope):
    """A guest-pass holder's induction certificate: still theirs, same revision, in a live machines space."""
    from apps.makerspaces.platform import module_enabled

    from .models import GuestCertificationGrant
    grant = rbac.scope_notification_policy(GuestCertificationGrant.objects.all(),
        makerspace_id=envelope.makerspace_id).select_related("certification_type").filter(
        pk=envelope.source_id, user_id=envelope.recipient_id, certification_type__is_active=True).first()
    return bool(grant and envelope.audience == "requester" and guest_version(grant) == envelope.revision
                and (grant.revoked_at is not None) == (envelope.event == "revoked")
                and module_enabled(envelope.makerspace, "machines"))


@safe_adapter
def notify_guest(grant, event):
    """Decision 223 (d): a guest-pass holder certified after an induction (or revoked) hears it, like a member.

    Owner leg only: staff already made the decision and the audit row records it."""
    space, certification = grant.makerspace, grant.certification_type
    expiry = to_local(space, grant.expires_at).isoformat() if grant.expires_at else ""
    what = gettext(GRANT_WORDS[event])
    own = {"subject": gettext("Certification %(what)s") % {"what": what},
           "text": gettext("Your certification %(name)s: %(what)s. Expiry: %(expiry)s.") % {
               "name": certification.name[:160], "what": what, "expiry": expiry},
           "link": local_link(space, "member")}
    return fanout(space=space, feature="certifications", stream="certifications", event=event, kind=GUEST_KIND,
        source=grant.pk, version=guest_version(grant), subject=grant, owner=grant.user, own=own, staff=None,
        scope=NotificationScope(machine_type=certification.machine_type_id),
        context={"guest_certification_grant_id": grant.pk})


def register():
    register_source(KIND, NotificationSource(eligible))
    register_source(GUEST_KIND, NotificationSource(eligible_guest))
    register_source(DIGEST, NotificationSource(eligible_digest, render_digest))


def render_digest(envelope):
    from .reminders_certification_digest import counts
    count = counts(envelope.makerspace, envelope.scope["machine_type_id"], timezone.now())
    return {"subject": gettext("Expiring certifications"),
            "text": gettext("%(count)s certification(s) expire soon; review and renew training.") % {"count": count}}
