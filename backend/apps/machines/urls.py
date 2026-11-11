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
from . import views_jobs as jobs, views_jobs_member as job_actions
from . import views_sessions_member as sessions
from . import views_supervised as supervised
from .views_supervised_people import SupervisedPeoplePickerView
from .views_member_machines import MemberMachineListView

urlpatterns = [
    # Lane L12: the uniform job flow (#140/#141).
    path("public/<slug:makerspace_slug>/machine-jobs/types", jobs.PublicJobTypesView.as_view(), name="public-machine-job-types"),
    path("public/<slug:makerspace_slug>/machine-jobs/uploads", jobs.PublicJobUploadView.as_view(), name="public-machine-job-upload"),
    path("public/<slug:makerspace_slug>/machine-jobs", jobs.PublicJobSubmitView.as_view(), name="public-machine-job-submit"),
    path("member/machine-jobs", jobs.MemberJobListView.as_view(), name="member-machine-jobs"),
    path("member/machine-jobs/<int:pk>", jobs.MemberJobDetailView.as_view(), name="member-machine-job-detail"),
    path("member/machine-jobs/<int:pk>/approve-quote", job_actions.MemberApproveQuoteView.as_view(), name="member-machine-job-approve-quote"),
    path("member/machine-jobs/<int:pk>/decline-quote", job_actions.MemberDeclineQuoteView.as_view(), name="member-machine-job-decline-quote"),
    path("member/machine-jobs/<int:pk>/resubmit", job_actions.MemberResubmitView.as_view(), name="member-machine-job-resubmit"),
    path("public/<slug:makerspace_slug>/machine-types/<int:type_id>/intake", PublicTypeIntakeView.as_view(), name="public-machine-intake"),
    path("admin/makerspaces/<int:makerspace_id>/machine-materials", MaterialListView.as_view(), name="machine-materials"),
    path("admin/makerspaces/<int:makerspace_id>/machine-materials/<int:pk>", MaterialDetailView.as_view(), name="machine-material-detail"),
    path("admin/makerspaces/<int:makerspace_id>/machine-types/<int:type_id>/intake", MachineTypeIntakeView.as_view(), name="machine-type-intake"),
    path("public/<slug:makerspace_slug>/machines/details", PublicMachineDetailListView.as_view(), name="public-machine-details"),
    path("public/<slug:makerspace_slug>/machines/<int:pk>", PublicMachineDetailView.as_view(), name="public-machine-detail"),
    path("member/makerspaces/<int:makerspace_id>/machines", MemberMachineListView.as_view(), name="member-machines"),
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
    # Lane L23: metered machine sessions (#158), behind `machines.sessions`.
    path("member/machines/<int:machine_id>/session", sessions.MemberSessionPreviewView.as_view(), name="member-machine-session-preview"),
    path("member/machines/<int:machine_id>/sessions/start", sessions.MemberSessionStartView.as_view(), name="member-machine-session-start"),
    path("member/machine-sessions", sessions.MemberSessionListView.as_view(), name="member-machine-sessions"),
    path("member/machine-sessions/<int:pk>/stop", sessions.MemberSessionStopView.as_view(), name="member-machine-session-stop"),
    # Release 0.12.0 (decision 223): supervised workshop sessions, behind `machines.supervised_sessions`.
    path("member/machines/<int:machine_id>/supervised-sessions", supervised.SupervisedSessionOpenView.as_view(), name="member-supervised-session-open"),
    path("member/makerspaces/<int:makerspace_id>/supervised-sessions", supervised.SupervisedSessionListView.as_view(), name="member-supervised-sessions"),
    path("member/supervised-sessions/<int:pk>", supervised.SupervisedSessionDetailView.as_view(), name="member-supervised-session"),
    path("member/supervised-sessions/<int:pk>/supervisees", supervised.SupervisedSuperviseeView.as_view(), name="member-supervised-supervisees"),
    path("member/supervised-sessions/<int:pk>/people", SupervisedPeoplePickerView.as_view(), name="member-supervised-people"),
    path("member/supervised-sessions/<int:pk>/supervisees/<int:user_id>", supervised.SupervisedSuperviseeRemoveView.as_view(), name="member-supervised-supervisee-remove"),
    path("member/supervised-sessions/<int:pk>/uses", supervised.SupervisedUseStartView.as_view(), name="member-supervised-use-start"),
    path("member/supervised-uses/<int:pk>/end", supervised.SupervisedUseEndView.as_view(), name="member-supervised-use-end"),
    path("member/supervised-sessions/<int:pk>/close", supervised.SupervisedSessionCloseView.as_view(), name="member-supervised-session-close"),
]
