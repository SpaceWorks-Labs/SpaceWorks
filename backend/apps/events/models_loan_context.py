"""Event-owned association to the core request; no core import of events."""
from django.db import models
from django.db.models import Q

MAX_REVISION = 9007199254740991

class EventLoanContext(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.PROTECT)
    request = models.OneToOneField("hardware_requests.HardwareRequest", on_delete=models.PROTECT)
    event = models.ForeignKey("events.Event", null=True, blank=True, on_delete=models.PROTECT)
    participant_registration = models.ForeignKey("events.EventRegistration", null=True, blank=True, on_delete=models.PROTECT)
    active = models.BooleanField(default=False)
    revision = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(Q(active=True, event__isnull=False) | Q(active=False, event__isnull=True, participant_registration__isnull=True)), name="event_loan_context_active_ck"),
            models.CheckConstraint(condition=Q(revision__gte=1, revision__lte=MAX_REVISION), name="event_loan_context_revision_ck"),
        ]
