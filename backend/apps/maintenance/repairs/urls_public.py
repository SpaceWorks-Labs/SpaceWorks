"""Member and public routes of the repairs package, mounted at `/api/v1/`."""

from django.urls import path

from . import views_member as member, views_public as public

urlpatterns = [
    path("member/issues", member.MemberIssueListView.as_view(), name="member-issues"),
    path("member/issues/loan-items", member.MemberLoanItemsView.as_view(), name="member-issue-loan-items"),
    path("member/issues/photos", member.MemberIssuePhotoUploadView.as_view(), name="member-issue-photo-upload"),
    path("public/<slug:makerspace_slug>/issues", public.PublicIssueReportView.as_view(), name="public-issue-report"),
    path("public/<slug:makerspace_slug>/issues/photos", public.PublicIssuePhotoUploadView.as_view(),
         name="public-issue-photo-upload"),
    path("public/technician-opt-in/<str:token>", public.TechnicianOptInView.as_view(),
         name="public-technician-opt-in"),
]

# Release 0.12.0 (decision 223): members report incidents and near misses.
from apps.maintenance.incidents.urls import member_urlpatterns as _incident_member_urlpatterns  # noqa: E402

urlpatterns += _incident_member_urlpatterns
