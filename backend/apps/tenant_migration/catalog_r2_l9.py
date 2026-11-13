"""Release-2 lane L9 (phase 8 i18n): tenant-dump field snapshot.

Two plain locale-code columns, no authority override: ``Makerspace.default_locale`` is an
ordinary preserved tenant setting, and ``User.preferred_locale`` travels with a full
tenant-exclusive user (an inert stub gets null; a linked existing target user keeps its
own). Neither selects target authority or disclosure.
"""

EXTRA_FIELDS = {
    "makerspaces.Makerspace": frozenset({"default_locale"}),
    "accounts.User": frozenset({"preferred_locale"}),
}
