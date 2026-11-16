"""Deployment-global uniqueness for the decision 343 machine-type documents.

A type document's object key is deployment-global: kept unless it collides on the target, where a fresh
key in the target space's machine prefix is generated (as for machine documents). Every other constraint
of the per-type setup, consumable-profile and template rows includes the makerspace, so it carries no
deployment-global risk.
"""

from .unique_value_generators import machine_document_key
from .unique_values_policy import PRESERVE, _policy

RULES = {
    ("machines.MachineTypeDocument", "field:object_key"): _policy(
        PRESERVE, "Keep the archived type-document key unless it collides on the target.", field="object_key",
        generator=machine_document_key),
}
