"""Organizations whose members may register; audience only, never authority."""

from django.conf import settings
from django.db import models


class EventAudienceOrganization(models.Model):
    """One organization admitted to an event's "Selected organizations" audience.

    Deliberately separate from ``EventOrganizer``: an organizer row makes that
    organization's event managers co-managers of the event
    (``organizer_authority.can_manage_event``), while an audience row only lets the
    organization's members register. Nothing in ``event_authority`` reads this table.
    """

    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="audience_organizations",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="event_audiences",
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("event", "organization"),
                name="uniq_event_audience_organization",
            ),
        ]
