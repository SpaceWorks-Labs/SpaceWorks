"""Signed Device Adapter API v1 routes, part 2: job dispatch + files, kiosk checkout, media (signaling, frames,
recording). Same authentication, tenant gating and 404-when-off behaviour as ``views_adapter``; every one is in
``route_registry_adapter`` and delegates to a service (no rule lives in a view)."""
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response

from apps.devices import services_adapter_jobs as jobs
from apps.devices import services_adapter_kiosk as kiosk
from apps.devices import services_adapter_media as media
from apps.devices.openapi_adapter import RESPONSES
from apps.devices.views_adapter import ERRORS, TAG, _doc
from apps.devices.views_adapter_base import SignedAdapterView, SignedCredentialView

AFTER = OpenApiParameter("after", int, description="Return only signals with a sequence number above this.")


class AdapterJobLeaseView(SignedAdapterView):
    @_doc("Lease the next dispatched machine-service job (signed; held back until the area is clear)",
          response="job_lease")
    def post(self, request):
        return Response(jobs.lease(request.user))


class AdapterJobAckView(SignedAdapterView):
    @_doc("Acknowledge a leased job and bind the vendor external job id (signed, idempotent)", "job_ack", "job_ack")
    def post(self, request, pk):
        return Response(jobs.acknowledge(request.user, pk, request.data))


class AdapterJobProgressView(SignedAdapterView):
    @_doc("Report progress of an acknowledged job (signed)", "job_progress", "job_progress")
    def post(self, request, pk):
        return Response(jobs.progress(request.user, pk, request.data))


class AdapterJobReportView(SignedAdapterView):
    @_doc("Terminal report with measured consumption, idempotent by operation_id (signed)", "job_report",
          "job_report")
    def post(self, request, pk):
        return Response(jobs.report(request.user, pk, request.data))


class AdapterJobFileView(SignedAdapterView):
    @_doc("Short-lived signed URLs for the job files (signed)", response="job_files")
    def get(self, request, pk):
        return Response(jobs.files(request.user, pk))


class AdapterKioskStartView(SignedCredentialView):
    @_doc("Authenticate a member (card QR, NFC, PIN) and open a five-minute kiosk session (signed)", "kiosk_start",
          "kiosk_start", code=201)
    def post(self, request):
        return Response(kiosk.start(request.user, request.data), status=201)


class AdapterKioskSessionView(SignedAdapterView):
    @_doc("End a kiosk session (signed)", response="kiosk_end")
    def delete(self, request, sid):
        return Response(kiosk.end(request.user, sid))


class AdapterKioskScanView(SignedAdapterView):
    @_doc("What may be done with a scanned tool: checkout, return or why not (signed)", "kiosk_scan", "kiosk_scan")
    def post(self, request, sid):
        return Response(kiosk.scan(request.user, sid, request.data))


class AdapterKioskEvidenceView(SignedAdapterView):
    @_doc("Presigned STAGING upload for the issue or return photo (signed)", "kiosk_evidence", "kiosk_evidence",
          code=201)
    def post(self, request, sid):
        return Response(kiosk.evidence(request.user, sid, request.data), status=201)


class AdapterKioskIssueView(SignedAdapterView):
    @_doc("Issue a tool through the self-checkout workflow; needs the uploaded issue photo (signed)", "kiosk_issue",
          "kiosk_loan", code=201)
    def post(self, request, sid):
        return Response(kiosk.issue(request.user, sid, request.data), status=201)


class AdapterKioskReturnView(SignedAdapterView):
    @_doc("Return a tool through the self-checkout workflow; needs the return photo and a remark (signed)",
          "kiosk_return", "kiosk_loan")
    def post(self, request, sid):
        return Response(kiosk.return_(request.user, sid, request.data))


class AdapterMediaSignalView(SignedAdapterView):
    @extend_schema(tags=[TAG], summary="Adapter side of the WebRTC signaling relay (signed)", parameters=[AFTER],
                   responses={200: RESPONSES["signal_poll"], **ERRORS})
    def get(self, request, watch_id):
        after = request.query_params.get("after", "0")
        return Response(media.adapter_poll(request.user, watch_id, int(after) if after.isdigit() else 0))

    @_doc("Send an SDP offer/answer or ICE candidate to the viewer (signed)", "signal", "signal_sent", code=201)
    def post(self, request, watch_id):
        return Response(media.adapter_signal(request.user, watch_id, request.data), status=201)


class AdapterMediaSnapshotView(SignedAdapterView):
    @_doc("Upload one still while a watch is open (signed; cached for a minute, never stored)", "frame", "frame",
          code=201)
    def post(self, request, watch_id):
        return Response(media.store_frame(request.user, watch_id, request.data), status=201)


class AdapterMediaRecordingView(SignedAdapterView):
    @_doc("Presigned upload for an opt-in recording clip; retention-limited and audited (signed)", "recording",
          "recording", code=201)
    def post(self, request, watch_id):
        return Response(media.recording_upload(request.user, watch_id, request.data), status=201)
