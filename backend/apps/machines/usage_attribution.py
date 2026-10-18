"""Boundary validation shared by generic and typed manual usage."""

from datetime import datetime

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User


def validate_attribution(machine, member=None, started_at=None):
    if member is not None:
        member_id = member.pk if isinstance(member, User) else member
        if type(member_id) is not int or member_id <= 0:
            raise ValidationError({"member": "Choose an active member of this makerspace."})
        member = User.objects.select_for_update(of=("self",), no_key=True).filter(
            pk=member_id, account_kind=User.AccountKind.MEMBER,
            is_active=True, access_status="active", is_tenant_dump_stub=False,
            retired_at__isnull=True, deletion_requested_at__isnull=True,
            account_purged_at__isnull=True,
            makerspace_memberships__makerspace_id=machine.makerspace_id,
            makerspace_memberships__status="active",
        ).first()
        if member is None:
            raise ValidationError({"member": "Choose an active member of this makerspace."})
    if started_at is not None and (not isinstance(started_at, datetime)
            or timezone.is_naive(started_at) or started_at > timezone.now()):
        raise ValidationError({"started_at": "Enter a past time including its timezone."})
    return member
