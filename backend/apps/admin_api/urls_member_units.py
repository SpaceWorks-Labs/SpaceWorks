"""Parity O-B1: staff routes for member units, unit assignment, unit-scoped staff and the import review queue."""
from django.urls import path

from apps.admin_api.views_member_unit_links import (
    MemberImportReviewApproveView, MemberImportReviewListView, MemberImportReviewRejectView, MembershipUnitView,
    PlanUnitsView, StaffUnitScopeView,
)
from apps.admin_api.views_member_units import (
    MemberUnitArchiveView, MemberUnitDetailView, MemberUnitLevelsView, MemberUnitListView, MemberUnitMoveView,
    MemberUnitRestoreView,
)

_SPACE = "makerspaces/<int:makerspace_id>"

urlpatterns = [
    path(f"{_SPACE}/member-units", MemberUnitListView.as_view(), name="admin-member-units"),
    path(f"{_SPACE}/member-unit-levels", MemberUnitLevelsView.as_view(), name="admin-member-unit-levels"),
    path(f"{_SPACE}/member-units/<int:pk>", MemberUnitDetailView.as_view(), name="admin-member-unit"),
    path(f"{_SPACE}/member-units/<int:pk>/move", MemberUnitMoveView.as_view(), name="admin-member-unit-move"),
    path(f"{_SPACE}/member-units/<int:pk>/archive", MemberUnitArchiveView.as_view(),
         name="admin-member-unit-archive"),
    path(f"{_SPACE}/member-units/<int:pk>/restore", MemberUnitRestoreView.as_view(),
         name="admin-member-unit-restore"),
    path(f"{_SPACE}/memberships/<int:membership_id>/unit", MembershipUnitView.as_view(),
         name="admin-membership-unit"),
    path(f"{_SPACE}/staff/<int:membership_id>/unit-scope", StaffUnitScopeView.as_view(),
         name="admin-staff-unit-scope"),
    path(f"{_SPACE}/membership-plans/<int:plan_id>/units", PlanUnitsView.as_view(), name="admin-plan-units"),
    path(f"{_SPACE}/member-import-reviews", MemberImportReviewListView.as_view(),
         name="admin-member-import-reviews"),
    path(f"{_SPACE}/member-import-reviews/<int:imported_id>/approve", MemberImportReviewApproveView.as_view(),
         name="admin-member-import-review-approve"),
    path(f"{_SPACE}/member-import-reviews/<int:imported_id>/reject", MemberImportReviewRejectView.as_view(),
         name="admin-member-import-review-reject"),
]
