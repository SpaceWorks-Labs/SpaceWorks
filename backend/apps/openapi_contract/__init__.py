"""The OpenAPI contract: what every documented operation must carry, and how it gets it.

`schema.SpaceWorksAutoSchema` is the project's DRF schema class. It fills the parts a
view does not state but its configuration already decides -- a security requirement from
its authentication and permission classes, error responses from its permission, throttle
and path parameters, an area tag from its path -- and stamps the deliberate exceptions
listed in `exceptions_*` (a write with no body, a provider-shaped free-form payload, an
empty acknowledgement). `check.contract_failures` is the guard over the generated schema;
`manage.py openapi_contract_check` runs it, and the CI `contracts` job fails on any finding.
"""
