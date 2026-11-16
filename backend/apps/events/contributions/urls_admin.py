from django.urls import path
from . import views_admin as v

B = "events/<int:pk>/"
N = "events-programme-admin-"
urlpatterns = [
    path(B + "roles/", v.RolesView.as_view(), name=N + "roles-list"),
    path(B + "roles/<int:assignment_id>/", v.RoleDetailView.as_view(), name=N + "roles"),
    path(B + "roles/<int:assignment_id>/approve/", v.RoleApproveView.as_view(), name=N + "roles-approve"),
    path(B + "roles/<int:assignment_id>/revoke/", v.RoleRevokeView.as_view(), name=N + "roles-revoke"),
    path(B + "volunteer-postings/", v.PostingsView.as_view(), name=N + "volunteer-postings-list"),
    path(B + "volunteer-postings/<int:posting_id>/", v.PostingDetailView.as_view(), name=N + "volunteer-postings-detail"),
    path(B + "shifts/", v.ShiftsView.as_view(), name=N + "shifts-list"),
    path(B + "shifts/<int:shift_id>/", v.ShiftDetailView.as_view(), name=N + "shifts-detail"),
    path(B + "shift-signups/<int:signup_id>/approve/", v.SignupApproveView.as_view(), name=N + "shift-signup-approve"),
    path(B + "shift-signups/<int:signup_id>/withdraw/", v.SignupWithdrawView.as_view(), name=N + "shift-signup-withdraw"),
    path(B + "shift-signups/<int:signup_id>/check-in/", v.SignupAttendanceView.as_view(), name=N + "shift-signup-check-in"),
    path(B + "shift-signups/<int:signup_id>/check-out/", v.SignupCheckOutView.as_view(), name=N + "shift-signup-check-out"),
    path(B + "shift-signups/<int:signup_id>/verify-hours/", v.SignupVerifyHoursView.as_view(), name=N + "shift-signup-verify-hours"),
    path(B + "shift-signups/<int:signup_id>/adjust-hours/", v.SignupAdjustHoursView.as_view(), name=N + "shift-signup-adjust-hours"),
]
