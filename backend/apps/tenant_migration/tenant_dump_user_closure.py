"""Immutable-image identity closure for sovereign Lane D tenant exits."""

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
from django.apps import apps

from apps.backup.raw_projection import no_decrypt_guard, raw_records
from apps.data_export.guards import (
    RegistryError,
    validate_semantic_references,
    validate_user_edges,
)
from apps.data_export.references import SEMANTIC_REFERENCES, USER_EDGES
from apps.data_export.types import Fidelity, SemanticUserRef

from .tenant_dump_errors import TenantDumpClosureRefused
from .tenant_dump_user_rows import STUB_SCHEMA_VERSION


USER_REF_DOMAIN = b"lane-d-user-v1\0"
SEMANTIC_USER_REWRITE_HANDLERS = {}


def person_annotation():
    from django.db.models import BooleanField, Case, Value, When

    from apps.accounts.staff_identity import person_q
    return Case(When(person_q(), then=Value(True)), default=Value(False), output_field=BooleanField())



def _sealed_member_edges(row):
    """A sealed submission roster names each member's account ID in a JSON list."""
    members = row.get("sealed_member_ids") or []
    if not isinstance(members, list) or any(type(value) is not int or value <= 0 for value in members):
        raise TenantDumpClosureRefused(
            "A sealed submission roster has an invalid member reference.",
            reason_code="semantic_user_reference_invalid",
        )
    return [("sealed_member_ids", value) for value in members]


SEMANTIC_USER_REWRITE_HANDLERS[("events.SubmissionSnapshot", "json:sealed_member_ids")] = _sealed_member_edges


@dataclass(frozen=True)
class UserClosure:
    included: tuple[dict, ...]
    stubbed: tuple[dict, ...]
    refused: tuple[dict, ...]
    digest: str

    def manifest(self):
        return {
            "included": list(self.included),
            "stubbed": list(self.stubbed),
            "refused": list(self.refused),
            "sha256": self.digest,
        }

    @property
    def stubbed_user_ids(self):
        return frozenset(item["emitted_user_pk"] for item in self.stubbed)


def user_ref(capture_id, source_user_pk):
    digest = hashlib.sha256()
    digest.update(USER_REF_DOMAIN)
    digest.update(str(capture_id).encode("utf-8"))
    digest.update(b"\0")
    digest.update(str(source_user_pk).encode("utf-8"))
    return digest.hexdigest()


def build_user_closure(rows, makerspace_id, capture_id, *, using="default"):
    """Classify referenced users using every membership in the frozen database."""
    _validate_registries()
    references = _referencing_edges(rows)
    user_ids = set(references)
    User = apps.get_model("accounts.User")
    identities = {row["id"]: row for row in User._base_manager.using(using).filter(pk__in=user_ids)
                  .annotate(person=person_annotation()).values("id", "person", "retired_at", "merged_into_id")}
    existing_user_ids = set(identities)
    missing = sorted(user_ids - existing_user_ids, key=str)
    if missing:
        refused = tuple(
            _entry(capture_id, pk, "missing_source_user", references[pk], emitted=None)
            for pk in missing
        )
        closure = _closure((), (), refused)
        raise TenantDumpClosureRefused(
            "A referenced source user is missing.",
            reason_code="missing_source_user",
            closure=closure,
        )

    memberships, staff_here = defaultdict(set), set()
    Membership = apps.get_model("makerspaces.MakerspaceMembership")
    for row in Membership._base_manager.using(using).filter(
        user_id__in=user_ids
    ).values("user_id", "makerspace_id", "track", "status"):
        memberships[row["user_id"]].add(row["makerspace_id"])
        if row["makerspace_id"] == int(makerspace_id) and row["track"] == "staff" and row["status"] == "active":
            staff_here.add(row["user_id"])

    included, stubbed = [], []
    for pk in sorted(user_ids, key=str):
        identity = identities[pk]
        # A person travels in full when every membership is in this space, or when they
        # hold an active staff role here (#128 C-18: staff sign in on the target). Shells
        # and platform accounts are always PII-free stubs.
        live_person = identity["person"] and identity["retired_at"] is None and identity["merged_into_id"] is None
        exclusive = live_person and (memberships[pk] == {int(makerspace_id)} or pk in staff_here)
        if exclusive:
            included.append(
                _entry(capture_id, pk, "tenant_exclusive", references[pk], emitted=pk)
            )
        else:
            stubbed.append(
                _entry(capture_id, pk, "not_tenant_exclusive", references[pk], emitted=pk)
            )
    return _closure(included, stubbed, ())


def reproduce_user_closure(using, capture_id):
    """Independently rebuild the digest from a sanitized scratch/target database."""
    rows = _database_reference_rows(using)
    references = _referencing_edges(rows)
    User = apps.get_model("accounts.User")
    users = {
        row["id"]: row
        for row in User._base_manager.using(using)
        .filter(pk__in=references)
        .values("id", "is_tenant_dump_stub")
    }
    verify_user_fk_closure(references, set(users))
    included, stubbed = [], []
    for pk in sorted(users, key=str):
        target = stubbed if users[pk]["is_tenant_dump_stub"] else included
        reason = "not_tenant_exclusive" if target is stubbed else "tenant_exclusive"
        target.append(_entry(capture_id, pk, reason, references[pk], emitted=pk))
    return _closure(included, stubbed, ())


def verify_user_fk_closure(references, emitted_user_ids):
    missing = sorted(set(references) - set(emitted_user_ids), key=str)
    if missing:
        raise TenantDumpClosureRefused(
            "A non-null user edge points at neither a full row nor a stub.",
            reason_code="unclosed_non_null_user_edge",
        )


def verify_closure_digest(actual, expected_digest):
    if actual.digest != expected_digest:
        raise TenantDumpClosureRefused(
            "The independently reproduced user closure digest differs.",
            reason_code="closure_digest_mismatch",
            closure=actual,
        )
    return actual.digest


def _referencing_edges(rows):
    references = defaultdict(list)
    for (fidelity, label, field_name), edge in USER_EDGES.items():
        if fidelity is not Fidelity.PORTABLE or not edge.included or label not in rows:
            continue
        model = apps.get_model(label)
        field = model._meta.get_field(field_name)
        key = field_name if edge.raw else field.attname
        for row in rows[label]:
            value = row.get(key)
            if value is not None:
                references[int(value)].append(
                    (label, row[model._meta.pk.attname], field_name)
                )
    _semantic_edges(rows, references)
    return {pk: tuple(sorted(edges, key=_edge_key)) for pk, edges in references.items()}


def _semantic_edges(rows, references):
    for (fidelity, label, location), decisions in SEMANTIC_REFERENCES.items():
        if fidelity is not Fidelity.PORTABLE or label not in rows:
            continue
        for decision in decisions:
            if not isinstance(decision, SemanticUserRef) or not decision.included:
                continue
            handler = SEMANTIC_USER_REWRITE_HANDLERS.get((label, location))
            if handler is None:
                raise TenantDumpClosureRefused(
                    "A semantic user reference has no rewrite handler.",
                    reason_code="semantic_user_reference_unhandled",
                )
            for row in rows[label]:
                for field_name, value in handler(row):
                    references[int(value)].append((label, row["id"], field_name))


def _database_reference_rows(using):
    result = {}
    labels = {"accounts.User"} | {
        label
        for (fidelity, label, _field), edge in USER_EDGES.items()
        if fidelity is Fidelity.PORTABLE and edge.included
    }
    with no_decrypt_guard():
        for label in sorted(labels):
            model = apps.get_model(label)
            result[label] = tuple(
                raw_records(model._base_manager.using(using).order_by("pk"), model)
            )
    return result


def _entry(capture_id, pk, reason, edges, *, emitted):
    return {
        "user_ref": user_ref(capture_id, pk),
        "emitted_user_pk": emitted,
        "reason_code": reason,
        "stub_schema_version": STUB_SCHEMA_VERSION if reason == "not_tenant_exclusive" else None,
        "referencing_edges": [
            {"model_label": label, "source_row_pk": row_pk if type(row_pk) is int else str(row_pk),
             "field_name": field}
            for label, row_pk, field in sorted(edges, key=_edge_key)
        ],
    }


def _closure(included, stubbed, refused):
    payload = {
        "included": sorted(included, key=lambda item: item["user_ref"]),
        "stubbed": sorted(stubbed, key=lambda item: item["user_ref"]),
        "refused": sorted(refused, key=lambda item: item["user_ref"]),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return UserClosure(
        tuple(payload["included"]),
        tuple(payload["stubbed"]),
        tuple(payload["refused"]),
        hashlib.sha256(encoded).hexdigest(),
    )


def _validate_registries():
    try:
        validate_user_edges(USER_EDGES)
        validate_semantic_references(SEMANTIC_REFERENCES)
    except RegistryError as exc:
        raise TenantDumpClosureRefused(
            "The user-edge registry is incomplete.",
            reason_code="unclassified_user_edge",
        ) from exc


def _edge_key(edge):
    return str(edge[0]), str(edge[1]), str(edge[2])
