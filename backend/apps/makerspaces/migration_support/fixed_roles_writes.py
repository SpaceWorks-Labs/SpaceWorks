"""Apply projected reference changes using historical classes and one DB alias."""

from apps.makerspaces.role_migration_mapping import FROZEN_BY_SLUG
from apps.makerspaces.migration_support.fixed_roles_audit import record


def migrate_memberships(models, alias, projection, canonical_ids):
    memberships = models["makerspaces.MakerspaceMembership"].objects.using(alias)
    additional = models["makerspaces.MembershipAdditionalRole"].objects.using(alias)
    scopes = models["machines.MembershipMachineTypeScope"].objects.using(alias)
    for row in projection["memberships"]:
        primary = row["primary_slug"]
        if primary is None:  # Null-FK legacy fallback is explicitly untouched.
            continue
        space_id, membership_id = row["makerspace_id"], row["id"]
        memberships.filter(pk=membership_id).update(
            assigned_role_id=canonical_ids[(space_id, primary)],
            role=FROZEN_BY_SLUG[primary][2] or "custom",
        )
        additional.bulk_create([
            models["makerspaces.MembershipAdditionalRole"](
                membership_id=membership_id, role_id=canonical_ids[(space_id, slug)],
                assigned_by_id=None,
            ) for slug in row["additional_slugs"]
        ])
        scopes.bulk_create([
            models["machines.MembershipMachineTypeScope"](
                membership_id=membership_id, machine_type_id=type_id,
            ) for type_id in row["machine_scope"]["to"]["types"]
        ])
        if row["changed"]:
            record(space_id, "staff.roles_migrated", "makerspaces.makerspacemembership",
                  membership_id, models=models, alias=alias, meta={
                      "membership_id": membership_id, "from_role": row["from_role"],
                      "to_roles": row["to_roles"], "dropped_actions": row["dropped_actions"],
                      "gained_actions": row["gained_actions"], "exception_tags": row["exception_tags"],
                      "machine_scope_outcome": row["machine_scope_outcome"],
                      "machine_scope": row["machine_scope"],
                  })


def migrate_references(models, alias, projection, canonical_ids, now):
    requests = models["makerspaces.MembershipRequest"].objects.using(alias)
    for row in projection["requests"]:
        target = canonical_ids[(row["makerspace_id"], row["primary_slug"])]
        requests.filter(pk=row["id"]).update(assigned_role_id=target)
        if row["assigned_role_id"] != target:
            record(row["makerspace_id"], "staff.roles_migrated", "makerspaces.membershiprequest",
                  row["id"], models=models, alias=alias, meta={"membership_request_id": row["id"],
                              "old_role_id": row["assigned_role_id"],
                              "to_roles": [row["primary_slug"]], "state": row["state"]})

    invitations = models["accounts.StaffInvitation"].objects.using(alias)
    for row in projection["invitations"]:
        target = canonical_ids[(row["makerspace_id"], row["primary_slug"])]
        updates = {"role_id": target}
        if row["resnapshot"]:
            updates["granted_actions"] = sorted(FROZEN_BY_SLUG[row["primary_slug"]][3])
        if row["revoke"]:
            updates["revoked_at"] = now
        invitations.filter(pk=row["id"]).update(**updates)
        if row["revoke"] or target != row["role_id"] or (
            row["resnapshot"] and updates["granted_actions"] != row["granted_actions"]
        ):
            audit_invitation(models, alias, row)

    schedules = models["operations.ReportSchedule"].objects.using(alias)
    for row in projection["schedules"]:
        schedules.filter(pk=row["id"]).update(
            recipient_roles=row["after_roles"],
            is_active=False if row["deactivate"] else row["is_active"],
        )
        record(row["makerspace_id"], "report_schedule.recipients_pruned_by_migration",
              "operations.reportschedule", row["id"], models=models, alias=alias, meta={
                  "schedule_id": row["id"], "before_roles": row["recipient_roles"],
                  "after_roles": row["after_roles"], "deactivated": row["deactivate"],
              })


def audit_invitation(models, alias, row):
    if row["revoke"]:
        record(row["makerspace_id"], "staff.invitation_revoked_by_migration",
               "accounts.staffinvitation", row["id"], models=models, alias=alias, meta={
                   "invitation_id": row["id"], "old_role_id": row["role_id"],
                   "original_granted_actions": row["granted_actions"],
                   "to_roles": [row["primary_slug"]], "revoked": True,
               })
    else:
        record(row["makerspace_id"], "staff.roles_migrated", "accounts.staffinvitation",
               row["id"], models=models, alias=alias, meta={
                   "invitation_id": row["id"], "old_role_id": row["role_id"],
                   "original_granted_actions": row["granted_actions"],
                   "to_roles": [row["primary_slug"]], "revoked": False,
               })
