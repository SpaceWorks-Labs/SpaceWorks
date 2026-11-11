"""Parity O-B6 (decision 295): ``Makerspace.kind`` (makerspace | organization) is a plain
settings column - a closed enum, non-PII, non-secret, never a reference - and exports with
the space. ``HostingRequest`` is platform coordination state and stays omitted."""

EXTRA_FIELDS = {
    "makerspaces.Makerspace": "kind",
}


def extend(fields):
    for label, extra in EXTRA_FIELDS.items():
        fields[label] += " " + extra
    return fields
