import secrets

from django.core.validators import MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class EventPromoCode(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="promo_codes")
    code_digest = models.CharField(max_length=64, editable=False, default=secrets.token_hex)
    percent_off = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(100)])
    amount_off = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    max_uses = models.PositiveIntegerField(default=1)
    uses = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Release 2 L6 (G29). An access code discounts nothing: it unlocks one hidden ticket
    # type. A discount code may be limited to one ticket type and applies per ticket (one
    # use per discounted ticket) or once per order (one use).
    kind = models.CharField(max_length=8, default="discount", choices=[
        ("discount", "Discount"), ("access", "Access code")])
    applies_per = models.CharField(max_length=8, default="ticket", choices=[
        ("ticket", "Each ticket"), ("order", "Once per order")])
    ticket_type = models.ForeignKey("events.EventTicketType", null=True, blank=True, on_delete=models.CASCADE,
                                    related_name="promo_codes")

    def clean(self):
        super().clean()
        if self.event_id and self.event.makerspace_id != self.makerspace_id:
            raise ValidationError({"event": "Event must belong to this makerspace."})
        if self.ticket_type_id and self.ticket_type.event_id != self.event_id:
            raise ValidationError({"ticket_type": "Ticket type must belong to this event."})

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["event", "code_digest"], name="event_promo_unique_code"),
            models.CheckConstraint(condition=Q(max_uses__gte=1), name="event_promo_positive_limit"),
            models.CheckConstraint(condition=Q(uses__lte=F("max_uses")), name="event_promo_usage_limit"),
            models.CheckConstraint(condition=Q(percent_off__lte=100, amount_off__gte=0), name="event_promo_valid_discount"),
            models.CheckConstraint(condition=(Q(kind="access", percent_off=0, amount_off=0, ticket_type__isnull=False)
                | Q(kind="discount", percent_off__gt=0, amount_off=0)
                | Q(kind="discount", percent_off=0, amount_off__gt=0)), name="event_promo_one_discount"),
        ]
