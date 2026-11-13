"""Certificate signatories (up to three per event) and their design approvals.

A signatory's printed name, title and signature image are frozen into each certificate at
issuance. When the event requires approval, every signatory a design revision prints must
approve that exact revision (and their own current details) before its certificates render.
"""
from django.utils.translation import gettext
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class EventCertificateSignatory(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="certificate_signatories")
    slot = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=120)
    title = models.CharField(max_length=120, blank=True)
    # The account that approves designs. Required while the event requires approval.
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="certificate_signatory_roles")
    signature = models.ForeignKey("events.EventCertificateArtwork", on_delete=models.PROTECT, null=True,
                                  blank=True, related_name="signatories")
    # Bumped on every change; an approval binds to one version of these details.
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("event_id", "slot")
        constraints = [
            models.UniqueConstraint(fields=("event", "slot"), name="event_cert_signatory_slot"),
            models.CheckConstraint(condition=Q(slot__gte=1) & Q(slot__lte=3), name="event_cert_signatory_slot_range"),
        ]

    def clean(self):
        super().clean()
        if self.signature_id and (self.signature.event_id != self.event_id or self.signature.promoted_at is None):
            raise ValidationError({"signature": gettext("Use a promoted signature image uploaded for this event.")})


class EventCertificateSignatoryApproval(models.Model):
    """Append-only: a signatory approved one design revision with one version of their details."""
    signatory = models.ForeignKey(EventCertificateSignatory, on_delete=models.CASCADE, related_name="approvals")
    template_revision = models.ForeignKey("events.EventCertificateTemplateRevision", on_delete=models.CASCADE,
                                          related_name="signatory_approvals")
    signatory_version = models.PositiveIntegerField()
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    related_name="+")
    approved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("signatory", "template_revision", "signatory_version"),
                                               name="event_cert_signatory_approval")]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(gettext("Signatory approvals are append-only."))
        if self.template_revision.event_id != self.signatory.event_id:
            raise ValidationError(gettext("The approval must name a design of the signatory's event."))
        return super().save(*args, **kwargs)
