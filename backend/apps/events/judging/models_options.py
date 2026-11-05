"""L21b per-event hackathon options: email switches (C-37), the two fees (X50, C-39) and hack-money refund switches.

A missing row means a new event: every switch off and no fee. The migration that adds this table
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
    # Hack-money G2: whether a withdrawn or not-shortlisted team's PAID entry fee opens a refund
    # DUE case. Off by default; a pending fee is always voided. Staff still decide every case.
    refund_on_withdrawal = models.BooleanField(default=False)
    refund_if_not_shortlisted = models.BooleanField(default=False)
    entry_fee = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    team_fee = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(entry_fee__isnull=True) | Q(entry_fee__gt=0), name="ev_options_entry_fee"),
            models.CheckConstraint(condition=Q(team_fee__isnull=True) | Q(team_fee__gt=0), name="ev_options_team_fee"),
        ]
