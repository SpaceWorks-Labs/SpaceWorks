from django.urls import path

from . import views_staff_accounts as views

BASE = "makerspaces/<int:makerspace_id>/staff-accounts/"
urlpatterns = [
    path(BASE, views.StaffAccountListCreateView.as_view(), name="admin-staff-accounts"),
    path(BASE + "policy", views.StaffAccountPolicyView.as_view(), name="admin-staff-account-policy"),
    path(BASE + "<int:user_id>/", views.StaffAccountChangeView.as_view(), name="admin-staff-account-change"),
    path(BASE + "<int:user_id>/deactivate/", views.StaffAccountDeactivateView.as_view(), name="admin-staff-account-deactivate"),
    path(BASE + "<int:user_id>/reactivate/", views.StaffAccountReactivateView.as_view(), name="admin-staff-account-reactivate"),
    path(BASE + "<int:user_id>/set-password/", views.StaffAccountSetPasswordView.as_view(), name="admin-staff-account-set-password"),
    path(BASE + "<int:user_id>/resend-invite/", views.StaffAccountResendInviteView.as_view(), name="admin-staff-account-resend-invite"),
]
