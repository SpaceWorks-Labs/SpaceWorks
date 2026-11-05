"""Release-2 lane r2-platform-overview (#183A): the superadmin platform overview export.

Leaves are the period preset, the excluded-spaces toggle and two counts: never a space
name, an amount or any person data.
"""

from .presentation_catalog_types import P

ENTRIES = (
    P("platform.overview_exported", "Platform overview exported", ("period", "include_excluded", "spaces", "rows")),
)
