from django.utils.translation import gettext
from apps.accounts.account_kind_guards import require_member_account

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.accounts.account_obligations import lock_obligation_owner
from apps.hardware_requests import notifications
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem
from apps.hardware_requests.workflow_errors import (
    InvalidTransition,
    RequestValidationError,
    RequesterBlocked,
)
from apps.hardware_requests.workflow_utils import locked_request
from apps.inventory import availability
from apps.makerspaces.models import Makerspace
from apps.notifications.emit import emit_notification


@dataclass(frozen=True)
class RequesterSnapshot:
    """Identity captured on a request independently from its durable principal.

    The signed-in account's own details, or -- for an account-less request in a space
    without member accounts (#80) -- the name, phone and email the borrower typed, the
    email already proven by a one-time code. Either way `requester_contact_verified`
    keeps its default of True; rows from the retired unverified opt-in keep their False
    flag and the mail suppression it drives.
    """

    username: str
    name: str
    email: str
    phone: str


def submit_request(
    makerspace,
    items,
    requested_for="",
    *,
    requester_principal,
    contact_snapshot,
    audit_actor,
    account_less_marker="",
    contact_key="",
    pickup_from=None,
    pickup_until=None,
    waitlist_entry_id=None,
):
    require_member_account(requester_principal)
    with transaction.atomic():
        from apps.encryption.write_fence import assert_mapped_write_allowed
        from apps.tenant_migration.gate_runtime import assert_write_allowed

        assert_write_allowed(makerspace.id)
        assert_mapped_write_allowed(makerspace.id)
        makerspace = Makerspace.objects.select_for_update().get(pk=makerspace.pk)
        from apps.makerspaces.guards import require_feature

        requester_principal = lock_obligation_owner(requester_principal)
        require_feature(makerspace, "loans.enabled")
        if any(getattr(item["product"], "is_consumable", False) for item in items):
            raise RequestValidationError("Consumables are logged as used, not lent.")
        availability.enforce_submission_borrow_limits(makerspace, requester_principal, items,
                                                      contact_key=contact_key)
        from apps.hardware_requests.pickup_windows import validate_window
        pickup_from, pickup_until = validate_window(makerspace, pickup_from, pickup_until)
        entry = None
        if waitlist_entry_id is not None:
            from apps.hardware_requests import waitlist
            entry = waitlist.claim(waitlist_entry_id, requester_principal, items)
        request = HardwareRequest.objects.create(
            makerspace=makerspace,
            requester=requester_principal,
            requester_username=contact_snapshot.username,
            requester_name=contact_snapshot.name,
            requester_contact_email=contact_snapshot.email,
            requester_contact_phone=contact_snapshot.phone,
            # Non-empty marks an account-less row, which every owner/contact-mail path keys on.
            anonymous_idempotency_key_fingerprint=account_less_marker,
            # The confirmed-email fingerprint: the account-less person, for borrow limits.
            anonymous_payload_fingerprint=contact_key,
            status=HardwareRequest.Status.PENDING_APPROVAL,
            requested_for=requested_for,
            pickup_from=pickup_from,
            pickup_until=pickup_until,
        )
        HardwareRequestItem.objects.bulk_create(
            [
                HardwareRequestItem(
                    request=request,
                    product=item["product"],
                    requested_quantity=item["quantity"],
                )
                for item in items
            ]
        )
        audit.record(
            audit_actor,
            "request.submitted",
            makerspace=makerspace,
            target=request,
            meta={"account_less": bool(account_less_marker)},
        )
        if entry is not None:
            from apps.hardware_requests import waitlist
            waitlist.bind_claim(entry, request)
        notifications.notify_request_submitted(request)
        emit_notification(
            makerspace,
            level="info",
            event="request.submitted",
            title=gettext("New hardware request"),
            body=gettext('Hardware request #{pk} submitted.').format(pk=request.pk),
        )
        return request


def accept_request(actor, request, accepted=None):
    with transaction.atomic():
        locked = locked_request(request)
        if locked.status != HardwareRequest.Status.PENDING_APPROVAL:
            raise InvalidTransition(
                f"Cannot accept hardware request with status {locked.status}."
            )

        items = list(locked.items.select_related("product").order_by("product_id"))
        if accepted is not None:
            unknown = set(accepted) - {item.pk for item in items}
            if unknown:
                raise RequestValidationError(
                    "Accepted quantities reference items that are not in this request."
                )
        total = 0
        for item in items:
            # accepted is None => accept all (full). A provided map is authoritative:
            # an item not listed is declined (0), so an empty map accepts nothing.
            qty = (
                item.requested_quantity
                if accepted is None
                else int(accepted.get(item.pk, 0))
            )
            if qty < 0 or qty > item.requested_quantity:
                raise RequestValidationError(
                    "Accepted quantity must be between 0 and the requested quantity."
                )
            item.accepted_quantity = qty
            item.save(update_fields=["accepted_quantity"])
            total += qty

        if total == 0:
            raise RequestValidationError(
                "Accept at least one unit, or reject the request instead."
            )

        # A claimed waitlist offer's held units become this reservation in the same
        # transaction (release then reserve under the same product lock).
        from apps.hardware_requests import waitlist
        waitlist.convert_claim(locked)
        # reserve_for_request now runs the individual-asset guard under its own
        # product row lock, so the check and the reservation can't race apart.
        availability.reserve_for_request(locked)

        from apps.hardware_requests.pickup_windows import deadline_at_accept
        locked.status = HardwareRequest.Status.ACCEPTED
        locked.accepted_by = actor
        locked.accepted_at = timezone.now()
        locked.pickup_until = deadline_at_accept(locked, now=locked.accepted_at)
        locked.save(
            update_fields=["status", "accepted_by", "accepted_at", "pickup_until", "updated_at"]
        )
        audit.record(
            actor,
            "request.accepted",
            makerspace=locked.makerspace,
            target=locked,
            meta={"accepted": {item.pk: item.accepted_quantity for item in items}},
        )
        notifications.notify_request_accepted(locked)
        return locked


def reject_request(actor, request, reason):
    reason = str(reason or "").strip()
    if not reason:
        raise RequestValidationError("Rejection reason is required.")

    with transaction.atomic():
        locked = locked_request(request)
        if locked.status != HardwareRequest.Status.PENDING_APPROVAL:
            raise InvalidTransition(
                f"Cannot reject hardware request with status {locked.status}."
            )

        from apps.hardware_requests import waitlist
        waitlist.release_claim(locked)
        locked.status = HardwareRequest.Status.REJECTED
        locked.rejection_reason = reason
        locked.save(update_fields=["status", "rejection_reason", "updated_at"])
        audit.record(
            actor,
            "request.rejected",
            makerspace=locked.makerspace,
            target=locked,
            meta={"reason": reason},
        )
        notifications.notify_request_rejected(locked)
        return locked
