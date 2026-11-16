from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from apps.events.models import Event
from apps.makerspaces.guards import require_feature
from .api_common import ProgrammeView, paginated, page_schema
from .models_roles import EventRolePosting
from .projections import posting
from .serializers import PostingSerializer, ERRORS


class VolunteerPostingPublicView(ProgrammeView):
    permission_classes = [AllowAny]

    @extend_schema(auth=[], responses={200: page_schema("PublicVolunteerPostingPage", PostingSerializer), **ERRORS})
    def get(self, request, public_token):
        event = get_object_or_404(Event.objects.select_related("makerspace"), public_token=public_token,
                                  status="published", is_public=True,
                                  page_state="live")
        require_feature(event.makerspace, "events.volunteering")
        now = timezone.now()
        rows = EventRolePosting.objects.filter(event=event, role="volunteer", visibility="public",
            state="open", opens_at__lte=now, closes_at__gt=now).order_by("pk")
        return paginated(request, rows, lambda row: posting(row, public=True))
