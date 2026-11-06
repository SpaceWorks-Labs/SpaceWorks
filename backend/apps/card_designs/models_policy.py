"""Design-approval switches at four levels, most specific wins (#128 C-28, #136).

Levels: space, organisation, ID programme, event. Two domain groups: `membership`
(member cards and ID programmes, Q-I12) defaults to approval ON at the space level;
`event` (event ID cards and tickets) defaults to OFF (#128), and an event, its
organisation or the space may turn it on.
"""
from django.utils.translation import gettext_lazy
from django.db import models
from django.db.models import Q


class CardApprovalSetting(models.Model):
    class Group(models.TextChoices):
        MEMBERSHIP = "membership", gettext_lazy("Membership and programme cards")
        EVENT = "event", gettext_lazy("Event cards and tickets")

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    group = models.CharField(max_length=12, choices=Group.choices)
    organization = models.ForeignKey("organizations.Organization", null=True, blank=True, on_delete=models.CASCADE,
                                     related_name="+")
    programme = models.ForeignKey("id_programmes.IdProgramme", null=True, blank=True, on_delete=models.CASCADE,
                                  related_name="+")
    event = models.ForeignKey("events.Event", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    required = models.BooleanField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(name="card_approval_one_level", condition=(
                Q(organization__isnull=True, programme__isnull=True, event__isnull=True)
                | Q(organization__isnull=False, programme__isnull=True, event__isnull=True)
                | Q(organization__isnull=True, programme__isnull=False, event__isnull=True)
                | Q(organization__isnull=True, programme__isnull=True, event__isnull=False))),
            models.UniqueConstraint(fields=["makerspace", "group"], name="uniq_card_approval_space",
                                    condition=Q(organization__isnull=True, programme__isnull=True,
                                                event__isnull=True)),
            models.UniqueConstraint(fields=["makerspace", "group", "organization"], name="uniq_card_approval_org",
                                    condition=Q(organization__isnull=False)),
            models.UniqueConstraint(fields=["programme"], name="uniq_card_approval_programme",
                                    condition=Q(programme__isnull=False)),
            models.UniqueConstraint(fields=["event", "group"], name="uniq_card_approval_event",
                                    condition=Q(event__isnull=False)),
        ]
