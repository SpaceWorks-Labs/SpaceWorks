"""Approved brand accents. Only editorial accents inherit these colours."""

from types import MappingProxyType

from django.core.exceptions import ValidationError


ACCENT_PRESETS = MappingProxyType({
    "maker_teal": {"label": "Maker Teal", "background": "#006E63", "foreground": "#FFF4E8"},
    "workshop_orange": {"label": "Workshop Orange", "background": "#FF7447", "foreground": "#142C2A"},
    "citron": {"label": "Citron", "background": "#DFFF8F", "foreground": "#142C2A"},
    "sky_blue": {"label": "Sky Blue", "background": "#B5CDFF", "foreground": "#142C2A"},
    "warm_yellow": {"label": "Warm Yellow", "background": "#FFD447", "foreground": "#142C2A"},
})
ACCENT_CHOICES = tuple((key, value["label"]) for key, value in ACCENT_PRESETS.items())


def validate_accent_preset(value):
    if value is not None and (not isinstance(value, str) or value not in ACCENT_PRESETS):
        raise ValidationError("Choose a Space Works accent preset.", code="invalid_accent_preset")
    return value


def project_accent(value):
    """Legacy/unknown presets degrade to inherited theme; never reject tenant colours."""
    return dict(ACCENT_PRESETS[value]) if isinstance(value, str) and value in ACCENT_PRESETS else None
