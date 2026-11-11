from django.urls import path

from apps.admin_api.views_machine_downtime import MachineDowntimeView, MachineLockoutView

from apps.admin_api.views_machine_candidates import MachineOperatorCandidatesView
from apps.admin_api.views_machine_consumables import (
    MachineConsumableCandidatesView,
    MachineConsumableDetailView,
    MachineConsumablesView,
    MachineConsumptionLogView,
)
from apps.admin_api.views_machine_documents import (
    MachineDocumentDeleteView,
    MachineDocumentPresignView,
    MachineDocumentsView,
    MachineDocumentUrlView,
)
from apps.admin_api.views_machine_image import MachineImageView
from apps.admin_api.views_machine_operators import (
    MachineOperatorDetailView,
    MachineOperatorsView,
)
from apps.admin_api.views_machine_publicity import MachinePublicityView
from apps.admin_api.views_machine_type_pricing import (
    MachineTypePricingDetailView,
    MachineTypePricingListView,
)
from apps.admin_api.views_machine_types import (
    MachineTypeDetailView,
    MachineTypeListCreateView,
)
from apps.admin_api.views_machines import MachineDetailView, MachineListCreateView
from apps.admin_api.views_machines_actions import (
    MachineErrorLogView,
    MachineRetireView,
    MachineSetStatusView,
    MachineUnretireView,
    MachineUsageView,
)


from .views_machine_usage_candidates import MachineUsageCandidatesView

urlpatterns = [
    path("machines/<int:pk>/usage-candidates", MachineUsageCandidatesView.as_view(), name="admin-machine-usage-candidates"),
    path(
        'makerspace/<int:makerspace_id>/machines',
        MachineListCreateView.as_view(),
        name='admin-machines',
    ),
    path(
        'makerspace/<int:makerspace_id>/machine-types',
        MachineTypeListCreateView.as_view(),
        name='admin-machine-types',
    ),
    path(
        'makerspace/<int:makerspace_id>/machine-types/<int:pk>',
        MachineTypeDetailView.as_view(),
        name='admin-machine-type-detail',
    ),
    path(
        'makerspace/<int:makerspace_id>/machine-type-pricing',
        MachineTypePricingListView.as_view(),
        name='admin-machine-type-pricing',
    ),
    path(
        'makerspace/<int:makerspace_id>/machine-type-pricing/<int:machine_type_id>',
        MachineTypePricingDetailView.as_view(),
        name='admin-machine-type-pricing-detail',
    ),
    path(
        'machines/<int:pk>',
        MachineDetailView.as_view(),
        name='admin-machine-detail',
    ),
    path(
        'machines/<int:pk>/image',
        MachineImageView.as_view(),
        name='admin-machine-image',
    ),
    path(
        'machines/<int:pk>/publicity',
        MachinePublicityView.as_view(),
        name='admin-machine-publicity',
    ),
    path(
        'machines/<int:pk>/set-status',
        MachineSetStatusView.as_view(),
        name='admin-machine-set-status',
    ),
    # Lane L12: the downtime ledger and maintenance lockout (machines.maintenance).
    path('machines/<int:pk>/downtime', MachineDowntimeView.as_view(), name='admin-machine-downtime'),
    path('machines/<int:pk>/lockout', MachineLockoutView.as_view(), name='admin-machine-lockout'),
    path(
        'machines/<int:pk>/retire',
        MachineRetireView.as_view(),
        name='admin-machine-retire',
    ),
    path(
        'machines/<int:pk>/unretire',
        MachineUnretireView.as_view(),
        name='admin-machine-unretire',
    ),
    path(
        'machines/<int:pk>/usage',
        MachineUsageView.as_view(),
        name='admin-machine-usage',
    ),
    path(
        'machines/<int:pk>/consumables',
        MachineConsumablesView.as_view(),
        name='admin-machine-consumables',
    ),
    path(
        'machines/<int:pk>/consumables/<int:cid>',
        MachineConsumableDetailView.as_view(),
        name='admin-machine-consumable-detail',
    ),
    path(
        'machines/<int:pk>/consumables/<int:cid>/log',
        MachineConsumptionLogView.as_view(),
        name='admin-machine-consumption-log',
    ),
    path(
        'machines/<int:pk>/consumable-candidates',
        MachineConsumableCandidatesView.as_view(),
        name='admin-machine-consumable-candidates',
    ),
    path(
        'machines/<int:pk>/operators',
        MachineOperatorsView.as_view(),
        name='admin-machine-operators',
    ),
    path(
        'machines/<int:pk>/operator-candidates',
        MachineOperatorCandidatesView.as_view(),
        name='admin-machine-operator-candidates',
    ),
    path(
        'machines/<int:pk>/operators/<int:user_pk>',
        MachineOperatorDetailView.as_view(),
        name='admin-machine-operator-detail',
    ),
    path(
        'machines/<int:pk>/documents/presign',
        MachineDocumentPresignView.as_view(),
        name='admin-machine-document-presign',
    ),
    path(
        'machines/<int:pk>/documents',
        MachineDocumentsView.as_view(),
        name='admin-machine-documents',
    ),
    path(
        'machines/documents/<int:pk>/url',
        MachineDocumentUrlView.as_view(),
        name='admin-machine-document-url',
    ),
    path(
        'machines/documents/<int:pk>',
        MachineDocumentDeleteView.as_view(),
        name='admin-machine-document-detail',
    ),
    path(
        'machines/<int:pk>/error-logs',
        MachineErrorLogView.as_view(),
        name='admin-machine-error-logs',
    ),
]

# Lane L23: metered machine sessions (#158), behind `machines.sessions`.
from apps.admin_api.views_machine_session_settings import MachineTypeSessionSettingsView  # noqa: E402
from apps.admin_api.views_machine_sessions import (  # noqa: E402
    MachineSessionAmendView, MachineSessionAssignView, MachineSessionConfirmView, MachineSessionListView,
    MachineSessionStopView,
)

urlpatterns += [
    path('makerspaces/<int:makerspace_id>/machine-sessions', MachineSessionListView.as_view(),
         name='admin-machine-sessions'),
    path('machine-sessions/<int:pk>/stop', MachineSessionStopView.as_view(), name='admin-machine-session-stop'),
    path('machine-sessions/<int:pk>/amend', MachineSessionAmendView.as_view(), name='admin-machine-session-amend'),
    path('machine-sessions/<int:pk>/assign', MachineSessionAssignView.as_view(), name='admin-machine-session-assign'),
    path('machine-sessions/<int:pk>/confirm', MachineSessionConfirmView.as_view(),
         name='admin-machine-session-confirm'),
    path('makerspaces/<int:makerspace_id>/machine-types/<int:type_id>/session-settings',
         MachineTypeSessionSettingsView.as_view(), name='admin-machine-type-session-settings'),
]

# Release 0.12.0 (decision 223): induction events, behind `machines.induction_events`.
from apps.admin_api.views_machine_induction import (  # noqa: E402
    EventInductionGrantView, EventInductionUnlinkView, EventInductionView, GuestCertificationRevokeView,
)
from apps.admin_api.views_machine_induction_upcoming import UpcomingInductionsView  # noqa: E402

urlpatterns += [
    path('makerspaces/<int:makerspace_id>/induction-events', UpcomingInductionsView.as_view(),
         name='admin-induction-events-upcoming'),
    path('makerspaces/<int:makerspace_id>/events/<int:event_id>/induction', EventInductionView.as_view(),
         name='admin-event-induction'),
    path('makerspaces/<int:makerspace_id>/events/<int:event_id>/induction/grant', EventInductionGrantView.as_view(),
         name='admin-event-induction-grant'),
    path('induction-links/<int:pk>', EventInductionUnlinkView.as_view(), name='admin-event-induction-unlink'),
    path('guest-certification-grants/<int:pk>/revoke', GuestCertificationRevokeView.as_view(),
         name='admin-guest-certification-revoke'),
]
