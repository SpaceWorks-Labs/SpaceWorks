"""Owner history is core and identity-bound, independent of membership/Events."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from apps.accounts.account_kind_guards import require_member_account
from apps.makerspaces.servability import servable_q
from .http import PrivateView, obligation, body, paginate
from . import serializers as s
from . import payee_workflow
from .obligation_models import EventPayoutObligation
from .queries import summary
from .transactions import command


class MemberPayoutListView(PrivateView):
    @extend_schema(tags=["Event payouts"], responses={200: s.PayoutSummarySerializer(many=True), **s.ERRORS})
    def get(self, request):
        from apps.accounts.reauthentication import binding
        binding(request)
        require_member_account(request.user)
        rows = EventPayoutObligation.objects.filter(servable_q("makerspace"), owner_member=request.user).order_by("-created_at", "pk")
        return paginate(request, rows, lambda row: summary(obligation(request, row.pk, owner=True)))


class MemberPayoutDetailView(PrivateView):
    @extend_schema(tags=["Event payouts"], responses={200: s.PayoutSummarySerializer, **s.ERRORS})
    def get(self, request, obligation_id):
        row = obligation(request, obligation_id, owner=True)
        return Response({**summary(row), "payee": payee_workflow.projection(payee_workflow.current(row)),
            "entries": list(row.entries.values("id", "amount_minor", "currency", "method", "reference", "paid_at", "amends_id", "is_void"))})


class MemberPayeeView(PrivateView):
    @extend_schema(tags=["Event payouts"], responses={200: s.PayoutResultSerializer, **s.ERRORS})
    def get(self, request, obligation_id):
        from django.conf import settings
        row = obligation(request, obligation_id, owner=True)
        return Response({"payee": payee_workflow.projection(payee_workflow.current(row)),
            "templates": getattr(settings, "EVENT_PAYOUT_ENABLED_TEMPLATES", ()),
            "disclosure_version": 1, "disclosure": "Routing details are used for this obligation and are visible to finance."})

    @extend_schema(tags=["Event payouts"], request=s.PayeeCommand, responses={200: s.PayoutResultSerializer, **s.ERRORS})
    def put(self, request, obligation_id):
        obligation(request, obligation_id, owner=True)
        return Response(payee_workflow.put(request=request, obligation_id=obligation_id, data=body(request, s.PayeeCommand)))

    @extend_schema(tags=["Event payouts"], request=s.Command, responses={200: s.PayoutResultSerializer, **s.ERRORS})
    def delete(self, request, obligation_id):
        data = body(request, s.Command)
        with command(request=request, obligation_id=obligation_id, data=data, action="payee.delete", owner=True) as ctx:
            if ctx.replay:
                return Response(ctx.replay)
            ctx.cas()
            row = payee_workflow.current(ctx.obligation, lock=True)
            if row:
                payee_workflow.purge_locked(ctx.obligation, row=row, now=timezone.now())
            ctx.obligation.version += 1
            ctx.obligation.save(update_fields=["version"])
            return Response(ctx.finish())


class MemberPayeeRevealView(PrivateView):
    @extend_schema(tags=["Event payouts"], request=s.RevealCommand, responses={200: s.RevealSerializer, **s.ERRORS})
    def post(self, request, obligation_id):
        obligation(request, obligation_id, owner=True)
        return Response(payee_workflow.reveal(request=request, obligation_id=obligation_id,
            data=body(request, s.RevealCommand), owner=True))
