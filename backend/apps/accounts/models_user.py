from django.utils.translation import gettext_lazy
from django.contrib.auth.models import AbstractUser
from django.db import models

from config.locale_registry import validate_supported_locale
from .managers import UserManager
from .account_constraints import user_constraints
from .account_kind_guards import guard_account_identity


def _normalized_email(value):
    return (value or "").strip().lower()


class User(AbstractUser):
    # One account per person. ``member`` IS the person (exposed as ``person`` in the
    # API); ``platform`` is the superadmin. ``staff`` survives only for inert shells:
    # legacy retired staff accounts and accounts merged into a person (``merged_into``).
    # Staff authority is a staff-TRACK membership on a person, never an account kind.
    class AccountKind(models.TextChoices):
        MEMBER = "member", "Person"
        STAFF = "staff", gettext_lazy("Inert shell")
        PLATFORM = "platform", "Platform"

    objects = UserManager()
    account_kind = models.CharField(max_length=16, choices=AccountKind.choices, default=AccountKind.MEMBER)
    staff_makerspace = models.ForeignKey(
        "makerspaces.Makerspace", on_delete=models.PROTECT, null=True, blank=True,
        related_name="staff_accounts",
    )
    retired_at = models.DateTimeField(null=True, blank=True)
    # An alias, not a delete: immutable history (audit actor, evidence, scans, ledger)
    # keeps pointing at the shell, and ``staff_identity.actor_ids_for`` follows it.
    merged_into = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="merged_shells",
    )
    merged_at = models.DateTimeField(null=True, blank=True)
    credential_generation = models.PositiveIntegerField(default=0)
    deletion_requested_at = models.DateTimeField(null=True, blank=True)
    deletion_purge_after = models.DateTimeField(null=True, blank=True)
    purge_started_at = models.DateTimeField(null=True, blank=True)
    account_restored_at = models.DateTimeField(null=True, blank=True)
    account_purged_at = models.DateTimeField(null=True, blank=True)
    deletion_email_ciphertext = models.TextField(blank=True, default="")
    deletion_username = models.CharField(max_length=150, blank=True, default="")

    class Role(models.TextChoices):
        SUPERADMIN = "superadmin", gettext_lazy("Super Admin")
        SPACE_MANAGER = "space_manager", gettext_lazy("Space Manager")
        REQUESTER = "requester", "Requester"

    class AccessStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        RESTRICTED = "restricted", "Restricted"
        SUSPENDED = "suspended", "Suspended"

    # Free-text contact info, copied onto requests/bookings as text. Stays exactly as
    # the user typed it, non-unique: two members may legitimately share a landline.
    phone = models.CharField(max_length=32, blank=True)
    # The LOGIN IDENTITY -- a separate, canonical E.164 column, deliberately not the
    # same field. Reusing `phone` would have meant rewriting existing free-text values
    # in a migration and putting a unique index on a column that already holds
    # duplicates in real deployments. This one starts empty everywhere, so its
    # constraint always applies cleanly.
    phone_e164 = models.CharField(max_length=20, blank=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    display_name = models.CharField(max_length=200, blank=True)
    # Phase 8 i18n: the account's own language; null means "use the makerspace default".
    # Platform account data, changed only by its owner through PATCH /auth/me.
    preferred_locale = models.CharField(
        max_length=16, null=True, blank=True, default=None, validators=[validate_supported_locale],
    )
    email_verified_at = models.DateTimeField(null=True, blank=True)
    # Provenance matters for login: only accounts created by the anonymous signup
    # flow must remain verification-only until they prove ownership of their email.
    # Staff-created users may legitimately start without an email verification stamp.
    self_registered_at = models.DateTimeField(null=True, blank=True)
    telegram_user_id = models.CharField(max_length=64, blank=True)
    must_change_password = models.BooleanField(default=False)
    # A staff-created person record, not an account. An unusable password alone is NOT
    # enough to keep it that way: the reset-envelope drain resolves an active user by
    # email and OTP confirmation calls `set_password`, so a walk-in given an email address
    # could otherwise become a real login. This flag is checked under the user lock at
    # issuance and confirmation. See `makerspaces.walk_in_services`.
    is_walk_in = models.BooleanField(default=False)
    # Lane D keeps shared/deployment-global people only as FK-closing rows.  This
    # marker is deliberately independent from the mutable account fields below:
    # authentication and authorization refuse it even if an operator later edits
    # ``is_active``, the password, or a role.
    is_tenant_dump_stub = models.BooleanField(default=False)
    role = models.CharField(
        max_length=32,
        choices=Role.choices,
        default=Role.REQUESTER,
    )
    access_status = models.CharField(
        max_length=32,
        choices=AccessStatus.choices,
        default=AccessStatus.ACTIVE,
    )
    restriction_reason = models.TextField(blank=True)

    class Meta(AbstractUser.Meta):
        constraints = user_constraints()

    # The two identity columns whose stored value must be known before a save can tell
    # whether they changed. Snapshotting is deliberately split from reading them.
    _IDENTITY_SNAPSHOT_FIELDS = ("email", "phone_e164")

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        # Snapshot ONLY the columns this query actually loaded. Reading `instance.email`
        # unconditionally forces a deferred load, and because `refresh_from_db` issues
        # its own `.only(<field>)` query, the instance it builds re-enters `from_db`
        # with the OTHER identity column deferred -- so the two snapshots load each
        # other forever. Any `.only()`/`.defer()` query on User omitting either column
        # raised RecursionError, which is what broke `/analytics/top-borrowers`.
        loaded = dict(zip(field_names, values))
        for field in cls._IDENTITY_SNAPSHOT_FIELDS:
            if field in loaded:
                setattr(instance, f"_loaded_{field}", loaded[field])
        return instance

    def _identity_baseline(self):
        """Stored values of the identity columns, for a row loaded without them.

        A deferred load leaves no snapshot, and treating a missing baseline as "nothing
        changed" would keep a verified stamp on an edited address or number -- the exact
        bypass the guards in `save` exist to prevent. Costs one query, and only when a
        deferred instance is being saved; a fully-loaded instance already has both.
        """
        baseline = {
            field: getattr(self, f"_loaded_{field}", None)
            for field in self._IDENTITY_SNAPSHOT_FIELDS
        }
        if all(value is not None for value in baseline.values()):
            return baseline
        if not self.pk or self._state.adding:
            # Nothing stored yet, so no change to detect and no stamp to protect.
            return baseline
        stored = (
            type(self)
            ._base_manager.filter(pk=self.pk)
            .values(*self._IDENTITY_SNAPSHOT_FIELDS)
            .first()
        )
        if stored is None:
            return baseline
        return {
            field: stored[field] if value is None else value
            for field, value in baseline.items()
        }

    def save(self, *args, **kwargs):
        guard_account_identity(self, using=kwargs.get("using"))
        # Changing a verified email must re-require verification: an admin/self email
        # edit clears email_verified_at (outstanding challenges reference the old email
        # snapshot and can no longer match the new current email, so they lapse).
        baseline = self._identity_baseline()
        cleared = []
        if baseline["email"] is not None and _normalized_email(
            baseline["email"]
        ) != _normalized_email(self.email):
            self.email_verified_at = None
            cleared.append("email_verified_at")
        # The same rule for the phone identity, and it matters more here: phone_e164 is
        # what the OTP login resolves an account by, so an edited number that kept its
        # verified stamp would let whoever holds the NEW number sign in as this user
        # without ever proving they hold it. /control/ can edit this field, so the guard
        # cannot live only in the linking service.
        if (
            baseline["phone_e164"] is not None
            and baseline["phone_e164"] != self.phone_e164
        ):
            self.phone_verified_at = None
            cleared.append("phone_verified_at")
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and cleared:
            kwargs["update_fields"] = list(update_fields) + [
                name for name in cleared if name not in update_fields
            ]
        super().save(*args, **kwargs)
        # Re-snapshot only what is actually present: assigning from a deferred field here
        # would force the same load `from_db` must avoid.
        deferred = self.get_deferred_fields()
        for field in self._IDENTITY_SNAPSHOT_FIELDS:
            if field not in deferred:
                setattr(self, f"_loaded_{field}", getattr(self, field))

