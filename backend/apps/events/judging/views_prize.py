"""Hack-money prize money HTTP adapters (#180 G3-G6/G8/G16, #181 G7). Nothing here moves money:
payouts stay hand-recorded, recoveries never charge anyone, claims are masked on every read."""

from rest_framework.response import Response

from . import prize_claims, prize_outcomes, prize_reads, prize_shares
from .api_common import MemberView, PrivateView, paginated, schema
from .prize_access import finance_event, read_key
from .serializers import CommandInput
from .serializers_prize import (
    AwardSplitRead, ClaimInput, ClaimRead, ForfeitInput, FulfilInput, MyPrizeRead, OutcomeRead, PrizePoolRead,
    PublicPrizeRead, RecoveryResolveInput, RevealInput, RevealRead, ShareRespondInput, SplitInput, StaffClaimRow,
)


class AdminPrizeSplit(PrivateView):
    @schema(request=SplitInput, response=AwardSplitRead,
            description="Staff record a split the team agreed (every share confirmed). events.prize_claims. "
                        "409 payout_exists once a payout stands.")
    def post(self, request, pk, award_id):
        return Response(prize_shares.record_split(pk, award_id, actor=request.user, data=request.data))


class PrizeFulfil(PrivateView):
    @schema(request=FulfilInput, response=OutcomeRead, status=201,
            description="A non-cash prize handed over or shipped, or a sponsor_direct prize the sponsor paid. "
                        "Never a ledger entry.")
    def post(self, request, pk, award_id):
        return Response(prize_outcomes.fulfil(pk, award_id, actor=request.user, data=request.data), status=201)


class PrizeForfeit(PrivateView):
    @schema(request=ForfeitInput, response=OutcomeRead, status=201,
            description="After the claim window: an unpaid prize or share is forfeited. No ledger effect.")
    def post(self, request, pk, award_id):
        return Response(prize_outcomes.forfeit(pk, award_id, actor=request.user, data=request.data), status=201)


class PrizeOutcomes(PrivateView):
    @schema(response=OutcomeRead(many=True), page=True,
            description="Fulfilments, sponsor payments, forfeits and recoveries (record_payment or the Event Manager).")
    def get(self, request, pk):
        return paginated(request, prize_outcomes.listing(finance_event(request.user, pk)), OutcomeRead)


class PrizeRecoveryResolve(PrivateView):
    @schema(request=RecoveryResolveInput, response=OutcomeRead, status=201,
            description="Close a recovery: 'repaid' writes a ledger receipt (prize_recovery); 'waived' needs a note.")
    def post(self, request, pk, outcome_id):
        return Response(prize_outcomes.resolve_recovery(pk, outcome_id, actor=request.user, data=request.data),
                        status=201)


class PrizeClaims(PrivateView):
    @schema(response=StaffClaimRow(many=True), page=True,
            description="Every share with its claim: payee details and PAN are masked, never shown in full.")
    def get(self, request, pk):
        event = finance_event(request.user, pk)
        with read_key(event.makerspace_id):
            return paginated(request, prize_reads.staff_claims(event), StaffClaimRow)


class PrizeClaimVerify(PrivateView):
    @schema(request=CommandInput, response=ClaimRead, description="Finance confirms a winner's payee details.")
    def post(self, request, pk, share_id):
        return Response(prize_claims.verify(pk, share_id, actor=request.user, data=request.data))


class PrizeClaimReveal(PrivateView):
    @schema(request=RevealInput, response=RevealRead,
            description="Finance reads one winner's full payee details and PAN to pay them. Audited on every "
                        "release with its reason (never the values). 404 once the details are cleared.")
    def post(self, request, pk, share_id):
        return Response(prize_claims.reveal(pk, share_id, actor=request.user, data=request.data))


class PrizePool(PrivateView):
    @schema(response=PrizePoolRead, description="G8: announced cash, sponsorship earmarked to the pool, paid, "
                                                "tax recorded, owed and recovered.")
    def get(self, request, pk):
        return Response(PrizePoolRead(prize_reads.prize_pool(finance_event(request.user, pk))).data)


class MemberPrizeSplit(MemberView):
    @schema(request=SplitInput, response=AwardSplitRead,
            description="The winning team's leader proposes how the prize is shared; members confirm each share.")
    def post(self, request, pk, makerspace_id, award_id):
        self.event(request, pk, makerspace_id)
        return Response(prize_shares.propose(pk, award_id, actor=request.user, data=request.data))


class MemberShareConfirm(MemberView):
    accept = True

    @schema(request=ShareRespondInput, response=AwardSplitRead, description="Answer a proposed prize share.")
    def post(self, request, pk, makerspace_id, share_id):
        self.event(request, pk, makerspace_id)
        return Response(prize_shares.respond(pk, share_id, actor=request.user, data=request.data, accept=self.accept))


class MemberShareDecline(MemberShareConfirm):
    accept = False


class MemberPrizeClaim(MemberView):
    @schema(request=ClaimInput, response=ClaimRead,
            description="Give where to be paid (the space's accepted payee templates) and, optionally, a PAN. "
                        "Encrypted; returned masked. 409 claim_window_closed after the window.")
    def post(self, request, pk, makerspace_id, award_id):
        self.event(request, pk, makerspace_id)
        return Response(prize_claims.submit(pk, award_id, actor=request.user, data=request.data))


class MemberPrizeClaimRemove(MemberView):
    @schema(request=CommandInput, response=ClaimRead, description="Remove my payee details and PAN while unpaid.")
    def post(self, request, pk, makerspace_id, award_id):
        self.event(request, pk, makerspace_id)
        return Response(prize_claims.remove(pk, award_id, actor=request.user, data=request.data))


class MyPrizes(MemberView):
    @schema(response=MyPrizeRead(many=True), page=True,
            description="My prizes in this space: status, my share, my payout (gross, tax, net) and my claim, masked.")
    def get(self, request, makerspace_id):
        from .boundary import active_member
        active_member(request.user)
        with read_key(makerspace_id):
            return paginated(request, prize_reads.my_prizes(request.user, makerspace_id), MyPrizeRead)


class PublicPrizes(PrivateView):
    from rest_framework.permissions import AllowAny
    permission_classes = [AllowAny]
    authentication_classes = []

    @schema(response=PublicPrizeRead(many=True), public=True,
            description="The event's prizes with kinds and amounts, only with 'show prize amounts publicly' on.")
    def get(self, request, public_token):
        from apps.events.submissions.gallery_projection import public_event
        event = public_event(public_token=public_token, request_context=request, gallery=False)
        return Response(PublicPrizeRead(prize_reads.public_prizes(event), many=True).data)
