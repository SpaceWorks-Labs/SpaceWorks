"""Boundary validation shared by generic and typed manual usage."""

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User


def validate_attribution(machine, member=None, started_at=None):
    if member is not None:
        member_id = getattr(member, "pk", member)
        member = User.objects.filter(
            pk=member_id, is_active=True, access_status="active",
            makerspace_memberships__makerspace_id=machine.makerspace_id,
            makerspace_memberships__status="active",
        ).first()
        if member is None:
            raise ValidationError({"member": "Choose an active member of this makerspace."})
    if started_at is not None and (timezone.is_naive(started_at) or started_at > timezone.now()):
        raise ValidationError({"started_at": "Enter a past time including its timezone."})
    return member
