from django.utils.translation import gettext_noop
from django.conf import settings
from django.db import models


class SpaceHostingType(models.Model):
    """Decision 236: is this space the operator's OWN (unlimited) or one it HOSTS (plans, limits, billing)?

    No row means ``own``. Only the superadmin changes it (audited). It only matters while the
    install-wide hosting switch is on: with it off every space behaves as ``own``, whatever is
    stored here. Platform governance, never part of a tenant dump.
    """

    class Kind(models.TextChoices):
        OWN = "own", gettext_noop("Own space")
        HOSTED = "hosted", gettext_noop("Hosted space")

    makerspace = models.OneToOneField("makerspaces.Makerspace", on_delete=models.CASCADE,
                                      related_name="hosting_type_row")
    hosting_type = models.CharField(max_length=8, choices=Kind.choices, default=Kind.OWN)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.makerspace_id}: {self.hosting_type}"
