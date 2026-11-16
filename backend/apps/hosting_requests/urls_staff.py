from django.urls import path

from apps.hosting_requests.views_staff import (
    MakerspaceHostingInvitationCancelView,
    MakerspaceHostingInvitationsView,
    OrganizationHostingInvitationCancelView,
    OrganizationHostingInvitationsView,
)

urlpatterns = [
    path(
        "makerspaces/<int:makerspace_id>/hosting-invitations",
        MakerspaceHostingInvitationsView.as_view(),
        name="admin-makerspace-hosting-invitations",
    ),
    path(
        "makerspaces/<int:makerspace_id>/hosting-invitations/<int:pk>/cancel",
        MakerspaceHostingInvitationCancelView.as_view(),
        name="admin-makerspace-hosting-invitation-cancel",
    ),
    path(
        "organizations/<int:pk>/hosting-invitations/",
        OrganizationHostingInvitationsView.as_view(),
        name="admin-organization-hosting-invitations",
    ),
    path(
        "organizations/<int:pk>/hosting-invitations/<int:invitation_id>/cancel",
        OrganizationHostingInvitationCancelView.as_view(),
        name="admin-organization-hosting-invitation-cancel",
    ),
]
