"""A Space Manager edits their own space's chat message templates (#190 follow-up).

The same editor, validation and audit rows (``chat_template.saved`` / ``.deleted``) as the
superadmin path in ``views_platform_chat_templates``, which stays as it is. Authority is
``MANAGE_MAKERSPACE`` in this space, resolved through rbac -- the action the chat rooms
themselves (``admin-notification-destinations``) already need, since a template decides
what those rooms are told. No new role or action. The superadmin reaches it too, through
the console surface rule, like every other space setting.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff, require_action
from apps.makerspaces.servability import servable_queryset
from apps.openapi_errors import errors

from .views_platform_chat_templates import ChatTemplateDetailBase, ChatTemplateListBase, ChatTemplateSerializer

TAGS = ["Makerspaces"]


class _SpaceScoped:
    def _space(self, request, makerspace_id):
        require_action(request.user, rbac.Action.MANAGE_MAKERSPACE, makerspace_id)
        return get_object_or_404(servable_queryset(), pk=makerspace_id)


@extend_schema_view(
    get=extend_schema(tags=TAGS, summary="List this space's chat message templates",
                      responses={200: ChatTemplateSerializer(many=True), **errors(401, 403, 404)}),
    post=extend_schema(tags=TAGS, summary="Add a chat message template for one event in this space",
                       request=ChatTemplateSerializer, responses={201: ChatTemplateSerializer, **errors(400, 401, 403, 404, 423)}),
)
class SpaceChatTemplateListCreateView(_SpaceScoped, ChatTemplateListBase):
    permission_classes = [IsActiveStaff]


@extend_schema_view(
    patch=extend_schema(tags=TAGS, summary="Change one of this space's chat message templates", request=ChatTemplateSerializer,
                        responses={200: ChatTemplateSerializer, **errors(400, 401, 403, 404, 423)}),
    delete=extend_schema(tags=TAGS, summary="Remove a chat template (the event goes back to the built-in text)",
                         responses={204: None, **errors(401, 403, 404, 423)}),
)
class SpaceChatTemplateDetailView(_SpaceScoped, ChatTemplateDetailBase):
    permission_classes = [IsActiveStaff]
