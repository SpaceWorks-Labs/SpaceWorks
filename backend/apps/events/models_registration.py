from django.utils.translation import gettext, gettext_noop
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from apps.events.submissions.pii import PrivateDocumentMixin
from apps.events.models_event import Event


class EventRegistration(PrivateDocumentMixin, models.Model):
    pii_document_fields = frozenset({"custom_answers"})
    pii_text_fields = frozenset({"name", "email", "phone"})
    pii_on_demand_keys = True
    version = models.PositiveIntegerField(default=1)
    attendance_revision = models.PositiveBigIntegerField(default=0)
    answer_locked_at = models.DateTimeField(null=True, blank=True)
    date_review_required = models.BooleanField(default=False)
    credential_mode = models.CharField(max_length=8, default="legacy",
                                       choices=(("legacy", "Legacy"), ("v2", "Version 2"), ("inert", "Inert")))
    #: A free crew place (lane L21a, #128 C-36): never counted in capacity, never charged,
    #: never part of an order or a team. Only `contributions/crew_workflow` sets it.
    is_crew = models.BooleanField(default=False, editable=False)
    class Status(models.TextChoices):
        PENDING_APPROVAL = "pending_approval", gettext_noop("Pending approval")
        REGISTERED = "registered", "Registered"
        WAITLISTED = "waitlisted", "Waitlisted"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"
        ATTENDED = "attended", "Attended"

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="registrations",
    )
    # Admission provenance survives later changes to the event audience.
    registration_audience = models.CharField(max_length=32, choices=Event.RegistrationAudience.choices, default=Event.RegistrationAudience.MEMBERS)
    ticket_type = models.ForeignKey("events.EventTicketType", on_delete=models.SET_NULL, null=True, blank=True)
    invite = models.ForeignKey("events.EventInvite", on_delete=models.SET_NULL, null=True, blank=True)
    promo_code = models.ForeignKey("events.EventPromoCode", on_delete=models.SET_NULL, null=True, blank=True)
    # Null preserves legacy flat-price behavior; new registrations freeze their quote.
    quoted_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # editable=False keeps this out of ModelForms and admin. Do not re-read it in
    # save(): register() uses save(update_fields=...) on a hot path, and no application
    # code assigns the token after creation.
    checkin_token = models.UUIDField(default=uuid4, unique=True, editable=False)
    name = models.TextField()
    email = models.TextField()
    phone = models.TextField()
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="event_registrations",
    )
    # Accepted collaboration authorizes discovery and creation, while this durable
    # provenance records where participation happened so member history and QR access
    # survive removal of that collaboration. SET_NULL is intentional: this is routing
    # convenience, not accountability evidence, and a purge should hide the activity
    # from that space rather than be blocked.
    registered_via_makerspace = models.ForeignKey(
        "makerspaces.Makerspace",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="event_registrations_via",
    )
    # MONEY, not activity: NOT cleared by the collaborator's `events` purge. A waitlisted row
    # is charged only at `_promote()`, so a purge in between would null the field above and
    # route the charge to the host, which the visitor cannot reach -- and no `Payment` exists
    # yet to carry it. Resurrects nothing: history/profile/QR read the field above, not this.
    payment_via_makerspace = models.ForeignKey(
        "makerspaces.Makerspace",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="event_registration_payment_routes",
    )
    # The version and timestamp are accountability evidence about a real person's
    # agreement. SET_NULL would either violate all-or-none or silently erase that
    # evidence, so the waiver itself is PROTECTed.
    host_waiver = models.ForeignKey(
        "makerspaces.MakerspaceWaiver",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="accepted_by_event_registrations",
    )
    host_waiver_accepted_at = models.DateTimeField(null=True, blank=True)
    host_waiver_version_accepted = models.CharField(
        max_length=64, null=True, blank=True,
    )
    email_exact_hash = models.BinaryField(max_length=32, null=True, editable=False)
    email_hash_generation = models.ForeignKey(
        "encryption.SearchKeyGeneration", on_delete=models.PROTECT,
        null=True, editable=False,
    )
    custom_answers = models.TextField(null=True, blank=True, default=None)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REGISTERED,
    )
    calendar_sequence = models.PositiveIntegerField(default=0)
    calendar_updated_at = models.DateTimeField(default=timezone.now)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    status_before_cancel = models.CharField(max_length=20, blank=True, default="")
    # A tail restore must not rewrite the original registration creation time.
    waitlist_position_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "email"],
                name="uniq_event_registration_email",
            ),
            models.UniqueConstraint(
                fields=["event", "email_hash_generation", "email_exact_hash"],
                condition=Q(email_hash_generation__isnull=False, email_exact_hash__isnull=False),
                name="uniq_event_registration_email_hash",
            ),
            models.UniqueConstraint(
                fields=["event", "member"],
                condition=Q(
                    member__isnull=False,
                    status__in=("pending_approval", "registered", "waitlisted", "attended"),
                ),
                name="uniq_active_event_registration_member",
            ),
            models.CheckConstraint(
                condition=(
                    Q(host_waiver__isnull=True, host_waiver_accepted_at__isnull=True,
                      host_waiver_version_accepted__isnull=True)
                    | Q(host_waiver__isnull=False, host_waiver_accepted_at__isnull=False,
                        host_waiver_version_accepted__isnull=False)
                ),
                name="event_registration_host_waiver_all_or_none",
            ),
        ]
        indexes = [
            models.Index(
                fields=["event", "status", "created_at"],
                name="eventreg_status_fifo_idx",
            ),
        ]

    def clean(self):
        super().clean()
        for field in ("ticket_type", "invite", "promo_code"):
            value = getattr(self, field)
            if value and value.event_id != self.event_id:
                raise ValidationError({field: gettext("Must belong to this event.")})
        if (
            self.host_waiver_id and self.event_id
            and self.host_waiver.makerspace_id != self.event.makerspace_id
        ):
            raise ValidationError(
                {"host_waiver": gettext("Waiver must belong to the event's host makerspace.")}
            )

    def save(self, *args, **kwargs):
        selected = kwargs.get("update_fields")
        # Partial status/credential writes must not reassign untouched mapped fields:
        # that would discard their authenticated cache without persisting new envelopes.
        for name in ("name", "email", "phone"):
            if selected is None or name in selected:
                value = (getattr(self, name) or "").strip()
                setattr(self, name, value.lower() if name == "email" else value)
        super().save(*args, **kwargs)
