"""Pure pre-write projection of the frozen snapshot. Shared with the dry-run."""

from collections import defaultdict

from apps.makerspaces.role_migration_mapping import (
    FROZEN_BY_SLUG, classify_role, map_role,
)


OPEN_REQUEST_STATES = frozenset({"requested", "invited", "awaiting_vouches", "awaiting_payment"})


def build_projection(snapshot):
    roles = {row["id"]: row for row in snapshot["makerspaces.MakerspaceRole"]}
    obsolete = {
        pk for pk, role in roles.items()
        if classify_role(role, role["makerspace_id"]) == "obsolete"
    }
    type_links, machine_links = defaultdict(set), defaultdict(set)
    for role_id, type_id in snapshot["role_type_links"]:
        type_links[role_id].add(type_id)
    for role_id, machine_id in snapshot["role_machine_links"]:
        machine_links[role_id].add(machine_id)
    type_owners = {row["id"]: row["makerspace_id"] for row in snapshot["machines.MachineType"]}
    tenant_types = {}

    def mapping(space_id, role_id):
        role = roles.get(role_id)
        classification = classify_role(role, space_id)
        if role_id is not None and role is None:
            raise ValueError(f"Missing original role {role_id} in makerspace {space_id}")
        if space_id not in tenant_types:
            tenant_types[space_id] = {pk for pk, owner in type_owners.items() if owner in {None, space_id}}
        allowed_types = tenant_types[space_id]
        return map_role(
            classification=classification, slug=role["slug"] if role else None,
            raw_grants=role["granted_actions"] if role else (),
            # Preserve stored type links verbatim. Silently filtering a historical
            # mislink could turn a nonempty inert scope into the empty-scope alert
            # fallback. Tenant-scoped runtime readers keep those mislinks inert.
            type_ids=type_links[role_id],
            machine_ids=machine_links[role_id], all_type_ids=allowed_types,
        )

    refused = []
    for row in snapshot["integrations.NotificationRecipient"]:
        if row["kind"] == "role" and row["role_id"] in obsolete:
            role = roles[row["role_id"]]
            refused.append({**row, "role_slug": role["slug"], "role_name": role["name"]})

    memberships = []
    for row in snapshot["makerspaces.MakerspaceMembership"]:
        role = roles.get(row["assigned_role_id"])
        result = mapping(row["makerspace_id"], row["assigned_role_id"])
        primary = result["primary_slug"]
        changed = primary is not None and (
            role["makerspace_id"] != row["makerspace_id"]
            or role["id"] in obsolete or role["slug"] != primary
            or role["name"] != FROZEN_BY_SLUG[primary][1] or not role["is_protected"]
            or role["legacy_role"] != FROZEN_BY_SLUG[primary][2]
            or row["role"] != (FROZEN_BY_SLUG[primary][2] or "custom")
            or bool(result["additional_slugs"] or result["dropped_actions"]
                    or result["gained_actions"])
            or result["machine_scope_outcome"] in {
                "copy_type_ids", "enumerate_all_types",
                "machine_manager_dropped: machine-only scope",
            }
            or bool(result["machine_scope"]["dropped_machine_ids"])
        )
        memberships.append({
            **row, **result, "changed": changed,
            "from_role": ({"id": role["id"], "slug": role["slug"], "name": role["name"],
                           "granted_actions": role["granted_actions"]} if role else None),
        })

    requests = []
    for row in snapshot["makerspaces.MembershipRequest"]:
        if row["assigned_role_id"] is None:
            continue  # No role reference: nothing protects a delete, nothing to change.
        result = mapping(row["makerspace_id"], row["assigned_role_id"])
        original = roles[row["assigned_role_id"]]
        if row["state"] in OPEN_REQUEST_STATES:
            primary = result["primary_slug"] or "member"
        elif classify_role(original, row["makerspace_id"]) == "catalogue_default":
            primary = original["slug"]  # Closed history on a kept built-in stays put.
        else:
            primary = "member"
        requests.append({**row, "primary_slug": primary})

    invitations = []
    for row in snapshot["accounts.StaffInvitation"]:
        original = roles[row["role_id"]]
        result = mapping(row["makerspace_id"], row["role_id"])
        primary = result["primary_slug"] or "member"
        canonical = FROZEN_BY_SLUG[primary][3]
        pending = row["accepted_at"] is None and row["revoked_at"] is None
        accepted = (
            pending and row["granted_actions"] == sorted(original["granted_actions"])
            and canonical <= frozenset(row["granted_actions"]) and primary != "member"
        )
        if accepted:
            target = primary
        elif not pending and classify_role(original, row["makerspace_id"]) == "catalogue_default":
            # Closed history on a kept built-in keeps its role; only obsolete/foreign
            # references must move before their row is deleted.
            target = original["slug"]
        else:
            target = "member"
        invitations.append({
            **row, "primary_slug": target,
            "revoke": pending and not accepted, "resnapshot": accepted,
        })

    obsolete_slugs = defaultdict(set)
    for pk in obsolete:
        obsolete_slugs[roles[pk]["makerspace_id"]].add(roles[pk]["slug"])
    schedules = []
    for row in snapshot["operations.ReportSchedule"]:
        before = row["recipient_roles"]
        after = [slug for slug in before if slug not in obsolete_slugs[row["makerspace_id"]]]
        if after != before:
            no_destination = not (after or row["recipient_actions"] or row["recipient_emails"]
                                  or row["destination_id"])
            schedules.append({**row, "after_roles": after, "deactivate": no_destination})

    return {
        "makerspaces": snapshot["makerspaces.Makerspace"], "refused_recipient_rules": refused,
        "memberships": memberships, "requests": requests, "invitations": invitations,
        "schedules": schedules, "obsolete_role_ids": sorted(obsolete),
    }


def refusal_message(rows):
    return "must fix before upgrading: obsolete/custom role notification rules: " + "; ".join(
        f"recipient={row['id']} makerspace={row['makerspace_id']} feature={row['feature']} "
        f"event={row['event']} role={row['role_id']} ({row['role_slug']}: {row['role_name']})"
        for row in rows
    )
