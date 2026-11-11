"""Release-2 lane L25 (#163B): the analytics connection and its read-only database login.

Leaves are the audience (space or platform), the login's role name, the changed field
NAMES, the member-details switch and the dashboard number: never a URL, an embed secret, a
password or a verifier.
"""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("analytics.credentials_viewed", gettext_noop("Analytics credentials viewed"), ("scope", "role")),
    P("analytics.connection_updated", gettext_noop("Analytics connection changed"), ("scope", "fields", "show_member_details")),
    P("analytics.login_created", gettext_noop("Analytics database login created"), ("scope", "role", "password_shown")),
    P("analytics.login_rotated", gettext_noop("Analytics database login password rotated"), ("scope", "role", "password_shown")),
    P("analytics.login_revoked", gettext_noop("Analytics database login revoked"), ("scope", "role")),
    P("analytics.dashboard_viewed", gettext_noop("Analytics dashboard opened"), ("scope", "dashboard")),
    # Decision 263 (Grafana): leaves name the provider, field names, areas, the dashboard uid and
    # the outcome; never the Grafana URL, the service-account token or a public access token.
    P("analytics.grafana_credentials_viewed", gettext_noop("Grafana connection viewed"), ("scope", "token_set")),
    P("analytics.grafana_connection_updated", gettext_noop("Grafana connection changed"), ("scope", "fields", "provider")),
    P("analytics.grafana_token_created", gettext_noop("Grafana token saved"), ("scope",)),
    P("analytics.grafana_token_rotated", gettext_noop("Grafana token replaced"), ("scope",)),
    P("analytics.grafana_token_revoked", gettext_noop("Grafana token removed"), ("scope",)),
    P("analytics.grafana_connection_tested", gettext_noop("Grafana connection tested"), ("scope", "ok")),
    P("analytics.grafana_bundle_downloaded", gettext_noop("Grafana bundle downloaded"), ("scope", "areas", "archive")),
    P("analytics.grafana_dashboard_viewed", gettext_noop("Grafana dashboard opened"), ("scope", "dashboard", "mode")),
)
