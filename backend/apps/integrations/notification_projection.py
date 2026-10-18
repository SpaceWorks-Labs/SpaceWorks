"""Scalar template variables shared by the workflow envelope adapters.

The reviewed messaging catalogue is the allow-list. Email contexts may contain
contacts, notes and bearer links; none of those are copied into envelope JSON.
"""
from apps.integrations.messaging.projections import PROJECTION_KEYS, project_context


def addressed_context(space, feature, event, audience, template_context=None):
    audience = "member" if audience == "requester" else audience
    if (feature, event, audience) not in PROJECTION_KEYS:
        return {}
    values = {**(template_context or {}), "makerspace": {"name": space.name}}
    return project_context(feature, event, audience, values)
