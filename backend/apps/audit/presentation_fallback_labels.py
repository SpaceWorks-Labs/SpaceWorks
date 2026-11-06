"""Readable labels for reviewed audit actions that carry no catalogue entry (R4 audit B).

An action routed through a wrapper (``record_auth_event``, ``events/services_core``'s
``audit``, the devices event table, ...) cannot hold a catalogue entry: the drift guard
only admits literal call sites. Those actions used to render as "Unrecognized audit
action" in every staff audit view although they are reviewed. They now get a label built
from the action key. Their metadata stays withheld exactly as before -- this changes the
label only, never what a staff reader may see of ``meta``.

An action that is neither under the dynamic deny policy nor listed below still reads
"Unrecognized audit action": an unreviewed action never gets a friendly label.
"""

# Emitted through wrappers the deny policy does not name (accounts/services_registration,
# accounts/services_phone and views_phone via record_auth_event; events/answer_derivations
# via its audit helper; the WhatsApp template admin via AuditedControlChangeMixin).
LABEL_ONLY_ACTIONS = frozenset((
    "events.answers.date_review_requested",
    "events.answers.date_reviewed",
    "events.answers.draft_source_deleted",
    "events.answers.draft_source_erased",
    "events.answers.locked",
    "events.answers.reopened",
    "events.answers.source_saved",
    "member.email_verification_failed",
    "member.email_verification_refused_walk_in",
    "member.email_verification_requested",
    "member.email_verified",
    "member.phone_link_failed",
    "member.phone_link_refused_anonymous_requester",
    "member.phone_link_refused_walk_in",
    "member.phone_link_requested",
    "member.phone_unlinked",
    "member.phone_verified",
    "member.signup_expired",
    "member.signup_requested",
    "platform.whatsapp_template_updated",
))


def humanized_label(action):
    """``event.registration_approved`` -> ``Event registration approved``."""
    words = str(action).replace(".", " ").replace("_", " ").split()
    text = " ".join(words)
    return text[:1].upper() + text[1:]
