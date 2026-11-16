"""Exercise generated context contracts rather than serializer-name guesses."""
from copy import deepcopy

import pytest
from django.urls import path
from drf_spectacular.drainage import get_override
from drf_spectacular.generators import SchemaGenerator
from rest_framework.exceptions import ValidationError

from apps.bookings.views_loan_context import BookingLoanContextView
from apps.events.serializers_loan_context import SafeInteger
from apps.events.views_loan_context import EventLoanContextView

MAX_SAFE = 9007199254740991


@pytest.fixture(scope="module")
def context_schema():
    patterns = []
    for domain, view in [("event", EventLoanContextView), ("booking", BookingLoanContextView)]:
        for kind, key in [("requests", "request_id"), ("direct-loans", "loan_id")]:
            patterns.append(path(
                f"api/v1/admin/makerspace/<int:makerspace_id>/{kind}/<int:{key}>/{domain}-context",
                view.as_view(), name=f"context-schema-{domain}-{kind}",
            ))
    return SchemaGenerator(patterns=patterns).get_schema(public=True)


@pytest.mark.parametrize("domain", ["event", "booking"])
@pytest.mark.parametrize("kind,key", [("requests", "request_id"), ("direct-loans", "loan_id")])
def test_delete_documents_required_json_cas_and_exact_safe_parameters(context_schema, domain, kind, key):
    route = f"/api/v1/admin/makerspace/{{makerspace_id}}/{kind}/{{{key}}}/{domain}-context"
    operation = context_schema["paths"][route]["delete"]
    body = operation["requestBody"]
    assert body["required"] is True
    assert set(body["content"]) == {"application/json"}
    reference = body["content"]["application/json"]["schema"]["$ref"].split("/")[-1]
    assert reference == f"{domain.title()}LoanContextCAS"
    component = context_schema["components"]["schemas"][reference]
    assert set(component["required"]) == {"expected_generation", "expected_revision"}
    assert set(component["properties"]) == {"expected_generation", "expected_revision"}
    assert component["properties"]["expected_revision"]["minimum"] == 0
    assert component["properties"]["expected_revision"]["maximum"] == MAX_SAFE
    for parameter in operation["parameters"]:
        assert parameter["schema"]["minimum"] == 1
        assert parameter["schema"]["maximum"] == MAX_SAFE
    put = context_schema["paths"][route]["put"]["requestBody"]
    assert set(put["content"]) == {"application/json"}


@pytest.mark.parametrize("component,field", [
    ("EventContextPut", "event_id"), ("EventContextPut", "participant_registration_id"),
    ("EventContextResponse", "event_id"), ("EventContextResponse", "participant_registration_id"),
    ("BookingContextPut", "booking_id"), ("BookingContextResponse", "booking_id"),
])
def test_generated_positive_ids_preserve_the_actual_safe_integer_boundary(context_schema, component, field):
    value = context_schema["components"]["schemas"][component]["properties"][field]
    assert value["minimum"] == 1
    assert value["maximum"] == MAX_SAFE
    assert SafeInteger(minimum=1).to_internal_value(1) == 1
    for invalid in [0, True, MAX_SAFE + 1]:
        with pytest.raises(ValidationError):
            SafeInteger(minimum=1).to_internal_value(invalid)


def test_instance_annotations_and_deepcopies_do_not_share_bounds():
    revision, identifier = SafeInteger(), SafeInteger(minimum=1)
    assert get_override(revision, "field")["minimum"] == 0
    assert get_override(identifier, "field")["minimum"] == 1
    assert get_override(deepcopy(identifier), "field")["minimum"] == 1
    assert get_override(revision, "field")["minimum"] == 0
