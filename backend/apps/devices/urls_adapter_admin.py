"""Staff routes for device adapters. Object routes use ``pk`` (the origin-scope resolver reads only kwargs["pk"])."""
from django.urls import path

from .views_adapter_admin import (
    AdapterBindingCommandView, AdapterBindingCreateView, AdapterBindingDetailView, AdapterCommandListView,
    AdapterDetailView, AdapterEventListView, AdapterListView,
)
from .views_adapter_admin_more import (
    AdapterAimView, AdapterBindingConfigView, AdapterJobCreateView, AdapterCredentialDetailView, AdapterCredentialListView, AdapterIndicateView, AdapterJogView,
    AdapterPoseListView, AdapterPositionView, AdapterWatchCreateView, AdapterWatchDetailView,
    AdapterWatchSnapshotView,
)

from .views_adapter_admin_logs import AdapterAccessDecisionListView, AdapterUsageListView
from .views_shelf import (
    ShelfCheckDetailView, ShelfCheckListView, ShelfClearView, ShelfCoverageView, ShelfLocationListView, ShelfShowView,
)
from .views_adapter_push import (  # noqa: E402
    AdapterTypeProfileView, AdapterWebhookDeliveriesView, AdapterWebhookRotateView, AdapterWebhookView,
)

admin_urlpatterns = [
    path("admin/makerspace/<int:makerspace_id>/shelf-pointer/coverage", ShelfCoverageView.as_view(),
         name="admin-shelf-coverage"),
    path("admin/makerspace/<int:makerspace_id>/shelf-pointer/show", ShelfShowView.as_view(), name="admin-shelf-show"),
    path("admin/makerspace/<int:makerspace_id>/shelf-pointer/clear", ShelfClearView.as_view(),
         name="admin-shelf-clear"),
    path("admin/makerspace/<int:makerspace_id>/shelf-pointer/locations", ShelfLocationListView.as_view(),
         name="admin-shelf-locations"),
    path("admin/makerspace/<int:makerspace_id>/shelf-checks", ShelfCheckListView.as_view(), name="admin-shelf-checks"),
    path("admin/shelf-checks/<uuid:pk>", ShelfCheckDetailView.as_view(), name="admin-shelf-check-detail"),
    path("admin/adapters/<uuid:pk>/webhook", AdapterWebhookView.as_view(), name="admin-adapter-webhook"),
    path("admin/adapters/<uuid:pk>/webhook/rotate", AdapterWebhookRotateView.as_view(),
         name="admin-adapter-webhook-rotate"),
    path("admin/adapters/<uuid:pk>/webhook/deliveries", AdapterWebhookDeliveriesView.as_view(),
         name="admin-adapter-webhook-deliveries"),
    path("admin/makerspace/<int:makerspace_id>/machine-types/<int:machine_type_id>/adapter-profile",
         AdapterTypeProfileView.as_view(), name="admin-adapter-type-profile"),
    path("admin/adapters/<uuid:pk>/access-decisions", AdapterAccessDecisionListView.as_view(),
         name="admin-adapter-access-decisions"),
    path("admin/adapters/<uuid:pk>/usage", AdapterUsageListView.as_view(), name="admin-adapter-usage"),
    path("admin/adapter-bindings/<uuid:pk>/jobs", AdapterJobCreateView.as_view(), name="admin-adapter-job-create"),
    path("admin/adapter-bindings/<uuid:pk>/config", AdapterBindingConfigView.as_view(),
         name="admin-adapter-binding-config"),
    path("admin/makerspace/<int:makerspace_id>/adapters", AdapterListView.as_view(), name="admin-adapter-list"),
    path("admin/adapters/<uuid:pk>", AdapterDetailView.as_view(), name="admin-adapter-detail"),
    path("admin/adapters/<uuid:pk>/bindings", AdapterBindingCreateView.as_view(), name="admin-adapter-binding-create"),
    path("admin/adapters/<uuid:pk>/commands", AdapterCommandListView.as_view(), name="admin-adapter-commands"),
    path("admin/adapters/<uuid:pk>/events", AdapterEventListView.as_view(), name="admin-adapter-events"),
    path("admin/adapter-bindings/<uuid:pk>", AdapterBindingDetailView.as_view(), name="admin-adapter-binding-detail"),
    path("admin/adapter-bindings/<uuid:pk>/commands", AdapterBindingCommandView.as_view(),
         name="admin-adapter-binding-command"),
    path("admin/adapter-bindings/<uuid:pk>/poses", AdapterPoseListView.as_view(), name="admin-adapter-poses"),
    path("admin/adapter-bindings/<uuid:pk>/aim", AdapterAimView.as_view(), name="admin-adapter-aim"),
    path("admin/adapter-bindings/<uuid:pk>/jog", AdapterJogView.as_view(), name="admin-adapter-jog"),
    path("admin/adapter-bindings/<uuid:pk>/indicate", AdapterIndicateView.as_view(), name="admin-adapter-indicate"),
    path("admin/adapter-bindings/<uuid:pk>/position", AdapterPositionView.as_view(), name="admin-adapter-position"),
    path("admin/adapter-bindings/<uuid:pk>/watch", AdapterWatchCreateView.as_view(), name="admin-adapter-watch-create"),
    path("admin/adapter-watches/<uuid:pk>", AdapterWatchDetailView.as_view(), name="admin-adapter-watch-detail"),
    path("admin/adapter-watches/<uuid:pk>/snapshot", AdapterWatchSnapshotView.as_view(),
         name="admin-adapter-watch-snapshot"),
    path("admin/makerspace/<int:makerspace_id>/adapter-credentials", AdapterCredentialListView.as_view(),
         name="admin-adapter-credentials"),
    path("admin/adapter-credentials/<uuid:pk>", AdapterCredentialDetailView.as_view(),
         name="admin-adapter-credential-detail"),
]
