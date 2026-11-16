from django.utils.translation import gettext
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class EventMemberPresentation(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE)
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    selected_profile = models.ForeignKey("makerspaces.MemberProfile", on_delete=models.SET_NULL,
                                        null=True, blank=True, related_name="event_presentations")
    selected_membership = models.ForeignKey("makerspaces.MakerspaceMembership", on_delete=models.SET_NULL,
                                           null=True, blank=True, related_name="+")
    source_revision = models.CharField(max_length=64, blank=True)
    print_photo_consent = models.BooleanField(default=False)
    public_card_consent = models.BooleanField(default=False)
    public_card_scopes = models.JSONField(default=list, blank=True)
    consent_revision = models.PositiveIntegerField(default=0)
    consented_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("event", "member"), name="event_member_presentation"),
            models.CheckConstraint(condition=(
                Q(selected_profile__isnull=False, selected_membership__isnull=False)
                | Q(selected_profile__isnull=True, selected_membership__isnull=True,
                    print_photo_consent=False, public_card_consent=False, public_card_scopes=[])
            ), name="event_presentation_selection_shape"),
        ]

    def clean(self):
        if self.selected_profile_id:
            if (self.selected_profile.membership_id != self.selected_membership_id
                    or self.selected_membership.user_id != self.member_id):
                raise ValidationError(gettext("Select your own matching profile and membership."))
        if set(self.public_card_scopes) - {"team", "mentor", "judge"}:
            raise ValidationError(gettext("Unknown public card scope."))
        if not self.public_card_consent and self.public_card_scopes:
            raise ValidationError(gettext("Public card scopes require separate consent."))


class EventMemberCard(models.Model):
    presentation = models.ForeignKey(EventMemberPresentation, on_delete=models.CASCADE, related_name="cards")
    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    scope = models.CharField(max_length=8, choices=((key, key) for key in ("team", "mentor", "judge")))

    class Meta:
        constraints = [models.UniqueConstraint(fields=("presentation", "scope"), name="event_public_card_scope")]


class EventPresentationCommand(models.Model):
    presentation = models.ForeignKey(EventMemberPresentation, on_delete=models.CASCADE)
    operation_id = models.UUIDField()
    request_sha256 = models.CharField(max_length=64)
    result = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("presentation", "operation_id"), name="event_presentation_command")]


from .source_lifecycle import register_source_lifecycle  # noqa: E402
register_source_lifecycle()
