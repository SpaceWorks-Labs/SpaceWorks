from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from rest_framework.permissions import IsAuthenticated, AllowAny
from .views_base import PrivateSubmissionView

from apps.events.contracts.providers import ReadPurpose
from .api_runtime import runtime
from .downloads import download_response
from .errors import SubmissionError
from .models_assets import SubmissionAsset, HackathonParticipantAsset
from .views_projects import ERRORS

RANGE = [OpenApiParameter("Range", str, OpenApiParameter.HEADER, description="One bytes=start-end or suffix range; multiple ranges return 416.")]
BINARY = {200: OpenApiTypes.BINARY, 206: OpenApiTypes.BINARY, 416: None, **ERRORS}


class AssetDownloadView(PrivateSubmissionView):
    permission_classes = [IsAuthenticated]
    participant = False
    staff = False

    @extend_schema(parameters=RANGE, responses=BINARY, tags=["Event asset streams"])
    def get(self, request, pk, asset_id, **kwargs):
        cls = HackathonParticipantAsset if self.participant else SubmissionAsset
        # Nested event mismatch is always hidden before invoking any storage.
        if not cls.objects.filter(pk=asset_id, event_id=pk).exists():
            raise SubmissionError("not_found", 404)
        adapter = runtime()
        purpose, snapshot_id = (ReadPurpose.OWNER_HISTORY if self.participant else ReadPurpose.TEAM_ORIGINAL), None
        if self.staff:
            # G/D derive this from a current staff role/assignment, never a URL query.
            purpose, snapshot_id = adapter.admin_read_purpose(request=request, event_id=pk, asset_id=asset_id)
        return download_response(request=request,
            reader=adapter.participant_reader if self.participant else adapter.asset_reader,
            storage_reader=adapter.storage_reader, actor_id=request.user.pk, asset_id=asset_id,
            snapshot_id=snapshot_id, purpose=purpose)


class GalleryAssetView(PrivateSubmissionView):
    permission_classes = [AllowAny]

    @extend_schema(parameters=RANGE, responses=BINARY, tags=["Event gallery streams"])
    def get(self, request, public_token, public_asset_id):
        from .gallery_projection import asset_download
        return asset_download(public_token, public_asset_id, request=request)
