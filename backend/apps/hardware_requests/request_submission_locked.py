"""Pending-request creation under the caller's tenant and borrower locks."""
from django.db import connection
from django.utils.translation import gettext

from apps.accounts.account_kind_guards import require_member_account
from apps.audit import services as audit
from apps.hardware_requests import notifications
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem
from apps.hardware_requests.workflow_errors import RequestValidationError
from apps.inventory import availability
from apps.makerspaces.guards import require_feature
from apps.notifications.emit import emit_notification


def submit_locked(makerspace, items, requested_for, *, requester_principal, contact_snapshot,
                  audit_actor, account_less_marker, contact_key, pickup_from, pickup_until,
                  waitlist_entry_id):
    """Caller owns source/PII fences, maker and obligation-owner locks until commit."""
    if not connection.in_atomic_block:
        raise RuntimeError("Pending request requires the caller's atomic transaction")
    require_member_account(requester_principal)
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
