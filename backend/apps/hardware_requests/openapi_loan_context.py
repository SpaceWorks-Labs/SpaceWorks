"""Schema-only contracts for strict JSON loan-context commands."""
from apps.openapi_contract.schema import SpaceWorksAutoSchema

_SAFE_ID = {"type": "integer", "minimum": 1, "maximum": 9007199254740991}
_ID_PARAMETERS = frozenset({
    "makerspace_id", "request_id", "loan_id", "intended_event_id", "intended_booking_id",
})


class LoanContextSchema(SpaceWorksAutoSchema):
    def _get_parameters(self):
        return [dict(parameter, schema=dict(_SAFE_ID))
                if parameter["name"] in _ID_PARAMETERS else parameter
                for parameter in super()._get_parameters()]

    def _get_request_body(self, direction="request"):
        # Spectacular normally omits DELETE bodies; context removal requires CAS.
        if self.method == "DELETE":
            component = self.resolve_serializer(self.get_request_serializer(), direction)
            return {"required": True, "content": {
                "application/json": {"schema": component.ref},
            }}
        body = super()._get_request_body(direction)
        if body and "application/json" in body["content"]:
            # These strict integer fields cannot accept form-encoded strings.
            return dict(body, content={"application/json": body["content"]["application/json"]})
        return body
