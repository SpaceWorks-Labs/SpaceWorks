from django.urls import path

from apps.hardware_requests import cron_views, timeline_views, views
from apps.hardware_requests import replay_recovery_views as recovery

from apps.hardware_requests.public_contact_views import RequestContactCodeView
from apps.hardware_requests.member_history_views import MemberBorrowingHistoryView

app_name = "hardware_requests"

from apps.hardware_requests.renewal_views import MemberLoanRenewView, StaffLoanRenewView
from apps.hardware_requests.kit_views import StaffKitPreviewView, MemberKitPreviewView
from apps.hardware_requests import loan_depth_views as depth
from apps.hardware_requests.contextual_equipment_views import ContextualSelfView, ContextualStaffView
from apps.inventory.equipment_kit_views import (
    KitArchiveView, KitPublicationView, KitTemplateDetailView, KitTemplateListView, KitVersionCreateView,
)
from apps.inventory.equipment_public_kit_views import PublicKitDetailView, PublicKitListView

urlpatterns = [
    path("public/<slug:makerspace_slug>/equipment-kits/", PublicKitListView.as_view(), name="equipment-kit-public-list"),
    path("public/<slug:makerspace_slug>/equipment-kits/<int:kit_id>/", PublicKitDetailView.as_view(), name="equipment-kit-public-detail"),
    path("admin/makerspace/<int:makerspace_id>/equipment-kits", KitTemplateListView.as_view(), name="equipment-kit-list"),
    path("admin/makerspace/<int:makerspace_id>/equipment-kits/<int:kit_id>", KitTemplateDetailView.as_view(), name="equipment-kit-detail"),
    path("admin/makerspace/<int:makerspace_id>/equipment-kits/<int:kit_id>/versions", KitVersionCreateView.as_view(), name="equipment-kit-version"),
    path("admin/makerspace/<int:makerspace_id>/equipment-kits/<int:kit_id>/publication", KitPublicationView.as_view(), name="equipment-kit-publication"),
    path("admin/makerspace/<int:makerspace_id>/equipment-kits/<int:kit_id>/archive", KitArchiveView.as_view(), name="equipment-kit-archive"),
    path("public/<slug:makerspace_slug>/requests/contextual", ContextualSelfView.as_view(), name="contextual-request-self"),
    path("admin/makerspace/<int:makerspace_id>/equipment-requests/contextual", ContextualStaffView.as_view(), name="contextual-request-staff"),
    path("member/makerspaces/<int:makerspace_id>/borrowing-history", MemberBorrowingHistoryView.as_view(), name="member-borrowing-history"),
    path("admin/makerspace/<int:makerspace_id>/kit-checklist-preview", StaffKitPreviewView.as_view(), name="staff-kit-preview"),
    path("public/<slug:makerspace_slug>/tools/checklist", MemberKitPreviewView.as_view(), name="public-tool-checklist"),
    path("member/makerspaces/<int:makerspace_id>/loans/<int:pk>/renew", MemberLoanRenewView.as_view(), name="member-loan-renew"),
    path("admin/makerspace/<int:makerspace_id>/loans/<int:pk>/renew", StaffLoanRenewView.as_view(), name="staff-loan-renew"),
    # Lane L12: withdraw/cancel, the waitlist and pickup timing.
    path("member/makerspaces/<int:makerspace_id>/requests/<int:pk>/withdraw", depth.MemberRequestWithdrawView.as_view(), name="member-request-withdraw"),
    path("admin/makerspace/<int:makerspace_id>/requests/<int:pk>/cancel", depth.StaffRequestCancelView.as_view(), name="staff-request-cancel"),
    path("member/makerspaces/<int:makerspace_id>/waitlist", depth.MemberWaitlistView.as_view(), name="member-loan-waitlist"),
    path("member/makerspaces/<int:makerspace_id>/waitlist/<int:pk>/leave", depth.MemberWaitlistLeaveView.as_view(), name="member-loan-waitlist-leave"),
    path("admin/makerspace/<int:makerspace_id>/waitlist", depth.StaffWaitlistView.as_view(), name="staff-loan-waitlist"),
    path("admin/makerspace/<int:makerspace_id>/loan-reservation-policy", depth.LoanReservationPolicyView.as_view(), name="admin-loan-reservation-policy"),
    path("admin/makerspace/<int:makerspace_id>/kiosk-replays/", recovery.ReplayRecoveryListView.as_view(), name="admin-kiosk-replay-list"),
    path("admin/kiosk-replays/<uuid:pk>/", recovery.ReplayRecoveryDetailView.as_view(), name="admin-kiosk-replay-detail"),
    path("admin/kiosk-replays/<uuid:pk>/resolve/", recovery.ReplayRecoveryResolveView.as_view(), name="admin-kiosk-replay-resolve"),
    path(
        "internal/cron/return-reminders",
        cron_views.ReturnReminderCronView.as_view(),
        name="cron-return-reminders",
    ),
    path(
        "public/<slug:makerspace_slug>/requests",
        views.RequestSubmitView.as_view(),
        name="request-submit",
    ),
    path(
        "public/<slug:makerspace_slug>/requests/email-code",
        RequestContactCodeView.as_view(),
        name="request-contact-code",
    ),
    path(
        "public/<slug:makerspace_slug>/tools/evidence-url",
        views.PublicToolEvidenceUploadUrlView.as_view(),
        name="public-tool-evidence-url",
    ),
    path(
        "public/<slug:makerspace_slug>/tools/checkout",
        views.PublicToolCheckoutView.as_view(),
        name="public-tool-checkout",
    ),
    path(
        "public/<slug:makerspace_slug>/tools/return",
        views.PublicToolReturnView.as_view(),
        name="public-tool-return",
    ),
    path(
        "public/requests/<uuid:public_token>/status",
        views.RequestStatusView.as_view(),
        name="request-status",
    ),
    path(
        "admin/makerspace/<int:makerspace_id>/pending-requests",
        views.PendingRequestsView.as_view(),
        name="pending-requests",
    ),
    path(
        "admin/makerspace/<int:makerspace_id>/accepted-requests",
        views.AcceptedRequestsView.as_view(),
        name="accepted-requests",
    ),
    path(
        "admin/makerspace/<int:makerspace_id>/active-loans",
        views.ActiveLoansView.as_view(),
        name="active-loans",
    ),
    path(
        "admin/makerspace/<int:makerspace_id>/request-history",
        views.RequestHistoryView.as_view(),
        name="request-history",
    ),
    path(
        "admin/makerspace/<int:makerspace_id>/direct-loans",
        views.DirectLoanListCreateView.as_view(),
        name="direct-loans",
    ),
    path(
        "admin/makerspace/<int:makerspace_id>/direct-loan-members",
        views.DirectLoanMemberListView.as_view(),
        name="direct-loan-members",
    ),
    path(
        "admin/direct-loans/<int:pk>/return",
        views.DirectLoanReturnView.as_view(),
        name="direct-loan-return",
    ),
    path(
        "admin/requests/<int:pk>/accept",
        views.AcceptRequestView.as_view(),
        name="request-accept",
    ),
    path(
        "admin/requests/<int:pk>/reject",
        views.RejectRequestView.as_view(),
        name="request-reject",
    ),
    path(
        "admin/requests/<int:pk>/assign-box",
        views.AssignBoxView.as_view(),
        name="request-assign-box",
    ),
    path(
        "admin/requests/<int:pk>/issue",
        views.IssueRequestView.as_view(),
        name="request-issue",
    ),
    path(
        "admin/requests/<int:pk>/return-due",
        views.SetReturnDueView.as_view(),
        name="request-return-due",
    ),
    path(
        "admin/requests/<int:pk>/return",
        views.ReturnRequestView.as_view(),
        name="request-return",
    ),
    path(
        "admin/requests/<int:pk>/timeline",
        timeline_views.RequestTimelineView.as_view(),
        name="request-timeline",
    ),
    path(
        "admin/inventory/<int:pk>/chain-of-custody",
        timeline_views.InventoryChainOfCustodyView.as_view(),
        name="admin-inventory-chain-of-custody",
    ),
    # Retained alias (open item A34): the guest-admin URL space is the handover API surface and no bundled
    # client calls this route, but external handover clients may; it serves the same ActiveLoansView with
    # the same scoping, so removing it would only break them. Not a role: Guest Admin is retired.
    path(
        "guest-admin/makerspace/<int:makerspace_id>/active-loans",
        views.ActiveLoansView.as_view(),
        name="guest-admin-active-loans",
    ),
    path(
        "guest-admin/requests/<int:pk>/return",
        views.ReturnRequestView.as_view(),
        name="guest-admin-request-return",
    ),
]
