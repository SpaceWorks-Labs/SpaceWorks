"""Core owner identity and tenant-row checks, independent of the optional inbox."""
from django.apps import apps
from django.db.models import Q

from apps.accounts import rbac
from apps.accounts.models import User
from apps.makerspaces.models import MakerspaceMembership


def owner_accounts():
    return User.objects.filter(is_active=True, access_status=User.AccessStatus.ACTIVE,
                               is_tenant_dump_stub=False, deletion_requested_at__isnull=True)


def owner_membership(makerspace, user_id):
    return rbac.scope_notification_policy(MakerspaceMembership.objects.all(),
        makerspace_id=makerspace.pk).filter(user_id=user_id).first()


def eligible_owner(makerspace, user_id):
    """Preserve inbox admission, including membership notification opt-out."""
    if not user_id or not owner_accounts().filter(pk=user_id).exists():
        return False
    membership = owner_membership(makerspace, user_id)
    return membership is None or (membership.status == "active" and membership.receives_notifications)


def owns_tenant_row(makerspace, user_id):
    # Existing rows count even after completion; free-text contact fields never do.
    owners = (
        ("hardware_requests.HardwareRequest", "makerspace_id", Q(requester_id=user_id)),
        ("hardware_requests.PublicToolLoan", "makerspace_id", Q(requester_id=user_id)),
        ("bookings.Booking", "space__makerspace_id", Q(member_id=user_id)),
        ("events.EventRegistration", "event__makerspace_id", Q(member_id=user_id)),
        ("machines.MachineServiceRequest", "makerspace_id",
         Q(member_id=user_id) | Q(member__isnull=True, requester_id=user_id)),
        ("payments.Payment", "makerspace_id", Q(member_id=user_id)),
    )
    for label, tenant_field, owner in owners:
        try:
            model = apps.get_model(label)
        except LookupError:
            continue
        if rbac.scope_notification_policy(model.objects.all(), makerspace_id=makerspace.pk,
                                         field=tenant_field).filter(owner).exists():
            return True
    return False
