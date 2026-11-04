from django.urls import path

from apps.hosting_requests.views_public import (
    HostingInvitationResolveView,
    HostingInvitationSubmitView,
    HostingRequestOpenView,
    HostingRequestResubmitView,
    HostingRequestSubmitView,
)

urlpatterns = [
    path("requests", HostingRequestSubmitView.as_view(), name="public-hosting-request-submit"),
    path("requests/open", HostingRequestOpenView.as_view(), name="public-hosting-request-open"),
    path("requests/resubmit", HostingRequestResubmitView.as_view(), name="public-hosting-request-resubmit"),
    path(
        "invitations/resolve",
        HostingInvitationResolveView.as_view(),
        name="public-hosting-invitation-resolve",
    ),
    path(
        "invitations/submit",
        HostingInvitationSubmitView.as_view(),
        name="public-hosting-invitation-submit",
    ),
]
