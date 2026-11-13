"""What a merge will do, shown before the person confirms it (U-C preview).

- ``privilege_diff``: the staff roles the survivor gains per makerspace (a source staff row
  moves only where the survivor has none; a duplicate staff row stays on the shell,
  revoked), and whether the survivor's 3-day staff-MFA grace opens (#128 C-1).
- ``moves``: per disposition, how many rows move to the survivor and how many stay on the
  shell; ``conflicts``: the UNIQUE_RESOLVE slots the survivor already holds.

``preview_sha256`` digests exactly this content; confirm refuses when it changed since the
person looked (``preview_stale``).
"""

import hashlib
import json

from apps.accounts import account_merge_walk as walk


def _staff_rows(user):
    from apps.makerspaces.models import MakerspaceMembership

    return list(MakerspaceMembership.staff_tracks.filter(user_id=user.pk, status="active")
                .select_related("makerspace", "assigned_role").order_by("makerspace_id"))


def _role_slugs(row):
    from apps.accounts.rbac_roles import membership_roles

    return sorted(role.slug for role in membership_roles(row))


def privilege_diff(survivor, source):
    held = {row.makerspace_id for row in _staff_rows(survivor)}
    gained, kept_on_shell = [], []
    for row in _staff_rows(source):
        entry = {"makerspace": {"id": row.makerspace_id, "slug": row.makerspace.slug, "name": row.makerspace.name},
                 "roles": _role_slugs(row)}
        (kept_on_shell if row.makerspace_id in held else gained).append(entry)
    return {"roles_gained": gained, "duplicate_staff_rows": kept_on_shell}


def has_factor(user):
    from apps.accounts.models_mfa import UserMFA
    from apps.accounts.models_webauthn import WebAuthnCredential

    return (UserMFA.objects.filter(user_id=user.pk, enabled_at__isnull=False).exists()
            or WebAuthnCredential.objects.filter(user_id=user.pk).exists())


def grace_opens(survivor, source, diff):
    """The survivor becomes staff without a factor and has never had a grace (#128 C-1)."""
    from apps.accounts.models_mfa_grace import StaffMfaGrace
    from apps.accounts.staff_identity import has_staff_role

    if not diff["roles_gained"] or has_staff_role(survivor) or has_factor(survivor):
        return False
    return not StaffMfaGrace.objects.filter(user_id__in=[survivor.pk, source.pk]).exists()


def moves(survivor, source):
    plan = walk.plan(source.pk, survivor.pk)
    totals = {walk.REPOINT: 0, walk.KEEP_ON_SHELL: 0, walk.UNIQUE_RESOLVE: 0}
    conflicts = []
    for (label, column), entry in sorted(plan.items()):
        totals[entry["disposition"]] += entry["rows"]
        if entry["disposition"] == walk.UNIQUE_RESOLVE and entry["keep"]:
            conflicts.append({"model": label, "field": column, "kept_on_shell": entry["keep"]})
    by_disposition = {
        "repoint": {"rows": totals[walk.REPOINT]},
        "keep_on_shell": {"rows": totals[walk.KEEP_ON_SHELL]},
        "unique_resolve": {"rows": totals[walk.UNIQUE_RESOLVE],
                           "kept_on_shell": sum(item["kept_on_shell"] for item in conflicts)},
    }
    return by_disposition, conflicts


def build(survivor, source):
    diff = privilege_diff(survivor, source)
    by_disposition, conflicts = moves(survivor, source)
    body = {
        "source": {"id": source.pk, "username": source.username, "display_name": source.display_name},
        "privilege_diff": diff,
        "grace_opens": grace_opens(survivor, source, diff),
        "moves": by_disposition,
        "conflicts": conflicts,
    }
    body["preview_sha256"] = digest(body)
    return body


def digest(body):
    content = {key: value for key, value in body.items() if key != "preview_sha256"}
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
