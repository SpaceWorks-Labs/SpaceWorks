"""Thin owner API; application answer and status writers live in services."""
from drf_spectacular.utils import extend_schema
from apps.apiclients.throttling import ClientTierRateThrottle
from rest_framework.response import Response
from . import admission_dates, admission_rsvp, admission_workflow
from .admission_inputs import ApplicationInput
from .api_base import MemberCommandView, ProgrammeView
from .api_context import context_for_token, owner_application
from .api_schema import ApplicationSerializer, ContextSerializer, ERRORS
from .serializers_commands import DateReviewInput, RsvpInput, WithdrawalInput


class ContextView(ProgrammeView):
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"

    @extend_schema(tags=["Event programme"], request=None, responses={200: ContextSerializer, **ERRORS})
    def get(self, request, public_token):
        return Response(context_for_token(public_token=public_token, actor=request.user, request=request))

    @extend_schema(tags=["Event programme"], request=None, responses={200: None, **ERRORS})
    def head(self, request, public_token):
        context_for_token(public_token=public_token, actor=request.user, request=request)
        return Response(status=200)


class ApplicationView(MemberCommandView):
    @extend_schema(tags=["Event programme"], request=None, responses={200: ApplicationSerializer, **ERRORS})
    def get(self, request, makerspace_id, pk):
        event, config = self.member_target(request, makerspace_id, pk)
        return Response(owner_application(event=event, config=config, actor=request.user, request=request))

    @extend_schema(tags=["Event programme"], request=ApplicationInput,
                   responses={200: ApplicationSerializer, 201: ApplicationSerializer, **ERRORS})
    def patch(self, request, makerspace_id, pk):
        event, config = self.member_target(request, makerspace_id, pk)
        data = self.command_data(request, ApplicationInput, draft=True)
        row, code = admission_workflow.save_application(event=event, actor=request.user, payload=data)
        return Response(owner_application(event=event, config=config, actor=request.user, request=request), status=code)


class ApplicationSubmitView(MemberCommandView):
    @extend_schema(tags=["Event programme"], request=ApplicationInput,
                   responses={200: ApplicationSerializer, 201: ApplicationSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        event, config = self.member_target(request, makerspace_id, pk)
        data = self.command_data(request, ApplicationInput)
        row, code = admission_workflow.save_application(event=event, actor=request.user, payload=data, submit=True)
        return Response(owner_application(event=event, config=config, actor=request.user, request=request), status=code)


class ApplicationWithdrawView(MemberCommandView):
    @extend_schema(tags=["Event programme"], request=WithdrawalInput, responses={200: ApplicationSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        event, config = self.member_target(request, makerspace_id, pk)
        admission_rsvp.withdraw(event_id=pk, actor=request.user, data=self.command_data(request, WithdrawalInput))
        return Response(owner_application(event=event, config=config, actor=request.user, request=request))


class ApplicationRsvpView(MemberCommandView):
    @extend_schema(tags=["Event programme"], request=RsvpInput, responses={200: ApplicationSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        event, config = self.member_target(request, makerspace_id, pk)
        admission_rsvp.rsvp(event_id=pk, actor=request.user, data=self.command_data(request, RsvpInput))
        return Response(owner_application(event=event, config=config, actor=request.user, request=request))


class ApplicationDateReviewView(MemberCommandView):
    @extend_schema(tags=["Event programme"], request=DateReviewInput, responses={200: ApplicationSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        event, config = self.member_target(request, makerspace_id, pk)
        admission_dates.review_date(event_id=pk, actor=request.user, data=self.command_data(request, DateReviewInput))
        return Response(owner_application(event=event, config=config, actor=request.user, request=request))
