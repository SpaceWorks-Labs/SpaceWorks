"""Release-2 lane L25 (#163B): the analytics connection and its read-only database login.

Leaves are the audience (space or platform), the login's role name, the changed field
NAMES, the member-details switch and the dashboard number: never a URL, an embed secret, a
password or a verifier.
"""

from django.utils.translation import gettext_lazy
from .presentation_catalog_types import P

ENTRIES = (
    P("analytics.credentials_viewed", gettext_lazy("Analytics credentials viewed"), ("scope", "role")),
    P("analytics.connection_updated", gettext_lazy("Analytics connection changed"), ("scope", "fields", "show_member_details")),
    P("analytics.login_created", gettext_lazy("Analytics database login created"), ("scope", "role", "password_shown")),
    P("analytics.login_rotated", gettext_lazy("Analytics database login password rotated"), ("scope", "role", "password_shown")),
    P("analytics.login_revoked", gettext_lazy("Analytics database login revoked"), ("scope", "role")),
    P("analytics.dashboard_viewed", gettext_lazy("Analytics dashboard opened"), ("scope", "dashboard")),
)
