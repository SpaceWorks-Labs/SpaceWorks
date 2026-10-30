"""Only writer of event credential generations; cancellation adapters call revoke_locked."""

import hashlib
import json
from dataclasses import dataclass, field

from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.accounts.staff_identity import is_person
from apps.audit.services import record
from apps.events.checkin_policy import window_for
from apps.events.event_permissions import CHECK_IN
from apps.events.models_registration import EventRegistration

from .boundary import advance, event_command, require_version
from .crypto import prepare, unwrap
from .errors import ProgrammeConflict
from .models import EventCredentialCommand, EventRegistrationCredential
from .scopes import registrations
from apps.encryption.account_write_fence import assert_account_fence_held
from apps.transaction_guards import in_domain_transaction

ELIGIBLE = ("registered", "attended")


def require_eligible(event, registration):
    member = registration.member
    if (registration.event_id != event.pk or event.status not in ("published", "completed")
            or registration.status not in ELIGIBLE or not member
            or not is_person(member) or not member.is_active
            or member.access_status != "active" or member.is_tenant_dump_stub or member.retired_at is not None):
        raise NotFound()


def current(registration):
    if registration.credential_mode != "v2":
        return None
    return EventRegistrationCredential.objects.filter(
        registration=registration, revoked_at__isnull=True, expires_at__gt=timezone.now(),
    ).first()


def revoke_locked(registration, *, actor=None, reason="cancelled"):
    """Caller holds event, source/fences and registration locks. No secret in audit."""
    if registration.member_id:
        assert_account_fence_held(registration.member_id)
    rows = EventRegistrationCredential.objects.select_for_update().filter(
        registration=registration, revoked_at__isnull=True,
    )
    for row in rows:
        row.revoked_at, row.revoked_by, row.revocation_reason = timezone.now(), actor, reason
        row.save(update_fields=("revoked_at", "revoked_by", "revocation_reason"))
        record(actor, "event.credential_revoked", makerspace=registration.event.makerspace,
               target=row, meta={"registration_id": registration.pk, "generation": row.generation,
                                 "reason": reason})


@dataclass(frozen=True)
class PreparedCredential:
    event_id: int
    registration_id: int
    generation: int
    material: object = field(repr=False)


def prepare_issue(event_id, registration_id):
    if in_domain_transaction():
        raise RuntimeError("Prepare credentials before the event transaction.")
    generation = (EventRegistrationCredential.objects.filter(registration_id=registration_id)
                  .aggregate(value=Max("generation"))["value"] or 0) + 1
    return PreparedCredential(event_id, registration_id, generation,
                              prepare(event_id, registration_id, generation))


def issue_locked(event, registration, *, actor=None, rotate=False, prepared=None):
    assert_account_fence_held(registration.member_id)
    require_eligible(event, registration)
    if window_for(event).closes_at <= timezone.now():
        raise ProgrammeConflict("The event credential window has closed.", code="credential_expired")
    existing = current(registration)
    if existing and not rotate:
        return existing
    generation = (EventRegistrationCredential.objects.filter(registration=registration)
                  .aggregate(value=Max("generation"))["value"] or 0) + 1
    if (not isinstance(prepared, PreparedCredential) or prepared.event_id != event.pk
            or prepared.registration_id != registration.pk or prepared.generation != generation):
        raise ProgrammeConflict("Credential generation changed. Retry preparation.", code="credential_changed")
    material = prepared.material
    revoke_locked(registration, actor=actor, reason="rotated" if rotate else "expired")
    row = EventRegistrationCredential.objects.create(
        registration=registration, generation=generation, token_digest=material.digest,
        token_ciphertext=material.ciphertext, key_version=material.key_version,
        expires_at=window_for(event).closes_at,
    )
    registration.credential_mode = "v2"
    registration.save(update_fields=("credential_mode",))
    record(actor, "event.credential_issued", makerspace=event.makerspace, target=row,
           meta={"registration_id": registration.pk, "generation": generation})
    return row


def command(event_id, registration_id, *, actor, operation_id, expected_version, action):
    from apps.events import event_authority
    event_authority.get_event(actor, event_id, CHECK_IN)
    digest = hashlib.sha256(json.dumps([registration_id, action, expected_version]).encode()).hexdigest()
    scope = registrations(event_id, [registration_id], prepare_names=True)
    prepared = prepare_issue(event_id, registration_id) if action == "rotate" else None
    with event_command(event_id, actor=actor, permission=CHECK_IN, account_ids=scope.account_ids,
                       revalidate=scope.revalidate) as (event, actor):
        receipt = EventCredentialCommand.objects.filter(event=event, operation_id=operation_id).first()
        if receipt:
            if receipt.request_sha256 != digest or receipt.actor_id != actor.pk:
                raise ProgrammeConflict("Operation ID was already used for a different command.", code="operation_conflict")
            return receipt.result
        require_version(event, expected_version)
        try:
            registration = EventRegistration.objects.select_for_update().get(pk=registration_id, event=event)
        except EventRegistration.DoesNotExist as exc:
            raise NotFound() from exc
        scope.bind(registration)
        registration.event = event
        if action == "rotate":
            row = issue_locked(event, registration, actor=actor, rotate=True, prepared=prepared)
        elif action == "revoke":
            revoke_locked(registration, actor=actor, reason="lost_card")
            row = None
        else:
            raise ValueError("Unknown credential command.")
        version = advance(event)
        result = {"id": row.pk if row else registration.pk, "event_id": event.pk,
                  "version": version, "state": "applied", "allowed_actions": [],
                  "credential_generation": row.generation if row else None}
        EventCredentialCommand.objects.create(event=event, operation_id=operation_id,
                                             actor=actor, request_sha256=digest, result=result)
        return result


def owner_payload(registration, *, actor):
    """Read-only. Issuance/adoption is explicit at registration/desk, never on GET."""
    if actor.pk != registration.member_id or not is_person(actor):
        raise NotFound()
    require_eligible(registration.event, registration)
    row = current(registration)
    if not row:
        raise NotFound()
    return unwrap(row, registration.event_id)


def expire(event_id):
    affected = list(EventRegistration.objects.filter(event_id=event_id,
        credentials__revoked_at__isnull=True, credentials__expires_at__lte=timezone.now()
    ).values_list("pk", flat=True).distinct())
    scope = registrations(event_id, affected)
    with event_command(event_id, account_ids=scope.account_ids, revalidate=scope.revalidate) as (event, _):
        rows = EventRegistration.objects.filter(
            event=event, pk__in=affected, credentials__revoked_at__isnull=True,
            credentials__expires_at__lte=timezone.now(),
        ).distinct().order_by("pk")
        ids = list(rows.values_list("pk", flat=True))
        for registration in EventRegistration.objects.select_for_update().filter(pk__in=ids).order_by("pk"):
            registration.event = event
            revoke_locked(registration, reason="expired")
