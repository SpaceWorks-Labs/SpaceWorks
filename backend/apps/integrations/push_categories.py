"""Watch-friendly native push presentation (#116, #128 C-27): channel, thread and safe actions.

Push is not a decision surface, exactly like chat. A push action may only OPEN the app or
call the recipient's own authenticated inbox routes (`POST .../{id}/read`, and
`.../{id}/snooze` while `notifications.inbox_snooze` is on). No action approves, rejects,
pays, refunds, issues, returns or hands anything over, and money and evidence notices carry
no action buttons at all.

Two independent wire values come out of this registry:

* `channel` -- the topic. Android uses it as the notification `channel_id` (people mute a
  topic per channel); iOS uses it for the per-feature subthread where one is useful.
* `category` -- the action set. iOS sends it as `aps.category` (the app registers one
  `UNNotificationCategory` per identifier below); Android apps read it from `data.category`.
  It is omitted for money/evidence notices, unknown events, and whenever the space's
  `mobile.watch_actions` switch is off.
"""

OPEN, MARK_SEEN, SNOOZE = "open", "mark_seen", "snooze"
SAFE_ACTIONS = (OPEN, MARK_SEEN, SNOOZE)

# Wire category identifier -> the action buttons, in display order. Fixed: apps register
# these at launch, so an identifier never changes meaning.
CATEGORIES = {
    "sw.open": (OPEN,),
    "sw.inbox": (OPEN, MARK_SEEN),
    "sw.inbox.snooze": (OPEN, MARK_SEEN, SNOOZE),
}

# Android channel id -> (channel name, iOS subthread). A subthread splits the busy topic
# out of the space's stack: an event day can send dozens of notices.
CHANNELS = {
    "sw_loans": ("Loans", False),
    "sw_bookings": ("Bookings", False),
    "sw_events": ("Events", True),
    "sw_machines": ("Machines and jobs", False),
    "sw_membership": ("Membership", False),
    "sw_money": ("Payments", False),
    "sw_space": ("Space operations", False),
}

# Every notification feature (`NotificationFeature`) has exactly one channel.
FEATURE_CHANNELS = {
    "hardware_requests": "sw_loans",
    "bookings": "sw_bookings",
    "events": "sw_events",
    "printing": "sw_machines",
    "maintenance": "sw_machines",
    "devices": "sw_machines",
    "members": "sw_membership",
    "certifications": "sw_membership",
    "presence": "sw_membership",
    "payments": "sw_money",
    "stock": "sw_space",
    "api_access": "sw_space",
}

# Explicitly NO actions (#116). Money: every payments event plus the charge notices other
# features raise. Evidence: the handover notices whose record carries scans and photos.
MONEY_FEATURES = frozenset({"payments"})
MONEY_EVENTS = {
    "hardware_requests": frozenset({"deposit_raised", "late_fee_raised", "rental_raised",
                                    "damage_charged", "lost_charged", "fees_waived"}),
    "members": frozenset({"renewal_due", "renewal_failed", "awaiting_payment", "payment_due",
                          "renewed"}),
}
EVIDENCE_EVENTS = {
    "hardware_requests": frozenset({"issued", "partially_returned", "returned",
                                    "closed_with_issue", "problem_report.filed"}),
    "printing": frozenset({"collected"}),
}
# Fail closed for events a later lane appends to the catalogue without classifying them here.
_UNSAFE_TOKENS = ("charge", "fee", "pay", "refund", "deposit", "price", "invoice", "dispute",
                  "settle", "claim", "receipt", "evidence", "photo", "handover", "handout")


def is_money(feature, event):
    return feature in MONEY_FEATURES or event in MONEY_EVENTS.get(feature, ())


def actionable(feature, event):
    """True only for a catalogued event that is neither money nor evidence."""
    from apps.integrations.notification_catalog import FEATURE_EVENTS

    if feature not in FEATURE_CHANNELS or event not in FEATURE_EVENTS.get(feature, ()):
        return False
    if is_money(feature, event) or event in EVIDENCE_EVENTS.get(feature, ()):
        return False
    return not any(token in event for token in _UNSAFE_TOKENS)


def channel_for(feature, event):
    if is_money(feature, event):
        return "sw_money"
    return FEATURE_CHANNELS.get(feature, "sw_space")


def thread_id(makerspace_id, channel):
    """iOS `thread-id`: the space, plus the topic where a subthread is useful."""
    subthread = CHANNELS.get(channel, ("", False))[1]
    return f"{makerspace_id}.{channel[3:]}" if subthread else str(makerspace_id)


def category_for(makerspace, feature, event, *, has_inbox_row):
    """The action set for this notice, or None (no buttons)."""
    from apps.makerspaces.platform import feature_enabled

    if makerspace is None or not actionable(feature, event):
        return None
    if not feature_enabled(makerspace, "mobile.watch_actions"):
        return None
    if not has_inbox_row:
        return "sw.open"
    return "sw.inbox.snooze" if feature_enabled(makerspace, "notifications.inbox_snooze") else "sw.inbox"
