"""Machine-access notices: granted, revoked, expiring soon (decision 319), to the member only.

Sent through the notification catalogue (Celery, translated, preferences respected). The catalogue
family key stays `certifications` for data stability (stored member preferences and templates); its
events are the machine-access ones now. Staff already made the decision and the audit row records it.
"""
from datetime import timedelta

from django.utils import timezone
from django.utils.translation import gettext, gettext_noop

from apps.hardware_requests.notifications_p2 import content, fanout, revision, safe_adapter
from apps.integrations.destinations import NotificationScope
from apps.integrations.email_templates import render
from apps.integrations.email_templates_registry_helpers import bag
from apps.integrations.notification_links import local_link
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.makerspaces.local_time import to_local

KIND = "machines.access_grant"
WORDS = {"granted": gettext_noop("granted"), "revoked": gettext_noop("revoked")}
EXPIRY_WARNING_DAYS = 7


def version(grant):
    return revision(grant.granted_at, grant.expires_at, grant.revoked_at, grant.member_id)


def label(grant):
    return (grant.machine.name if grant.machine_id else grant.machine_type.name)[:160]


def eligible(envelope):
    from apps.accounts import rbac

    from .models import MachineAccessGrant
    rows = rbac.scope_notification_policy(MachineAccessGrant.objects.all(), makerspace_id=envelope.makerspace_id,
                                          field="makerspace_id")
    grant = rows.select_related("machine", "machine_type").filter(
        pk=envelope.source_id, member_id=envelope.recipient_id).first()
    if grant is None or envelope.audience != "requester" or version(grant) != envelope.revision:
        return False
    if (grant.revoked_at is not None) != (envelope.event == "revoked"):
        return False
    return envelope.event != "expiring" or (grant.expires_at is not None and grant.expires_at > timezone.now())


@safe_adapter
def notify_access(grant, event):
    space = grant.makerspace
    expiry = to_local(space, grant.expires_at).isoformat() if grant.expires_at else ""
    context = {"makerspace": bag(name=space.name), "event_name": event,
               "subject": bag(id=grant.pk, name=label(grant), expires_at=expiry)}
    if event == "expiring":
        own = content(render(space, "certifications", "requester", event, context))
    else:
        what = gettext(WORDS[event])
        own = {"subject": gettext("Machine access %(what)s") % {"what": what},
               "text": gettext("Your access to %(name)s was %(what)s. Expiry: %(expiry)s.") % {
                   "name": label(grant), "what": what, "expiry": expiry or gettext("none")}}
    own["link"] = local_link(space, "member")
    scope = NotificationScope(machine=grant.machine_id) if grant.machine_id else NotificationScope(
        machine_type=grant.machine_type_id)
    return fanout(space=space, feature="certifications", stream="certifications", event=event, kind=KIND,
                  source=grant.pk, version=version(grant), subject=grant, owner=grant.member, own=own, staff=None,
                  scope=scope, context={"machine_access_grant_id": grant.pk})


def notify_expiring(now=None):
    """Tell each member whose live grant ends within a week, once per grant (`expiry_notice_sent_at`).

    Runs deployment-wide from the session sweep, so each grant enters its own space's tenant boundary (NCA audit
    0.12.0): a frozen, paused or migrating space is skipped and its notices wait for the next run."""
    from apps.accounts import rbac
    from apps.makerspaces.scheduled_scope import live_space_ids
    from apps.tenant_migration.gate_runtime import fanout_tenant_write

    from .models import MachineAccessGrant
    moment = now or timezone.now()
    # Archived/inactive spaces and spaces with machines switched off send nothing (L-M1).
    rows = rbac.scope_for_scheduled_work(MachineAccessGrant.objects.all()).filter(
        makerspace_id__in=live_space_ids("machines"))
    due = rows.select_related("makerspace", "machine", "machine_type", "member").filter(
        revoked_at__isnull=True, expiry_notice_sent_at__isnull=True, expires_at__gt=moment,
        expires_at__lte=moment + timedelta(days=EXPIRY_WARNING_DAYS)).order_by("makerspace_id", "pk")[:200]
    counts, sent = {"skipped": 0}, 0
    for grant in due:
        with fanout_tenant_write(grant.makerspace_id, operation="machine_access_expiry", counts=counts) as go:
            if not go:
                continue
            # Claim BEFORE sending: two overlapping sweeps can never both win the row, so a member is
            # told once (the notice itself is queued after commit by the catalogue).
            if not MachineAccessGrant.objects.filter(pk=grant.pk, expiry_notice_sent_at__isnull=True).update(
                    expiry_notice_sent_at=moment):
                continue
            notify_access(grant, "expiring")
            sent += 1
    return sent


def register():
    register_source(KIND, NotificationSource(eligible))
