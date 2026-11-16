"""The event crew (X44, #128 C-36): the organising team, beside participants.

A crew member signs up through the event's crew link (reviewed unless the event says
otherwise) or is added by staff. An approved crew member gets a free crew PLACE: a
registration flagged `is_crew`, which never counts against capacity, never belongs to an
order, never joins a team and is never charged. Crew membership grants no event staff
authority at all; desks still need their own role. Answers (dietary needs included) are
scoped PII (#28); the public crew section shows only people who opted in and have a
public profile (#25).
"""
from django.utils.translation import gettext_noop
from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.encryption.mappers import ScopedPiiModelMixin

LIVE = ("applied", "approved")


class EventCrewMember(ScopedPiiModelMixin, models.Model):
    class State(models.TextChoices):
        APPLIED = "applied", "Applied"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"
        WITHDRAWN = "withdrawn", "Withdrawn"
        REMOVED = "removed", "Removed"

    class Origin(models.TextChoices):
        SIGNUP = "signup", gettext_noop("Sign-up link")
        STAFF = "staff", gettext_noop("Added by staff")

    class Kind(models.TextChoices):
        ORGANISER = "organiser", gettext_noop("Organiser")
        VOLUNTEER = "volunteer", gettext_noop("Volunteer")
        MENTOR = "mentor", gettext_noop("Mentor")
        JUDGE = "judge", gettext_noop("Judge")

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="crew")
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="event_crew_roles")
    origin = models.CharField(max_length=8, choices=Origin.choices, default=Origin.SIGNUP)
    #: A free label ("Door", "AV", "Catering"); `mentor` marks a mentor crew ticket.
    crew_role = models.CharField(max_length=60, blank=True, default="")
    #: The role class behind the badge and filters (E-B3); the free `crew_role` label stays beside it.
    kind = models.CharField(max_length=12, choices=Kind.choices, null=True, blank=True)
    #: Staff order on the public crew section and the roster.
    position = models.PositiveIntegerField(default=0)
    #: Staff hide a crew member from the public section without ending the role.
    staff_hidden = models.BooleanField(default=False)
    state = models.CharField(max_length=10, choices=State.choices, default=State.APPLIED)
    answers = models.TextField(default="{}")
    dietary = models.TextField(blank=True, default="")
    show_publicly = models.BooleanField(default=False)
    registration = models.OneToOneField("events.EventRegistration", null=True, blank=True, on_delete=models.SET_NULL,
                                        related_name="crew_place")
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["event_id", "position", "pk"]
        constraints = [models.UniqueConstraint(fields=["event", "member"], condition=Q(state__in=LIVE),
                                               name="event_crew_one_live")]
