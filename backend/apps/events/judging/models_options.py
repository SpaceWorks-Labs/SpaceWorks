"""L21b per-event hackathon options: email switches (C-37) and the two fees (X50, C-39).

A missing row means a new event: every switch off and no fee (the entry fee, when set, is due before stage 1). The migration that adds this table
writes a row for every existing event with today's two emails ON, so their behaviour is unchanged.
"""

from django.db import models
from django.db.models import Q

from .models_base import EventOwned


class HackathonProgrammeOptions(EventOwned):
    event = models.OneToOneField("events.Event", on_delete=models.CASCADE, related_name="programme_options")
    results_email = models.BooleanField(default=False)
    submission_receipt_email = models.BooleanField(default=False)
    finalists_email = models.BooleanField(default=False)
    refund_on_disqualification = models.BooleanField(default=False)
    entry_fee = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    team_fee = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    # #178/#179 emails start OFF like every hackathon email (C-37): stage deadline reminders and shortlist results.
    stage_reminder_email = models.BooleanField(default=False)
    shortlist_email = models.BooleanField(default=False)
    # S17: the one entry fee is paid before submitting this stage position (and every later one).
    entry_fee_stage = models.PositiveSmallIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(entry_fee__isnull=True) | Q(entry_fee__gt=0), name="ev_options_entry_fee"),
            models.CheckConstraint(condition=Q(team_fee__isnull=True) | Q(team_fee__gt=0), name="ev_options_team_fee"),
            models.CheckConstraint(condition=Q(entry_fee_stage__gte=1, entry_fee_stage__lte=10), name="ev_options_fee_stage"),
        ]
