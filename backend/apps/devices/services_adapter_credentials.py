"""NFC and PIN credentials for adapter access: digests only, tenant-scoped, one live credential per kind and member.

A PIN cannot identify a person on its own, so an adapter sends the member number printed on the member card with
it; the digest is keyed per tenant AND user. Lockout (5 wrong PINs lock the credential for 15 minutes) and the
per-binding and per-space attempt budgets live in ``services_adapter_pin``. Setting a new secret for a kind
retires the previous one (rotation).
"""
import re

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.audit import services as audit
from apps.devices.adapter_access import ACCESS_SWITCH, authorize_staff
from apps.devices.models import AdapterCredential
from apps.devices.services_adapter_core import AdapterError, credential_digest
from apps.devices.services_locks import lock_tenant

PIN = re.compile(r"^[0-9]{6,12}$")
COMMON_PINS = frozenset({"123123", "121212", "112233", "123321", "654321", "696969", "159753", "147258", "520520",
                         "123654", "102030", "101010", "202020", "007007", "131313", "123456789", "987654321"})


def weak_pin(pin):
    """True for a PIN anyone would try first: one repeated digit, a straight run up or down, or a well-known one."""
    if len(set(pin)) == 1 or pin in COMMON_PINS:
        return True
    steps = {(int(b) - int(a)) % 10 for a, b in zip(pin, pin[1:])}
    return steps in ({1}, {9})


def set_credential(actor, makerspace_id, user_id, kind, secret, label=""):
    from apps.accounts.models import User
    from apps.makerspaces.models import MakerspaceMembership
    authorize_staff(actor, makerspace_id, child=ACCESS_SWITCH)
    # New PINs (decision 336j): 6 to 12 digits and not guessable. PINs set before 0.12.0 with 4 or 5 digits keep
    # working until the member's next PIN change; only setting a PIN is checked here.
    if kind == "pin" and not PIN.match(secret):
        raise AdapterError("invalid_pin", "A PIN is 6 to 12 digits.")
    if kind == "pin" and weak_pin(secret):
        raise AdapterError("weak_pin", "That PIN is too easy to guess; choose another.")
    member = User.objects.filter(pk=user_id, is_active=True).first()
    if member is None or not MakerspaceMembership.objects.filter(
            makerspace_id=makerspace_id, user=member, status="active").exists():
        raise NotFound()
    digest = credential_digest(makerspace_id, kind, secret, user_id=member.pk if kind == "pin" else None)
    try:
        with transaction.atomic():
            makerspace = lock_tenant(makerspace_id)
            now = timezone.now()
            AdapterCredential.objects.filter(makerspace=makerspace, user=member, kind=kind,
                                             disabled_at__isnull=True).update(disabled_at=now)
            row = AdapterCredential.objects.create(makerspace=makerspace, user=member, kind=kind, digest=digest,
                                                   label=label, created_by=actor)
            audit.record(actor, "devices.adapter_credential_set", makerspace=makerspace, target=member, meta={
                "member_id": member.pk, "kind": kind, "credential_id": str(row.pk)})
    except IntegrityError as exc:
        raise AdapterError("credential_in_use", "That credential is already assigned.", status_code=409) from exc
    return row


def disable_credential(actor, credential_id):
    from apps.accounts import rbac
    row = rbac.scope_by_action(actor, rbac.Action.MANAGE_DEVICES, AdapterCredential.objects.all()).filter(
        pk=credential_id).first()
    if row is None:
        raise NotFound()
    authorize_staff(actor, row.makerspace_id, child=ACCESS_SWITCH)
    with transaction.atomic():
        makerspace = lock_tenant(row.makerspace_id)
        AdapterCredential.objects.filter(pk=row.pk, disabled_at__isnull=True).update(disabled_at=timezone.now())
        audit.record(actor, "devices.adapter_credential_removed", makerspace=makerspace, target=row.user, meta={
            "member_id": row.user_id, "kind": row.kind, "credential_id": str(row.pk)})
    row.refresh_from_db()
    return row


def list_credentials(actor, makerspace_id, user_id=None):
    authorize_staff(actor, makerspace_id, child=ACCESS_SWITCH)
    rows = AdapterCredential.objects.filter(makerspace_id=makerspace_id).order_by("-created_at")
    return rows.filter(user_id=user_id) if user_id else rows[:200]
