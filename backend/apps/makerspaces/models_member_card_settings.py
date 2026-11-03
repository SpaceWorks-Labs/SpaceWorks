"""Per-space member-card settings (SPEC §4.2; release 2 L3).

The printed number is the membership's fixed member number in the space's L4 pattern
(`membership_number`), so there is no second prefix or pattern here. The design
approval switch lives with the other approval levels in `card_designs.CardApprovalSetting`.
"""
from django.db import models


class MemberCardSettings(models.Model):
    makerspace = models.OneToOneField("makerspaces.Makerspace", on_delete=models.CASCADE,
                                      related_name="member_card_settings")
    # On for spaces created after release 2; card_designs migration 0003 writes False for
    # every space that already existed, so upgrading never issues cards by surprise (Q3).
    auto_issue = models.BooleanField(default=True)
    email_on_issue = models.BooleanField(default=False)
    # Public "is this card valid" page: off until a manager turns it on (Q1).
    public_verify = models.BooleanField(default=False)
    verify_show_plan = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"member card settings ({self.makerspace_id})"
