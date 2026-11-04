"""Creation policy shared by Django's createsuperuser and account services.

One account per person: new accounts are people (``member``) or platform. Staff
authority is granted later as a staff-track membership, never as an account kind; the
``staff`` kind is reserved for inert shells, which only a tenant import creates.
"""

from django.contrib.auth.models import UserManager as DjangoUserManager


class UserManager(DjangoUserManager):
    def create_user(self, username, email=None, password=None, *, account_kind="member", **extra_fields):
        if account_kind not in {"member", "platform"}:
            raise ValueError("New accounts are people or platform accounts; grant staff roles instead.")
        if extra_fields.get("staff_makerspace") is not None or extra_fields.get("staff_makerspace_id"):
            raise ValueError("Staff authority is a staff-track membership, not an account tenant.")
        platform = account_kind == "platform"
        if extra_fields.get("is_superuser", platform) != platform:
            raise ValueError("Only platform accounts may be superusers.")
        role = extra_fields.setdefault("role", "superadmin" if platform else "requester")
        if (role == "superadmin") != platform:
            raise ValueError("Platform accounts must use the superadmin role.")
        extra_fields["is_superuser"] = platform
        extra_fields.setdefault("is_staff", platform)
        return self._create_user(username, email, password, account_kind=account_kind, **extra_fields)

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("account_kind", "platform")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields["account_kind"] != "platform" or not extra_fields["is_staff"]:
            raise ValueError("Superusers must be platform staff accounts.")
        return self.create_user(username, email, password, **extra_fields)
