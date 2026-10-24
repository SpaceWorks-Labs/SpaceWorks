"""Read-only private C shortlist signals; calculations never import these values."""

from rest_framework import serializers

from .api_common import PrivateView, admin_event, paginated, schema
from .ports import runtime
from .serializers import ClosedSerializer


class ShortlistSignalRead(ClosedSerializer):
    team_id = serializers.IntegerField(min_value=1)
    fresh_nominations = serializers.IntegerField(min_value=0)
    repeat_nominations = serializers.IntegerField(min_value=0)
    final_rating_count = serializers.IntegerField(min_value=0)
    final_rating_mean = serializers.DecimalField(max_digits=8, decimal_places=4, allow_null=True)
    top_two_picks = serializers.IntegerField(min_value=0)


class ShortlistSignals(PrivateView):
    @schema(response=ShortlistSignalRead(many=True), page=True,
            description="Full-manager private shortlist signals from C; never used as judging scores.")
    def get(self, request, pk):
        event = admin_event(request, pk, None)
        rows = runtime().shortlist_signals(event_id=event.pk)
        return paginated(request, list(rows), ShortlistSignalRead)
