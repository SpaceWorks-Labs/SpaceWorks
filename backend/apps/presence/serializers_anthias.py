from rest_framework import serializers

from .models_display import LAYOUTS, PRIVACY_LEVELS
from .serializers import StrictSerializer


class AnthiasPlayerSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    host_url = serializers.CharField()
    username = serializers.CharField(allow_blank=True)
    has_password = serializers.BooleanField(help_text="Whether a password is stored. The password is never returned.")
    api_version = serializers.CharField(allow_blank=True)
    anthias_version = serializers.CharField(allow_blank=True)
    status = serializers.ChoiceField(choices=["never", "ok", "error"])
    last_error = serializers.CharField(allow_blank=True, help_text="A short reason code, e.g. auth_failed or timeout.")
    last_synced_at = serializers.DateTimeField(allow_null=True)


class AnthiasPlayerListSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(help_text="Whether display.anthias_push is on for this space.")
    allow_private_hosts = serializers.BooleanField(help_text="Whether this deployment lets players sit on a private LAN address.")
    players = AnthiasPlayerSerializer(many=True)


class AnthiasPlayerWriteSerializer(StrictSerializer):
    name = serializers.CharField(max_length=80, required=False)
    host_url = serializers.CharField(max_length=200, required=False)
    username = serializers.CharField(max_length=80, required=False, allow_blank=True)
    password = serializers.CharField(max_length=200, required=False, allow_blank=True, write_only=True,
                                     help_text="Write-only. Blank clears it; omit to keep the stored one.")


class AnthiasTestSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    reason = serializers.CharField(allow_blank=True)
    api_version = serializers.CharField(allow_blank=True)
    anthias_version = serializers.CharField(allow_blank=True)


class DisplayLinkSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    url = serializers.CharField(help_text="The screen's address, with its secret in the fragment (a browser never sends a fragment to a server).")


class DisplayPlayersSerializer(StrictSerializer):
    player_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=10)


class NowConfigSerializer(StrictSerializer):
    sections = serializers.ListField(child=serializers.CharField(max_length=24), required=False, max_length=8)
    privacy = serializers.ChoiceField(choices=PRIVACY_LEVELS, required=False)
    refresh_seconds = serializers.IntegerField(required=False)


class NowConfigResponseSerializer(serializers.Serializer):
    sections = serializers.ListField(child=serializers.CharField())
    privacy = serializers.CharField()
    refresh_seconds = serializers.IntegerField()
    layouts = serializers.ListField(child=serializers.CharField(), default=list(LAYOUTS))
