"""D11: carried staff are new tenant principals, never linked target identities."""

from apps.accounts.models import User
from apps.accounts.username_allocation import allocate_staff_username
from apps.makerspaces.role_catalog import ROLE_BY_SLUG

from .insertion_errors import ArchiveFormatError, IdentityResolutionError
from .archive_stream import database_value


def is_staff_row(label, row):
    if label in {"makerspaces.MembershipAdditionalRole", "machines.MembershipMachineTypeScope"}:
        user = row.membership.user
    elif label in {"makerspaces.MakerspaceMembership", "notifications.MemberNotificationPreference", "notifications.NotificationPreference"}:
        user = row.user
    else:
        return False
    return user.account_kind == "staff" and user.retired_at is None


class StaffArchiveContext:
    def __init__(self, archive):
        tenant = next(archive.raw_rows("makerspaces.Makerspace"))["id"]
        self.users = {}
        for row in archive.raw_rows("accounts.User"):
            if row.get("account_kind") != "staff":
                continue
            if str(row.get("staff_makerspace_id")) != str(tenant):
                raise ArchiveFormatError("A staff identity belongs to a different source tenant.")
            self.users[str(row["id"])] = row
        self.roles = {
            str(row["id"]): row["slug"] for row in archive.raw_rows("makerspaces.MakerspaceRole")
            if str(row["makerspace_id"]) == str(tenant)
            and str(row.get("is_default", "")).lower() == "true"
            and str(row.get("is_protected", "")).lower() == "true"
        }
        self.memberships = {
            str(row["id"]): str(row["user_id"])
            for row in archive.raw_rows("makerspaces.MakerspaceMembership")
            if str(row["user_id"]) in self.users
        }

    def decorate(self, label, row):
        staff = False
        role_field = None
        if label == "accounts.User":
            staff = str(row["id"]) in self.users
        elif label == "makerspaces.MakerspaceMembership":
            staff = str(row["user_id"]) in self.users
            role_field = "assigned_role_id"
        elif label in {"makerspaces.MembershipAdditionalRole", "machines.MembershipMachineTypeScope"}:
            staff = str(row["membership_id"]) in self.memberships
            role_field = "role_id" if label.endswith("MembershipAdditionalRole") else None
        elif label in {"notifications.MemberNotificationPreference", "notifications.NotificationPreference"}:
            staff = str(row["user_id"]) in self.users
        row = {**row, "_staff_account": staff}
        if staff and role_field:
            slug = self.roles.get(str(row[role_field]))
            if slug not in ROLE_BY_SLUG or slug == "member":
                raise ArchiveFormatError("A carried staff role is not a source tenant built-in role.")
            row["_staff_role_slug"] = slug
        return row


def validate_staff_decision(source, decision):
    if (decision.identity_resolution != decision.IdentityResolution.CREATE_WALK_IN
            or decision.target_user_id is not None
            or decision.membership_disposition == decision.MembershipDisposition.NO_MEMBERSHIP):
        raise IdentityResolutionError("Carried staff must create a new account and retain their membership.")


def create_staff_identity(source, target_pk, target):
    def create(username):
        user = User(pk=target_pk, username=username, account_kind="staff", staff_makerspace=target,
            email=source.get("email", ""), first_name=source.get("first_name", ""),
            last_name=source.get("last_name", ""), display_name=source.get("display_name", ""),
            phone=source.get("phone", ""),
            date_joined=database_value(User._meta.get_field("date_joined"), source["date_joined"]),
            must_change_password=True,
            is_active=database_value(User._meta.get_field("is_active"), source.get("is_active", "true")),
            is_staff=False, is_superuser=False)
        user.set_unusable_password()
        user.save(force_insert=True)
        return user
    return allocate_staff_username(source.get("username", "staff"), target.slug, create=create)


def create_provenance_stub(source, target_pk):
    from uuid import uuid4
    from .tenant_dump_user_rows import _stub_values
    values = _stub_values(uuid4().hex)
    User.objects.create(pk=target_pk, **values)


def apply_staff_role(model, source, row, target):
    if not source.get("_staff_account"):
        return False
    slug = source.get("_staff_role_slug")
    if slug:
        field = "assigned_role" if model._meta.label.endswith("MakerspaceMembership") else "role"
        row[model._meta.get_field(field).column] = target.roles.get(
            slug=slug, is_protected=True, is_default=True).pk
        if field == "assigned_role":
            row["role"] = ROLE_BY_SLUG[slug].legacy_role or "custom"
    return True
