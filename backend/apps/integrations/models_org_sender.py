"""A co-hosting organisation's display sender for event email (#71 X2, #115a).

Only the display name and the reply-to change. The From ADDRESS, the SMTP/provider
connection, the email module gate and every suppression rule stay the hosting space's,
so an organisation can never send through a space that has email switched off.
"""

from django.conf import settings
from django.db import models


class OrganizationEmailSender(models.Model):
    organization = models.OneToOneField("organizations.Organization", on_delete=models.CASCADE,
                                        related_name="email_sender")
    sender_name = models.CharField(max_length=80, blank=True)
    reply_to = models.EmailField(max_length=254, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "integrations"
