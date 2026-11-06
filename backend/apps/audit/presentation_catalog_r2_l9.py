"""Release-2 lane L9 (phase 8 i18n): language preference changes.

Leaves are the two locale codes (``default`` when an account follows its makerspace):
never anything else about the account.
"""

from django.utils.translation import gettext_lazy
from .presentation_catalog_types import P

ENTRIES = (
    P("account.locale_changed", gettext_lazy("Account language changed"), ("before", "after")),
    P("makerspace.default_locale_changed", gettext_lazy("Makerspace default language changed"), ("before", "after")),
)
