"""Reject malformed portable loan-context relationships before admission."""
from django.apps import apps
from django.db.models import F, Q

from apps.backup.capture_managers import every_row


def validate_loan_context_import(makerspace_id):
    if apps.is_installed("apps.events"):
        model = apps.get_model("events", "EventLoanContext")
        bad = every_row(model).filter(makerspace_id=makerspace_id).exclude(
            request__makerspace_id=F("makerspace_id"))
        bad = bad | every_row(model).filter(makerspace_id=makerspace_id, event__isnull=False).exclude(
            event__makerspace_id=F("makerspace_id"))
        bad = bad | every_row(model).filter(makerspace_id=makerspace_id, participant_registration__isnull=False).exclude(
            participant_registration__event_id=F("event_id"))
        if bad.exists():
            raise ValueError("Imported event loan context failed tenant or borrower validation.")
        from apps.accounts.loan_context_identity import borrower_aliases
        aliases = {}
        rows = every_row(model).filter(makerspace_id=makerspace_id, participant_registration__isnull=False).select_related("request__requester", "participant_registration")
        for row in rows.iterator():
            borrower = row.request.requester
            if borrower.pk not in aliases:
                try:
                    aliases[borrower.pk] = borrower_aliases(borrower)
                except (ValueError, RuntimeError) as exc:
                    raise ValueError("Imported event loan context failed tenant or borrower validation.") from exc
            if row.participant_registration.member_id not in aliases[borrower.pk]:
                raise ValueError("Imported event loan context failed tenant or borrower validation.")
    if apps.is_installed("apps.bookings"):
        model = apps.get_model("bookings", "BookingLoanContext")
        bad = every_row(model).filter(makerspace_id=makerspace_id).exclude(request__makerspace_id=F("makerspace_id"))
        bad = bad | every_row(model).filter(makerspace_id=makerspace_id, booking__isnull=False).exclude(
            booking__space__makerspace_id=F("makerspace_id"))
        if bad.exists():
            raise ValueError("Imported booking loan context failed tenant validation.")
