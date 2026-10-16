"""Curated public content. Ownership follows the typed resource, never a generic ID."""

from django.db import models


class BookingResourcePage(models.Model):
    space = models.OneToOneField("bookings.BookableSpace", on_delete=models.CASCADE,
                                 related_name="website_page")
    released = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def makerspace(self):
        return self.space.makerspace

    @property
    def makerspace_id(self):
        return self.space.makerspace_id


class BookingResourcePageAsset(models.Model):
    page = models.ForeignKey(BookingResourcePage, on_delete=models.CASCADE, related_name="assets")
    object_key = models.CharField(max_length=300, unique=True)
    size_bytes = models.PositiveIntegerField()
    alt_text = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)


class BookingResourcePageSection(models.Model):
    class Kind(models.TextChoices):
        RULES = "rules", "Rules"
        AMENITY = "amenity", "Amenity"
        FAQ = "faq", "FAQ"
        LINK = "link", "Link"
        SPONSOR = "sponsor", "Sponsor"
        GALLERY = "gallery", "Gallery"

    page = models.ForeignKey(BookingResourcePage, on_delete=models.CASCADE, related_name="sections")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    slug = models.SlugField(max_length=80)
    title = models.CharField(max_length=200)
    body = models.CharField(max_length=10000, blank=True)
    url = models.URLField(max_length=500, blank=True)
    asset = models.ForeignKey(BookingResourcePageAsset, on_delete=models.SET_NULL, null=True, blank=True)
    visibility = models.CharField(max_length=12, choices=(("draft", "Draft"), ("published", "Published")), default="draft")
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("position", "id")
        constraints = [models.UniqueConstraint(fields=("page", "slug"), name="booking_section_page_slug")]
