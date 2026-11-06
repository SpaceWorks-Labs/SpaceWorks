"""Account-linked speaker identity: the durable credit behind speaker history.

A website speaker section (`EventPageSection(kind=speaker)`) is editorial copy with no
account behind it, and an `EventStaffGrant` labelled "Speaker" is revocable authority, not
credit. Neither can answer "which events did this person speak at", so this row exists.

It is linked one of two ways, and both are audited with the actor who did it:

- staff ASSIGN an account they can see within the event's scope (`linked_via=staff_assigned`);
- a person CLAIMS a single-use invite link while signed in (`linked_via=claimed`).

Only the token's HMAC digest is stored. Removal is a soft `removed_at`, never a delete, so the
audit trail and the history projection agree about what once existed.
"""

from django.utils.translation import gettext_lazy
from django.conf import settings
from django.db import models
from django.db.models import Q


class EventSpeaker(models.Model):
    class LinkedVia(models.TextChoices):
        STAFF_ASSIGNED = "staff_assigned", gettext_lazy("Assigned by staff")
        CLAIMED = "claimed", gettext_lazy("Claimed by invite")

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="speakers")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE,
                             related_name="event_speaking")
    section = models.ForeignKey("events.EventPageSection", null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="speaker_identities")
    display_name = models.CharField(max_length=200)
    linked_via = models.CharField(max_length=16, choices=LinkedVia.choices, blank=True, default="")
    # Also hand the speaker a check_in staff grant when they are linked.
    grants_check_in = models.BooleanField(default=False)
    claim_token_digest = models.CharField(max_length=64, blank=True, default="", editable=False)
    claim_expires_at = models.DateTimeField(null=True, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="+")
    removed_at = models.DateTimeField(null=True, blank=True)
    removed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")
        constraints = [
            models.UniqueConstraint(fields=("event", "user"), condition=Q(removed_at__isnull=True, user__isnull=False),
                                    name="event_speaker_active_account"),
            models.UniqueConstraint(fields=("claim_token_digest",), condition=~Q(claim_token_digest=""),
                                    name="event_speaker_claim_digest"),
        ]

    @property
    def status(self):
        if self.removed_at:
            return "removed"
        return "linked" if self.user_id else "invited"
