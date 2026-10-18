from django.urls import path
from drf_spectacular.utils import extend_schema
from .notification_slack_views import ChatOAuthCallbackView, ChatInboundView, ChatInstallationView
from .notification_slack_installation import MattermostInstallationSerializer, InstallationStatusSerializer
from .notification_api_errors import REAUTH_403, errors


class MattermostInstallationView(ChatInstallationView):
    channel = "mattermost"
    serializer_class = MattermostInstallationSerializer

    @extend_schema(tags=["Chat notifications"], request=MattermostInstallationSerializer,
        responses={200: InstallationStatusSerializer, **errors(400, 401, 403, 404, 429, 423, 503, e403=REAUTH_403)})
    def post(self, request, makerspace_id):
        return super().post(request, makerspace_id)


urlpatterns = [
    path("makerspace/<int:makerspace_id>/mattermost/installation", MattermostInstallationView.as_view(), name="notification-mattermost-install"),
    path("makerspace/<int:makerspace_id>/mattermost/oauth/callback", ChatOAuthCallbackView.as_view(channel="mattermost"), name="notification-mattermost-oauth"),
    path("makerspace/<int:makerspace_id>/mattermost/inbound", ChatInboundView.as_view(channel="mattermost"), name="notification-mattermost-inbound"),
]
