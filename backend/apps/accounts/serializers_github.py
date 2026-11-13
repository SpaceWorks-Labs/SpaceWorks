from rest_framework import serializers
from apps.accounts.safe_next import NextPathField


class GithubBrowserStartSerializer(serializers.Serializer):
    redirect_uri = serializers.URLField(max_length=2048)
    nonce = serializers.RegexField(r"^[A-Za-z0-9_-]{43,128}$", write_only=True)
    next = NextPathField()


class GithubBrowserStartResponseSerializer(serializers.Serializer):
    authorization_url = serializers.URLField()
    state = serializers.CharField()
    expires_in = serializers.IntegerField()
