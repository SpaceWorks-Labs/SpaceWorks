"""Release-2 lane L26 (public stats page, #170): tenant-dump field snapshot.

Five plain Makerspace settings columns travel as ordinary tenant content (no authority
override): they only shape what the public stats page shows, still bounded by the target's
own modules and its page switch.
"""

from apps.data_export.classification_r2_l26 import EXTRA_FIELDS as _EXPORTED

EXTRA_FIELDS = {label: frozenset(names.split()) for label, names in _EXPORTED.items()}
