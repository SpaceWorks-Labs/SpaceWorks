"""Mounted by G under /api/v1/member/ after origin/source/claim registration."""
from django.urls import path
from . import views_member as v

B = "makerspaces/<int:makerspace_id>/events/<int:pk>/"
N = "events-programme-member-"
urlpatterns = [
    path(B + "role-postings/", v.PostingListView.as_view(), name=N + "role-posting-list"),
    path(B + "role-postings/<int:posting_id>/", v.PostingDetailView.as_view(), name=N + "role-posting-detail"),
    path(B + "role-postings/<int:posting_id>/application/", v.RoleApplicationCreateView.as_view(), name=N + "role-application-create"),
    path(B + "role-applications/", v.RoleApplicationListView.as_view(), name=N + "role-application-list"),
    path(B + "role-applications/<int:assignment_id>/", v.RoleApplicationDetailView.as_view(), name=N + "role-application-detail"),
    path(B + "role-applications/<int:assignment_id>/submit/", v.RoleSubmitView.as_view(), name=N + "role-application-submit"),
    path(B + "role-applications/<int:assignment_id>/withdraw/", v.RoleWithdrawView.as_view(), name=N + "role-application-withdraw"),
    path(B + "role-applications/<int:assignment_id>/date-review/", v.RoleDateReviewView.as_view(), name=N + "role-application-date-review"),
    path(B + "shifts/", v.ShiftListView.as_view(), name=N + "shift-list"),
    path(B + "shifts/<int:shift_id>/apply/", v.ShiftApplyView.as_view(), name=N + "shift-apply"),
    path(B + "shift-signups/", v.SignupListView.as_view(), name=N + "shift-signup-list"),
    path(B + "shift-signups/<int:signup_id>/", v.SignupDetailView.as_view(), name=N + "shift-signup-detail"),
    path(B + "shift-signups/<int:signup_id>/withdraw/", v.SignupWithdrawView.as_view(), name=N + "shift-signup-withdraw"),
    path(B + "shift-signups/<int:signup_id>/check-in/", v.SignupCheckInView.as_view(), name=N + "shift-signup-check-in"),
    path(B + "shift-signups/<int:signup_id>/check-out/", v.SignupCheckOutView.as_view(), name=N + "shift-signup-check-out"),
]
