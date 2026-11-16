"""checkout.kiosk: a device is only a terminal for the EXISTING self-checkout workflow; it bypasses nothing.

A member authenticates at the device (NFC tag, member number + PIN, or member-card QR + PIN: the same resolver,
lockout and attempt budgets as ``access.authorize``; a card QR alone, or a public card check link, opens nothing).
That opens a short-lived member session bound to THAT device, binding and
device key (a cache entry with a hard five-minute expiry: if the cache is lost the session simply ends and the
member authenticates again, so it fails closed). Every step then delegates to ``hardware_requests``:

* ``scan``     -> the same eligibility rules as the public scanner (`_qr_checkout_eligible`, active-loan check);
* ``evidence`` -> the normal presigned STAGING upload (the final object key is never client-writable);
* ``issue``    -> ``self_checkout_workflow.checkout_tool`` (authenticated member, eligible tool, issue evidence,
                  borrow limits, the lapsed-term and guest-pass rules, audit, charges);
* ``return``   -> ``self_checkout_workflow.return_tool`` (return photo AND remark, same-requester rule, audit).

This module adds no rule of its own and never touches ``Loan``/``Request`` rows; it cannot issue or return a tool
without the evidence the workflow demands.
"""
import secrets

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.devices.adapter_access import adapter_device, binding_for, require_adapters
from apps.devices.adapters.caps.checkout_kiosk import EVIDENCE, ISSUE, RETURN, SCAN, SESSION_START
from apps.devices.services_adapter_access import log_decision, resolve_member
from apps.devices.services_adapter_core import AdapterError, audit_adapter, check

KIOSK_SWITCH = "machines.integrations.kiosk"
SESSION_SECONDS = 300
KEY = "adapter-kiosk:{}"


def _refusal(exc):
    """Workflow refusals as typed adapter codes (the message is the workflow's own, never a secret)."""
    from apps.hardware_requests import workflow_errors as errs
    mapping = ((errs.InvalidTransition, "tool_state_conflict", 409), (errs.RequesterBlocked, "requester_blocked", 403),
               (errs.DepositRequired, "deposit_required", 409), (errs.EvidenceNotUploaded, "evidence_not_uploaded", 400),
               (errs.RequestValidationError, "checkout_refused", 400), (errs.ReturnValidationError, "return_refused", 400))
    for kind, code, status in mapping:
        if isinstance(exc, kind):
            return AdapterError(code, str(exc)[:200], status_code=status)
    return None


def _space(makerspace_id):
    from apps.makerspaces.guards import require_feature
    return require_feature(makerspace_id, "inventory.self_checkout")


def _denial_code(exc):
    """The workflow's own refusal code for the access log (e.g. ``member_account_required``)."""
    codes = exc.get_codes()
    if isinstance(codes, dict):
        codes = codes.get("code")
    return str(codes or "member_restricted")[:48]


def _admit(makerspace, member):
    """None when the member may use the kiosk, else the refusal; a savepoint keeps the caller's log write alive."""
    from rest_framework.exceptions import APIException

    from apps.accounts.account_kind_guards import require_member_account
    from apps.hardware_requests import guest_lending
    try:
        with transaction.atomic():
            require_member_account(member)
            guest_lending.admit_self_checkout(makerspace, member, taking=False)  # taking is re-checked at issue
    except APIException as exc:
        return exc
    return None


def start(principal, body):
    """Authenticate a member at the device; returns a session id valid for five minutes (or a typed denial).

    Every attempt is logged, including a member the workflow refuses (L-A7): that refusal is raised only AFTER the
    access-log and audit rows are committed, so it can no longer roll them back.
    """
    check(SESSION_START, body, label="kiosk session")
    now = timezone.now()
    refused = None
    with transaction.atomic():
        device = adapter_device(principal, lock=True)
        binding = binding_for(device, body["binding_id"], "checkout.kiosk")
        makerspace = _space(device.makerspace_id)
        member, reason = resolve_member(device.makerspace, body["credential"], now, binding=binding)
        if member is not None:
            refused = _admit(makerspace, member)
            reason = _denial_code(refused) if refused is not None else "ok"
        log_decision(device, binding, body["credential"]["type"], member, reason, now)
        if member is None:
            return {"allowed": False, "decision": "denied", "reason": reason}
        if refused is None:
            sid = secrets.token_hex(16)
            cache.set(KEY.format(sid), {
                "device_id": str(device.pk), "key_version": device.key_version, "binding_id": str(binding.pk),
                "makerspace_id": device.makerspace_id, "user_id": member.pk}, SESSION_SECONDS)
            audit_adapter(device.makerspace, device, "devices.adapter_kiosk_started",
                          meta={"binding_id": str(binding.pk), "member_id": member.pk})
    if refused is not None:
        raise refused
    return {"allowed": True, "decision": "allowed", "session_id": sid, "expires_in": SESSION_SECONDS,
            "member": {"display_name": member.display_name}}


def _session(principal, sid):
    """(device, member, makerspace) of a live session bound to THIS device and key, else 404 (expired or foreign)."""
    require_adapters(principal.makerspace_id, KIOSK_SWITCH)
    device = adapter_device(principal)
    data = cache.get(KEY.format(sid))
    if (not data or data["device_id"] != str(device.pk) or data["key_version"] != device.key_version
            or data["makerspace_id"] != device.makerspace_id):
        raise NotFound()
    from apps.accounts.models import User
    member = User.objects.filter(pk=data["user_id"], is_active=True, access_status="active").first()
    if member is None:
        cache.delete(KEY.format(sid))
        raise NotFound()
    return device, member, _space(device.makerspace_id)


def end(principal, sid):
    device, member, _space_row = _session(principal, sid)
    cache.delete(KEY.format(sid))
    audit_adapter(device.makerspace, device, "devices.adapter_kiosk_ended", meta={"member_id": member.pk})
    return {"ended": True}


def scan(principal, sid, body):
    """What may be done with a scanned tool: ``checkout``, ``return`` (this member's loan) or why not."""
    check(SCAN, body, label="kiosk scan")
    from apps.boxes.access import inventory_qr_codes
    from apps.boxes.api_views_eligibility import _qr_checkout_eligible
    from apps.boxes.models import QrCode
    from apps.boxes.qr_lookup import scanned_q
    from apps.hardware_requests.models import PublicToolLoan
    device, member, makerspace = _session(principal, sid)
    qr = inventory_qr_codes(QrCode.objects.all()).filter(
        scanned_q(body["qr_payload"]), makerspace=makerspace, status=QrCode.Status.ACTIVE).first()
    if qr is None:
        return {"action": "unknown"}
    loan = PublicToolLoan.objects.filter(makerspace=makerspace, status=PublicToolLoan.Status.CHECKED_OUT).filter(
        Q(qr_code=qr) | Q(qr_ids__contains=[qr.id])).first()
    if loan is not None:
        mine = loan.requester_id == member.pk
        return {"action": "return" if mine else "checked_out_by_other", "indicated": mine and _indicate(makerspace, qr)}
    eligible = _qr_checkout_eligible(qr, require_public=True)
    return {"action": "checkout" if eligible else "ineligible", "indicated": eligible and _indicate(makerspace, qr)}


def _indicate(makerspace, qr):
    """Queue ``locate.indicate`` on a bound pointer with a calibrated pose for the scanned tool. Fail-safe, staff data
    (poses, locations) stays on the server: the kiosk is only told whether a shelf was lit."""
    import logging
    from apps.boxes.models import QrCode
    from apps.devices.models import AdapterPose
    from apps.inventory.models import InventoryAsset, InventoryProduct
    try:
        keys = []
        if qr.target_type == QrCode.TargetType.BOX:
            keys.append(("box", str(qr.target_id)))
        else:
            product_id = qr.target_id
            if qr.target_type == QrCode.TargetType.ASSET:
                product_id = InventoryAsset.objects.filter(pk=qr.target_id, makerspace=makerspace).values_list(
                    "product_id", flat=True).first()
            product = InventoryProduct.objects.filter(pk=product_id, makerspace=makerspace).first()
            if product is not None:
                keys.append(("item", str(product.pk)))
                if product.storage_location:
                    keys.append(("storage_location", product.storage_location))
        for target_type, target_id in keys:
            pose = AdapterPose.objects.select_related("binding__device").filter(
                makerspace=makerspace, target_type=target_type, target_id=target_id, binding__enabled=True,
                binding__device__status="active", binding__capabilities__contains=["locate.indicate"]).first()
            if pose is None:
                continue
            from apps.devices.services_shelf_pointer import point_at
            point_at(makerspace, pose, actor=None, duration_seconds=15, action="devices.adapter_indicated")
            return True
    except Exception:  # noqa: BLE001 - lighting a shelf must never fail a checkout step
        logging.getLogger(__name__).warning("kiosk indicate failed", exc_info=True)
    return False


def evidence(principal, sid, body):
    """A presigned STAGING upload for the photo. The device PUTs the bytes itself, then sends ``evidence_id``."""
    check(EVIDENCE, body, label="kiosk evidence")
    from apps.hardware_requests import guest_lending
    from apps.hardware_requests import self_checkout_contact as contact_flow
    device, member, makerspace = _session(principal, sid)
    if body["content_type"] not in settings.EVIDENCE_ALLOWED_MIME:  # a typed 400, like artifacts (errors.md)
        raise AdapterError("content_type_not_allowed", "That content type is not allowed for evidence photos.")
    cap = settings.EVIDENCE_MAX_BYTES  # the presign's own content-length range; refuse early, not at the PUT
    if body.get("size_bytes", 0) > cap:
        raise AdapterError("artifact_too_large", "The photo is larger than this deployment allows.", status_code=413,
                           max_bytes=cap)
    guest_lending.admit_self_checkout(makerspace, member, taking=body["evidence_type"] == "issue")
    response = contact_flow.issue_upload(makerspace, body, uploader=member, actor=member)
    if response.status_code != 201:
        raise AdapterError("storage_unavailable", "Evidence storage is unavailable; retry.", status_code=503)
    return dict(response.data)


def _loan_view(loan):
    return {"status": loan.status, "public_token": str(loan.request.public_token)}


def issue(principal, sid, body):
    check(ISSUE, body, label="kiosk issue")
    from apps.hardware_requests import guest_lending, self_checkout_workflow
    device, member, makerspace = _session(principal, sid)
    guest_lending.admit_self_checkout(makerspace, member, taking=True)
    try:
        loan = self_checkout_workflow.checkout_tool(
            makerspace, member, body["qr_payload"], evidence_id=body["evidence_id"], remark="", kit_checklist=[])
    except Exception as exc:  # noqa: BLE001 - typed below; anything else keeps its own handler
        typed = _refusal(exc)
        if typed is None:
            raise
        raise typed from exc
    return _loan_view(loan)


def return_(principal, sid, body):
    check(RETURN, body, label="kiosk return")
    from apps.hardware_requests import self_checkout_workflow
    device, member, makerspace = _session(principal, sid)
    try:
        loan = self_checkout_workflow.return_tool(
            makerspace, member, body["qr_payload"], evidence_id=body["evidence_id"], remark=body["remark"],
            report_problem=False, problem_note="", kit_checklist=[])
    except Exception as exc:  # noqa: BLE001
        typed = _refusal(exc)
        if typed is None:
            raise
        raise typed from exc
    return _loan_view(loan)
