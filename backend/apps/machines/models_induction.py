"""Induction events and guest certifications (release 0.12.0, decision 223 (d)/(k)).

``EventInductionLink`` marks an event as an induction for one certification type; the
link grants nothing by itself. After the event staff pick attendees and grant from it
(``induction.grant_from_induction``), one audited grant per person.

``GuestCertificationGrant`` is the narrow path for a guest-pass holder, who has no
membership and so cannot hold a ``CertificationGrant``. It carries the same append-only
shape (revoke, never delete; stored expiry) and names the event it came from.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class EventInductionLink(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="induction_links")
    certification_type = models.ForeignKey(
        "machines.CertificationType", on_delete=models.CASCADE, related_name="induction_links")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["event", "certification_type"], name="induction_link_uniq"),
        ]

    def __str__(self):
        return f"Event {self.event_id} inducts {self.certification_type_id}"


class GuestCertificationGrant(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    certification_type = models.ForeignKey(
        "machines.CertificationType", on_delete=models.CASCADE, related_name="guest_grants")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="guest_certification_grants")
    source_event = models.ForeignKey(
        "events.Event", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    granted_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=["makerspace", "user"], name="guestcert_space_user_idx")]

    def __str__(self):
        return f"{self.user_id} -> {self.certification_type_id}"

    def is_active(self, now=None):
        if self.revoked_at is not None:
            return False
        moment = now or timezone.now()
        return self.expires_at is None or self.expires_at > moment
