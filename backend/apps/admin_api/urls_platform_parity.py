"""#190 parity: the web superadmin console's own paths for what was /control/-only.

IP rules and automatic blocks, account disable / re-enable / two-step reset, single sign-on
(OIDC) providers, request queues (archive, API key and web address requests), a space's
chat templates, restore drills (run one now, settings) and self-host move requests (decide,
export, delete the file, one-use download link). Mounted at api/v1/admin/.
"""

from django.urls import path

from apps.accounts.views_platform_accounts import (
    PlatformAccountDisableView, PlatformAccountEnableView, PlatformAccountLookupView, PlatformAccountTwoStepResetView,
)
from apps.accounts.views_platform_ip_access import (
    IPAccessRuleDetailView, IPAccessRuleListCreateView, IPAutoBlockListView, IPAutoBlockUnblockView,
)
from apps.accounts.views_platform_oidc import OidcProviderDetailView, OidcProviderListCreateView
from apps.admin_api.views_platform_queues import (
    ApiKeyRequestApproveView, ApiKeyRequestListView, ApiKeyRequestRejectView, ArchiveRequestDecideView,
    ArchiveRequestDeclineView, ArchiveRequestListView, SubdomainRequestApproveView, SubdomainRequestListView,
    SubdomainRequestRejectView,
)
from apps.integrations.views_platform_chat_templates import ChatTemplateDetailView, ChatTemplateListCreateView
from apps.backup.views_drills import RestoreDrillListView, RestoreDrillSettingsView
from apps.separability.registry import runtime_active


def _moves():
    from apps.tenant_migration.views_selfhost_moves_platform import (
        PlatformMoveDecisionView, PlatformMoveDiscardView, PlatformMoveDownloadLinkView, PlatformMoveExportView,
        PlatformMoveListView, PlatformMoveRejectView,
    )
    move = "platform/selfhost-moves/<uuid:pk>/"
    return [
        path("platform/selfhost-moves", PlatformMoveListView.as_view(), name="admin-platform-selfhost-moves"),
        path(move + "approve", PlatformMoveDecisionView.as_view(), name="admin-platform-selfhost-move-approve"),
        path(move + "reject", PlatformMoveRejectView.as_view(), name="admin-platform-selfhost-move-reject"),
        path(move + "export", PlatformMoveExportView.as_view(), name="admin-platform-selfhost-move-export"),
        path(move + "discard", PlatformMoveDiscardView.as_view(), name="admin-platform-selfhost-move-discard"),
        path(move + "download-url", PlatformMoveDownloadLinkView.as_view(),
             name="admin-platform-selfhost-move-download-url"),
    ]


urlpatterns = [
    path("platform/ip-rules", IPAccessRuleListCreateView.as_view(), name="admin-platform-ip-rules"),
    path("platform/ip-rules/<int:pk>", IPAccessRuleDetailView.as_view(), name="admin-platform-ip-rule"),
    path("platform/ip-blocks", IPAutoBlockListView.as_view(), name="admin-platform-ip-blocks"),
    path("platform/ip-blocks/<int:pk>/unblock", IPAutoBlockUnblockView.as_view(),
         name="admin-platform-ip-block-unblock"),
    path("platform/accounts", PlatformAccountLookupView.as_view(), name="admin-platform-accounts"),
    path("platform/accounts/<int:pk>/disable", PlatformAccountDisableView.as_view(), name="admin-platform-account-disable"),
    path("platform/accounts/<int:pk>/enable", PlatformAccountEnableView.as_view(), name="admin-platform-account-enable"),
    path("platform/accounts/<int:pk>/reset-two-step", PlatformAccountTwoStepResetView.as_view(),
         name="admin-platform-account-reset-two-step"),
    path("platform/oidc-providers", OidcProviderListCreateView.as_view(), name="admin-platform-oidc-providers"),
    path("platform/oidc-providers/<int:pk>", OidcProviderDetailView.as_view(), name="admin-platform-oidc-provider"),
    path("platform/archive-requests", ArchiveRequestListView.as_view(), name="admin-platform-archive-requests"),
    path("platform/archive-requests/<int:pk>/approve", ArchiveRequestDecideView.as_view(),
         name="admin-platform-archive-request-approve"),
    path("platform/archive-requests/<int:pk>/decline", ArchiveRequestDeclineView.as_view(),
         name="admin-platform-archive-request-decline"),
    path("platform/api-key-requests", ApiKeyRequestListView.as_view(), name="admin-platform-api-key-requests"),
    path("platform/api-key-requests/<int:pk>/approve", ApiKeyRequestApproveView.as_view(),
         name="admin-platform-api-key-request-approve"),
    path("platform/api-key-requests/<int:pk>/reject", ApiKeyRequestRejectView.as_view(),
         name="admin-platform-api-key-request-reject"),
    path("platform/subdomain-requests", SubdomainRequestListView.as_view(), name="admin-platform-subdomain-requests"),
    path("platform/subdomain-requests/<int:pk>/approve", SubdomainRequestApproveView.as_view(),
         name="admin-platform-subdomain-request-approve"),
    path("platform/subdomain-requests/<int:pk>/reject", SubdomainRequestRejectView.as_view(),
         name="admin-platform-subdomain-request-reject"),
    path("platform/spaces/<int:makerspace_id>/chat-templates", ChatTemplateListCreateView.as_view(),
         name="admin-platform-chat-templates"),
    path("platform/spaces/<int:makerspace_id>/chat-templates/<int:pk>", ChatTemplateDetailView.as_view(),
         name="admin-platform-chat-template"),
    path("platform/restore-drills", RestoreDrillListView.as_view(), name="admin-platform-restore-drills"),
    path("platform/restore-drills/settings", RestoreDrillSettingsView.as_view(),
         name="admin-platform-restore-drill-settings"),
]
# A deployment without tenant migration ships none of its views (tombstone), so they are
# imported only when the app is active -- the same rule as config.urls.separable.
if runtime_active("tenant_migration"):
    urlpatterns += _moves()
