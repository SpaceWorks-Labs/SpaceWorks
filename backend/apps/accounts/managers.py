"""Creation policy shared by Django's createsuperuser and account services."""

from django.contrib.auth.models import UserManager as DjangoUserManager


class UserManager(DjangoUserManager):
    def create_user(self, username, email=None, password=None, *, account_kind="member",
                    staff_makerspace=None, **extra_fields):
        if account_kind not in {"member", "staff", "platform"}:
            raise ValueError("Unknown account kind.")
        if (account_kind == "staff") != (staff_makerspace is not None):
            raise ValueError("Staff accounts require exactly one makerspace.")
        platform = account_kind == "platform"
        if extra_fields.get("is_superuser", platform) != platform:
            raise ValueError("Only platform accounts may be superusers.")
        role = extra_fields.setdefault("role", "superadmin" if platform else "requester")
        if (role == "superadmin") != platform:
            raise ValueError("Platform accounts must use the superadmin role.")
        extra_fields["is_superuser"] = platform
        extra_fields.setdefault("is_staff", platform)
        return self._create_user(username, email, password, account_kind=account_kind,
                                 staff_makerspace=staff_makerspace, **extra_fields)

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("account_kind", "platform")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields["account_kind"] != "platform" or not extra_fields["is_staff"]:
            raise ValueError("Superusers must be platform staff accounts.")
        return self.create_user(username, email, password, **extra_fields)
