from django.urls import path
from apps.organizations.views_governance import OrganizationMembershipDetailView
from apps.organizations.views_console import OrganizationLinksView, OrganizationLinkDeleteView

from apps.integrations.org_sender_views import OrganizationEmailSenderView
from apps.bookings.views_organization_hours_org import OrganizationOwnHoursBankView, OrganizationOwnHoursLedgerView
from apps.organizations.views_review import (
    OrganizationMemberRollupView, OrganizationResubmitView, OrganizationReviewQueueView,
    OrganizationReviewView,
)
from apps.organizations.views_admin import (
    OrganizationDetailView,
    OrganizationInvitationListCreateView,
    OrganizationInvitationRevokeView,
    OrganizationListView,
    OrganizationMembershipListView,
)


urlpatterns = [
    path("organization-reviews/", OrganizationReviewQueueView.as_view(), name="admin-organization-review-queue"),
    path("organizations/<int:pk>/review/", OrganizationReviewView.as_view(), name="admin-organization-review"),
    path("organizations/<int:pk>/resubmit/", OrganizationResubmitView.as_view(), name="admin-organization-resubmit"),
    path("organizations/<int:pk>/member-rollup/", OrganizationMemberRollupView.as_view(), name="admin-organization-member-rollup"),
    path("organizations/<int:pk>/hours-bank/", OrganizationOwnHoursBankView.as_view(), name="admin-organization-hours-bank"),
    path("organizations/<int:pk>/hours-bank/<int:makerspace_id>/ledger/", OrganizationOwnHoursLedgerView.as_view(), name="admin-organization-hours-ledger"),
    path("organizations/<int:pk>/memberships/<int:membership_id>/", OrganizationMembershipDetailView.as_view(), name="admin-organization-membership-detail"),
    path("organizations/<int:pk>/makerspaces/", OrganizationLinksView.as_view(), name="admin-organization-links"),
    path("organizations/<int:pk>/makerspaces/<int:makerspace_id>/", OrganizationLinkDeleteView.as_view(), name="admin-organization-link-delete"),
    path("organizations/", OrganizationListView.as_view(), name="admin-organization-list"),
    path("organizations/<int:pk>/", OrganizationDetailView.as_view(), name="admin-organization-detail"),
    path("organizations/<int:pk>/email-sender/", OrganizationEmailSenderView.as_view(),
         name="admin-organization-email-sender"),
    path(
        "organizations/<int:pk>/memberships/",
        OrganizationMembershipListView.as_view(),
        name="admin-organization-memberships",
    ),
    path(
        "organizations/<int:pk>/invitations/",
        OrganizationInvitationListCreateView.as_view(),
        name="admin-organization-invitations",
    ),
    path(
        "organization-invitations/<int:pk>/",
        OrganizationInvitationRevokeView.as_view(),
        name="admin-organization-invitation-revoke",
    ),
]
