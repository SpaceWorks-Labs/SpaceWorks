"""Batch source-policy parity; run only in the admitted isolated suite."""
import pytest
from apps.hardware_requests.loan_context_access import authorized_request_queryset, require_request_actor
from apps.hardware_requests.models import PublicToolLoan
from tests.test_request_workflow import make_space, make_member, make_product, make_hardware_request

pytestmark = pytest.mark.django_db


def test_batch_policy_matches_instance_policy_for_all_source_kinds():
    space = make_space("context-source-policy")
    space.enabled_features = list(set(space.enabled_features or []) | {"loans.enabled", "inventory.self_checkout"})
    space.save(update_fields=["enabled_features"])
    manager = make_member("context-source-manager", space)
    product = make_product(space)
    requests = [make_hardware_request(space, product) for _ in range(3)]
    for req, source in zip(requests[1:], [PublicToolLoan.Source.PUBLIC_SELF_CHECKOUT, PublicToolLoan.Source.ADMIN_DIRECT]):
        PublicToolLoan.objects.create(makerspace=space, request=req, requester=req.requester,
            source=source, target_type="direct", target_id=req.pk, target_label="tool")
    assert {row.pk for row in authorized_request_queryset(manager, space)} == {row.pk for row in requests}
    for request in requests:
        assert require_request_actor(manager, request).pk == manager.pk
