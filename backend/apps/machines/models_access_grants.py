"""Machine access grants (decision 319): who may use a machine, given by the Space Manager.

A grant names one member and EITHER one machine OR one machine type (every machine of that
type). It replaces the certification/induction gate: certification records are kept as
read-only history, and the migration turns them into grants. A grant is never deleted:
revocation sets `revoked_at`/`revoked_by`, and `expires_at` is a stored moment, so the
grant row stays as the accountability trail of who allowed whom onto a machine, and when.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class MachineAccessGrant(models.Model):
    class Source(models.TextChoices):
        STAFF = "staff", "Granted by staff"
        MIGRATION = "migration", "Converted from a certification"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="machine_access_grants")
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name="machine_access_grants")
    machine = models.ForeignKey("machines.Machine", null=True, blank=True, on_delete=models.CASCADE,
                                related_name="access_grants")
    machine_type = models.ForeignKey("machines.MachineType", null=True, blank=True, on_delete=models.CASCADE,
                                     related_name="access_grants")
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="machine_access_granted")
    granted_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True)
    source = models.CharField(max_length=12, choices=Source.choices, default=Source.STAFF)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="machine_access_revoked")
    # Set once the "expiring soon" notice went out, so the sweep never repeats it.
    expiry_notice_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-granted_at", "-pk"]
        indexes = [models.Index(fields=["makerspace", "member"], name="machaccess_space_member_idx")]
        constraints = [
            models.CheckConstraint(
                condition=(Q(machine__isnull=False, machine_type__isnull=True)
                       | Q(machine__isnull=True, machine_type__isnull=False)),
                name="machaccess_machine_xor_type"),
            # Per makerspace (336k/M8): built-in machine types (makerspace NULL) are shared by every
            # space, so a member's live type grant in one space must never block or be renewed by another.
            models.UniqueConstraint(fields=["makerspace", "member", "machine"], condition=Q(revoked_at__isnull=True,
                                    machine__isnull=False), name="machaccess_one_live_machine"),
            models.UniqueConstraint(fields=["makerspace", "member", "machine_type"], condition=Q(revoked_at__isnull=True,
                                    machine_type__isnull=False, machine__isnull=True),
                                    name="machaccess_one_live_type"),
        ]

    def __str__(self):
        return f"{self.member_id} -> {self.machine_id or self.machine_type_id}"

    def is_live(self, now=None):
        if self.revoked_at is not None:
            return False
        return self.expires_at is None or self.expires_at > (now or timezone.now())
