from django.urls import path

from . import views_staff_roles as views

BASE = "makerspaces/<int:makerspace_id>/staff-roles/"
# The fifth name, admin-staff-roles-mfa-reset, is S-A's route (accounts/urls_security.py).
urlpatterns = [
    path(BASE, views.StaffRoleListCreateView.as_view(), name="admin-staff-roles"),
    path(BASE + "<int:membership_id>/", views.StaffRoleDetailView.as_view(), name="admin-staff-roles-detail"),
    path(BASE + "<int:membership_id>/revoke/", views.StaffRoleRevokeView.as_view(), name="admin-staff-roles-revoke"),
    path(BASE + "<int:membership_id>/restore/", views.StaffRoleRestoreView.as_view(), name="admin-staff-roles-restore"),
]
