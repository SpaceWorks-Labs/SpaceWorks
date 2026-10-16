"""Validated manager installation boundaries; never accept a personal destination."""
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .notification_slack_http import api, ProviderFailure
from .notification_slack_oauth import save_install


class InstallationStatusSerializer(serializers.Serializer):
    channel = serializers.CharField()
    generation = serializers.IntegerField()
    configured = serializers.BooleanField()


class OAuthStartSerializer(serializers.Serializer):
    connect_url = serializers.URLField()
    expires_at = serializers.DateTimeField()


class CallbackStatusSerializer(serializers.Serializer):
    verified = serializers.BooleanField()


class OAuthCallbackSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=2048)
    state = serializers.CharField(max_length=512)


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise ValidationError({"detail": "Unknown fields or invalid object."})
        return super().to_internal_value(data)


class MattermostInstallationSerializer(StrictSerializer):
    server_url = serializers.URLField(max_length=2048)
    bot_token = serializers.CharField(max_length=2048, write_only=True)
    client_id = serializers.RegexField(r"^[a-z0-9]{26}$", max_length=26)
    client_secret = serializers.CharField(max_length=2048, write_only=True)
    webhook_token = serializers.CharField(max_length=256, write_only=True)

    def validate_server_url(self, value):
        from .notification_mattermost_http import resolve_server, server_url
        base = server_url(value)
        resolve_server(base, "/api/v4/users/me")
        return base


class DiscordInstallationSerializer(StrictSerializer):
    bot_token = serializers.CharField(max_length=2048, write_only=True)
    application_id = serializers.RegexField(r"^[0-9]{1,20}$")
    public_key = serializers.RegexField(r"^[a-fA-F0-9]{64}$")
    guild_id = serializers.RegexField(r"^[0-9]{1,20}$")
    client_secret = serializers.CharField(max_length=2048, write_only=True)

    def validate_public_key(self, value):
        return value.lower()


def install_mattermost(config, actor, credentials):
    from .notification_mattermost_http import mattermost_api
    bot = mattermost_api(credentials["server_url"], "GET", "/api/v4/users/me", token=credentials["bot_token"])
    if not bot.get("is_bot") or not bot.get("id") or bot.get("delete_at"):
        raise ProviderFailure("invalid_endpoint")
    return save_install(config, actor, credentials, credentials["server_url"])


def install_discord(config, actor, credentials):
    from .notification_discord import API
    app = api("GET", API + "/applications/@me", token=credentials["bot_token"], auth="Bot")
    if app.get("id") != credentials["application_id"] or app.get("verify_key") != credentials["public_key"]:
        raise ProviderFailure("invalid_endpoint")
    guild = api("GET", API + f"/guilds/{credentials['guild_id']}", token=credentials["bot_token"], auth="Bot")
    if guild.get("id") != credentials["guild_id"]:
        raise ProviderFailure("invalid_endpoint")
    return save_install(config, actor, credentials, f"{credentials['application_id']}:{credentials['guild_id']}")
