"""Explicit capabilities, allowance and theme shapes for the frozen v1 envelope."""

from rest_framework import serializers as s
from drf_spectacular.utils import extend_schema_field
from .public_page_sections import PAYLOADS
from .public_page_contract import PALETTES


class PaletteChoices(s.Serializer):
    inherit = s.CharField(allow_null=True)
    maker_teal = s.CharField()
    workshop_orange = s.CharField()
    citron = s.CharField()
    sky_blue = s.CharField()
    warm_yellow = s.CharField()


class EditorCapabilities(s.Serializer):
    allowed_section_types = s.ListField(child=s.ChoiceField(choices=tuple(PAYLOADS)))
    required_groups = s.ListField(child=s.ChoiceField(choices=tuple(PAYLOADS)))
    palette_choices = PaletteChoices()
    can_edit_details = s.BooleanField()
    can_publish = s.BooleanField()
    suggested_handle = s.CharField(allow_null=True)


class PageLimits(s.Serializer):
    document_bytes = s.IntegerField()
    sections = s.IntegerField()
    assets = s.IntegerField()
    upload_bytes = s.IntegerField()
    storage_bytes = s.IntegerField(allow_null=True)
    storage_bytes_used = s.IntegerField()


class ThemeConfig(s.Serializer):
    mode = s.ChoiceField(choices=("system", "light", "dark"), required=False)
    logo_url = s.CharField(required=False, allow_blank=True)
    primary_color = s.CharField(required=False, allow_blank=True)
    accent_color = s.CharField(required=False, allow_blank=True)


@extend_schema_field({"type": "array", "items": {"type": "array", "minItems": 3, "maxItems": 3,
    "items": {"oneOf": [{"type": "string"}, {"type": "number"}]}}})
class PalettePairs(s.Field):
    def to_representation(self, value):
        return value


class Palette(s.Serializer):
    fill = s.ListField(child=s.IntegerField(), min_length=3, max_length=3)
    foreground = s.ListField(child=s.IntegerField(), min_length=3, max_length=3)
    hover = s.ListField(child=s.IntegerField(), min_length=3, max_length=3)
    active = s.ListField(child=s.IntegerField(), min_length=3, max_length=3)
    soft = s.ListField(child=s.IntegerField(), min_length=3, max_length=3)
    ink = s.ListField(child=s.IntegerField(), min_length=3, max_length=3)
    # Existing palette diagnostics are heterogeneous fixed tuples.
    pairs = PalettePairs(required=False)


class ResolvedTheme(s.Serializer):
    theme_config = ThemeConfig()
    light = Palette()
    dark = Palette()


class Presentation(s.Serializer):
    accent_choice = s.ChoiceField(choices=("inherit", *PALETTES))
    resolved_theme = ResolvedTheme()


class RevisionSummary(s.Serializer):
    section_types = s.ListField(child=s.ChoiceField(choices=tuple(PAYLOADS)))
