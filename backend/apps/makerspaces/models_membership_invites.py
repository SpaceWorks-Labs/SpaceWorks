"""Shareable multi-use membership invite links (X11).

A link is a bearer credential: only an HMAC digest of its code is stored, the clear code
is shown to staff once at creation. Redeeming it lets a signed-in member join through the
invitation path even when the space (or the link's plan) is invite-only. `uses` counts
redemptions; a link is dead once revoked, expired or at `max_uses`. Deployment-local:
never exported, never carried by a tenant dump.
"""
from django.conf import settings
from django.db import models
from django.db.models import F, Q


class MembershipInviteLink(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="membership_invite_links")
    code_digest = models.CharField(max_length=64, unique=True, editable=False)
    label = models.CharField(max_length=120, blank=True, default="")
    plan = models.ForeignKey("makerspaces.MembershipPlan", null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="invite_links")
    #: Parity O-B1: a link may preselect the member unit the joiner lands in.
    unit = models.ForeignKey("makerspaces.MemberUnit", null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="invite_links")
    max_uses = models.PositiveIntegerField(default=1)
    uses = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="created_membership_invite_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(condition=Q(max_uses__gte=1, max_uses__lte=10000),
                                   name="membership_invite_link_limit"),
            models.CheckConstraint(condition=Q(uses__lte=F("max_uses")), name="membership_invite_link_usage"),
        ]

    def live(self, now):
        return (self.revoked_at is None and self.uses < self.max_uses
                and (self.expires_at is None or self.expires_at > now))
