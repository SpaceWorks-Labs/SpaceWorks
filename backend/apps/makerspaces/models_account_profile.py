"""The global, account-level member profile (decisions 302-305).

**One profile per person, hung off `accounts.User`**, addressed by the account's public handle like
a username and visible to every signed-in user by default (decision 303a). It supersedes the
per-membership `MemberProfile`, whose rows stay in place, read-only, for one more release
(decision 304d: no data is deleted in this release).

**Why it is still deliberately NOT PII-encrypted.** Scoped encryption is per makerspace and `User`
is platform-global, so a field on the user cannot be scoped to anything -- which is why
`accounts.User` is outside the PII registry. Every column here is content the member typed in
order to have it shown (headline, bio, links), and the identifying fields (email, phone) stay on
`User`. `ScopedPiiModelMixin` is therefore omitted on purpose; `separability.E001` only fires for
models that take the mixin.

**Account-level data, never tenant data.** None of these four models is in a tenant dump or a
space export: a space only ever sees the *directory projection* (name, headline, avatar) built from
this row at read time. They travel with the account (merge, purge) rather than with a makerspace.

Defaults (decision 303): `is_visible` and every section toggle default True, the open web
(`public_visible` + `public_consented_at`) defaults False.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy

STATUS_CHOICES = (
    ("student", gettext_lazy("Student")),
    ("working", gettext_lazy("Working")),
    ("freelancing", gettext_lazy("Freelancing")),
    ("looking_for_work", gettext_lazy("Looking for work")),
    ("open_to_collaborate", gettext_lazy("Open to collaborate")),
    ("building_startup", gettext_lazy("Building a startup")),
    ("other", gettext_lazy("Other")),
)
STATUS_KEYS = tuple(key for key, _ in STATUS_CHOICES)

# Every per-section toggle on the profile. The write serializer, the audit `sections_changed`
# meta and the reader all iterate this one tuple so a new section cannot be forgotten in one.
SECTION_TOGGLES = (
    "show_status", "show_about", "show_experience", "show_education", "show_achievements",
    "show_projects", "show_skills", "show_links", "show_interests", "show_events",
    "show_spaces", "show_certifications",
)


# Counts-only activity graph switches (decision 304c: the graph is account-level too). The master and
# the two content families (events, projects) follow the open default; the families that expose
# operational history of the person (speaking, machine jobs, bookings, loans) stay opt-in, as before.
ACTIVITY_TOGGLES = ("show_activity_graph", "show_speaking", "show_machine_activity", "show_bookings", "show_loans")


class AccountProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="account_profile",
    )
    is_visible = models.BooleanField(
        default=True,
        help_text=gettext_lazy("Whether signed-in users can see this profile."),
    )
    public_visible = models.BooleanField(default=False)
    public_consented_at = models.DateTimeField(null=True, blank=True, editable=False)
    show_status = models.BooleanField(default=True)
    show_about = models.BooleanField(default=True)
    show_experience = models.BooleanField(default=True)
    show_education = models.BooleanField(default=True)
    show_achievements = models.BooleanField(default=True)
    show_projects = models.BooleanField(default=True)
    show_skills = models.BooleanField(default=True)
    show_links = models.BooleanField(default=True)
    show_interests = models.BooleanField(default=True)
    show_events = models.BooleanField(default=True)
    show_spaces = models.BooleanField(default=True)
    show_certifications = models.BooleanField(default=True)
    show_activity_graph = models.BooleanField(default=True)
    show_speaking = models.BooleanField(default=False)
    show_machine_activity = models.BooleanField(default=False)
    show_bookings = models.BooleanField(default=False)
    show_loans = models.BooleanField(default=False)
    headline = models.CharField(max_length=200, blank=True, default="")
    status = models.CharField(max_length=24, blank=True, default="", choices=STATUS_CHOICES)
    status_note = models.CharField(max_length=120, blank=True, default="")
    institution = models.CharField(max_length=200, blank=True, default="")
    bio = models.TextField(blank=True, default="")
    avatar_key = models.CharField(max_length=500, blank=True, default="")
    domains = models.JSONField(default=list, blank=True)
    skills = models.JSONField(default=list, blank=True)
    links = models.JSONField(default=list, blank=True)
    interests = models.JSONField(default=list, blank=True)
    languages = models.JSONField(default=list, blank=True)
    education = models.JSONField(default=list, blank=True)
    github_username = models.CharField(max_length=39, blank=True, default="")
    # None means "not known" (unconfigured, rate-limited or never synced): the surface omits the section.
    github_contributions = models.PositiveIntegerField(null=True, blank=True)
    github_synced_at = models.DateTimeField(null=True, blank=True)
    # Set by the legacy merge (decision 304d) so it never runs twice for a user, and so the
    # one-time "your profile is now visible" notice (303d) is sent exactly once.
    merged_from_legacy = models.BooleanField(default=False, editable=False)
    open_notice_pending = models.BooleanField(default=False, editable=False)
    # Decision 335c: the merge turned the open web OFF because not every merged legacy profile had
    # consented; the member is asked once to confirm again. Cleared by any explicit open-web choice.
    public_reconfirm_pending = models.BooleanField(default=False, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["open_notice_pending"], name="acctprofile_notice_idx")]

    def __str__(self):
        return f"Account profile for {self.user_id}"


class AccountProject(models.Model):
    profile = models.ForeignKey(AccountProfile, on_delete=models.CASCADE, related_name="projects")
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=200, blank=True, default="")
    tags = models.JSONField(default=list, blank=True)
    # "Shown on the profile": True by default now that the profile itself is open (303a).
    public_visible = models.BooleanField(default=True)
    description = models.TextField(blank=True, default="")
    image_key = models.CharField(max_length=500, blank=True, default="")
    links = models.JSONField(default=list, blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    # Decision 302d: the hackathon submission this project was imported from. A stored id,
    # not an FK, so a tombstoned or purged event never blocks (or is blocked by) a profile.
    source_submission_id = models.PositiveBigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("position", "id")
        constraints = [models.UniqueConstraint(
            fields=("profile", "source_submission_id"), name="account_project_one_import_per_submission")]

    def __str__(self):
        return self.title


class AccountTimelineEntry(models.Model):
    class Kind(models.TextChoices):
        EXPERIENCE = "experience", "Experience"
        EDUCATION = "education", "Education"
        VOLUNTEERING = "volunteering", "Volunteering"

    profile = models.ForeignKey(AccountProfile, on_delete=models.CASCADE, related_name="timeline")
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
            name="account_timeline_date_order",
        )]


class ProfileAchievement(models.Model):
    """A self-reported achievement the member typed (decision 302c).

    Always labelled "self-reported" next to the derived, space-verified ones; nothing here is ever
    checked against SpaceWorks data, so nothing here can be mistaken for proof.
    """

    profile = models.ForeignKey(AccountProfile, on_delete=models.CASCADE, related_name="achievements")
    title = models.CharField(max_length=160)
    issuer = models.CharField(max_length=160, blank=True, default="")
    achieved_on = models.DateField(null=True, blank=True)
    url = models.URLField(max_length=500, blank=True, default="")
    description = models.TextField(max_length=2000, blank=True, default="")
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("order", "-achieved_on", "id")
