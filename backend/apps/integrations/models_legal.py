"""Platform-level privacy / terms content (parity E-B8, decision 294).

One row per page and language. A missing row means "use the shipped default" (``operations/legal_pages.py``),
so a fresh install serves honest text without any operator work. Platform governance data: never part of a
space's own copy and never in a tenant dump. A space's own override lives in ``branding_config["legal_pages"]``.
"""

from django.db import models


class PlatformLegalPage(models.Model):
    class Slug(models.TextChoices):
        PRIVACY = "privacy", "Privacy"
        TERMS = "terms", "Terms"

    slug = models.CharField(max_length=16, choices=Slug.choices)
    # "" = the page for every language the operator did not translate.
    language = models.CharField(max_length=16, blank=True, default="")
    markdown = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["slug", "language"], name="uniq_platform_legal_page")]
        ordering = ("slug", "language")

    def __str__(self):
        return f"{self.slug}/{self.language or '*'}"
