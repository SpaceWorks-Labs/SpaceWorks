"""Release 2 L25 (#163B): one Metabase connection per space, and one for the platform.
Decision 263 adds Grafana to the same row (provider, URL, token, organization, dashboards).

Secrets never leave this row in clear: the Metabase embed secret, the Grafana
service-account token and the database login's password are Fernet ciphertext (`makerspaces.secrets`, the per-makerspace integration
pattern) and are decrypted only to sign an embed token or never again (the password is
shown once, when it is made). Who changed what lives in the audit log, not in actor
columns, so these rows carry no user foreign key.
"""

from django.utils.translation import gettext
from django.core.exceptions import ValidationError
from django.db import models

from apps.makerspaces.secrets import decrypt_value, encrypt_value

from .grafana_validation import PROVIDERS, validate_grafana_dashboards


def validate_dashboards(value):
    if not isinstance(value, list) or len(value) > 50:
        raise ValidationError(gettext("Dashboards must be a list of at most 50 entries."))
    seen = set()
    for entry in value:
        if not (isinstance(entry, dict) and set(entry) == {"id", "title"}):
            raise ValidationError(gettext("Each dashboard is {id, title}."))
        number, title = entry["id"], entry["title"]
        if not (isinstance(number, int) and not isinstance(number, bool) and 0 < number < 2**31):
            raise ValidationError(gettext("A dashboard id is a positive Metabase dashboard number."))
        if not (isinstance(title, str) and 0 < len(title.strip()) <= 120):
            raise ValidationError(gettext("A dashboard title is 1 to 120 characters."))
        if number in seen:
            raise ValidationError(gettext("A dashboard is listed once."))
        seen.add(number)


class ConnectionFields(models.Model):
    metabase_url = models.CharField(max_length=300, blank=True, default="")
    embed_secret = models.TextField(blank=True, default="")
    dashboards = models.JSONField(default=list, blank=True, validators=[validate_dashboards])
    telemetry_config = models.JSONField(default=dict, blank=True)
    login_role = models.CharField(max_length=63, blank=True, default="")
    login_password = models.TextField(blank=True, default="")
    login_created_at = models.DateTimeField(null=True, blank=True)
    login_rotated_at = models.DateTimeField(null=True, blank=True)
    # Decision 263: Grafana beside (or instead of) Metabase, over the same login and views.
    # The service-account token is Fernet ciphertext like the embed secret.
    provider = models.CharField(max_length=16, choices=[(key, key) for key in PROVIDERS], default="metabase")
    grafana_url = models.CharField(max_length=300, blank=True, default="")
    grafana_token = models.TextField(blank=True, default="")
    grafana_token_set_at = models.DateTimeField(null=True, blank=True)
    grafana_org_id = models.PositiveIntegerField(default=1)
    grafana_dashboards = models.JSONField(default=list, blank=True, validators=[validate_grafana_dashboards])
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def set_embed_secret(self, raw):
        self.embed_secret = encrypt_value(raw)

    def get_embed_secret(self):
        return decrypt_value(self.embed_secret)

    def set_grafana_token(self, raw):
        self.grafana_token = encrypt_value(raw)

    def get_grafana_token(self):
        return decrypt_value(self.grafana_token)

    def set_login_password(self, raw):
        self.login_password = encrypt_value(raw)


class AnalyticsConnection(ConnectionFields):
    """A space's Metabase: its URL, embed secret, listed dashboards and read-only login."""

    makerspace = models.OneToOneField(
        "makerspaces.Makerspace", on_delete=models.CASCADE, related_name="analytics_connection")
    # PII in the curated views (member names and emails) is masked unless this is on.
    show_member_details = models.BooleanField(default=False)

    def __str__(self):
        return f"analytics:{self.makerspace_id}"


class PlatformAnalyticsConnection(ConnectionFields):
    """The one platform-wide Metabase (superadmin): sees every space, never member details."""

    singleton = models.BooleanField(default=True, unique=True, editable=False)

    def __str__(self):
        return "analytics:platform"

    @classmethod
    def load(cls):
        row, _ = cls.objects.get_or_create(singleton=True)
        return row
