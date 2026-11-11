from rest_framework import serializers
from apps.accounts.models_social import SocialSurface
from apps.accounts.safe_next import NextPathField


class OidcBrowserStartSerializer(serializers.Serializer):
    surface = serializers.ChoiceField(choices=SocialSurface.choices, default=SocialSurface.MEMBER)
    redirect_uri = serializers.URLField(max_length=2048)
    email = serializers.EmailField(required=False, allow_blank=True)
    makerspace_slug = serializers.SlugField(required=False, allow_blank=True)
    next = NextPathField()


class SocialLinkStartSerializer(serializers.Serializer):
    """Linking binds to the signed-in session; no surface, email or makerspace selector."""
    redirect_uri = serializers.URLField(max_length=2048)


class OidcBrowserStartResponseSerializer(serializers.Serializer):
    authorization_url = serializers.URLField()
    state = serializers.CharField()
    nonce = serializers.CharField()
    expires_in = serializers.IntegerField()


class OidcBrowserCallbackSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=4096, trim_whitespace=True)
    state = serializers.CharField(max_length=512, trim_whitespace=True)
    nonce = serializers.CharField(max_length=512, trim_whitespace=True)


class OidcBrowserLoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    user = serializers.DictField()
    outcome = serializers.CharField()
    next = serializers.CharField(required=False, help_text="The validated `next` path given at start, when any.")
