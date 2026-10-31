"""Report notices disclose navigation only and recheck the report's own action."""
from django.utils import timezone

from apps.accounts import rbac
from apps.accounts.rbac_roles import additional_roles_prefetch, membership_roles
from apps.admin_api.permissions import active_user
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.makerspaces.models import MakerspaceMembership
from .models_report_schedules import ReportDelivery
from .notifications_p2 import body, fanout, revision, safe_notification, scoped, staff_link
from .report_registry import REPORT_REGISTRY

SOURCE = "operations.report_ready"


def recipients(schedule, definition):
    """Only role/action selectors establish personal recipients, never raw email."""
    # Report recipients are chosen by staff role/action: staff-track rows (U-A1).
    rows = rbac.scope_notification_policy(
        MakerspaceMembership.staff_tracks.all(), makerspace_id=schedule.makerspace_id,
    ).select_related(
        "user", "assigned_role",
    ).prefetch_related(additional_roles_prefetch()).filter(status="active", receives_notifications=True)
    for member in rows:
        user = member.user
        if not active_user(user) or not rbac.can(user, definition.required_action, schedule.makerspace_id):
            continue
        selected = any(role.slug in schedule.recipient_roles for role in membership_roles(member))
        if member.assigned_role_id is None and schedule.recipient_roles:
            from apps.makerspaces.models import MakerspaceRole
            selected = scoped(MakerspaceRole, schedule.makerspace_id).filter(
                legacy_role=member.role, slug__in=schedule.recipient_roles,
            ).exists()
        if selected or any(rbac.can(user, action, schedule.makerspace_id) for action in schedule.recipient_actions):
            yield user


def source_revision(delivery):
    return revision(delivery.pk, delivery.created_at, delivery.schedule.updated_at)


def load(envelope):
    return scoped(ReportDelivery, envelope.makerspace_id, field="schedule__makerspace_id").select_related(
        "schedule__makerspace", "schedule__created_by",
    ).filter(pk=envelope.source_id).first()


def eligible(envelope):
    from .report_schedule_services import _skip_reason
    delivery = load(envelope)
    if delivery is None or envelope.event != "scheduled_report":
        return False
    schedule = delivery.schedule
    definition = REPORT_REGISTRY.get(schedule.report_key)
    return bool(delivery.object_key and delivery.expires_at and delivery.expires_at > timezone.now()
        and schedule.is_active and not _skip_reason(schedule, definition)
        and envelope.revision == source_revision(delivery)
        and envelope.recipient_id in {user.pk for user in recipients(schedule, definition)})


def content(delivery):
    definition = REPORT_REGISTRY[delivery.schedule.report_key]
    return body("Scheduled report ready", f"Scheduled report '{definition.title}' is ready. "
                "Sign in to the staff console to view the report.", staff_link(delivery.schedule.makerspace, "reports"))


def render(envelope):
    return content(load(envelope))


@safe_notification
def notify_report(delivery):
    definition = REPORT_REGISTRY.get(delivery.schedule.report_key)
    if definition is None:
        return
    for user in recipients(delivery.schedule, definition):
        # api_access is the existing ungated administrative category. The live
        # source above, not that category, grants report disclosure authority.
        fanout(row=delivery, space=delivery.schedule.makerspace, feature="api_access", stream="reports",
            event="scheduled_report", source_kind=SOURCE, revision=source_revision(delivery),
            owner=user, owner_body=content(delivery), staff=False)


def emailed_by_envelope(delivery, definition):
    """Addresses whose personal report envelope resolves an email leg."""
    from apps.integrations.models_contract import NotificationEnvelope
    from apps.integrations.notification_resolution import resolve
    from .notifications_p2 import identity
    space = delivery.schedule.makerspace
    key = identity(space.pk, SOURCE, delivery.pk, source_revision(delivery), "scheduled_report")
    found = set()
    for user in recipients(delivery.schedule, definition):
        envelope = NotificationEnvelope.objects.filter(dedup_key=f"p2:{key}:u:{user.pk}").first()
        if user.email and envelope and any(target.channel == "email" for target in resolve(envelope)):
            found.add(user.email.strip().casefold())
    return found


def register():
    register_source(SOURCE, NotificationSource(eligible, render))
