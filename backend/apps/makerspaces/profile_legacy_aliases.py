"""The per-space profile routes, kept as thin DEPRECATED aliases onto the account profile.

Decision 304 made the profile global, but shipped clients still call
`/member/makerspaces/<id>/profile/...`. Each alias keeps its old guard (an active membership of
that space plus the `membership` module -> the same 403) and then does exactly what the
account-level route does, so there is one implementation and no second place to forget a rule.
The path space only scopes the audit row; it no longer selects a profile.
"""

from drf_spectacular.openapi import AutoSchema
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from apps.accounts.account_kind_guards import require_member_account
from apps.makerspaces.guards import require_module
from apps.makerspaces.member_activity_service import active_membership
from apps.presence.guard import MemberPresenceRequired

from . import profile_services
from .account_profile_children_views import (
    AchievementDetailView, AchievementListView, TimelineDetailView, TimelineListView,
)
from .account_profile_views import ERRORS, AccountHandleView, GlobalProfileView
from .profile_image_views import AccountProfileImageView
from .profile_project_import import ProjectImportView
from .profile_serializers import ProfileReadSerializer, ProfileWriteSerializer


class DeprecatedSchema(AutoSchema):
    def is_deprecated(self):
        return True


class LegacyMembershipMixin:
    schema = DeprecatedSchema()

    def actor(self, request, makerspace_id=None, **kwargs):
        membership = active_membership(request.user, makerspace_id)
        if membership is None:
            raise MemberPresenceRequired()
        require_module(membership.makerspace, "membership")
        require_member_account(request.user)
        self.audit_space = membership.makerspace
        self.membership_ = membership
        return request.user


class LegacyProfileView(LegacyMembershipMixin, GlobalProfileView):
    @extend_schema(tags=["Member profile"], deprecated=True, request=None,
                   summary="Deprecated: use GET /member/profile",
                   responses={200: ProfileReadSerializer, **ERRORS})
    def get(self, request, **kwargs):
        self.actor(request, **kwargs)
        return Response(ProfileReadSerializer(profile_services.read_profile(self.membership_)).data)

    @extend_schema(tags=["Member profile"], deprecated=True, request=ProfileWriteSerializer,
                   summary="Deprecated: use PUT /member/profile",
                   responses={200: ProfileReadSerializer, **ERRORS})
    def put(self, request, **kwargs):
        self.actor(request, **kwargs)
        data = ProfileWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        profile_services.save_profile(self.membership_, data.validated_data)
        return Response(ProfileReadSerializer(profile_services.read_profile(self.membership_)).data)

    patch = put


class LegacyHandleView(LegacyMembershipMixin, AccountHandleView):
    pass


class LegacyTimelineListView(LegacyMembershipMixin, TimelineListView):
    pass


class LegacyTimelineDetailView(LegacyMembershipMixin, TimelineDetailView):
    pass


class LegacyAchievementListView(LegacyMembershipMixin, AchievementListView):
    pass


class LegacyAchievementDetailView(LegacyMembershipMixin, AchievementDetailView):
    pass


class LegacyProjectImportView(LegacyMembershipMixin, ProjectImportView):
    pass


class LegacyProfileImageView(LegacyMembershipMixin, AccountProfileImageView):
    pass
