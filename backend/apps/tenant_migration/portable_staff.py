"""One account per person: staff-track rows travel WITH their person (U-D).

There is no staff identity any more. A person's staff-track membership, its additional
roles and machine-type scopes, and the person's notification choices in this space travel
with that person under the ordinary link/create decision. Their built-in roles resolve by
protected slug to the target's seeded roles. A person LINKED to an existing target person
arrives with every staff-track row REVOKED unless the superadmin granted them explicitly
(``ImportIdentityDecision.grant_staff_roles``); a created person keeps the source status.

An archive written before one account per person (the split format, Q11) converts one
version back: its roster has no ``track`` column, and a staff account's rows (built-in
staff roles only, M4) become staff-track rows of that same person, now a person.
"""

from django.utils import timezone

from apps.makerspaces.role_catalog import ROLE_BY_SLUG

from .insertion_errors import ArchiveFormatError

MEMBERSHIP = "makerspaces.MakerspaceMembership"
STAFF_CHILD_LABELS = frozenset({"makerspaces.MembershipAdditionalRole", "machines.MembershipMachineTypeScope", "machines.MembershipMachineScope"})
PREFERENCE_LABELS = frozenset({"notifications.MemberNotificationPreference", "notifications.NotificationPreference"})
STAFF, COMMUNITY = "staff", "community"
SPLIT_STAFF_KIND = "staff"


def is_staff_row(label, row):
    """Source model instance: does this row belong to a staff-track membership?"""
    from apps.makerspaces.models import MakerspaceMembership

    if label == MEMBERSHIP:
        return row.track == STAFF
    if label in STAFF_CHILD_LABELS:
        return MakerspaceMembership.staff_tracks.filter(pk=row.membership_id).exists()
    if label in PREFERENCE_LABELS:
        return MakerspaceMembership.staff_tracks.filter(user_id=row.user_id, makerspace_id=row.makerspace_id).exists()
    return False


class StaffArchiveContext:
    def __init__(self, archive):
        tenant = str(next(archive.raw_rows("makerspaces.Makerspace"))["id"])
        self.roles = {
            str(row["id"]): row["slug"] for row in archive.raw_rows("makerspaces.MakerspaceRole")
            if str(row["makerspace_id"]) == tenant
            and str(row.get("is_default", "")).lower() == "true"
            and str(row.get("is_protected", "")).lower() == "true"
        }
        # Split format only: live staff accounts (a current archive's "staff" rows are shells).
        self.split_staff = {str(row["id"]) for row in archive.raw_rows("accounts.User")
                            if row.get("account_kind") == SPLIT_STAFF_KIND and row.get("staff_makerspace_id")}
        self.memberships = {str(row["id"]): str(row["user_id"]) for row in archive.raw_rows(MEMBERSHIP)
                            if self._track(row) == STAFF}
        self.staff_users = set(self.memberships.values())

    def _track(self, row):
        if row.get("track"):
            return row["track"]
        return STAFF if str(row["user_id"]) in self.split_staff else COMMUNITY

    def decorate(self, label, row):
        staff, role_field = False, None
        if label == "accounts.User":
            if str(row["id"]) in self.split_staff:
                row = {**row, "account_kind": "member"}
        elif label == MEMBERSHIP:
            row = {**row, "track": self._track(row)}
            staff, role_field = row["track"] == STAFF, "assigned_role_id"
        elif label in STAFF_CHILD_LABELS:
            staff = str(row["membership_id"]) in self.memberships
            role_field = "role_id" if label.endswith("MembershipAdditionalRole") else None
        elif label in PREFERENCE_LABELS:
            staff = str(row["user_id"]) in self.staff_users
        row = {**row, "_staff_account": staff}
        if staff and role_field:
            slug = self.roles.get(str(row[role_field]))
            if slug not in ROLE_BY_SLUG or slug == "member":
                raise ArchiveFormatError("A carried staff role is not a source tenant built-in role.")
            row["_staff_role_slug"] = slug
        return row


def create_provenance_stub(source, target_pk):
    from uuid import uuid4

    from apps.accounts.models import User

    from .tenant_dump_user_rows import _stub_values
    User.objects.create(pk=target_pk, **_stub_values(uuid4().hex))


def apply_staff_role(model, source, row, target, job=None):
    """Resolve a carried staff row's built-in role; a linked person's row stays revoked."""
    if not source.get("_staff_account"):
        return False
    slug = source.get("_staff_role_slug")
    if slug:
        field = "assigned_role" if model._meta.label == MEMBERSHIP else "role"
        row[model._meta.get_field(field).column] = target.roles.get(
            slug=slug, is_protected=True, is_default=True).pk
        if field == "assigned_role":
            row["role"] = ROLE_BY_SLUG[slug].legacy_role or "custom"
    if model._meta.label == MEMBERSHIP and job is not None and not staff_roles_kept(job, source["user_id"]):
        row["status"] = "revoked"
        row["revoked_at"] = row.get("revoked_at") or timezone.now()
    return True


def staff_roles_kept(job, source_user_id):
    from .identity_resolution import decision_for_source_user

    decision = decision_for_source_user(job, source_user_id)
    return (decision.identity_resolution != decision.IdentityResolution.LINK_EXISTING
            or decision.grant_staff_roles)
