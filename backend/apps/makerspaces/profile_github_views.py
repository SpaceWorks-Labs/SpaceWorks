"""GitHub is a separately labelled calendar, never a SpaceWorks activity family."""

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.accounts.authentication import SpaceWorksJWTAuthentication

from .account_profile_access import resolve_by_handle
from .profile_github import calendar_for
from .public_profile_views import ERRORS, REDIRECT, PublicProfileBase


class GitHubDaySerializer(serializers.Serializer):
    date = serializers.DateField()
    count = serializers.IntegerField(min_value=0)


class GitHubCalendarSerializer(serializers.Serializer):
    source = serializers.ChoiceField(choices=["github"])
    days = GitHubDaySerializer(many=True)


class PublicProfileGitHubView(PublicProfileBase):
    authentication_classes = [SpaceWorksJWTAuthentication]

    @extend_schema(tags=["Public profiles"],
                   responses={200: GitHubCalendarSerializer, **REDIRECT, **ERRORS},
                   description="Cached GitHub calendar dates and daily counts, separately labelled from SpaceWorks. "
                               "Same readers as the profile; requires the activity-graph switch. "
                               "Empty when unconfigured, pending or unavailable.")
    def get(self, request, handle):
        self.cache_headers()
        profile, redirected = resolve_by_handle(handle, request.user, request)
        if not profile.show_activity_graph:
            raise NotFound()  # checked BEFORE the redirect: a retired URL never confirms a hidden graph
        if redirected:
            return Response(status=302, headers={"Location": f"/api/v1/public/profiles/{redirected}/github"})
        return Response(GitHubCalendarSerializer(calendar_for(profile)).data)
