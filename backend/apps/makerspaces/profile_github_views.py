"""GitHub is a separately labelled calendar, never a SpaceWorks activity family."""

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from .profile_github import calendar_for
from .public_profile_views import ERRORS, REDIRECT, PublicProfileBase


class GitHubDaySerializer(serializers.Serializer):
    date = serializers.DateField()
    count = serializers.IntegerField(min_value=0)


class GitHubCalendarSerializer(serializers.Serializer):
    source = serializers.ChoiceField(choices=["github"])
    days = GitHubDaySerializer(many=True)


class PublicProfileGitHubView(PublicProfileBase):
    @extend_schema(tags=["Public profiles"], auth=[],
                   responses={200: GitHubCalendarSerializer, **REDIRECT, **ERRORS},
                   description="Cached GitHub calendar dates and daily counts, separately labelled from SpaceWorks. "
                               "Requires activity-graph consent. Empty when unconfigured, pending or unavailable.")
    def get(self, request, handle):
        claim, redirect = self.resolve(request, handle, "github")
        if not claim.profile.show_activity_graph:
            raise NotFound()
        if redirect is not None:
            return redirect
        return Response(GitHubCalendarSerializer(calendar_for(claim)).data)
