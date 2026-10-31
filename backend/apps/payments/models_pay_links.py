"""A secure pay link for one account-less charge staff raised (lane L5, X19).

The link is a bearer credential for exactly one pending charge: it shows what is owed
and lets the holder pay it, and nothing else -- no account, name or contact detail. Only
the SHA-256 digest of the token is stored; the token itself exists only in the URL that
staff copy or that the space emails once. A new link for the same charge revokes the old.
"""

from django.db import models


class PaymentPayLink(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    payment = models.ForeignKey("payments.Payment", on_delete=models.CASCADE, related_name="pay_links")
    token_digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["payment"], condition=models.Q(revoked_at__isnull=True),
                                    name="pay_link_one_live_per_payment"),
        ]
