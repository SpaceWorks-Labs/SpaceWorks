from django.utils.translation import gettext
from django.apps import apps
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from apps.accounts import rbac
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.servability import servable_queryset
from apps.makerspaces.guards import require_module


def contract_space(user, makerspace_id, *, manager=False):
    space = get_object_or_404(rbac.scope_notification_policy(servable_queryset(), makerspace_id=makerspace_id, field="pk"))
    if (not user.is_active or user.access_status != "active" or user.is_tenant_dump_stub
            or rbac.personal_notification_membership_refused(user, space.pk)):
        raise PermissionDenied()
    if manager:
        if not rbac.is_space_manager_identity(user, space.pk):
            raise PermissionDenied(gettext("Channel settings require a Space Manager."))
        return space
    from .messaging.ties import has_tenant_tie
    if has_tenant_tie(user, space):
        return space
    if rbac.scope_by_makerspace(user, MakerspaceMembership.objects.all()).filter(
        makerspace=space, user=user, status="active",
    ).exists() or rbac.effective_actions(user, space.pk):
        return space
    # Explicit account-only domain owners retain personal delivery/settings access.
    for label, owner, tenant in (
        ("bookings.Booking", "member", "space__makerspace_id"),
        ("events.EventRegistration", "member", "event__makerspace_id"),
        ("payments.Payment", "member", "makerspace_id"),
        ("hardware_requests.HardwareRequest", "requester", "makerspace_id"),
        ("hardware_requests.PublicToolLoan", "requester", "makerspace_id"),
    ):
        model = apps.get_model(label)
        if rbac.scope_notification_policy(model.objects.all(), makerspace_id=space.pk, field=tenant).filter(**{owner: user}).exists():
            return space
    raise PermissionDenied()
