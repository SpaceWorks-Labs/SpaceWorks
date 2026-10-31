"""Per-person opt-out from the monthly staff membership summary (X33).

The summary is a scheduled-report preset delivered to staff with `manage_members`; a
row here removes one person from it in one space. Deleting the row opts back in.
"""
from django.conf import settings
from django.db import models


class MembershipSummaryOptOut(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="membership_summary_opt_outs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="membership_summary_opt_outs")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["makerspace", "user"], name="uniq_membership_summary_opt_out")]
