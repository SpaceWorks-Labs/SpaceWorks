"""Private, scoped HTTP boundary. A read never creates a domain row."""
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework.exceptions import NotFound
from apps.accounts.staff_identity import is_person, is_platform
from apps.accounts import rbac
from apps.accounts.claim_sessions import claim_context
from apps.accounts.reauthentication import binding
from apps.events import event_authority
from apps.events.models import Event
from apps.events.staged_forms.http import PrivateView as BasePrivateView, body, paginated
from apps.makerspaces.guards import require_module
from apps.makerspaces.origin_scope import origin_scoped_makerspace_id
from apps.presence.guard import require_active_principal
from apps.payments.event_payouts.errors import require
from .transactions import authorize, check_origin


class PrivateView(BasePrivateView):
    def handle_exception(self, exc):
        from apps.payments.event_payouts.validation import PayoutValidationError
        from apps.payments.event_payouts.errors import PayoutError
        if isinstance(exc, PayoutValidationError) and exc.code == "budget_exhausted":
            exc = PayoutError(exc.code, status=409)
        return super().handle_exception(exc)


def check_read(request, event, *, owner=False):
    # Payee money is session-only (decision 219d): no API client, PAT or OAuth token reads it.
    require(getattr(request, "api_client", None) is None and getattr(request, "person_credential", None) is None
            and (is_person(request.user) or is_platform(request.user)), "full_session_required", status=403)
    binding(request)
    require(claim_context(request.user) is None, "full_session_required", status=403)
    require_active_principal(request.user, event.makerspace)
    require_module(event.makerspace, "events")
    from apps.makerspaces.platform import module_enabled
    require(module_enabled(event.makerspace, "event_reimbursements"), "reimbursement_unavailable")
    check_origin(request, event, owner=owner)
    return event


def member_event(request, pk, makerspace_id):
    event = get_object_or_404(Event.objects.select_related("makerspace"), pk=pk, makerspace_id=makerspace_id)
    check_read(request, event, owner=True)
    authorize(request.user, event, owner=True, request=request)
    return event


def admin_event(request, pk, *, finance_only=False):
    rows = Event.objects.select_related("makerspace")
    finance_rows = rbac.scope_by_action(request.user, rbac.Action.VIEW_FINANCE, rows)
    review_rows = event_authority.events_for(request.user, "review_reimbursements", rows)
    event = get_object_or_404(rows.filter(Q(pk__in=finance_rows.values("pk")) |
        Q(pk__in=review_rows.values("pk"))), pk=pk)
    check_read(request, event)
    finance = rbac.can(request.user, rbac.Action.VIEW_FINANCE, event.makerspace_id)
    require(finance or not finance_only, "finance_required", status=403)
    return event, finance
