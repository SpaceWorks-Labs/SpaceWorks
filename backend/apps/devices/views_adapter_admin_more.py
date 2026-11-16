"""Staff routes: shelf-pointer poses and calibration, NFC/PIN credentials and camera watch sessions."""
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.devices import services_adapter_credentials as creds
from apps.devices import services_adapter_locate as locate
from apps.devices import services_adapter_watch as watch
from apps.devices.openapi_adapter_staff import RESPONSES as DOC, page
from apps.devices.serializers_adapter import (
    AimSerializer, CommandSerializer, CredentialSerializer, CredentialWriteSerializer, IndicateSerializer,
    BindingConfigSerializer, JobCreateSerializer, JogSerializer, PoseKeySerializer, PoseSerializer, PoseWriteSerializer, WatchSerializer, WatchStartSerializer,
)
from apps.devices.serializers_adapter_logs import BindingJobSerializer
from apps.devices.throttles import WATCH_RELAY_THROTTLES, WATCH_START_THROTTLES
from apps.devices.views_adapter_admin import ERRORS, TAG
from apps.devices.views_adapter_admin_logs import JOB_PARAMS, binding_jobs


def _valid(serializer_class, data):
    serializer = serializer_class(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


class AdapterPoseListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="List the saved poses of a shelf-pointer binding (staff only)",
                   responses={200: PoseSerializer(many=True), **ERRORS})
    def get(self, request, pk):
        return Response(PoseSerializer(locate.list_poses(request.user, pk), many=True).data)

    @extend_schema(tags=[TAG], summary="Save the pose for a location, item or box", request=PoseWriteSerializer,
                   responses={200: PoseSerializer, **ERRORS})
    def put(self, request, pk):
        return Response(PoseSerializer(locate.save_pose(request.user, pk, **_valid(PoseWriteSerializer, request.data))).data)

    @extend_schema(tags=[TAG], summary="Clear a saved pose", request=PoseKeySerializer, responses={204: None, **ERRORS})
    def delete(self, request, pk):
        locate.clear_pose(request.user, pk, **_valid(PoseKeySerializer, request.data))
        return Response(status=204)


class AdapterAimView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Calibration: aim the pointer at a candidate pose", request=AimSerializer,
                   responses={201: CommandSerializer, **ERRORS})
    def post(self, request, pk):
        return Response(CommandSerializer(locate.aim(request.user, pk, _valid(AimSerializer, request.data)["pose"])).data,
                        status=201)


class AdapterJogView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Calibration: nudge the pointer", request=JogSerializer,
                   responses={201: CommandSerializer, **ERRORS})
    def post(self, request, pk):
        return Response(CommandSerializer(locate.jog(request.user, pk, **_valid(JogSerializer, request.data))).data,
                        status=201)


class AdapterIndicateView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Point at or light a calibrated location, item or box (staff only)",
                   request=IndicateSerializer, responses={201: CommandSerializer, **ERRORS})
    def post(self, request, pk):
        return Response(CommandSerializer(locate.indicate(request.user, pk, **_valid(IndicateSerializer, request.data))).data,
                        status=201)


class AdapterPositionView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="The pointer's latest reported position during calibration",
                   responses={200: DOC["position"], **ERRORS})
    def get(self, request, pk):
        return Response({"pose": locate.latest_position(request.user, pk)})


class AdapterCredentialListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="List NFC/PIN credentials (never the secret or digest)",
                   responses={200: CredentialSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        user_id = request.query_params.get("user_id")
        rows = creds.list_credentials(request.user, makerspace_id, int(user_id) if user_id and user_id.isdigit() else None)
        return Response(CredentialSerializer(rows, many=True).data)

    @extend_schema(tags=[TAG], summary="Set (or rotate) a member's NFC tag or PIN; the secret is never returned",
                   request=CredentialWriteSerializer, responses={201: CredentialSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        row = creds.set_credential(request.user, makerspace_id, **_valid(CredentialWriteSerializer, request.data))
        return Response(CredentialSerializer(row).data, status=201)


class AdapterCredentialDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Disable a credential", request=None,
                   responses={200: CredentialSerializer, **ERRORS})
    def delete(self, request, pk):
        return Response(CredentialSerializer(creds.disable_credential(request.user, pk)).data)


class AdapterWatchCreateView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = WATCH_START_THROTTLES

    @extend_schema(tags=[TAG], summary="Open a camera watch session (audited, five minutes, limited)",
                   request=WatchStartSerializer, responses={201: WatchSerializer, **ERRORS})
    def post(self, request, pk):
        data = _valid(WatchStartSerializer, request.data)
        row = watch.start_watch(request.user, pk, data["reason"], data["record"], audio=data["audio"],
                               talk=data["talk"], notice_ack=data["notice_ack"])
        return Response(WatchSerializer(row).data, status=201)


class AdapterWatchDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="End a camera watch session", request=None,
                   responses={200: WatchSerializer, **ERRORS})
    def delete(self, request, pk):
        return Response(WatchSerializer(watch.end_watch(request.user, pk)).data)


class AdapterWatchSnapshotView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = WATCH_RELAY_THROTTLES

    @extend_schema(tags=[TAG], summary="Request one still while a watch session is open", request=None,
                   responses={201: CommandSerializer, **ERRORS})
    def post(self, request, pk):
        return Response(CommandSerializer(watch.request_snapshot(request.user, pk)).data, status=201)



class AdapterJobCreateView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="A binding's adapter jobs with command state (paginated, newest first)",
                   parameters=JOB_PARAMS, responses={200: page("AdapterBindingJobPage", BindingJobSerializer), **ERRORS})
    def get(self, request, pk):
        return binding_jobs(request, pk)

    @extend_schema(tags=[TAG], summary="Dispatch an in-progress machine-service request to the adapter",
                   request=JobCreateSerializer, responses={201: DOC["job_created"], **ERRORS})
    def post(self, request, pk):
        from apps.devices import services_adapter_jobs as jobs
        job = jobs.create_job(request.user, pk, _valid(JobCreateSerializer, request.data)["service_request_id"])
        return Response({"job_id": str(job.pk), "state": job.state}, status=201)


class AdapterBindingConfigView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Set a binding's server-enforced safety config (idle auto-off, area clear)",
                   request=BindingConfigSerializer, responses={200: DOC["binding_config"], **ERRORS})
    def put(self, request, pk):
        from apps.devices import services_adapter_admin as admin
        binding = admin.set_config(request.user, pk, dict(_valid(BindingConfigSerializer, request.data)))
        from apps.devices.services_adapter_safety import config_view
        return Response({"id": str(binding.pk), **config_view(binding)})
