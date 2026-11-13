from rest_framework import serializers

from .models_display import LAYOUTS, MAX_REFRESH, MAX_ROTATION, MIN_REFRESH, MIN_ROTATION, PANELS, PRIVACY_LEVELS, THEMES
from .serializers import StrictSerializer


class DisplayCardSerializer(serializers.Serializer):
    handle = serializers.CharField(allow_null=True)
    display_name = serializers.CharField()
    avatar_url = serializers.CharField(allow_null=True)
    headline = serializers.CharField(allow_blank=True)
    status = serializers.DictField(allow_null=True)
    skills = serializers.ListField(child=serializers.CharField())
    presence_status = serializers.CharField()
    since = serializers.DateTimeField()


class HereNowSerializer(serializers.Serializer):
    audience = serializers.ChoiceField(choices=["public", "member"])
    people = DisplayCardSerializer(many=True)
    others_count = serializers.IntegerField()
    total = serializers.IntegerField()


class MachineNowItemSerializer(serializers.Serializer):
    name = serializers.CharField()
    type = serializers.CharField()
    status = serializers.ChoiceField(choices=["in_use", "free", "out_of_service"])


class MachinesNowSerializer(serializers.Serializer):
    in_use = serializers.IntegerField()
    free = serializers.IntegerField()
    out_of_service = serializers.IntegerField()
    items = MachineNowItemSerializer(many=True)


class InventoryHighlightsSerializer(serializers.Serializer):
    items = serializers.ListField(child=serializers.DictField(),
                                  help_text="name, category, image_url and the public availability object.")


class SponsorsWallSerializer(serializers.Serializer):
    sponsors = serializers.ListField(child=serializers.DictField(), help_text="name, tier and logo_url.")


class DisplayRegisterResponseSerializer(serializers.Serializer):
    token = serializers.CharField(help_text="The screen's secret; keep it, it is shown once.")
    code = serializers.CharField()
    code_expires_at = serializers.DateTimeField()


class DisplayStateSerializer(serializers.Serializer):
    state = serializers.ChoiceField(choices=["unclaimed", "paired"])
    code = serializers.CharField(required=False)
    code_expires_at = serializers.DateTimeField(required=False)
    generated_at = serializers.DateTimeField(required=False)
    space = serializers.DictField(required=False)
    config = serializers.DictField(required=False)
    here_now = HereNowSerializer(allow_null=True, required=False)
    calendar = serializers.DictField(allow_null=True, required=False)
    machines = MachinesNowSerializer(allow_null=True, required=False)
    announcement = serializers.CharField(allow_null=True, required=False)
    public_stats = serializers.DictField(allow_null=True, required=False)
    opening_hours = serializers.DictField(allow_null=True, required=False)
    inventory_highlights = InventoryHighlightsSerializer(allow_null=True, required=False)
    sponsors = SponsorsWallSerializer(allow_null=True, required=False)


class DisplayConfigSerializer(StrictSerializer):
    name = serializers.CharField(max_length=80, required=False, allow_blank=True)
    panels = serializers.ListField(child=serializers.ChoiceField(choices=PANELS), required=False)
    rotation_seconds = serializers.IntegerField(min_value=MIN_ROTATION, max_value=MAX_ROTATION, required=False)
    announcement = serializers.CharField(max_length=280, required=False, allow_blank=True)
    layout = serializers.ChoiceField(choices=LAYOUTS, required=False)
    theme = serializers.ChoiceField(choices=THEMES, required=False)
    privacy = serializers.ChoiceField(choices=PRIVACY_LEVELS, required=False,
                                      help_text="`profiles` is the pre-settings behaviour; the others only show less.")
    refresh_seconds = serializers.IntegerField(min_value=MIN_REFRESH, max_value=MAX_REFRESH, required=False)
    slide_seconds = serializers.DictField(child=serializers.IntegerField(min_value=MIN_ROTATION, max_value=MAX_ROTATION),
                                          required=False, help_text="Per-panel seconds for the playlist layout.")


class DisplayClaimSerializer(DisplayConfigSerializer):
    code = serializers.CharField(max_length=8)


class DisplayAdminSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    panels = serializers.ListField(child=serializers.CharField())
    rotation_seconds = serializers.IntegerField()
    announcement = serializers.CharField()
    layout = serializers.CharField()
    theme = serializers.CharField()
    privacy = serializers.CharField()
    refresh_seconds = serializers.IntegerField()
    slide_seconds = serializers.DictField()
    player_ids = serializers.ListField(child=serializers.IntegerField())
    has_link = serializers.BooleanField(help_text="A link screen (Anthias): it has a staff-issued address.")
    url = serializers.CharField(allow_blank=True, help_text="The secret-bearing address, only in the provision and "
                                                            "New address responses; empty everywhere else.")
    claimed_at = serializers.DateTimeField()
    last_seen_at = serializers.DateTimeField(allow_null=True)
    online = serializers.BooleanField()


class DisplayListSerializer(serializers.Serializer):
    displays = DisplayAdminSerializer(many=True)
    enabled = serializers.BooleanField(help_text="Whether presence.public_display is on for this space.")
