"""Printed card numbers (O-B4, parity C4): one scheme per space default and per title override.

A scheme holds a LIVE `prefix`/`pattern` (what new cards use) and a DRAFT pair that only becomes live
when the design it belongs to is published (`numbering_publish`), so a draft's numbering never reaches
a card before approval. The counter is bumped under `select_for_update` inside the issue transaction.
"""
from django.db import models
from django.db.models import Q


class CardNumberScheme(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    title = models.ForeignKey("makerspaces.MembershipTitle", null=True, blank=True, on_delete=models.CASCADE,
                              related_name="+")
    prefix = models.CharField(max_length=6, blank=True, default="")
    pattern = models.CharField(max_length=40, blank=True, default="")
    draft_prefix = models.CharField(max_length=6, blank=True, default="")
    draft_pattern = models.CharField(max_length=40, blank=True, default="")
    published_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["makerspace"], condition=Q(title__isnull=True),
                                    name="uniq_card_number_scheme_space"),
            models.UniqueConstraint(fields=["makerspace", "title"], condition=Q(title__isnull=False),
                                    name="uniq_card_number_scheme_title"),
        ]

    @property
    def key(self):
        return f"title:{self.title_id}" if self.title_id else "default"


class CardNumberCounter(models.Model):
    """The next sequence value for one scheme; `year` is 0 when the pattern has no year token."""
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    scheme_key = models.CharField(max_length=32)
    year = models.PositiveSmallIntegerField(default=0)
    next_value = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["makerspace", "scheme_key", "year"],
                                               name="uniq_card_number_counter")]
