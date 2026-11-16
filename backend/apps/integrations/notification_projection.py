"""Scalar template variables shared by the workflow envelope adapters.

The reviewed messaging catalogue is the allow-list. Email contexts may contain
contacts, notes and bearer links; none of those are copied into envelope JSON.
"""
from apps.integrations.messaging.projections import PROJECTION_KEYS, project_context
from .notification_catalog_events_programme import MENTOR_HELP_PERSONAL_EVENT


def addressed_context(space, feature, event, audience, template_context=None):
    audience = "member" if audience == "requester" else audience
    if (feature, event, audience) not in PROJECTION_KEYS:
        return {}
    values = {**(template_context or {}), "makerspace": {"name": space.name}}
    return project_context(feature, event, audience, values)


def whatsapp_template_context(envelope):
    if envelope.event != MENTOR_HELP_PERSONAL_EVENT:
        return envelope.context
    # Bind only approved public scalars even for legacy template rows created without a feature.
    allowed = PROJECTION_KEYS[("events", MENTOR_HELP_PERSONAL_EVENT, "member")]
    return {key: envelope.context[key] for key in allowed if key in envelope.context}
