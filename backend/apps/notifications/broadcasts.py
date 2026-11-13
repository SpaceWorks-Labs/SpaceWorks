"""Member communication passes current RBAC, segment, channel and personal gates."""

from django.utils.translation import gettext
from django.db import transaction
from django.db.models import Q, Exists, OuterRef
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts import rbac
from apps.audit import services as audit
from apps.makerspaces.models import MakerspaceMembership, MembershipPlan, MembershipTerm
from apps.makerspaces.platform import feature_enabled, module_enabled
from apps.notifications.models_broadcasts import MemberBroadcast


def segment_members(space, segment):
    now = timezone.now()
    rows = rbac.scope_notification_policy(MakerspaceMembership.objects.select_related('user'), makerspace_id=space.pk).filter(
        status='active', receives_notifications=True, user__is_active=True,
        user__access_status='active', user__is_tenant_dump_stub=False,
    )
    terms = rbac.scope_notification_policy(MembershipTerm.objects.all(), makerspace_id=space.pk,
                                          field='membership__makerspace_id')
    current = terms.filter(membership_id=OuterRef('pk'), starts_at__lte=now, ends_at__gt=now, status='active')
    if segment.get('plan_id'):
        if not rbac.scope_notification_policy(MembershipPlan.objects.all(), makerspace_id=space.pk).filter(pk=segment['plan_id']).exists():
            raise ValidationError({'plan_id': gettext('Unknown plan in this makerspace.')})
        # A lapsed-plan campaign addresses the expired plan's former members.
        # Requiring a current term here would make plan + lapsed always empty.
        plan_terms = terms.filter(membership_id=OuterRef('pk'), ends_at__lte=now) if segment.get('status') == 'lapsed' else current
        rows = rows.annotate(matches_plan=Exists(plan_terms.filter(plan_id=segment['plan_id']))).filter(matches_plan=True)
    if segment.get('status'):
        rows = rows.annotate(current_term=Exists(current))
        if segment['status'] == 'lapsed':
            rows = rows.annotate(has_term=Exists(terms.filter(membership_id=OuterRef('pk'), ends_at__lte=now))).filter(has_term=True, current_term=False)
        else:
            rows = rows.filter(current_term=True)
    if segment.get('machine_type_id'):  # decision 319: members who may use this machine type (a grant, not a certification)
        if not module_enabled(space, 'machines'):
            raise ValidationError({'machine_type_id': gettext('Machines are disabled.')})
        from apps.machines.models import MachineAccessGrant, MachineType
        kinds = MachineType.objects.filter(Q(makerspace_id=space.pk) | Q(makerspace__isnull=True))
        if not kinds.filter(pk=segment['machine_type_id']).exists():
            raise ValidationError({'machine_type_id': gettext('Unknown machine type in this makerspace.')})
        grants = rbac.scope_notification_policy(MachineAccessGrant.objects.all(), makerspace_id=space.pk,
                                               field='makerspace_id').filter(
            member_id=OuterRef('user_id'), revoked_at__isnull=True,
        ).filter(Q(machine_type_id=segment['machine_type_id']) | Q(machine__machine_type_id=segment['machine_type_id'])
                 ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        rows = rows.annotate(has_access=Exists(grants)).filter(has_access=True)
    return rows.order_by('pk')


@transaction.atomic
def send_broadcast(space, *, actor, title, body, **segment):
    from apps.makerspaces.guards import require_module_locked
    space = require_module_locked(space, 'membership')
    space = require_module_locked(space, 'notifications')
    if not rbac.can(actor, rbac.Action.MANAGE_MEMBERS, space):
        raise PermissionDenied()
    if not feature_enabled(space, 'membership.broadcasts'):
        from apps.makerspaces.guards import feature_off
        raise feature_off('membership.broadcasts', 'Member broadcasts are turned off.')
    # Explicit cap prevents one HTTP transaction from enqueueing an unbounded roster.
    ids = list(segment_members(space, segment).values_list('user_id', flat=True)[:2001])
    if len(ids) > 2000:
        raise ValidationError({'segment': gettext('Choose a segment of at most 2000 members.')})
    broadcast = MemberBroadcast.objects.create(makerspace=space, created_by=actor, title=title, body=body)
    audit.record(actor, 'notification.broadcast_created', makerspace=space, target=broadcast,
                 meta={'recipient_count': len(ids)})
    from apps.makerspaces.notifications_p2_broadcasts import notify_broadcast
    for user_id in ids:
        notify_broadcast(broadcast, user_id=user_id, segment=segment)
    return broadcast, len(ids)
