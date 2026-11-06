"""Issue reports (#103) and who works them (#98, #102).

An issue names one subject (a machine, an inventory item or unit, or a room) and, when
a member filed it, the loan, booking or machine job it came from. It moves

    reported -> triaged -> assigned -> in_progress -> fixed -> closed   (or -> rejected)

Triage with repairs switched on links it to L12's single `WorkOrder` (no second repair
model); with repairs off a report is notify-only and staff close or reject it. Every
step writes an `IssueEvent` and an audit row. The reporter's name and email are scoped
PII; a Technician only ever sees the first name (Q-T2).
"""

from django.utils.translation import gettext_noop
from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.encryption.mappers import ScopedPiiModelMixin

from .models_contacts import AREA_CHOICES

SUBJECT_CHOICES = [("machine", "Machine"), ("inventory_product", "Inventory item"),
                   ("inventory_asset", "Inventory unit"), ("bookable_space", "Bookable space")]
PRIORITY_CHOICES = [("low", "Low"), ("normal", "Normal"), ("high", "High"), ("urgent", "Urgent")]


class IssueReport(ScopedPiiModelMixin, models.Model):
    class State(models.TextChoices):
        REPORTED = "reported", "Reported"
        TRIAGED = "triaged", "Triaged"
        ASSIGNED = "assigned", "Assigned"
        IN_PROGRESS = "in_progress", gettext_noop("In progress")
        FIXED = "fixed", "Fixed"
        CLOSED = "closed", "Closed"
        REJECTED = "rejected", "Rejected"

    class Source(models.TextChoices):
        LOAN = "loan", "Loan"
        BOOKING = "booking", "Booking"
        MACHINE_JOB = "machine_job", gettext_noop("Machine job")
        STAFF = "staff", "Staff"

    class QuoteState(models.TextChoices):
        NONE = "none", gettext_noop("No quote")
        PENDING = "pending", gettext_noop("Awaiting approval")
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"

    OPEN_STATES = (State.REPORTED, State.TRIAGED, State.ASSIGNED, State.IN_PROGRESS)

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="issue_reports")
    area = models.CharField(max_length=10, choices=AREA_CHOICES)
    subject_type = models.CharField(max_length=24, choices=SUBJECT_CHOICES)
    machine = models.ForeignKey("machines.Machine", null=True, blank=True, on_delete=models.CASCADE,
                                related_name="issue_reports")
    product = models.ForeignKey("inventory.InventoryProduct", null=True, blank=True, on_delete=models.CASCADE,
                                related_name="issue_reports")
    asset = models.ForeignKey("inventory.InventoryAsset", null=True, blank=True, on_delete=models.CASCADE,
                              related_name="issue_reports")
    room = models.ForeignKey("bookings.BookableSpace", null=True, blank=True, on_delete=models.CASCADE,
                             related_name="issue_reports")
    source = models.CharField(max_length=12, choices=Source.choices)
    loan = models.ForeignKey("hardware_requests.HardwareRequest", null=True, blank=True,
                             on_delete=models.SET_NULL, related_name="issue_reports")
    booking = models.ForeignKey("bookings.Booking", null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="issue_reports")
    machine_job = models.ForeignKey("machines.MachineServiceRequest", null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="issue_reports")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="+")
    reporter_name = models.TextField(blank=True)
    reporter_email = models.TextField(blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    state = models.CharField(max_length=12, choices=State.choices, default=State.REPORTED, db_index=True)
    priority = models.CharField(max_length=8, choices=PRIORITY_CHOICES, default="normal")
    work_order = models.OneToOneField("maintenance.WorkOrder", null=True, blank=True, on_delete=models.SET_NULL,
                                      related_name="issue")
    resolution = models.TextField(blank=True)
    quote_state = models.CharField(max_length=10, choices=QuoteState.choices, default=QuoteState.NONE)
    quote_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    quote_currency = models.CharField(max_length=3, blank=True, default="")
    quote_note = models.TextField(blank=True)
    quote_contact = models.ForeignKey("maintenance.TechnicianContact", null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name="+")
    payout_entry = models.ForeignKey("payments.LedgerEntry", null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="+")
    reporter_notified_at = models.DateTimeField(null=True, blank=True)
    fixed_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["makerspace", "state", "-created_at"], name="issue_report_scope_idx")]
        constraints = [
            models.CheckConstraint(name="issue_report_one_subject", condition=(
                Q(subject_type="machine", machine__isnull=False, product__isnull=True, asset__isnull=True,
                  room__isnull=True)
                | Q(subject_type="inventory_product", machine__isnull=True, product__isnull=False,
                    asset__isnull=True, room__isnull=True)
                | Q(subject_type="inventory_asset", machine__isnull=True, asset__isnull=False, room__isnull=True)
                | Q(subject_type="bookable_space", machine__isnull=True, product__isnull=True,
                    asset__isnull=True, room__isnull=False))),
            models.CheckConstraint(name="issue_report_quote_amount",
                                   condition=Q(quote_amount__isnull=True) | Q(quote_amount__gte=0)),
        ]

    @property
    def subject(self):
        return self.machine or self.asset or self.product or self.room

    def __str__(self):
        return f"Issue {self.pk}: {self.title}"


class IssueAssignment(models.Model):
    """Who works an issue: a technician contact, or a person (a manager self-assigning)."""

    issue = models.ForeignKey(IssueReport, on_delete=models.CASCADE, related_name="assignments")
    contact = models.ForeignKey("maintenance.TechnicianContact", null=True, blank=True, on_delete=models.CASCADE,
                                related_name="assignments")
    person = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE,
                               related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(name="issue_assignment_one_party",
                                   condition=Q(contact__isnull=False, person__isnull=True)
                                   | Q(contact__isnull=True, person__isnull=False)),
            models.UniqueConstraint(fields=["issue", "contact"], condition=Q(contact__isnull=False),
                                    name="issue_assignment_contact_uniq"),
            models.UniqueConstraint(fields=["issue", "person"], condition=Q(person__isnull=False),
                                    name="issue_assignment_person_uniq"),
        ]
