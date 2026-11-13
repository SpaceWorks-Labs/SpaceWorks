"""Review fix: an actor whose account row vanished mid-request is a 404, never a 500."""
import pytest
from django.http import Http404
from rest_framework.exceptions import NotFound

from apps.accounts.models import User
from apps.hardware_requests.loan_context_access import authorized_request_queryset, require_request_actor
from apps.inventory import equipment_kit_services, equipment_use_service
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


def _ghost():
    return User(pk=987654321, username="ghost")  # authenticated instance, no row


def test_loan_context_access_refuses_a_vanished_actor():
    space = make_space("ghost-space")
    assert not authorized_request_queryset(_ghost(), space).exists()
    with pytest.raises(NotFound):
        require_request_actor(_ghost(), object())


def test_kit_template_mutations_refuse_a_vanished_actor():
    space = make_space("ghost-kits")
    with pytest.raises(Http404):
        equipment_kit_services.create_template(actor=_ghost(), makerspace_id=space.pk, name="Kit", lines=[])
    with pytest.raises(Http404):
        equipment_kit_services._locked_template(_ghost(), space.pk, 1, 1)


def test_linked_use_inner_refuses_a_vanished_actor():
    space = make_space("ghost-use")
    with pytest.raises(Http404):
        equipment_use_service._linked_use(actor=_ghost(), makerspace_id=space.pk, product_id=1, operation_id="op",
                                          source_kind="plan", source_id=1, quantity=1, note="")
