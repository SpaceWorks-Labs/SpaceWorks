"""Resolve the portable user closure without importing source account authority."""

from dataclasses import dataclass
import hashlib

from apps.accounts.models import User

from .portable_people import _create_walk_in, audit_staff_grant, create_person  # noqa: F401 -- re-exported
from .insertion_errors import IdentityResolutionError, PrimaryKeyMapUnavailable
from .models_import_job import ImportIdentityDecision
from .transaction_state import require_import_transaction

REQUIRED_TABLE = "tenant_import_required_identity"


@dataclass(frozen=True)
class IdentityResolutionReport:
    linked: int
    created: int
    preexisting_global_authority: tuple[dict[str, object], ...]
    linked_global_state_fingerprint: bytes
    shells_created: int = 0
    shells_remapped: int = 0
    credentials_installed: int = 0


class RequiredIdentitySet:
    """Deduplicated required source users held in transaction-local PostgreSQL."""

    def __init__(self):
        self.connection = require_import_transaction()
        self.pending = {}
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"CREATE TEMPORARY TABLE {REQUIRED_TABLE} "
                "(source_user_id text PRIMARY KEY, mandatory boolean NOT NULL, resolved_target text) ON COMMIT DROP"
            )

    def add_row(self, model, row):
        if model._meta.label not in {"audit.AuditLog", "makerspaces.Makerspace"}:
            for field in model._meta.local_concrete_fields:
                if (
                    field.is_relation
                    and field.related_model is not None
                    and field.related_model._meta.label == "accounts.User"
                    and row.get(field.attname)
                ):
                    optional_creator = model._meta.label in {"inventory.EquipmentProposalReceipt", "inventory.EquipmentConsumableUseReceipt", "events.EventBookingDecision"} and field.name == "creator"
                    self.add(row[field.attname], mandatory=not optional_creator)
        if model._meta.label == "machines.ServiceRequestFile" and row.get(
            "owner_user_id"
        ):
            self.add(row["owner_user_id"])

    def add(self, source_user_id, *, mandatory=True):
        key = str(source_user_id)
        self.pending[key] = self.pending.get(key, False) or mandatory
        if len(self.pending) >= 500:
            self.flush()

    def flush(self):
        if not self.pending:
            return
        with self.connection.cursor() as cursor:
            cursor.executemany(
                f"INSERT INTO {REQUIRED_TABLE} (source_user_id, mandatory) VALUES (%s, %s) "
                f"ON CONFLICT (source_user_id) DO UPDATE SET mandatory = {REQUIRED_TABLE}.mandatory OR EXCLUDED.mandatory",
                list(self.pending.items()),
            )
        self.pending.clear()

    def contains(self, source_user_id):
        self.flush()
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"SELECT 1 FROM {REQUIRED_TABLE} WHERE source_user_id=%s",
                [str(source_user_id)],
            )
            return cursor.fetchone() is not None

    def count(self):
        self.flush()
        with self.connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM {REQUIRED_TABLE} WHERE mandatory")
            return cursor.fetchone()[0]

    def mandatory(self, source_user_id):
        self.flush()
        with self.connection.cursor() as cursor:
            cursor.execute(f"SELECT mandatory FROM {REQUIRED_TABLE} WHERE source_user_id=%s", [str(source_user_id)])
            row = cursor.fetchone()
        return bool(row and row[0])

    def should_resolve(self, job, source_user_id):
        if not self.contains(source_user_id):
            return False
        return self.mandatory(source_user_id) or job.identity_decisions.filter(source_user_id=str(source_user_id)).exists()

    def mark_resolved(self, source_user_id, target_user_id):
        self.flush()
        with self.connection.cursor() as cursor:
            cursor.execute(f"UPDATE {REQUIRED_TABLE} SET resolved_target=%s WHERE source_user_id=%s", [str(target_user_id), str(source_user_id)])
            if cursor.rowcount != 1:
                raise IdentityResolutionError("Resolved identity was not in the source closure.")

    def was_resolved(self, source_user_id, target_user_id):
        self.flush()
        with self.connection.cursor() as cursor:
            cursor.execute(f"SELECT resolved_target FROM {REQUIRED_TABLE} WHERE source_user_id=%s", [str(source_user_id)])
            row = cursor.fetchone()
        return bool(row and row[0] == str(target_user_id))


def preallocate_walk_in_ids(job, pk_map, required):
    """Reserve CREATE_WALK_IN user IDs before any imported row is inserted."""
    create_ids = (
        source_id
        for source_id in job.identity_decisions.filter(
            identity_resolution=ImportIdentityDecision.IdentityResolution.CREATE_WALK_IN
        )
        .values_list("source_user_id", flat=True)
        .iterator(chunk_size=500)
        if required.should_resolve(job, source_id)
    )
    pk_map.reserve(User, create_ids)


def resolve_identities(archive, job, pk_map, required, deks=None):
    """Validate the complete closure, create bounded walk-ins, and populate its PK map."""
    from apps.accounts import staff_identity

    seen_count = 0
    for source in archive.rows("accounts.User"):
        source_id = source["id"]
        if not required.should_resolve(job, source_id):
            continue
        seen_count += int(required.mandatory(source_id))
        decision = _required_decision(job, source_id)
        if source.get("account_kind") in {staff_identity.PLATFORM_KIND, staff_identity.SHELL_KIND} and (
            decision.identity_resolution != decision.IdentityResolution.CREATE_WALK_IN
            or decision.target_user_id is not None
        ):
            raise IdentityResolutionError("Platform provenance and merged shells must become new inert rows.")
        if decision.grant_staff_roles and decision.identity_resolution != decision.IdentityResolution.LINK_EXISTING:
            raise IdentityResolutionError("Only a linked person's staff roles take an explicit grant.")
        if decision.identity_resolution == decision.IdentityResolution.LINK_EXISTING:
            if decision.target_user is None:
                raise IdentityResolutionError(
                    f"Source user {source_id} has an incomplete LINK_EXISTING decision."
                )
            if not staff_identity.is_person(decision.target_user):
                raise IdentityResolutionError("Member identities may link only to live member (person) accounts.")
            if source.get("deletion_requested_at") or source.get("account_purged_at"):
                raise IdentityResolutionError("A deleted source identity must be imported as a separate inactive identity.")
        elif decision.identity_resolution == decision.IdentityResolution.CREATE_WALK_IN:
            if decision.target_user_id is not None:
                raise IdentityResolutionError(
                    f"Source user {source_id} has an invalid CREATE_WALK_IN decision."
                )
            pk_map.lookup(User, source_id)
        else:
            raise IdentityResolutionError(
                f"Source user {source_id} has an unsupported identity decision."
            )
    if required.count() != seen_count:
        raise IdentityResolutionError(
            "A retained source identity is absent from global/users.csv."
        )

    linked = created = installed = 0
    reported, shells = [], []
    linked_state_fingerprint = 0
    user_model = User
    credentials = None
    for source in archive.rows("accounts.User"):
        source_id = source["id"]
        if not required.should_resolve(job, source_id):
            continue
        decision = _required_decision(job, source_id)
        if decision.identity_resolution == decision.IdentityResolution.LINK_EXISTING:
            target = decision.target_user
            if target is None:
                raise IdentityResolutionError(
                    f"Source user {source_id} has an incomplete LINK_EXISTING decision."
                )
            pk_map.add_many(user_model, [(source_id, target.pk)])
            required.mark_resolved(source_id, target.pk)
            linked += 1
            linked_state_fingerprint ^= _authority_record_fingerprint(
                target.pk, target.is_superuser, target.is_staff, target.role
            )
            if target.is_superuser or target.role == User.Role.SUPERADMIN:
                reported.append(
                    {
                        "source_user_id": source_id,
                        "target_user_id": target.pk,
                        "kind": "target_global_superadmin",
                    }
                )
            if decision.grant_staff_roles:
                audit_staff_grant(job, source_id, target)
            continue
        if source.get("account_kind") == staff_identity.PLATFORM_KIND:
            from .portable_staff import create_provenance_stub
            create_provenance_stub(source, pk_map.lookup(user_model, source_id))
        elif source.get("account_kind") == staff_identity.SHELL_KIND:
            shells.append(source)
            continue
        else:
            if credentials is None:
                from .credential_block import read_credential_block
                credentials = read_credential_block(archive, job.source_makerspace_id, deks or {})
            installed += create_person(source, pk_map.lookup(user_model, source_id), credentials.get(str(source_id)),
                                        job.target_makerspace)
        required.mark_resolved(source_id, pk_map.lookup(user_model, source_id))
        created += 1
    from .portable_shells import create_shells
    shells_created, shells_remapped = create_shells(archive, job, pk_map, shells)
    for source in shells:
        required.mark_resolved(source["id"], pk_map.lookup(user_model, source["id"]))
    return IdentityResolutionReport(
        linked,
        created + shells_created,
        tuple(reported),
        linked_state_fingerprint.to_bytes(32, "big"),
        shells_created=shells_created,
        shells_remapped=shells_remapped,
        credentials_installed=installed,
    )


def _required_decision(job, source_id):
    try:
        return job.identity_decisions.select_related("target_user").get(
            source_user_id=source_id
        )
    except ImportIdentityDecision.DoesNotExist as exc:
        raise IdentityResolutionError(
            f"Source user {source_id} has no identity decision."
        ) from exc


def decision_for_source_user(job, source_user_id):
    try:
        return job.identity_decisions.get(source_user_id=str(source_user_id))
    except ImportIdentityDecision.DoesNotExist as exc:
        raise IdentityResolutionError(
            f"Source user {source_user_id} has no identity decision."
        ) from exc


def linked_authority_fingerprint(job, pk_map):
    fingerprint = 0
    decisions = job.identity_decisions.filter(
        identity_resolution=ImportIdentityDecision.IdentityResolution.LINK_EXISTING
    ).select_related("target_user")
    for decision in decisions.iterator(chunk_size=500):
        try:
            pk_map.lookup(User, decision.source_user_id)
        except PrimaryKeyMapUnavailable:
            continue
        target = decision.target_user
        if target is None:
            raise IdentityResolutionError("A LINK_EXISTING decision lost its target.")
        fingerprint ^= _authority_record_fingerprint(
            target.pk, target.is_superuser, target.is_staff, target.role
        )
    return fingerprint.to_bytes(32, "big")


def _authority_record_fingerprint(user_id, is_superuser, is_staff, role):
    payload = f"{user_id}:{int(is_superuser)}:{int(is_staff)}:{role}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest(), "big")
