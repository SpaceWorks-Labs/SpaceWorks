from django.urls import path
from drf_spectacular.utils import extend_schema
from .notification_slack_views import ChatOAuthCallbackView, ChatInboundView, ChatInstallationView
from .notification_slack_installation import DiscordInstallationSerializer, InstallationStatusSerializer
from .notification_api_errors import REAUTH_403, errors


class DiscordInstallationView(ChatInstallationView):
    channel = "discord"
    serializer_class = DiscordInstallationSerializer

    @extend_schema(tags=["Chat notifications"], request=DiscordInstallationSerializer,
        responses={200: InstallationStatusSerializer, **errors(400, 401, 403, 404, 429, 423, 503, e403=REAUTH_403)})
    def post(self, request, makerspace_id):
        return super().post(request, makerspace_id)


urlpatterns = [
    path("makerspace/<int:makerspace_id>/discord/installation", DiscordInstallationView.as_view(), name="notification-discord-install"),
    path("makerspace/<int:makerspace_id>/discord/oauth/callback", ChatOAuthCallbackView.as_view(channel="discord"), name="notification-discord-oauth"),
    path("makerspace/<int:makerspace_id>/discord/inbound", ChatInboundView.as_view(channel="discord"), name="notification-discord-inbound"),
]
