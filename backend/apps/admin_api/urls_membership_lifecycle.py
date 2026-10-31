"""Release-2 membership lifecycle routes (lane L4): financial year, plans, register,
import, renewals, titles, erasure. Mounted under the admin API prefix."""
from django.urls import path

from apps.admin_api.views_financial_year import FinancialYearView
from apps.admin_api.views_membership_desk import (
    InviteLinkListView, InviteLinkRevokeView, JoinRequestBulkDecideView, MembershipExtendView,
    MembershipTitleDetailView, MembershipTitleListView, RenewalRemindersView, RenewalWorklistView,
)
from apps.admin_api.views_membership_erasure_import import (
    ErasureDecisionView, ErasureQueueView, ImportedMemberListView, MemberImportApplyView, MemberImportPreviewView,
)
from apps.admin_api.views_membership_plan_archive import MembershipPlanArchiveView
from apps.admin_api.views_membership_records import (
    MembershipConsentLedgerView, MembershipRecordView, MembershipStaffHistoryView, MembershipTitleAssignmentsView,
    MembershipTitleUnassignView,
)
from apps.admin_api.views_membership_refunds import RefundCaseMembershipSuggestionView
from apps.admin_api.views_membership_register import MemberRegisterView
from apps.admin_api.views_membership_summary import MembershipSummaryView

_SPACE = "makerspaces/<int:makerspace_id>"

urlpatterns = [
    path(f"{_SPACE}/financial-year", FinancialYearView.as_view(), name="admin-financial-year"),
    path("membership-plans/<int:pk>/archive", MembershipPlanArchiveView.as_view(), name="admin-membership-plan-archive"),
    path(f"{_SPACE}/membership-titles", MembershipTitleListView.as_view(), name="admin-membership-titles"),
    path("membership-titles/<int:pk>", MembershipTitleDetailView.as_view(), name="admin-membership-title-detail"),
    path(f"{_SPACE}/membership-invite-links", InviteLinkListView.as_view(), name="admin-membership-invite-links"),
    path("membership-invite-links/<int:pk>/revoke", InviteLinkRevokeView.as_view(),
         name="admin-membership-invite-link-revoke"),
    path(f"{_SPACE}/renewal-worklist", RenewalWorklistView.as_view(), name="admin-membership-renewal-worklist"),
    path(f"{_SPACE}/renewal-reminders", RenewalRemindersView.as_view(), name="admin-membership-renewal-reminders"),
    path(f"{_SPACE}/join-requests/bulk-decide", JoinRequestBulkDecideView.as_view(),
         name="admin-membership-join-requests-bulk-decide"),
    path(f"{_SPACE}/members/import/preview", MemberImportPreviewView.as_view(), name="admin-member-import-preview"),
    path(f"{_SPACE}/members/import/apply", MemberImportApplyView.as_view(), name="admin-member-import-apply"),
    path(f"{_SPACE}/members/imported", ImportedMemberListView.as_view(), name="admin-member-imported"),
    path(f"{_SPACE}/erasure-requests", ErasureQueueView.as_view(), name="admin-membership-erasure-requests"),
    path("erasure-requests/<int:pk>/approve", ErasureDecisionView.as_view(decision="approve"),
         name="admin-membership-erasure-approve"),
    path("erasure-requests/<int:pk>/reject", ErasureDecisionView.as_view(decision="reject"),
         name="admin-membership-erasure-reject"),
    path(f"{_SPACE}/member-register", MemberRegisterView.as_view(), name="admin-member-register"),
    path(f"{_SPACE}/membership-summary", MembershipSummaryView.as_view(), name="admin-membership-summary"),
    path(f"{_SPACE}/refund-cases/<int:case_id>/membership-suggestion", RefundCaseMembershipSuggestionView.as_view(),
         name="admin-refund-case-membership-suggestion"),
    path("memberships/<int:pk>/extend", MembershipExtendView.as_view(), name="admin-membership-extend"),
    path("memberships/<int:pk>/record", MembershipRecordView.as_view(), name="admin-membership-record"),
    path("memberships/<int:pk>/titles", MembershipTitleAssignmentsView.as_view(), name="admin-membership-title-assignments"),
    path("memberships/<int:pk>/titles/<int:title_id>", MembershipTitleUnassignView.as_view(),
         name="admin-membership-title-unassign"),
    path("memberships/<int:pk>/consents", MembershipConsentLedgerView.as_view(), name="admin-membership-consents"),
    path("memberships/<int:pk>/history", MembershipStaffHistoryView.as_view(), name="admin-membership-history"),
]
