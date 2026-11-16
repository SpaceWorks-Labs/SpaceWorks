from django.urls import path

from .profile_github_views import PublicProfileGitHubView

urlpatterns = [
    path("public/profiles/<str:handle>/github", PublicProfileGitHubView.as_view(), name="public-profile-github"),
]
