from django.urls import path

from apps.machines.views_public import PublicMachineListView
from apps.machines.views_member_certifications import MemberCertificationsView
from apps.machines.views_public_service import PublicMachineServiceSubmitView
from apps.machines.views_public_printer_service import (
    PublicPrinterPoolsView, PublicPrinterQueuesView, PublicPrinterRequestView,
    PublicPrinterStatusView, PublicPrinterUploadView,
)


from .views_public_detail import PublicMachineDetailView, PublicMachineDetailListView
from .views_public_service_status import PublicMachineServiceStatusView
from .views_service_cancel import MemberMachineServiceCancelView, MemberMachineServiceOwnerView

from .views_materials import MaterialListView, MaterialDetailView, PublicTypeIntakeView
from .views_intake import MachineTypeIntakeView

urlpatterns = [
    path("public/<slug:makerspace_slug>/machine-types/<int:type_id>/intake", PublicTypeIntakeView.as_view(), name="public-machine-intake"),
    path("admin/makerspaces/<int:makerspace_id>/machine-materials", MaterialListView.as_view(), name="machine-materials"),
    path("admin/makerspaces/<int:makerspace_id>/machine-materials/<int:pk>", MaterialDetailView.as_view(), name="machine-material-detail"),
    path("admin/makerspaces/<int:makerspace_id>/machine-types/<int:type_id>/intake", MachineTypeIntakeView.as_view(), name="machine-type-intake"),
    path("public/<slug:makerspace_slug>/machines/details", PublicMachineDetailListView.as_view(), name="public-machine-details"),
    path("public/<slug:makerspace_slug>/machines/<int:pk>", PublicMachineDetailView.as_view(), name="public-machine-detail"),
    path("member/makerspaces/<int:makerspace_id>/certifications", MemberCertificationsView.as_view(), name="member-certifications"),
    path(
        'public/<slug:makerspace_slug>/machines',
        PublicMachineListView.as_view(),
        name='public-machines',
    ),
    path(
        'public/<slug:makerspace_slug>/machine-service-requests',
        PublicMachineServiceSubmitView.as_view(),
        name='public-machine-service-request-submit',
    ),
    path('public/<slug:makerspace_slug>/machine-service/3d-printer/queues', PublicPrinterQueuesView.as_view(), name='public-printer-service-queues'),
    path('public/<slug:makerspace_slug>/machine-service/3d-printer/consumable-pools', PublicPrinterPoolsView.as_view(), name='public-printer-service-pools'),
    path('public/<slug:makerspace_slug>/machine-service/3d-printer/uploads', PublicPrinterUploadView.as_view(), name='public-printer-service-upload'),
    path('public/<slug:makerspace_slug>/machine-service/3d-printer/requests', PublicPrinterRequestView.as_view(), name='public-printer-service-request'),
    path('public/machine-service/3d-printer/requests/<uuid:public_token>/status', PublicPrinterStatusView.as_view(), name='public-printer-service-status'),
    path('public/machine-service/requests/<uuid:public_token>/status', PublicMachineServiceStatusView.as_view(), name='public-machine-service-status'),
    path('member/machine-service/requests/<int:pk>/cancel', MemberMachineServiceCancelView.as_view(), name='member-machine-service-cancel'),
    path('member/machine-service/requests/by-token/<uuid:public_token>/owner', MemberMachineServiceOwnerView.as_view(), name='member-machine-service-owner'),
]
