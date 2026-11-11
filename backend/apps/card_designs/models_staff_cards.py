"""Staff ID cards (O-B4 part 2): one card per active staff membership, any staff role.

A staff card is a fourth holder kind next to member, programme and event cards, so it rides the same
engine (designs, rendering, verify tokens, wallet passes, desk print). It shows what the person holds
LIVE (name, roles, machine scope), so the row stores only identity of the card: its number, when it was
issued and when it ended. The roles held at issue are kept in `roles` solely to detect a role change.
Staff cards own a separate number scheme (`StaffCardNumbering`) and the shared counter table.
"""
from django.db import models
from django.db.models import Q
from django.utils import timezone


class StaffCard(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="staff_cards")
    # SET_NULL: a deleted staff membership leaves the revoked card as a record (never a live credential).
    membership = models.ForeignKey("makerspaces.MakerspaceMembership", null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="staff_cards")
    card_number = models.PositiveIntegerField()
    number_text = models.CharField(max_length=32, blank=True, default="")
    roles = models.JSONField(default=list, blank=True)
    print_count = models.PositiveIntegerField(default=0)
    last_printed_at = models.DateTimeField(null=True, blank=True)
    issued_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=32, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["makerspace_id", "-issued_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["makerspace", "card_number"], name="uniq_staff_card_number"),
            models.UniqueConstraint(fields=["membership"], condition=Q(revoked_at__isnull=True, membership__isnull=False),
                                    name="uniq_live_staff_card_per_membership"),
            models.UniqueConstraint(fields=["makerspace", "number_text"], condition=~Q(number_text=""),
                                    name="uniq_staff_card_number_text"),
        ]

    # The public check shows the holder's name for staff cards (a staff member is a public-facing role).
    verify_show_name = True
    verify_show_photo = False
    photo_object_key = ""
    email_format = "pdf"

    @property
    def is_active(self):
        return self.revoked_at is None


class StaffCardNumbering(models.Model):
    """The staff number scheme of one space (separate from the member-card schemes)."""
    makerspace = models.OneToOneField("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    prefix = models.CharField(max_length=6, blank=True, default="")
    pattern = models.CharField(max_length=40, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)
