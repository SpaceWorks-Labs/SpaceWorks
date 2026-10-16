"""Migration audit writer: exact row MAC payload, historical models, no live event."""

import logging
import uuid
from datetime import UTC, datetime

from apps.audit.canonical import calculate_row_mac, canonicalize_meta
from apps.audit.keys import AuditMacKeyUnavailable, _unwrap_key, audit_mac_configured
from apps.audit.services import _sanitize_meta


logger = logging.getLogger(__name__)


def record(space_id, action, target_type, target_id, *, models, alias, meta):
    log_model, key_model = models["audit.AuditLog"], models["audit.AuditMacKey"]
    stored_meta = canonicalize_meta(_sanitize_meta(meta))
    event_uuid, created_at = uuid.uuid4(), datetime.now(UTC)
    row_mac = None
    if audit_mac_configured():
        # Deliberately bypass get_audit_mac_key(): it queries the live model on the
        # default alias and uses a process cache. Migrations must use their registry
        # and connection, including when an operator uses migrate --database.
        key_row = key_model.objects.using(alias).filter(makerspace_id=space_id).first()
        try:
            if key_row is None:
                raise AuditMacKeyUnavailable(f"No audit MAC key for makerspace {space_id}.")
            key = _unwrap_key(space_id, key_row.wrapped_key)
        except AuditMacKeyUnavailable:
            # Same honest unattested state and operational signal as audit.record().
            logger.critical("audit_mac_key_unavailable", extra={
                "makerspace_id": space_id, "action": action,
            })
        else:
            row_mac = calculate_row_mac(
                key, makerspace_id=space_id, event_uuid=event_uuid, actor_id=None,
                action=action, target_type=target_type, target_id=str(target_id),
                meta=stored_meta, created_at=created_at,
            )
    return log_model.objects.using(alias).create(
        actor_id=None, makerspace_id=space_id, action=action, target_type=target_type,
        target_id=str(target_id), meta=stored_meta, event_uuid=event_uuid,
        created_at=created_at, row_mac=row_mac,
    )
