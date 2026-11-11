"""Managed-platform fair-use limits; deliberately dormant on self-hosts."""

from django.utils.translation import gettext
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.staff_identity import person_q
from apps.makerspaces.limits_core import RESOURCE_LABELS


def custom_domain_allowed(makerspace) -> bool:
    from apps.makerspaces import domain_verification

    if domain_verification.is_self_host():
        return True
    from apps.managed_hosting.hosting_type import is_hosted

    if not is_hosted(makerspace):
        return True  # decision 236: an own space is never limited
    return bool((makerspace.resource_limit_overrides or {}).get("custom_domain"))


def _products(makerspace) -> int:
    from apps.inventory.models import InventoryProduct

    return InventoryProduct.objects.filter(
        makerspace=makerspace, is_archived=False
    ).count()


def _assets(makerspace) -> int:
    from apps.inventory.models import InventoryAsset

    return InventoryAsset.objects.filter(
        makerspace=makerspace, product__is_archived=False
    ).count()


def _machines(makerspace) -> int:
    from apps.machines.models import Machine

    return Machine.objects.filter(makerspace=makerspace, is_active=True).count()


def _events(makerspace) -> int:
    from apps.events.models import Event

    now = datetime.now(UTC)
    return Event.objects.filter(
        makerspace=makerspace,
        status=Event.Status.PUBLISHED,
        ends_at__gte=now,
    ).count()


def _staff(makerspace) -> int:
    from apps.accounts.models import User
    from apps.makerspaces.models import MakerspaceMembership

    # Staff quota counts staff-TRACK rows on people (one account per person).
    return MakerspaceMembership.staff_tracks.filter(
        person_q("user__"),
        makerspace=makerspace,
        user__is_active=True,
        user__access_status=User.AccessStatus.ACTIVE,
    ).count()


def _members(makerspace) -> int:
    from apps.accounts.models import User
    from apps.makerspaces.models import MakerspaceMembership

    return MakerspaceMembership.objects.filter(
        person_q("user__"), makerspace=makerspace, status="active", user__is_active=True,
        user__access_status=User.AccessStatus.ACTIVE,
    ).count()


def _bookings(makerspace) -> int:
    from apps.bookings.models import Booking

    return Booking.objects.filter(
        space__makerspace=makerspace,
        status__in=(Booking.Status.PENDING, Booking.Status.CONFIRMED),
        ends_at__gt=timezone.now(),
    ).count()


def _api_clients(makerspace) -> int:
    from apps.apiclients.models import ApiClient

    return ApiClient.objects.filter(makerspace=makerspace, is_active=True).count()


def _data_exports(makerspace) -> int:
    from apps.data_export.models import DataExportJob

    return DataExportJob.objects.filter(
        makerspace=makerspace,
        status__in=(DataExportJob.Status.PENDING, DataExportJob.Status.RUNNING),
    ).count()


def _print_requests(makerspace) -> int:
    now = datetime.now(UTC)
    month_start = datetime(now.year, now.month, 1, tzinfo=UTC)
    if now.month == 12:
        next_month = datetime(now.year + 1, 1, 1, tzinfo=UTC)
    else:
        next_month = datetime(now.year, now.month + 1, 1, tzinfo=UTC)
    from apps.machines.models import MachineServiceRequest
    from apps.machines.printer_capabilities import resolve_global_printer_type

    # A tenant can reuse the built-in slug for a generic type. Only the global
    # printer type owns the print allowance, matching the public printer surface.
    printer_type = resolve_global_printer_type()
    if printer_type is None:
        return 0

    return MachineServiceRequest.objects.filter(
        makerspace=makerspace,
        queue__machine_type=printer_type,
        created_at__gte=month_start,
        created_at__lt=next_month,
    ).count()


def _guest_passes(makerspace) -> int:
    """Passes issued today (UTC), revoked ones included so revoke-and-reissue cannot dodge the cap."""
    from apps.makerspaces.models import GuestPass

    now = datetime.now(UTC)
    day_start = datetime(now.year, now.month, now.day, tzinfo=UTC)
    return GuestPass.objects.filter(
        makerspace=makerspace, created_at__gte=day_start, created_at__lt=day_start + timedelta(days=1),
    ).count()


def _machine_service_open(makerspace) -> int:
    from apps.machines.models import MachineServiceRequest

    return MachineServiceRequest.objects.filter(
        makerspace=makerspace,
        status__in=(
            MachineServiceRequest.Status.PENDING,
            MachineServiceRequest.Status.ACCEPTED,
            MachineServiceRequest.Status.IN_PROGRESS,
        ),
    ).count()


def _machine_service_submit(makerspace) -> int:
    from apps.machines.models import MachineServiceRequest

    now = datetime.now(UTC)
    day_start = datetime(now.year, now.month, now.day, tzinfo=UTC)
    return MachineServiceRequest.objects.filter(
        makerspace=makerspace,
        created_at__gte=day_start,
        created_at__lt=day_start + timedelta(days=1),
    ).count()


def _storage(makerspace) -> int:
    from .website_asset_journal import pending_bytes
    from .storage_events_programme import accounted_bytes
    # Dedicated event pools count toward provider usage but not the ordinary tenant
    # entitlement; pending page-asset deletions still hold their bytes until cleaned.
    return max(0, makerspace.storage_bytes_used - accounted_bytes(makerspace)) + pending_bytes(makerspace.pk)


def add_storage(makerspace, size_bytes) -> None:
    """Charge managed object storage; raise when over the storage cap.

    Opens its own ``transaction.atomic()`` so the ``select_for_update`` row lock
    works at every finalize call site regardless of whether the caller already
    holds a transaction (it degrades to a savepoint when nested). Owner rule 261: bytes are
    counted for EVERY space (own, self-host, hosted) so a storage limit the superadmin sets later
    can be enforced; an unlimited space is counted but never refused.
    """
    from apps.makerspaces import limits

    if not size_bytes:
        return
    limit = limits.resource_limit(makerspace, "storage")
    from django.db.models import F

    from apps.makerspaces.models import Makerspace

    # #261: bytes are counted for every space (own and unlimited ones too), so a later switch to
    # "hosted" or a new storage limit starts from the real figure (see limits_storage_backfill).
    with transaction.atomic():
        locked = Makerspace.objects.select_for_update().get(pk=makerspace.pk)
        if limit is not None and _storage(locked) + size_bytes > limit:
            raise serializers.ValidationError(
                {
                    "limit": gettext("You've reached the free storage limit for this space — ask the operator to raise it or self-host.")
                },
                code="limit_reached",
            )
        Makerspace.objects.filter(pk=makerspace.pk).update(
            storage_bytes_used=F("storage_bytes_used") + size_bytes
        )


def free_storage(makerspace, size_bytes) -> None:
    """Release managed object storage (never below zero); counted for every space (#261)."""
    if not size_bytes:
        return
    from apps.makerspaces.models import Makerspace
    from django.db.models import F, Value
    from django.db.models.functions import Greatest

    Makerspace.objects.filter(pk=makerspace.pk).update(
        storage_bytes_used=Greatest(F("storage_bytes_used") - size_bytes, Value(0))
    )


def _emails(makerspace) -> int:
    from apps.integrations.models import DailyEmailCounter

    today = datetime.now(UTC).date()
    return (
        DailyEmailCounter.objects.filter(makerspace=makerspace, day=today)
        .values_list("count", flat=True)
        .first()
        or 0
    )


_COUNTERS: dict[str, Callable[[object], int]] = {
    "products": _products,
    "assets": _assets,
    "machines": _machines,
    "events": _events,
    "bookings": _bookings,
    "staff": _staff,
    "members": _members,
    "api_clients": _api_clients,
    "print": _print_requests,
    "machine_service_open": _machine_service_open,
    "machine_service_submit": _machine_service_submit,
    "data_exports": _data_exports,
    "guest_passes": _guest_passes,
    "storage": _storage,
    "email": _emails,
}


from apps.makerspaces.limits_check import check_quota  # noqa: E402,F401  (split out at the 300-line ceiling)
