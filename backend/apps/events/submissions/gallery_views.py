"""Gallery routes have their own live publication gate, not EventPage expiry."""

from django.http import Http404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.events.judging.api_common import ERRORS, MemberView, PrivateView, admin_event, paginated, schema
from . import gallery_consent_workflow as consent
from . import gallery_workflow as workflow
from .gallery_api_schemas import AdminGalleryRead, GalleryConsentRead, GalleryEntryRead, GalleryPublishRead, PublicResultsRead
from .gallery_models import GalleryEntry, GalleryPublication
from .gallery_projection import asset_download, project_entry, public_event, public_results
from .gallery_serializers import (
    GalleryAmendInput, GalleryGrantInput, GalleryHideInput, GalleryPublishInput, GalleryResultCorrectionInput, GalleryWithdrawInput,
)


class GalleryPublish(PrivateView):
    @schema(request=GalleryPublishInput, response=GalleryPublishRead)
    def post(self, request, pk):
        return Response(workflow.publish(pk, actor=request.user, data=request.data))


class AdminGallery(PrivateView):
    @schema(response=AdminGalleryRead)
    def get(self, request, pk):
        event = admin_event(request, pk, None)
        publication = GalleryPublication.objects.filter(event=event).first()
        return Response({"id": publication.pk if publication else None,
            "version": publication.version if publication else 0,
            "result_revision_id": publication.result_revision_id if publication else None,
            "entries": [{"id": e.pk, "snapshot_id": e.snapshot_id, "version": e.version,
                         "title": e.title, "hidden": e.hidden_at is not None}
                        for e in publication.entries.order_by("pk")] if publication else []})


class GalleryHide(PrivateView):
    @schema(request=GalleryHideInput, response=GalleryPublishRead)
    def post(self, request, pk, entry_id):
        return Response(workflow.hide(pk, entry_id, actor=request.user, data=request.data))


class GalleryAmend(PrivateView):
    @schema(request=GalleryAmendInput, response=GalleryPublishRead)
    def post(self, request, pk):
        return Response(workflow.amend(pk, actor=request.user, data=request.data))


class GalleryCorrectResult(PrivateView):
    @schema(request=GalleryResultCorrectionInput, response=GalleryPublishRead)
    def post(self, request, pk):
        return Response(workflow.correct_result(pk, actor=request.user, data=request.data))


class GalleryConsentDetail(MemberView):
    @schema(response=GalleryConsentRead)
    def get(self, request, pk, makerspace_id, team_id):
        self.event(request, pk, makerspace_id)
        return Response(consent.project_owner(pk, team_id, actor=request.user))


class GalleryConsentWithdraw(MemberView):
    @schema(request=GalleryWithdrawInput, response=GalleryConsentRead)
    def post(self, request, pk, makerspace_id, team_id):
        self.event(request, pk, makerspace_id)
        return Response(consent.withdraw(pk, team_id, actor=request.user, data=request.data))


class GalleryConsentGrant(MemberView):
    @schema(request=GalleryGrantInput, response=GalleryConsentRead)
    def post(self, request, pk, makerspace_id, team_id):
        self.event(request, pk, makerspace_id)
        return Response(consent.grant(pk, team_id, actor=request.user, data=request.data))


class PublicGalleryBase(PrivateView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "public_read"


class GalleryList(PublicGalleryBase):
    @schema(response=GalleryEntryRead(many=True), page=True, public=True)
    def get(self, request, public_token):
        event = public_event(public_token=public_token, request_context=request)
        rows = GalleryEntry.objects.filter(event=event, hidden_at__isnull=True).select_related("event").order_by("pk")
        result = []
        for row in rows:
            try:
                result.append(project_entry(row))
            except Http404:
                continue
        # Counts are over currently publishable entries only, never private rows.
        return paginated(request, result, GalleryEntryRead)


class GalleryDetail(PublicGalleryBase):
    @schema(response=GalleryEntryRead, public=True)
    def get(self, request, public_token, entry_public_id):
        event = public_event(public_token=public_token, request_context=request)
        row = GalleryEntry.objects.filter(event=event, public_id=entry_public_id).select_related("event").first()
        if row is None:
            raise Http404
        return Response(GalleryEntryRead(project_entry(row)).data)


class GalleryAsset(PublicGalleryBase):
    @extend_schema(tags=["Public event programme"], auth=[],
        parameters=[OpenApiParameter("Range", str, OpenApiParameter.HEADER)],
        responses={(200, "application/octet-stream"): OpenApiResponse(bytes, description="Live-consented bytes; no-store, no redirects."),
                   (206, "application/octet-stream"): OpenApiResponse(bytes, description="Single bounded range."),
                   416: OpenApiResponse(description="Invalid/unsatisfiable range."), **ERRORS})
    def get(self, request, public_token, public_asset_id):
        return asset_download(public_token, public_asset_id, request=request)


class PublicResults(PublicGalleryBase):
    @schema(response=PublicResultsRead, public=True)
    def get(self, request, public_token):
        event = public_event(public_token=public_token, request_context=request)
        return Response(PublicResultsRead(public_results(event)).data)
