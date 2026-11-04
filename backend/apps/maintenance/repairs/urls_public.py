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
