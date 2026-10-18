"""Curated website content; publication is independent of the event lifecycle."""

from django.db import models
from django.db.models import F, Q

from .website_content import SPONSOR_TIERS, default_section_enabled, default_section_order


class EventPage(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    event = models.OneToOneField("events.Event", null=True, blank=True,
                                 on_delete=models.CASCADE, related_name="website_page")
    series = models.OneToOneField("events.EventSeries", null=True, blank=True,
                                  on_delete=models.CASCADE, related_name="website_page")
    released = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(default=1)
    tagline = models.CharField(max_length=300, blank=True)
    accent_color = models.CharField(max_length=7, blank=True)
    section_order = models.JSONField(default=default_section_order)
    section_enabled = models.JSONField(default=default_section_enabled)
    venue = models.JSONField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(
            condition=(Q(event__isnull=False, series__isnull=True)
                       | Q(event__isnull=True, series__isnull=False)),
            name="event_page_exact_owner",
        )]


class EventPageAsset(models.Model):
    page = models.ForeignKey(EventPage, on_delete=models.CASCADE, related_name="assets")
    object_key = models.CharField(max_length=300, unique=True)
    size_bytes = models.PositiveIntegerField()
    alt_text = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)


class EventPageSection(models.Model):
    """Typed page children share bounded editorial fields and slug identity."""

    class Kind(models.TextChoices):
        INTRO = "intro", "Introduction"
        LOGO = "logo", "Page logo"
        SPEAKER = "speaker", "Speaker"
        TRACK = "track", "Track"
        ROOM = "room", "Room"
        SPONSOR = "sponsor", "Sponsor"
        FAQ = "faq", "FAQ"
        RESOURCE = "resource", "Resource"
        HIGHLIGHT = "highlight", "Highlight"
        PRIZES = "prizes", "Prizes"
        JUDGES = "judges", "Judges"
        MENTORS = "mentors", "Mentors"
        PROJECT_GALLERY = "project_gallery", "Project gallery"
        RESULTS = "results", "Results"

    page = models.ForeignKey(EventPage, on_delete=models.CASCADE, related_name="sections")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    slug = models.SlugField(max_length=80)
    title = models.CharField(max_length=200)
    body = models.CharField(max_length=10000, blank=True)
    url = models.URLField(max_length=500, blank=True)
    asset = models.ForeignKey(EventPageAsset, on_delete=models.SET_NULL, null=True, blank=True)
    visibility = models.CharField(max_length=12, choices=(("draft", "Draft"), ("published", "Published")), default="draft")
    position = models.PositiveIntegerField(default=0)
    headline = models.CharField(max_length=200, blank=True)
    organization = models.CharField(max_length=200, blank=True)
    website_url = models.URLField(max_length=500, blank=True)
    linkedin_url = models.URLField(max_length=500, blank=True)
    x_url = models.URLField(max_length=500, blank=True)
    sponsor_tier = models.CharField(max_length=24, choices=[(tier, tier) for tier in SPONSOR_TIERS],
                                    default="community_partner")
    icon = models.CharField(max_length=40, blank=True)
    options = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("position", "id")
        constraints = [models.UniqueConstraint(fields=("page", "slug"), name="event_section_page_slug")]


class EventSession(models.Model):
    page = models.ForeignKey(EventPage, on_delete=models.CASCADE, related_name="sessions")
    slug = models.SlugField(max_length=80)
    title = models.CharField(max_length=200)
    body = models.CharField(max_length=10000, blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    track = models.ForeignKey(EventPageSection, on_delete=models.RESTRICT, null=True, blank=True, related_name="track_sessions")
    room = models.ForeignKey(EventPageSection, on_delete=models.RESTRICT, null=True, blank=True, related_name="room_sessions")
    delay_minutes = models.PositiveIntegerField(default=0)
    visibility = models.CharField(max_length=12, choices=(("draft", "Draft"), ("published", "Published")), default="draft")

    class Meta:
        ordering = ("starts_at", "id")
        constraints = [
            models.UniqueConstraint(fields=("page", "slug"), name="event_session_page_slug"),
            models.CheckConstraint(condition=Q(ends_at__gt=F("starts_at")), name="event_session_positive_window"),
            models.CheckConstraint(condition=Q(delay_minutes__lte=1440), name="event_session_delay_bound"),
        ]


class EventSessionSpeaker(models.Model):
    session = models.ForeignKey(EventSession, on_delete=models.CASCADE, related_name="speaker_links")
    speaker = models.ForeignKey(EventPageSection, on_delete=models.RESTRICT, related_name="session_links")

    class Meta:
        constraints = [models.UniqueConstraint(fields=("session", "speaker"), name="event_session_speaker_unique")]
