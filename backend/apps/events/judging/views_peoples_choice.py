"""People's choice HTTP adapters (#181 S3). Every write delegates to a workflow holding the event lock,
the command receipt and the audit; the vote route also carries its own per-account throttle."""

from drf_spectacular.utils import extend_schema_view
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.events.submissions.gallery_projection import public_event
from . import peoples_choice as config
from . import peoples_choice_ballots as ballots
from . import peoples_choice_payouts as pc_payouts
from . import peoples_choice_results as results
from . import peoples_choice_votes as votes
from .api_common import MemberView, PrivateView, schema
from .serializers import CommandInput
from .serializers_l21b import PayoutRead
from .serializers_peoples_choice import (
    BallotRead, ConfigInput, ConfigRead, PayableWinnersRead, PeoplesChoicePayoutInput, PublicRead, StandingsRead,
    VoidInput, VoteInput, VoteRowRead,
)
from apps.events.submissions.gallery_views import PublicGalleryBase


@extend_schema_view(get=schema(response=ConfigRead),
                    patch=schema(request=ConfigInput, response=ConfigRead,
                                 description="Switch the award on or off, the audience (any signed-in member, or "
                                             "checked-in attendees only), the voting window, an optional prize and "
                                             "the voting-open email (off by default). Final once published."))
class PeoplesChoiceSettings(PrivateView):
    http_method_names = ["get", "patch", "head", "options"]

    def get(self, request, pk):
        return Response(config.read(pk, actor=request.user))

    def patch(self, request, pk):
        return Response(config.update(pk, actor=request.user, data=request.data))


class PeoplesChoiceStandings(PrivateView):
    @schema(response=StandingsRead, description="Staff only: the live count before publication, else the "
                                                "published standings. Never shown to voters or the public early.")
    def get(self, request, pk):
        return Response(StandingsRead(results.standings(pk, actor=request.user)).data)


class PeoplesChoicePublish(PrivateView):
    @schema(request=CommandInput, response=StandingsRead,
            description="Publish once, after voting closes; expected_version is the settings version. "
                        "Freezes the count, names the joint winners and ends voting. 409 already_published.")
    def post(self, request, pk):
        return Response(results.publish(pk, actor=request.user, data=request.data))


class PeoplesChoiceVotes(PrivateView):
    @schema(response=VoteRowRead(many=True), page=True,
            description="Who voted (to spot abuse), never which project each person chose.")
    def get(self, request, pk):
        event, rows = ballots.listing(pk, actor=request.user)
        paginator = PageNumberPagination()
        paginator.page_size = 24
        page = paginator.paginate_queryset(rows, request)
        context = {"request": request, "makerspace_id": event.makerspace_id}
        return paginator.get_paginated_response(VoteRowRead(page, many=True, context=context).data)


class PeoplesChoiceVoteVoid(PrivateView):
    @schema(request=VoidInput, response=VoteRowRead,
            description="Void one ballot with a reason; the row stays, so that person cannot vote again.")
    def post(self, request, pk, handle):
        row = ballots.void(pk, handle, actor=request.user, data=request.data)
        context = {"request": request, "makerspace_id": config.staff_event(request.user, pk).makerspace_id}
        return Response(VoteRowRead(row, context=context).data)


@extend_schema_view(get=schema(response=PayableWinnersRead),
                    post=schema(request=PeoplesChoicePayoutInput, response=PayoutRead, status=201,
                                description="Record a People's choice prize payout by hand (record_payment or the "
                                            "Event Manager); one L5 ledger expense. Reverse it on the L21b route."))
class PeoplesChoicePayouts(PrivateView):
    def get(self, request, pk):
        return Response({"winners": pc_payouts.payable(pk, actor=request.user)})

    def post(self, request, pk):
        return Response(pc_payouts.record_payout(pk, actor=request.user, data=request.data), status=201)


class MemberPeoplesChoice(MemberView):
    @schema(response=BallotRead, description="Your ballot: whether you can vote now and why not, the project you "
                                             "chose, and your own team's projects. No counts.")
    def get(self, request, pk, makerspace_id):
        event = self.event(request, pk, makerspace_id)
        return Response(BallotRead(votes.ballot(event, actor=request.user)).data)


class MemberPeoplesChoiceVote(MemberView):
    throttle_scope = "peoples_choice_vote"

    @schema(request=VoteInput, response=BallotRead,
            description="Cast or change your one vote (expected_version is your ballot's version, 0 at first). "
                        "403 own_project, attendees_only, voided, closed; per-account throttle.")
    def post(self, request, pk, makerspace_id):
        self.event(request, pk, makerspace_id)
        return Response(votes.cast(pk, actor=request.user, data=request.data))


class PublicPeoplesChoice(PublicGalleryBase):
    @schema(response=PublicRead, public=True)
    def get(self, request, public_token):
        event = public_event(public_token=public_token, request_context=request)
        return Response(PublicRead(results.public_projection(event)).data)
