"""Maker profiles: what a member chooses to show the rest of their makerspace.

**Hung off `MakerspaceMembership`, never off `User`.** Scoped PII encryption is
per-makerspace and `User` is platform-global, which is exactly why `accounts.User` is
absent from the PII registry — so a profile attached to the user could not be scoped to
anything. Per-membership is also the truer model: what someone chooses to publish to one
space is not automatically theirs to publish in another, and the Activities section is
that space's events.

**Deliberately NOT `ScopedPiiModelMixin`.** The encryption layer protects contact
identifiers held about a person; every field here is content the member wrote and asked
to have shown. Encrypting a field whose purpose is publication buys nothing and would
drag in the envelope, dual-read and blind-index machinery for it. The identifying fields
still live on `User`, outside the registry for the reason above. `separability.E001` only
fires for models that take the mixin, and its own hint names dropping the mixin as the
correct answer for a model that holds no PII of that kind.

**Visibility is opt-in and defaults to off.** A directory that published every member the
day it shipped would publish people who never asked, and the privacy floor for the
member-visible directory (display name and avatar only, never email or phone) only means
anything if being listed at all is a choice.
"""

from django.db import models
from django.conf import settings
from django.db.models.functions import Lower
from django.core.validators import RegexValidator

HANDLE_PATTERN = r"^[a-z0-9](?:[a-z0-9._-]{1,28}[a-z0-9])$"


class MemberProfile(models.Model):
    membership = models.OneToOneField(
        "makerspaces.MakerspaceMembership",
        on_delete=models.CASCADE,
        related_name="profile",
    )
    is_visible = models.BooleanField(
        default=False,
        help_text="Whether other members of this makerspace can see this profile.",
    )
    public_visible = models.BooleanField(default=False)
    public_consented_at = models.DateTimeField(null=True, blank=True, editable=False)
    show_activity_graph = models.BooleanField(default=False)
    show_events = models.BooleanField(default=False)
    show_speaking = models.BooleanField(default=False)
    show_projects = models.BooleanField(default=False)
    show_machine_activity = models.BooleanField(default=False)
    show_bookings = models.BooleanField(default=False)
    show_loans = models.BooleanField(default=False)
    domains = models.JSONField(default=list, blank=True)
    skills = models.JSONField(default=list, blank=True)
    links = models.JSONField(default=list, blank=True)
    # CONSENT, not configurability: profile visibility publishes fields the member typed
    # into the form, while attendance is separately derived information. Reusing
    # is_visible would disclose it on already-visible profiles without a new member act.
    show_attended_events = models.BooleanField(
        default=False,
        help_text="Whether to publish recently attended events on this member profile.",
    )
    # Same consent rule: certifications are staff-derived training records, not text the
    # member typed, so publishing them on a visible profile needs its own opt-in.
    show_certifications = models.BooleanField(
        default=False,
        help_text="Whether to publish held certifications on this member profile.",
    )
    headline = models.CharField(max_length=200, blank=True, default="")
    institution = models.CharField(max_length=200, blank=True, default="")
    bio = models.TextField(blank=True, default="")
    avatar_key = models.CharField(max_length=500, blank=True, default="")
    # Free-form tag lists rather than link tables: they are unordered strings the member
    # types, nothing joins on them, and a table per tag kind would buy referential
    # integrity for data that has no referent. Length caps live in the serializer.
    interests = models.JSONField(default=list, blank=True)
    languages = models.JSONField(default=list, blank=True)
    education = models.JSONField(default=list, blank=True)
    github_username = models.CharField(max_length=39, blank=True, default="")
    # Null means "not known", which is what an unconfigured deployment, a rate-limited
    # GitHub and a never-synced profile all report. The surface omits the section rather
    # than rendering a zero, because a zero is a claim and None is not.
    github_contributions = models.PositiveIntegerField(null=True, blank=True)
    github_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_visible"], name="memberprofile_visible_idx"),
        ]

    def __str__(self):
        return f"Profile for {self.membership_id}"


class MemberProject(models.Model):
    profile = models.ForeignKey(
        MemberProfile, on_delete=models.CASCADE, related_name="projects"
    )
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=200, blank=True, default="")
    tags = models.JSONField(default=list, blank=True)
    public_visible = models.BooleanField(default=False)
    description = models.TextField(blank=True, default="")
    image_key = models.CharField(max_length=500, blank=True, default="")
    # `[{"label": ..., "url": ...}]`. Arbitrary labelled links, because a project's
    # relevant destinations are a repo for one member and a build log or a shop listing
    # for the next; a fixed set of columns would fit neither.
    links = models.JSONField(default=list, blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("position", "id")

    def __str__(self):
        return self.title


class PublicHandle(models.Model):
    """One global namespace claim, pointing at one explicitly chosen tenant profile."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name="public_handle", null=True, blank=True)
    profile = models.ForeignKey(MemberProfile, on_delete=models.CASCADE, related_name="handles", null=True, blank=True)
    makerspace = models.OneToOneField("makerspaces.Makerspace", null=True, blank=True,
                                     on_delete=models.CASCADE, related_name="public_handle")
    organization = models.OneToOneField("organizations.Organization", null=True, blank=True,
                                       on_delete=models.CASCADE, related_name="public_handle")
    handle = models.CharField(max_length=30, validators=[RegexValidator(HANDLE_PATTERN)])
    claimed_at = models.DateTimeField(auto_now_add=True)
    changed_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("handle"), name="public_handle_ci_unique"),
            models.CheckConstraint(condition=models.Q(handle__regex=HANDLE_PATTERN),
                                   name="public_handle_grammar"),
            models.CheckConstraint(condition=(
                models.Q(user__isnull=False, profile__isnull=False, makerspace__isnull=True, organization__isnull=True)
                | models.Q(user__isnull=True, profile__isnull=True, makerspace__isnull=False, organization__isnull=True)
                | models.Q(user__isnull=True, profile__isnull=True, makerspace__isnull=True, organization__isnull=False)
            ), name="public_handle_typed_owner"),
        ]


class PublicHandleRedirect(models.Model):
    """A retired claim reserves its name for thirty days; redirects require live consent."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                             on_delete=models.CASCADE, related_name="public_handle_redirects")
    profile = models.ForeignKey(MemberProfile, on_delete=models.CASCADE, related_name="handle_redirects", null=True, blank=True)
    makerspace = models.ForeignKey("makerspaces.Makerspace", null=True, blank=True,
                                   on_delete=models.CASCADE, related_name="public_handle_redirects")
    organization = models.ForeignKey("organizations.Organization", null=True, blank=True,
                                     on_delete=models.CASCADE, related_name="public_handle_redirects")
    handle = models.CharField(max_length=30)
    released_at = models.DateTimeField()
    expires_at = models.DateTimeField(db_index=True)

    def save(self, *args, **kwargs):
        # Compatibility for member-only callers; capture the stable account once.
        if self.profile_id and self.user_id is None:
            self.user_id = self.profile.membership.user_id
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("handle"), name="profile_redirect_ci_unique"),
            models.CheckConstraint(condition=models.Q(handle__regex=HANDLE_PATTERN), name="redirect_handle_grammar"),
            models.CheckConstraint(condition=(
                models.Q(user__isnull=False, profile__isnull=False, makerspace__isnull=True, organization__isnull=True)
                | models.Q(user__isnull=True, profile__isnull=True, makerspace__isnull=False, organization__isnull=True)
                | models.Q(user__isnull=True, profile__isnull=True, makerspace__isnull=True, organization__isnull=False)
            ), name="redirect_handle_typed_owner"),
        ]


class ProfileTimelineEntry(models.Model):
    class Kind(models.TextChoices):
        EXPERIENCE = "experience", "Experience"
        EDUCATION = "education", "Education"
        VOLUNTEERING = "volunteering", "Volunteering"

    profile = models.ForeignKey(MemberProfile, on_delete=models.CASCADE, related_name="timeline")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    title = models.CharField(max_length=200)
    organization = models.CharField(max_length=200, blank=True, default="")
    location = models.CharField(max_length=200, blank=True, default="")
    start = models.DateField()
    end = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True, default="")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("order", "-start", "id")
        constraints = [models.CheckConstraint(
            condition=models.Q(end__isnull=True) | models.Q(end__gte=models.F("start")),
            name="profile_timeline_date_order",
        )]
