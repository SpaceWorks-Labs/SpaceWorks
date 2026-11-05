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
    # Hack-money G6: show prize names, kinds and amounts on the public event page (off by default).
    show_prize_amounts = models.BooleanField(default=False)
    # Hack-money G4: days after results are announced in which winners claim; after it staff may forfeit.
    prize_claim_days = models.PositiveSmallIntegerField(null=True, blank=True)
    # Hack-money G10 (`events.deposits`): an optional refundable commitment deposit, raised when a place
    # is confirmed. After the event staff approve ONE settlement batch: attendees (who also submitted,
    # when required) get a refund DUE case, no-shows keep the charge. Money moves only on staff approval.
    deposit_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    deposit_requires_submission = models.BooleanField(default=False)
    deposits_settled_at = models.DateTimeField(null=True, blank=True)
    entry_fee = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    team_fee = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(entry_fee__isnull=True) | Q(entry_fee__gt=0), name="ev_options_entry_fee"),
            models.CheckConstraint(condition=Q(team_fee__isnull=True) | Q(team_fee__gt=0), name="ev_options_team_fee"),
            models.CheckConstraint(condition=Q(deposit_amount__isnull=True) | Q(deposit_amount__gt=0),
                                   name="ev_options_deposit"),
        ]
