"""Hack-money finance commands: the crew pool (G14) and organiser-booked travel (G12)."""
from rest_framework import serializers as s
from apps.payments.event_payouts.validation import MAX_MINOR
from .serializers import Command
from .serializers_request import StrictInteger, Currency

METHODS = ("cash", "upi", "bank_transfer", "card", "cheque", "online", "other")


class CrewPoolCommand(Command):
    expected_version = StrictInteger(min_value=0, max_value=0)
    initial_total_minor = StrictInteger(min_value=0, max_value=MAX_MINOR)


class DirectBookingCommand(Command):
    expected_pool_version = StrictInteger(min_value=1)
    amount_minor = StrictInteger(min_value=1, max_value=MAX_MINOR)
    currency = Currency()
    vendor = s.CharField(max_length=150, help_text="Who the space paid: the airline, bus operator or agent.")
    booked_on = s.DateField()
    method = s.ChoiceField(choices=METHODS)
    reference = s.CharField(max_length=64, allow_blank=True, required=False)
    receipt_id = s.IntegerField(min_value=1, required=False, allow_null=True,
                                help_text="An uploaded ledger receipt (photo or PDF), as for any expense.")


class DirectBookingCancelCommand(Command):
    expected_pool_version = StrictInteger(min_value=1)
    reason = s.CharField(max_length=300)
