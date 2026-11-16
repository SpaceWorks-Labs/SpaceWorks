"""Additional combinable roles attached to a membership."""

from django.conf import settings
from django.db import models


class MembershipAdditionalRole(models.Model):
    membership = models.ForeignKey(
        "makerspaces.MakerspaceMembership", on_delete=models.CASCADE,
        related_name="additional_roles",
    )
    role = models.ForeignKey(
        "makerspaces.MakerspaceRole", on_delete=models.PROTECT,
        related_name="additional_memberships",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "role"], name="membershipadditionalrole_uniq",
            ),
        ]
