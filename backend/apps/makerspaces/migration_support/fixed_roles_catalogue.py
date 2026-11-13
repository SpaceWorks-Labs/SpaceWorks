"""Collision-safe Step E; only historical role models supplied by the migration."""

from apps.makerspaces.role_migration_mapping import FROZEN_CATALOG


def canonicalize_roles(role_model, alias, snapshot, obsolete_ids):
    originals = snapshot["makerspaces.MakerspaceRole"]
    obsolete_ids = set(obsolete_ids)
    canonical_names = {entry[1].casefold() for entry in FROZEN_CATALOG}
    canonical_slugs = {entry[0].casefold() for entry in FROZEN_CATALOG}
    used_names, used_slugs = {}, {}
    for row in originals:
        space_id = row["makerspace_id"]
        used_names.setdefault(space_id, set()).add(row["name"].casefold())
        used_slugs.setdefault(space_id, set()).add(row["slug"].casefold())
    query = role_model.objects.using(alias)

    def unique(base, suffix, used):
        # Preserve the id suffix within CharField(max_length=80). Include a counter
        # if a user already chose our temporary/custom spelling before upgrading.
        counter = 0
        while True:
            tail = suffix + (f"-{counter}" if counter else "")
            candidate = base[:80 - len(tail)] + tail
            if candidate.casefold() not in used:
                used.add(candidate.casefold())
                return candidate
            counter += 1

    # (i) Rename every colliding obsolete row BEFORE moving defaults or seeding.
    for row in originals:
        if row["id"] not in obsolete_ids:
            continue
        space_id = row["makerspace_id"]
        updates = {"legacy_role": None, "is_default": False}
        if row["name"].casefold() in canonical_names:
            updates["name"] = unique(row["name"], f" (custom {row['id']})", used_names[space_id])
        if row["slug"].casefold() in canonical_slugs:
            updates["slug"] = unique(row["slug"], f"-custom-{row['id']}", used_slugs[space_id])
        query.filter(pk=row["id"]).update(**updates)

    survivors = [row for row in originals if row["id"] not in obsolete_ids]
    # (ii) Move ALL surviving defaults out of the name namespace first. Clear the
    # legacy mirror too, since historical edits may have swapped those unique values.
    for row in survivors:
        temporary = unique("", f"__fixed_roles_tmp_{row['id']}", used_names[row["makerspace_id"]])
        query.filter(pk=row["id"]).update(name=temporary, legacy_role=None, is_protected=True)

    by_key = {(row["makerspace_id"], row["slug"]): row["id"] for row in survivors}
    canonical_ids = {}
    for space in snapshot["makerspaces.Makerspace"]:
        for slug, name, legacy, actions in FROZEN_CATALOG:
            key = (space["id"], slug)
            fields = {
                "name": name, "slug": slug, "legacy_role": legacy,
                "granted_actions": sorted(actions), "is_default": True, "is_protected": True,
            }
            # (iii) Seed missing entries (including the three new roles) only after
            # every survivor is temporary. Restoration is a distinct pass below.
            if key not in by_key:
                canonical_ids[key] = query.create(makerspace_id=space["id"], **fields).pk
            else:
                canonical_ids[key] = by_key[key]

    # (iv) Restore surviving canonical names, grants, mirrors and flags last.
    for row in survivors:
        entry = next(entry for entry in FROZEN_CATALOG if entry[0] == row["slug"])
        query.filter(pk=row["id"]).update(
            name=entry[1], legacy_role=entry[2], granted_actions=sorted(entry[3]),
            is_default=True, is_protected=True,
        )
    return canonical_ids
