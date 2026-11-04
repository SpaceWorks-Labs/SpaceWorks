"""Settings authority: per-person module grants and Space Manager locks (#101, #128 C-11).

Rows are written only by ``apps.makerspaces.settings_authority``, which audits every write.
Both tables are append-only history: a grant or lock is never edited or deleted, it is
ended once (``revoked_at`` / ``released_at``) and a new row starts the next period. At most
one live row exists per key, enforced in the database. The whole-tenant purge removes them
with their makerspace.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class _AppendOnly(models.Model):
    # The only permitted UPDATE ends a live row; everything else is a new row.
    _END_FIELDS = ()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk is not None and set(kwargs.get("update_fields") or ()) - set(self._END_FIELDS):
            raise ValueError(f"{type(self).__name__} is append-only; only ending a live row is allowed.")
        if self.pk is not None and not kwargs.get("update_fields"):
            raise ValueError(f"{type(self).__name__} is append-only; pass update_fields to end it.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError(f"{type(self).__name__} is append-only and is never deleted.")


class ModuleSettingsGrant(_AppendOnly):
    """A Space Manager lets ONE person (C-11a) change one module's settings in one space."""

    _END_FIELDS = ("revoked_at", "revoked_by")

    makerspace = models.ForeignKey(
        "makerspaces.Makerspace", on_delete=models.CASCADE, related_name="settings_grants",
    )
    # A settings module from `settings_authority.MODULE_MANAGER_ACTIONS`, not a module key:
    # `inventory` has no key of its own.
    module = models.CharField(max_length=32)
    grantee = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+",
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    granted_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("makerspace", "module", "grantee"), condition=Q(revoked_at__isnull=True),
                name="settings_grant_one_live_per_person",
            ),
        ]
        indexes = [models.Index(fields=("makerspace", "module"), name="settings_grant_space_module_idx")]
        ordering = ("module", "granted_at", "id")

    def __str__(self):
        return f"{self.makerspace_id}:{self.module}:{self.grantee_id}"


class ModuleSettingLock(_AppendOnly):
    """A Space Manager lock: no delegated edit of this setting, fixed exceptions included."""

    _END_FIELDS = ("released_at", "released_by")

    makerspace = models.ForeignKey(
        "makerspaces.Makerspace", on_delete=models.CASCADE, related_name="setting_locks",
    )
    setting_key = models.CharField(max_length=100)
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    note = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
    released_at = models.DateTimeField(null=True, blank=True)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("makerspace", "setting_key"), condition=Q(released_at__isnull=True),
                name="setting_lock_one_live_per_key",
            ),
        ]
        ordering = ("setting_key", "created_at", "id")

    def __str__(self):
        return f"{self.makerspace_id}:{self.setting_key}"
