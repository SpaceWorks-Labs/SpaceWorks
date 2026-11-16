"""Minimal roster and opted-in finder contracts; never private account fallbacks."""
from rest_framework import serializers


class PublicProfileSerializer(serializers.Serializer):
    display_name = serializers.CharField(required=False)
    url = serializers.CharField(required=False)
    photo_url = serializers.CharField(required=False)


class RosterMemberSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    member_id = serializers.IntegerField()
    joined_at = serializers.DateTimeField()
    profile = PublicProfileSerializer(allow_null=True)


class JoinRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    profile = PublicProfileSerializer(allow_null=True)


class FinderCardSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    version = serializers.IntegerField()
    kind = serializers.ChoiceField(choices=["person", "team"])
    intro = serializers.CharField()
    skills = serializers.ListField(child=serializers.CharField())
    name = serializers.CharField(required=False)
    slots = serializers.IntegerField(required=False)
    profile = PublicProfileSerializer(allow_null=True, required=False)
    profiles = PublicProfileSerializer(many=True, required=False)
