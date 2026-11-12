"""Remove a card photo's background (D314c): the holder's own card, and staff on a holder's card.

Staff routes reuse each kind's own photo authority (member cards: MANAGE_MEMBER_CARDS; staff cards: the
staff-card managers; event cards: an organiser of the event), so cross-tenant and unauthorised both answer 404.
Members act on their own card only and must agree that the photo is sent to the space's eraser service. With
`cards.photo_cutout` off every route answers 404. The job is asynchronous: POST queues, GET shows the status
(queued, running, done, failed), PATCH chooses "cutout" or "original", DELETE discards the cut-out.
"""
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status as http
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.openapi_errors import errors

from . import cutouts
from .eraser_notice import set_opt_out, with_notice
from .holder_access import own_card
from .serializers_image_adapter import (CutoutOptOutSerializer, CutoutRequestSerializer, CutoutSerializer,
                                       CutoutUseSerializer)

STAFF_TAG = "Card photos (staff)"
MEMBER_TAG = "My cards"
KINDS = ("member_card", "event_card")
_ERR = errors(400, 401, 403, 404, 409)


class CutoutPostThrottle(ScopedRateThrottle):
    """Only the POST sends a photo to an external service; reads and choices are free."""

    def allow_request(self, request, view):
        return request.method != "POST" or super().allow_request(request, view)


class _CutoutBase(APIView):
    permission_classes = [IsAuthenticated]
    by_holder = False
    kind = ""

    def card(self, request, **kwargs):  # pragma: no cover - each subclass resolves its card
        raise NotImplementedError

    def status(self, card):
        """The cut-out status with the eraser notice and the photo owner's opt-out (decision 345(b))."""
        return with_notice(self.kind, card, cutouts.status(self.kind, card))

    def get(self, request, **kwargs):
        card = self.card(request, **kwargs)
        cutouts._require_on(card.makerspace, self.kind)
        return Response(self.status(card))

    def post(self, request, **kwargs):
        card = self.card(request, **kwargs)
        data = CutoutRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        cutouts.request(request.user, self.kind, card, by_holder=self.by_holder,
                        consent=data.validated_data["consent"])
        return Response(self.status(card), status=http.HTTP_202_ACCEPTED)

    def patch(self, request, **kwargs):
        card = self.card(request, **kwargs)
        data = CutoutUseSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        cutouts.set_use(request.user, self.kind, card, data.validated_data["use"])
        return Response(self.status(card))

    def delete(self, request, **kwargs):
        card = self.card(request, **kwargs)
        cutouts.discard(request.user, self.kind, card)
        return Response(self.status(card))


def _docs(tag, who):
    return {
        "get": extend_schema(tags=[tag], summary=f"Background-removal status of {who} card photo", request=None,
                             responses={200: CutoutSerializer, **errors(401, 403, 404)}),
        "post": extend_schema(tags=[tag], summary=f"Remove the background of {who} card photo (queues a job)",
                              description="Needs `cards.photo_cutout` and a configured eraser service; counts against "
                                          "`photo_cutout_jobs_monthly`. The original is kept.",
                              request=CutoutRequestSerializer, responses={202: CutoutSerializer, **_ERR}),
        "patch": extend_schema(tags=[tag], summary="Use the cut-out or the original", request=CutoutUseSerializer,
                               responses={200: CutoutSerializer, **_ERR}),
        "delete": extend_schema(tags=[tag], summary="Discard the cut-out (the original stays)", request=None,
                                responses={200: CutoutSerializer, **errors(401, 403, 404)}),
    }


@extend_schema_view(**_docs(STAFF_TAG, "a holder's"))
class _StaffCutoutView(_CutoutBase):
    def card(self, request, pk):
        from .views_staff_photo import (EventCardStaffPhotoView, MemberCardStaffPhotoView)
        resolver = {"member_card": MemberCardStaffPhotoView, "event_card": EventCardStaffPhotoView}.get(self.kind)
        if resolver is not None:
            return resolver().card(request, pk)
        from .staff_card_access import card_for  # a staff card: the managers of staff cards
        return card_for(request.user, pk)


class MemberCardCutoutView(_StaffCutoutView):
    kind = "member_card"


class StaffCardCutoutView(_StaffCutoutView):
    kind = "staff_card"


class EventIdCardCutoutView(_StaffCutoutView):
    kind = "event_card"


@extend_schema_view(**_docs(MEMBER_TAG, "my"))
class MyCardCutoutView(_CutoutBase):
    """The holder's own opt-in. Throttled: each POST sends a photo to an external service."""
    by_holder = True
    throttle_classes = [CutoutPostThrottle]
    throttle_scope = "id_join_upload"

    def card(self, request, kind, card_id):
        if kind not in KINDS:
            raise NotFound()
        self.kind = kind
        return own_card(request.user, kind, card_id)[1]

    def get(self, request, kind, card_id):
        return super().get(request, kind=kind, card_id=card_id)

    def post(self, request, kind, card_id):
        return super().post(request, kind=kind, card_id=card_id)

    def patch(self, request, kind, card_id):
        return super().patch(request, kind=kind, card_id=card_id)

    def delete(self, request, kind, card_id):
        return super().delete(request, kind=kind, card_id=card_id)

    @extend_schema(tags=[MEMBER_TAG], summary="Opt my card photo out of (or back into) background removal",
                   description="Decision 345(b). Opting out deletes any cut-out and means the photo is never sent to the "
                               "eraser by anyone (staff and bulk uploads skip it); the card prints the original. "
                               "Allowed whether or not the eraser is switched on. Audited.",
                   request=CutoutOptOutSerializer, responses={200: CutoutSerializer, **errors(400, 401, 403, 404)})
    def put(self, request, kind, card_id):
        card = self.card(request, kind=kind, card_id=card_id)
        data = CutoutOptOutSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        set_opt_out(request.user, self.kind, card, data.validated_data["opted_out"])
        return Response(self.status(card))
