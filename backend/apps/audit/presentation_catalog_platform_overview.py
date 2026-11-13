"""Release-2 lane r2-platform-overview (#183A): the superadmin platform overview export.

Leaves are the period preset, the excluded-spaces toggle and two counts: never a space
name, an amount or any person data.
"""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("platform.overview_exported", gettext_noop("Platform overview exported"), ("period", "include_excluded", "spaces", "rows")),
    # Decision 242(l): counts only; the search text is never stored.
    P("platform.inbox_viewed", gettext_noop("Cross-space inbox viewed"), ("spaces",)),
    P("platform.searched", gettext_noop("Platform search run"), ("hits", "kinds")),
    # Open item C13: the platform admin list was read (a count only).
    P("platform.admins_viewed", gettext_noop("Platform admin list viewed"), ("admins",)),
)
