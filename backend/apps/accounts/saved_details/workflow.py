"""Account-only vault mutations; tombstones prevent stale intents resurrecting data."""
from django.utils.translation import gettext
from django.utils import timezone

from apps.audit.services import record
from apps.encryption.account_mappers import account_key_context
from apps.encryption.account_readiness import assert_ready
from apps.encryption.account_services import prepare_account_key
from apps.encryption.account_write_fence import account_write

from .access import require_owner
from .commands import remember, replay, request_digest
from .crypto import open_value, seal
from .errors import SavedDetailsError
from .fields import descriptor, normalize
from .models import MemberSavedAsset, MemberSavedDetail


def require_version(actual, expected):
    if type(expected) is not int or expected != actual:
        raise SavedDetailsError("stale_version", gettext("This saved detail changed. Review it before saving."), 409, current_version=actual)


def require_resume(user_id, value):
    asset = MemberSavedAsset.objects.filter(
        pk=value["asset_id"], user_id=user_id, state="ready", sha256=value["sha256"],
    ).first()
    if asset is None:
        raise SavedDetailsError("asset_not_ready", gettext("Choose your own ready résumé."), 409)
    from .asset_policy import require_ready
    require_ready(asset)


def put_locked(actor, field_key, value, expected_version, key):
    descriptor(field_key)
    if field_key == "resume":
        require_resume(actor.pk, value)
    row = MemberSavedDetail.objects.select_for_update().filter(user=actor, field_key=field_key).first()
    require_version(row.version if row else 0, expected_version)
    row = row or MemberSavedDetail(user=actor, field_key=field_key, version=0)
    row.version += 1
    row.value_type = "object" if isinstance(value, dict) else "array" if isinstance(value, list) else "string"
    row.consented_at, row.deleted_at = timezone.now(), None
    row.value_envelope = seal(value, row, "value_envelope", key)
    row.save()
    if field_key == "resume":
        MemberSavedAsset.objects.filter(pk=value["asset_id"], user_id=actor.pk).update(
            last_selected_at=timezone.now(), next_cleanup_at=timezone.now())
    record(actor, "account.saved_detail_updated", target=row, meta={"field_key": field_key, "version": row.version})
    return {"field_key": field_key, "value": value, "version": row.version}


def change_detail(actor_id, field_key, body, *, delete=False):
    require_owner(actor_id)
    descriptor(field_key)
    operation_id = body["operation_id"]
    digest = request_digest(["delete" if delete else "put", field_key], body)
    previous = replay(actor_id, operation_id, digest)
    if previous is not None:
        if not delete:
            previous["value"] = normalize(field_key, body["value"])
        return previous
    value = None if delete else normalize(field_key, body["value"])
    if not delete and body.get("save_consent") is not True:
        raise SavedDetailsError("save_consent_required", gettext("Choose whether to save this detail."))
    key = prepare_account_key(actor_id)
    with account_write(actor_id), account_key_context(key):
        actor = require_owner(actor_id, lock=True)
        previous = replay(actor_id, operation_id, digest, key=key)
        if previous is not None:
            if not delete:
                previous["value"] = value
            return previous
        if not delete:
            response = put_locked(actor, field_key, value, body["expected_version"], key)
        else:
            row = MemberSavedDetail.objects.select_for_update().filter(user=actor, field_key=field_key).first()
            require_version(row.version if row else 0, body["expected_version"])
            row = row or MemberSavedDetail(user=actor, field_key=field_key, version=0, value_type="deleted", consented_at=timezone.now())
            row.version += 1
            # A tombstone is itself encrypted; blank is never a plaintext escape.
            row.value_envelope = seal(None, row, "value_envelope", key)
            row.deleted_at = timezone.now()
            row.save()
            record(actor, "account.saved_detail_deleted", target=row, meta={"field_key": field_key, "version": row.version})
            response = {"field_key": field_key, "deleted": True, "version": row.version}
        return remember(actor_id, operation_id, digest, response, key)


def list_details(actor_id):
    require_owner(actor_id)
    assert_ready()
    rows = list(MemberSavedDetail.objects.filter(user_id=actor_id).order_by("field_key"))
    fields = []
    for row in rows:
        info = descriptor(row.field_key)
        # Null is an owner-visible deletion tombstone, never a saved canonical
        # value. Its version is needed to recreate the field safely after reload.
        fields.append({"field_key": row.field_key, "value": None if row.deleted_at else open_value(row, "value_envelope"), "version": row.version,
                       "sensitive": info["sensitive"], "default_save": info["default_save"]})
    return {"version": sum(row.version for row in rows), "fields": fields, "readiness": "ready"}


def saved_dob_loader(*, actor_id, version):
    require_owner(actor_id)
    row = MemberSavedDetail.objects.filter(user_id=actor_id, field_key="date_of_birth", deleted_at__isnull=True, version=version).first()
    if row is None:
        raise SavedDetailsError("stale_version", gettext("Review your saved date of birth."), 409)
    return open_value(row, "value_envelope")
