"""Parity O-B6 (decision 295): tenant-dump field snapshot for ``Makerspace.kind``.

A closed-enum settings column that travels with the space like any other preserved
setting; it selects no target authority or disclosure."""

EXTRA_FIELDS = {
    "makerspaces.Makerspace": frozenset({"kind"}),
}
