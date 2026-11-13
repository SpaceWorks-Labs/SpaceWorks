"""Preflight membership dispositions against the archived model graph."""

from collections import Counter

from django.apps import apps

from .archive_stream import PORTABLE_DATASETS
from .models_import_job import ImportIdentityDecision
from .protocol_errors import MembershipDependencyError


def validate_membership_dispositions(archive, decisions):
    """Reject dropped memberships whose non-null archived dependents survive."""
    # One account per person: a source "staff" row is an inert merged shell (a split-format
    # staff account was decorated into a person), and both shells and platform provenance
    # become new inert rows. A person's staff roles travel with the person's decision.
    source_kinds = {str(row["id"]): row.get("account_kind", "member") for row in archive.rows("accounts.User")}
    for item in decisions:
        if source_kinds.get(str(item["source_user_id"])) in {"platform", "staff"} and (
            item["identity_resolution"] != ImportIdentityDecision.IdentityResolution.CREATE_WALK_IN
            or item.get("target_user_id") is not None
        ):
            raise MembershipDependencyError("Platform provenance and merged shells must become new inert rows.")
        if item.get("grant_staff_roles") and (
                item["identity_resolution"] != ImportIdentityDecision.IdentityResolution.LINK_EXISTING):
            raise MembershipDependencyError("Only a linked person's staff roles take an explicit grant.")
    dropped_users = {
        str(item["source_user_id"])
        for item in decisions
        if item["membership_disposition"]
        == ImportIdentityDecision.MembershipDisposition.NO_MEMBERSHIP
    }
    if not dropped_users:
        return

    membership_ids = {
        str(row["id"]): str(row["user_id"])
        for row in archive.rows("makerspaces.MakerspaceMembership")
        if str(row["user_id"]) in dropped_users
    }
    if not membership_ids:
        return

    membership_model = apps.get_model("makerspaces.MakerspaceMembership")
    conflicts = Counter()
    for model in apps.get_models():
        label = model._meta.label
        if label not in PORTABLE_DATASETS:
            continue
        dependency_fields = tuple(
            field
            for field in model._meta.local_concrete_fields
            if field.is_relation
            and field.related_model is membership_model
            and not field.null
        )
        if not dependency_fields:
            continue
        for row in archive.rows(label):
            if any(str(row.get(field.attname, "")) in membership_ids for field in dependency_fields):
                conflicts[label] += 1

    if conflicts:
        summary = ", ".join(
            f"{label}={count}" for label, count in sorted(conflicts.items())
        )
        raise MembershipDependencyError(
            "no_membership would retain rows with a required membership reference: "
            f"{summary}."
        )
