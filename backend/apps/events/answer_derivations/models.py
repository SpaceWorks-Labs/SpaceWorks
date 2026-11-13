"""Encrypted source evidence; numeric age has no persistence field here."""

from django.utils.translation import gettext
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.encryption.crypto import is_envelope, parse_envelope


class DerivationQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise RuntimeError("Derivation writes require the answer workflow.")

    def bulk_update(self, *args, **kwargs):
        raise RuntimeError("Derivation writes require the answer workflow.")

    def bulk_create(self, *args, **kwargs):
        raise RuntimeError("Derivation writes require the answer workflow.")


class EventAnswerDerivation(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="answer_derivations")
    registration = models.ForeignKey(
        "events.EventRegistration", null=True, blank=True, on_delete=models.CASCADE,
        related_name="answer_derivations",
    )
    application = models.ForeignKey(
        "events.HackathonApplication", null=True, blank=True, on_delete=models.CASCADE,
        related_name="answer_derivations",
    )
    role_assignment = models.ForeignKey(
        "events.EventRoleAssignment", null=True, blank=True, on_delete=models.CASCADE,
        related_name="answer_derivations",
    )
    question_id = models.CharField(max_length=128)
    source_dob_envelope = models.TextField(editable=False)
    event_date_revision = models.PositiveIntegerField()
    as_of_date = models.DateField()
    locked_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    # Reopen appends ciphertext and source metadata before the owner can edit.
    # These snapshots contain no computed values, raw DOB or free-text reason.
    source_history = models.JSONField(default=list, editable=False)
    objects = models.Manager.from_queryset(DerivationQuerySet)()

    class Meta:
        app_label = "events"
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(registration__isnull=False, application__isnull=True, role_assignment__isnull=True)
                    | Q(registration__isnull=True, application__isnull=False, role_assignment__isnull=True)
                    | Q(registration__isnull=True, application__isnull=True, role_assignment__isnull=False)
                ), name="event_derivation_one_subject",
            ),
            *[
                models.UniqueConstraint(
                    fields=[name, "question_id"], condition=Q(**{f"{name}__isnull": False}),
                    name=f"event_derivation_{suffix}_question",
                )
                for name, suffix in (("registration", "reg"), ("application", "app"), ("role_assignment", "role"))
            ],
            models.CheckConstraint(condition=Q(version__gte=1), name="event_derivation_version_positive"),
            models.CheckConstraint(condition=Q(event_date_revision__gte=1), name="event_derivation_date_positive"),
        ]

    def clean(self):
        from .subjects import subject_model
        from apps.events.contracts.subjects import SubjectKind

        if sum(getattr(self, f"{name}_id") is not None for name in (
            "registration", "application", "role_assignment",
        )) != 1:
            raise ValidationError(gettext("Bind exactly one answer subject."))
        # Retained evidence can outlive its owner's User edge. Null/pseudonymous
        # owners cannot read or edit it, but tenant fidelity import must preserve it.
        for kind in SubjectKind:
            pk = getattr(self, f"{kind.value}_id")
            if pk is not None and not subject_model(kind).objects.filter(pk=pk, event_id=self.event_id).exists():
                raise ValidationError(gettext("Answer subject must belong to this event."))
        if not self.question_id or len(self.question_id) > 128:
            raise ValidationError(gettext("Use a bounded question identifier."))
        if not is_envelope(self.source_dob_envelope):
            raise ValidationError(gettext("Birth date source must be encrypted."))
        parse_envelope(self.source_dob_envelope)
        self._validate_history()

    def _validate_history(self):
        allowed = {"source_dob_envelope", "event_date_revision", "as_of_date", "locked_at", "version", "reason_envelope"}
        if not isinstance(self.source_history, list):
            raise ValidationError(gettext("Use encrypted source snapshots."))
        for snapshot in self.source_history:
            if not isinstance(snapshot, dict) or set(snapshot) != allowed:
                raise ValidationError(gettext("Use encrypted source snapshots."))
            for name in ("source_dob_envelope", "reason_envelope"):
                parse_envelope(snapshot[name])

    def save(self, *args, **kwargs):
        if not getattr(self, "_workflow_write", False):
            raise RuntimeError("Derivation writes require the answer workflow.")
        self.clean()
        if not self._state.adding:
            prior = type(self).objects.get(pk=self.pk)
            identity = ("event_id", "registration_id", "application_id", "role_assignment_id", "question_id")
            if any(getattr(self, name) != getattr(prior, name) for name in identity):
                raise ValidationError(gettext("Derivation identity is immutable."))
            if self.source_history[:len(prior.source_history)] != prior.source_history:
                raise ValidationError(gettext("Source history is append-only."))
            if prior.locked_at and not getattr(self, "_workflow_reopen", False):
                protected = ("source_dob_envelope", "as_of_date", "event_date_revision", "locked_at")
                if any(getattr(self, name) != getattr(prior, name) for name in protected):
                    raise ValidationError(gettext("Locked source evidence is immutable."))
        return super().save(*args, **kwargs)
