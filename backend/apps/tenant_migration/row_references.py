"""Foreign-key remapping for import rows (split from `row_planning`).

Re-exported from ``row_planning``; import them from there.
"""

from django.apps import apps

from .closure_references import (
    CROSS_TENANT_DEPENDENT_REFERENCES,
    MOVABLE_ROW_REFERENCES,
    MissingReferenceDisposition,
)
from .identity_resolution import decision_for_source_user
from .insertion_errors import PrimaryKeyMapUnavailable
from .target_projection import FK_POLICIES, ReferenceDisposition


def _remap_foreign_keys(model, source, row, job, pk_map, target, references):
    from .portable_staff import apply_staff_role
    staff = apply_staff_role(model, source, row, target, job)
    for field in model._meta.local_concrete_fields:
        if not field.is_relation or field.related_model is None:
            continue
        source_value = row[field.column]
        if source_value is None:
            continue
        edge_policy = FK_POLICIES.get((model._meta.label, field.name))
        if staff and (model._meta.label, field.name) in {
            ("makerspaces.MakerspaceMembership", "assigned_role"),
            ("makerspaces.MembershipAdditionalRole", "role"),
        }:
            continue
        if staff and model._meta.label in {"machines.MembershipMachineTypeScope", "machines.MembershipMachineScope"}:
            edge_policy = None
        if edge_policy and edge_policy.disposition is ReferenceDisposition.DROP_ROW:
            return False
        if edge_policy and edge_policy.disposition is ReferenceDisposition.REMAP_TARGET_MEMBER:
            row[field.column] = target.roles.get(slug="member").pk
            continue
        if field.related_model._meta.label == "accounts.User":
            row[field.column] = pk_map.lookup(field.related_model, source_value)
        elif field.related_model._meta.label == "encryption.SearchKeyGeneration":
            continue
        elif field.related_model._meta.label == "accounts.MemberClaimCode":
            row[field.column] = None
        else:
            try:
                row[field.column] = pk_map.lookup(field.related_model, source_value)
            except PrimaryKeyMapUnavailable:
                if field.name == "profile" and model._meta.label in {
                    "makerspaces.MakerspacePublicPageRevisionMember", "events.EventPageRevisionMember",
                }:
                    row[field.column] = None
                    continue
                # A crafted archive may retain the numeric id beside its snapshot.
                # Only a declared NULL disposition authorizes turning that id inert.
                if field.null and _null_with_provenance(
                    model._meta.label, field.name, source, references
                ):
                    row[field.column] = None
                else:
                    raise
    return True


def _null_with_provenance(label, field_name, source, references):
    rule = MOVABLE_ROW_REFERENCES.get((label, field_name))
    if rule is not None:
        disposition = rule.disposition
    else:
        disposition = CROSS_TENANT_DEPENDENT_REFERENCES.get((label, field_name))
    return (
        disposition is MissingReferenceDisposition.NULL_WITH_PROVENANCE
        and references.get(label, source["id"], field_name) is not None
    )


def _clear_walk_in_waiver_evidence(label, source, row, job):
    if label != "makerspaces.MakerspaceMembership":
        return
    decision = decision_for_source_user(job, source["user_id"])
    if decision.identity_resolution != decision.IdentityResolution.CREATE_WALK_IN:
        return
    for name in (
        "waiver_accepted_at", "waiver_version_accepted", "accepted_waiver",
        "witnessed_waiver", "witnessed_waiver_version", "witnessed_by",
        "witnessed_actor_snapshot", "witnessed_at",
    ):
        field = apps.get_model(label)._meta.get_field(name)
        row[field.column] = None
