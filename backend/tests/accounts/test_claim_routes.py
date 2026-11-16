import pytest
from django.urls import path
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet

from apps.accounts.claim_pre_auth_guard import (
    framework_lifecycle_methods,
    validate_claim_middleware,
)
from apps.accounts.claim_route_guard import (
    ClaimRouteConfigurationError,
    validate_claim_route_matrix,
)
from apps.accounts.claim_route_types import Allowed, AnonymousRead, ReadOnly, Refused, RowOwnership, ID
from apps.accounts.claim_routes import policy_for


class ReadView(APIView):
    def get(self, request):
        return Response({})


def policies(name, *methods):
    return {(name, method): AnonymousRead() for method in methods}


def assert_guard_fails(patterns, matrix, expected):
    with pytest.raises(ClaimRouteConfigurationError, match=expected):
        validate_claim_route_matrix(
            patterns,
            policies=matrix,
            require_all_active=False,
            check_middleware=False,
        )


def test_current_all_active_tree_has_a_complete_claim_matrix(settings):
    assert settings.TOMBSTONED_APPS == frozenset()
    # Exact route/method coverage and stale-entry rejection are enforced by the
    # guard. Keep both parent programmes visible without guessing a merged count.
    names = {row.view_name for row in validate_claim_route_matrix()}
    assert {"member-event-history", "member-my-usage", "auth-account-deletion",
            "auth-account-restore-email", "auth-logout-all"} <= names
    # Release 2 has 117 claimable programme names after session-only routes are
    # excluded (114 plus the three member routes the programme gained late). Reimbursements add
    # 27 member-surface names.
    from apps.accounts.programme_route_catalog import ROUTES
    from apps.apiclients.scope_registry_programme import SESSION_ONLY
    programme = {name for name, _methods, _target in ROUTES if name not in SESSION_ONLY}
    assert len(programme) == 117
    from apps.accounts.reimbursement_route_catalog import ROUTES as REIMBURSEMENT_ROUTES
    reimbursements = {name for name, _methods, _target, surface in REIMBURSEMENT_ROUTES if surface == "member"}
    assert len(reimbursements) == 27
    assert programme | reimbursements <= names


def test_event_history_and_speaker_claims_require_full_account_sessions():
    for method in ("GET", "HEAD"):
        policy = policy_for("member-event-history", method)
        assert isinstance(policy, Refused)
        assert policy.ownership is RowOwnership.MIXED_REFUSED
    assert isinstance(policy_for("member-event-speaker-claim", "POST"), Refused)
    for name in ("member-event-history", "member-event-speaker-claim"):
        assert isinstance(policy_for(name, "OPTIONS"), AnonymousRead)


@pytest.mark.parametrize("name", [
    "member-event-ticket", "member-event-ticket-png", "member-event-registration-calendar",
])
def test_event_tickets_have_explicit_claim_policies(name):
    for method in ("GET", "HEAD"):
        policy = policy_for(name, method)
        assert isinstance(policy, Refused)
        assert policy.ownership is RowOwnership.MIXED_REFUSED
    assert isinstance(policy_for(name, "OPTIONS"), AnonymousRead)


def test_organization_eligibility_has_explicit_account_only_claim_policies():
    from apps.accounts.claim_routes import CLAIM_ROUTES

    name = "public-event-organization-eligibility"
    for method in ("GET", "HEAD"):
        assert (name, method) in CLAIM_ROUTES
        assert isinstance(policy_for(name, method), Refused)
    assert isinstance(policy_for(name, "OPTIONS"), AnonymousRead)


def test_machine_metadata_and_inventory_watches_have_explicit_claim_policies():
    for name in ("public-machine-intake", "public-machine-details", "public-machine-detail"):
        for method in ("GET", "HEAD", "OPTIONS"):
            assert isinstance(policy_for(name, method), AnonymousRead)
    for method in ("POST", "DELETE"):
        policy = policy_for("v1:public-inventory-watch", method)
        assert isinstance(policy, Allowed)
        assert policy.tenant.value == "slug" and policy.audited
    assert isinstance(policy_for("v1:public-inventory-watch", "OPTIONS"), AnonymousRead)


def test_member_loan_renewal_has_an_audited_owner_scoped_claim_policy():
    policy = policy_for("hardware_requests:member-loan-renew", "POST")
    assert isinstance(policy, Allowed)
    assert policy.tenant == ID and policy.audited
    assert policy.ownership is RowOwnership.LOCAL_OWNER_ENFORCED
    assert isinstance(policy_for("hardware_requests:member-loan-renew", "OPTIONS"), AnonymousRead)


def test_unclassified_runtime_lookup_fails_closed_and_middleware_stays_out():
    assert isinstance(policy_for("future-member-route", "POST"), Refused)
    assert validate_claim_middleware() == []


def test_refused_route_must_run_the_claim_authenticator():
    class AuthenticationBypassView(APIView):
        authentication_classes = []

        def post(self, request):
            return Response({})

    patterns = [
        path(
            "api/v1/auth/bypass",
            AuthenticationBypassView.as_view(),
            name="auth-bypass",
        )
    ]
    matrix = {
        ("auth-bypass", "POST"): Refused("must refuse"),
        ("auth-bypass", "OPTIONS"): AnonymousRead(),
    }
    assert_guard_fails(
        patterns, matrix, "Refused claim route does not authenticate claim tokens"
    )


def test_an_unclassified_route_fails_the_guard():
    patterns = [path("api/v1/member/new", ReadView.as_view(), name="new-member-route")]
    assert_guard_fails(patterns, {}, "Unclassified claim route")


def test_adding_a_method_to_an_existing_route_fails_the_guard():
    class ExpandedView(ReadView):
        def post(self, request):
            return Response({})

    patterns = [path("api/v1/member/existing", ExpandedView.as_view(), name="existing")]
    matrix = policies("existing", "GET", "HEAD", "OPTIONS")
    assert_guard_fails(patterns, matrix, "existing POST")


def test_duplicate_qualified_name_fails_the_guard():
    patterns = [
        path("api/v1/member/one", ReadView.as_view(), name="duplicate"),
        path("api/v1/member/two", ReadView.as_view(), name="duplicate"),
    ]
    matrix = policies("duplicate", "GET", "HEAD", "OPTIONS")
    assert_guard_fails(patterns, matrix, "Duplicate qualified claim route name")


def test_unnamed_pattern_fails_the_guard():
    patterns = [path("api/v1/member/unnamed", ReadView.as_view())]
    assert_guard_fails(patterns, {}, "Unnamed claim-reachable URL pattern")


def test_dispatch_override_fails_the_guard():
    class DispatchingView(ReadView):
        def dispatch(self, request, *args, **kwargs):
            return super().dispatch(request, *args, **kwargs)

    patterns = [path("api/v1/member/dispatch", DispatchingView.as_view(), name="dispatching")]
    matrix = policies("dispatching", "GET", "HEAD", "OPTIONS")
    assert_guard_fails(patterns, matrix, "overrides pre-auth lifecycle hook dispatch")


def test_response_lifecycle_override_still_fails_the_guard():
    class FinalizingView(ReadView):
        def finalize_response(self, request, response, *args, **kwargs):
            return super().finalize_response(request, response, *args, **kwargs)

    patterns = [path("api/v1/member/finalize", FinalizingView.as_view(), name="finalizing")]
    assert_guard_fails(patterns, policies("finalizing", "GET", "HEAD", "OPTIONS"),
                       "overrides pre-auth lifecycle hook finalize_response")


def test_wildcard_policy_fails_the_guard():
    patterns = [path("api/v1/member/read", ReadView.as_view(), name="read")]
    matrix = {("read", "*"): ReadOnly(tenant=ID)}
    assert_guard_fails(patterns, matrix, "wildcards are forbidden")


def test_callback_wrapper_and_catch_all_fail_the_guard():
    def wrapper(callback):
        def wrapped(*args, **kwargs):
            return callback(*args, **kwargs)

        wrapped.cls = callback.cls
        wrapped.__wrapped__ = callback
        return wrapped

    wrapped = wrapper(ReadView.as_view())
    patterns = [path("api/v1/member/<path:rest>", wrapped, name="catch-all")]
    matrix = policies("catch-all", "GET", "HEAD", "OPTIONS")
    with pytest.raises(ClaimRouteConfigurationError) as exc:
        validate_claim_route_matrix(
            patterns, policies=matrix, require_all_active=False, check_middleware=False
        )
    assert "Catch-all" in str(exc.value)
    assert "callback wrapper" in str(exc.value)


def test_viewset_actions_are_inspected_per_pattern():
    class ExampleViewSet(ViewSet):
        def list(self, request):
            return Response({})

        def create(self, request):
            return Response({})

    callback = ExampleViewSet.as_view({"get": "list", "post": "create"})
    patterns = [path("api/v1/member/viewset", callback, name="viewset")]
    matrix = policies("viewset", "GET", "HEAD", "OPTIONS")
    assert_guard_fails(patterns, matrix, "viewset POST")


def test_installed_framework_graph_includes_every_pre_auth_hook_family():
    assert {
        "__init__",
        "as_view",
        "setup",
        "initialize_request",
        "initial",
        "dispatch",
        "http_method_not_allowed",
        "get_parser_context",
        "get_parsers",
        "get_authenticators",
        "perform_authentication",
        "perform_content_negotiation",
        "determine_version",
        "get_permissions",
        "get_throttles",
    } <= framework_lifecycle_methods()
