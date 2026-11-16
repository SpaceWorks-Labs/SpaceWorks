"""Included below /api/v1/ by the makerspaces URL barrel."""
from django.urls import path
from .public_profile_views import (
    PublicProfileView, PublicProfileActivityView, PublicProfileProjectsView, PublicProfileEventsView,
)
from .handle_views import HandleCheckView
from .profile_github_urls import urlpatterns as github_patterns
from .account_profile_views import AccountHandleView, GlobalProfileView, ProfileByAccountView
from .account_profile_children_views import (
    AchievementDetailView, AchievementListView, TimelineDetailView, TimelineListView,
)
from .profile_image_views import AccountProfileImageView
from .profile_project_import import ProjectImportView
from .profile_legacy_aliases import (
    LegacyAchievementDetailView, LegacyAchievementListView, LegacyHandleView, LegacyProjectImportView,
    LegacyTimelineDetailView, LegacyTimelineListView,
)

LEGACY = "member/makerspaces/<int:makerspace_id>/profile"

urlpatterns = [
    *github_patterns,
    path("handles/check", HandleCheckView.as_view(), name="handle-check"),
    path("public/profiles/<str:handle>/", PublicProfileView.as_view(), name="public-profile"),
    path("public/profiles/<str:handle>/activity", PublicProfileActivityView.as_view(), name="public-profile-activity"),
    path("public/profiles/<str:handle>/events", PublicProfileEventsView.as_view(), name="public-profile-events"),
    path("public/profiles/<str:handle>/projects", PublicProfileProjectsView.as_view(), name="public-profile-projects"),
    path("profiles/by-account/<int:user_id>/", ProfileByAccountView.as_view(), name="profile-by-account"),
    # Account-level owner routes (decision 304): the profile is global, no makerspace in the path.
    path("member/profile", GlobalProfileView.as_view(), name="member-global-profile"),
    path("member/profile/handle", AccountHandleView.as_view(), name="member-global-profile-handle"),
    path("member/profile/image", AccountProfileImageView.as_view(), name="member-global-profile-image"),
    path("member/profile/timeline", TimelineListView.as_view(), name="member-global-profile-timeline"),
    path("member/profile/timeline/<int:pk>", TimelineDetailView.as_view(), name="member-global-profile-timeline-detail"),
    path("member/profile/achievements", AchievementListView.as_view(), name="member-global-profile-achievements"),
    path("member/profile/achievements/<int:pk>", AchievementDetailView.as_view(), name="member-global-profile-achievement-detail"),
    path("member/profile/project-import", ProjectImportView.as_view(), name="member-global-profile-project-import"),
    # Deprecated per-space aliases onto the same implementation (kept for shipped clients).
    path(f"{LEGACY}/handle", LegacyHandleView.as_view(), name="member-profile-handle"),
    path(f"{LEGACY}/timeline", LegacyTimelineListView.as_view(), name="member-profile-timeline"),
    path(f"{LEGACY}/timeline/<int:pk>", LegacyTimelineDetailView.as_view(), name="member-profile-timeline-detail"),
    path(f"{LEGACY}/achievements", LegacyAchievementListView.as_view(), name="member-profile-achievements"),
    path(f"{LEGACY}/achievements/<int:pk>", LegacyAchievementDetailView.as_view(), name="member-profile-achievement-detail"),
    path(f"{LEGACY}/project-import", LegacyProjectImportView.as_view(), name="member-profile-project-import"),
]
