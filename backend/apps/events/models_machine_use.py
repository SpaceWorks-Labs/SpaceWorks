"""Event-owned record that a machine session, job or machine-time booking was done for an event (decision 342).

Like `EventLoanContext` and `EventMachineBookingLink`, the association lives in the events app so the
machines app never imports events: a link points at ONE session, ONE service request or ONE machine-time booking and names the event.
The requester may give it when submitting; the area manager may set, change or clear it afterwards. Every
change is audited with before and after (`machine_event.*`), and a link whose cost the organiser approved is
locked. It carries no person and no money; the member is the session's or request's own member, which is also
how a member sees only their own links.

`MachineEventCostApproval` is the organiser's append-only decision to charge a linked item's cost to the
event. It records the decision and the amount at that moment; it never changes a charge. The member's own
charge stands until space staff settle it through the ordinary ledger (see docs/how-to/machine-use-for-events.md).
"""
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext, gettext_noop

from apps.payments.money_model import MoneyDecimalField


class MachineEventLink(models.Model):
    class Source(models.TextChoices):
        """Who first gave the link: the requester, an adapter session, or the area manager."""
        REQUESTER = "requester", gettext_noop("Given by the requester")
        ADAPTER = "adapter", gettext_noop("Given by an adapter session")
        MANAGER = "manager", gettext_noop("Logged by the area manager")

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.PROTECT, related_name="+")
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="machine_use_links")
    machine_type = models.ForeignKey("machines.MachineType", on_delete=models.CASCADE, related_name="+")
    session = models.OneToOneField("machines.MachineSession", null=True, blank=True, on_delete=models.CASCADE,
                                   related_name="event_link")
    service_request = models.OneToOneField("machines.MachineServiceRequest", null=True, blank=True,
                                           on_delete=models.CASCADE, related_name="event_link")
    # A machine-time booking (machine space kind): the same link, same eligibility and same manager rights.
    booking = models.OneToOneField("bookings.Booking", null=True, blank=True, on_delete=models.CASCADE,
                                   related_name="event_link")
    source = models.CharField(max_length=10, choices=Source.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["makerspace", "event"], name="machine_event_link_event_idx")]
        constraints = [models.CheckConstraint(
            condition=(Q(session__isnull=False, service_request__isnull=True, booking__isnull=True)
                       | Q(session__isnull=True, service_request__isnull=False, booking__isnull=True)
                       | Q(session__isnull=True, service_request__isnull=True, booking__isnull=False)),
            name="machine_event_link_one_subject")]


class MachineEventCostApproval(models.Model):
    class Decision(models.TextChoices):
        APPROVED = "approved", gettext_noop("Approved to charge to the event")
        WITHDRAWN = "withdrawn", gettext_noop("Approval withdrawn")

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.PROTECT, related_name="+")
    link = models.ForeignKey(MachineEventLink, on_delete=models.CASCADE, related_name="cost_approvals")
    decision = models.CharField(max_length=10, choices=Decision.choices)
    # The linked item's charge as it stood when the organiser decided (null when it carries none).
    amount = MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    payment = models.ForeignKey("payments.Payment", null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="+")
    note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [models.CheckConstraint(condition=Q(amount__isnull=True) | Q(amount__gte=0),
                                              name="machine_event_cost_not_negative")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(gettext("Cost approvals are append-only."))
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(gettext("Cost approvals are retained until authorized purge."))
