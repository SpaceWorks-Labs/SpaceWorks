"""Account-bound initial-password invitations, stored as bearer digests."""

from django.conf import settings
from django.db import models


class StaffInvitation(models.Model):
    # Legacy invitations stay unbound. Never infer ownership from shared email.
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               null=True, blank=True, related_name="staff_invitations")
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    email_ciphertext = models.TextField()
    role = models.ForeignKey("makerspaces.MakerspaceRole", on_delete=models.CASCADE)
    granted_actions = models.JSONField(default=list)
    role_snapshot = models.JSONField(default=list)
    machine_scope_snapshot = models.JSONField(default=list)
    machine_ids_snapshot = models.JSONField(default=list)
    credential_generation = models.PositiveIntegerField(default=0)
    token_digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True)
    revoked_at = models.DateTimeField(null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="staff_invitations_created")
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, related_name="staff_invitations_accepted")
    created_at = models.DateTimeField(auto_now_add=True)
    failed_attempts = models.PositiveSmallIntegerField(default=0)

    @property
    def email(self):
        from apps.makerspaces.secrets import decrypt_value
        return decrypt_value(self.email_ciphertext)
