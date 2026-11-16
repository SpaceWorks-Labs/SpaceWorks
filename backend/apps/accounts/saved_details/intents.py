"""Encrypted pre-event preparation and account-only postcommit application."""
from django.utils.translation import gettext
from dataclasses import dataclass, field
from datetime import timedelta
import hashlib
from uuid import UUID, uuid4

from django.db import connection, transaction
from django.utils import timezone

from apps.audit.services import record
from apps.encryption.account_mappers import account_key_context
from apps.encryption.account_services import get_account_key, prepare_account_key
from apps.encryption.account_write_fence import AccountKeyChanged, account_write, verify_prepared_epoch
from apps.encryption.crypto import PiiUnavailable

from .access import require_owner
from .crypto import canonical, open_value, seal
from .errors import SavedDetailsError
from .fields import require_form_operation, require_form_slot, selected_values
from .models import MemberSavedDetail, SavedDetailUpdateIntent
from .workflow import put_locked
from .subject_binding import require_subject
from apps.transaction_guards import in_domain_transaction

_SEAL = object()


@dataclass(frozen=True, kw_only=True)
class ValidatedSaveInput:
    """Constructed by F's trusted validator adapter, never a browser serializer."""
    subject: object
    mapped_values: dict = field(repr=False)
    canonical_answers: object = field(repr=False)
    form_descriptor: object = field(repr=False)
    event_date_revision: int


@dataclass(frozen=True, kw_only=True)
class PreparedSave:
    intent_id: UUID
    operation_id: UUID
    subject: object
    ciphertext: bytes = field(repr=False)
    key_version: int = field(repr=False)
    key_epoch: int = field(repr=False)
    canonical_answer_sha256: str
    form_sha256: str
    event_date_revision: int
    expires_at: object
    base_versions: tuple
    chosen_fields: tuple
    _proof: object = field(repr=False)
    outer_operation_id: UUID | None = None
    form_slot: str | None = None


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def validate_form_save_conflicts(forms):
    """G calls before any domain writes; slot -> (validated input, choices, CAS).

    Compare normalized values in memory only. Error payloads contain slots/keys,
    never values or their hashes. G owns deterministic child UUID generation.
    """
    selected_by_key, owner = {}, None
    for slot, (form, choices, versions) in sorted(forms.items()):
        require_form_slot(slot)
        if not isinstance(form, ValidatedSaveInput):
            raise SavedDetailsError("invalid_form_input", gettext("Use the validated owner form."))
        require_subject(form.subject)
        scope = (form.subject.event_id, form.subject.owner_member_id)
        if (owner is not None and owner != scope) or (slot != "base") != (str(form.subject.kind) == "stage_response"):
            raise SavedDetailsError("invalid_subject", gettext("Forms must belong to the same participant."), 409)
        owner = scope
        for key, value in selected_values(form, choices, versions).items():
            prior = selected_by_key.get(key)
            if prior and (prior[1] != value or prior[2] != versions[key]):
                raise SavedDetailsError("saved_detail_form_conflict", gettext("Review conflicting save choices across forms."), 409,
                                        form_slots=[prior[0], slot], field_keys=[key])
            selected_by_key[key] = (slot, value, versions[key])


def prepare_saved_detail_intent(*, actor_id, subject, validated_form, choices, base_versions, operation_id,
                              outer_operation_id=None, form_slot=None):
    if in_domain_transaction():
        raise RuntimeError("Prepare saved details before entering domain transactions.")
    require_owner(actor_id)
    require_subject(subject)
    require_form_operation(outer_operation_id, form_slot, subject)
    if not isinstance(validated_form, ValidatedSaveInput) or validated_form.subject != subject or subject.owner_member_id != actor_id:
        raise SavedDetailsError("invalid_form_input", gettext("Use the validated owner form."))
    if not isinstance(operation_id, UUID):
        raise SavedDetailsError("invalid_save_choices", gettext("Check save choices and operation ID."))
    selected = selected_values(validated_form, choices, base_versions)
    if not selected:
        return None
    if len(canonical(selected).encode()) > 32_768:
        raise SavedDetailsError("saved_details_too_large", gettext("Saved details exceed the size limit."), 413)
    key = prepare_account_key(actor_id)
    intent = SavedDetailUpdateIntent(id=uuid4(), user_id=actor_id)
    ciphertext = seal(selected, intent, "encrypted_payload", key).encode()
    return PreparedSave(
        intent_id=intent.id, operation_id=operation_id, subject=subject, ciphertext=ciphertext,
        key_version=key.version, key_epoch=key.epoch, canonical_answer_sha256=digest(validated_form.canonical_answers),
        form_sha256=digest(validated_form.form_descriptor), event_date_revision=validated_form.event_date_revision,
        expires_at=timezone.now() + timedelta(seconds=60), base_versions=tuple((k, base_versions[k]) for k in sorted(selected)),
        chosen_fields=tuple(sorted(selected)), _proof=_SEAL,
        outer_operation_id=outer_operation_id, form_slot=form_slot,
    )


def insert_prepared_locked(prepared, *, subject, locks):
    """Caller acquired source/global/tenant/shared account fences BEFORE event lock."""
    if not connection.in_atomic_block or not isinstance(prepared, PreparedSave) or prepared._proof is not _SEAL:
        raise RuntimeError("An in-process preparation and domain transaction are required.")
    if timezone.now() >= prepared.expires_at:
        raise SavedDetailsError("save_preparation_expired", gettext("Review saved details and submit again."), 409)
    require_subject(prepared.subject)
    require_subject(subject)
    prior = prepared.subject
    same = (prior.event_id, prior.owner_member_id, prior.kind) == (subject.event_id, subject.owner_member_id, subject.kind)
    binding = prior.subject_id == subject.subject_id if prior.subject_id is not None else prior.creation_operation_id == prepared.operation_id
    if not same or not binding or subject.subject_id is None or subject.owner_member_id not in locks.account_ids or locks.event_id != subject.event_id:
        raise SavedDetailsError("invalid_subject", gettext("This preparation belongs to another form."), 409)
    from .subject_binding import require_binding
    binding = require_binding(prepared, subject, locks)
    if prepared.form_sha256 != binding.form_sha256:
        raise SavedDetailsError("form_revision_changed", gettext("Review the revised form."), 409)
    if prepared.event_date_revision != binding.event_date_revision:
        raise SavedDetailsError("event_date_changed", gettext("Reload the form for the revised event date."), 409)
    if prepared.canonical_answer_sha256 != binding.canonical_answer_sha256:
        raise SavedDetailsError("answers_changed", gettext("Review the changed answers."), 409)
    if set(binding.chosen_fields) != set(prepared.chosen_fields):
        raise SavedDetailsError("save_choices_changed", gettext("Review the changed save choices."), 409)
    verify_prepared_epoch(subject.owner_member_id, prepared.key_epoch, version=prepared.key_version)
    row = SavedDetailUpdateIntent(
        id=prepared.intent_id, user_id=subject.owner_member_id, operation_uuid=prepared.operation_id,
        event_id=subject.event_id, subject_kind=str(subject.kind), subject_id=subject.subject_id,
        base_versions=dict(prepared.base_versions), chosen_fields=list(prepared.chosen_fields),
        encrypted_payload=prepared.ciphertext.decode(), key_version=prepared.key_version, key_epoch=prepared.key_epoch,
        expires_at=timezone.now() + timedelta(days=7),
    )
    # Ciphertext authentication already happened during preparation; mapper checks
    # the sealed context without broker I/O. This is NOT account key provisioning.
    from apps.encryption.account_mappers import prepared_envelope_write
    with prepared_envelope_write(row.user_id, row.key_version, row.key_epoch):
        row.save(force_insert=True)
    record(require_owner(row.user_id), "account.saved_detail_intent_created", target=row, meta={"fields": row.chosen_fields})
    return row.id


def _holds(current, value, key):
    """Already-saved check inside the account write, using the key prepared outside it.
    A value sealed under another key version cannot be opened here; the version CAS decides."""
    try:
        return open_value(current, "value_envelope", key) == value
    except AccountKeyChanged:
        return False


def apply_intent(intent_id):
    pending = SavedDetailUpdateIntent.objects.filter(pk=intent_id, state="pending").first()
    if pending is None:
        return
    from apps.encryption.account_models import PiiAccountWriteFence
    if not PiiAccountWriteFence.objects.filter(user_id=pending.user_id, epoch=pending.key_epoch, state="open").exists():
        with account_write(pending.user_id):
            actor = require_owner(pending.user_id, lock=True)
            row = SavedDetailUpdateIntent.objects.select_for_update().get(pk=intent_id)
            if row.state == "pending":
                row.state, row.failure_code, row.encrypted_payload = "failed", "account_key_changed", ""
                row.completed_at = timezone.now()
                row.field_status = {name: {"state": "failed", "code": row.failure_code} for name in row.chosen_fields}
                row.save(update_fields=["state", "failure_code", "encrypted_payload", "completed_at", "field_status"])
                record(actor, "account.saved_detail_intent_completed", target=row, meta={"state": row.state, "code": row.failure_code})
        return
    try:
        key = get_account_key(pending.user_id, version=pending.key_version)
    except PiiUnavailable:
        with account_write(pending.user_id):
            actor = require_owner(pending.user_id, lock=True)
            row = SavedDetailUpdateIntent.objects.select_for_update().get(pk=intent_id)
            if row.state == "pending" and row.failure_code != "account_key_unavailable":
                row.failure_code = "account_key_unavailable"
                row.save(update_fields=["failure_code"])
                record(actor, "account.saved_detail_intent_retry_required", target=row, meta={"code": row.failure_code})
        return
    values = open_value(pending, "encrypted_payload", key)
    with account_write(pending.user_id), account_key_context(key):
        actor = require_owner(pending.user_id, lock=True)
        row = SavedDetailUpdateIntent.objects.select_for_update().get(pk=intent_id)
        if row.state != "pending":
            return
        row.failure_code = ""
        try:
            verify_prepared_epoch(actor.pk, row.key_epoch, version=row.key_version)
            changed_epoch = False
        except AccountKeyChanged:
            changed_epoch = True
        if changed_epoch:
            row.state, row.failure_code = "failed", "account_key_changed"
            row.field_status = {name: {"state": "failed", "code": "account_key_changed"} for name in row.chosen_fields}
        elif row.expires_at <= timezone.now():
            row.state, row.failure_code = "failed", "save_intent_expired"
            row.field_status = {name: {"state": "failed", "code": row.failure_code} for name in row.chosen_fields}
        else:
            for name in sorted(row.chosen_fields):
                current = MemberSavedDetail.objects.filter(user=actor, field_key=name).first()
                version = current.version if current else 0
                if current is not None and not current.deleted_at and _holds(current, values[name], key):
                    row.field_status[name] = {"state": "unchanged", "version": version}
                elif version != row.base_versions[name]:
                    row.field_status[name] = {"state": "conflict", "current_version": version}
                else:
                    try:
                        with transaction.atomic():
                            response = put_locked(actor, name, values[name], version, key)
                        row.field_status[name] = {"state": "applied", "version": response["version"]}
                    except SavedDetailsError as exc:
                        row.field_status[name] = {"state": "failed", "code": str(exc.detail["code"])}
            states = {s["state"] for s in row.field_status.values()}
            row.state = "failed" if "failed" in states else "conflict" if "conflict" in states else "applied"
        row.completed_at = timezone.now()
        row.encrypted_payload = ""  # terminal payload erasure needs no retired key write
        row.save()
        record(actor, "account.saved_detail_intent_completed", target=row, meta={"state": row.state})


def intent_status(actor_id, operation_id):
    require_owner(actor_id)
    row = SavedDetailUpdateIntent.objects.filter(user_id=actor_id, operation_uuid=operation_id).first()
    if row is None:
        raise SavedDetailsError("not_found", gettext("Saved detail update not found."), 404)
    result = {"operation_id": str(row.operation_uuid), "state": row.state, "fields": row.field_status, "retryable": row.state == "pending"}
    if row.failure_code:
        result["code"] = row.failure_code
    return result
