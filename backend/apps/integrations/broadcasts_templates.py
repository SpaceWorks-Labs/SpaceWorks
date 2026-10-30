"""Bounded placeholders use the existing Django email renderer, with data-only context."""

import re
from rest_framework.exceptions import ValidationError
from .email_templates import _render_strings


def validate_strings(subject, body, allowed):
    if not subject.strip() or len(subject) > 200 or "\n" in subject or "\r" in subject:
        raise ValidationError({"subject": "Use a subject of 1-200 characters on one line."})
    if not body.strip() or len(body) > 10000:
        raise ValidationError({"body": "Use a message of 1-10000 characters."})
    for value in (subject, body):
        tokens = re.findall(r"{{\s*([a-z_]+)\s*}}", value)
        remainder = re.sub(r"{{\s*[a-z_]+\s*}}", "", value)
        if set(tokens) - set(allowed) or any(token in remainder for token in ("{{", "}}", "{%", "%}", "{#", "#}")):
            raise ValidationError({"body": f"Use only these placeholders: {', '.join(allowed)}."})


def render(subject, body, context):
    validate_strings(subject, body, context)
    rendered = _render_strings(subject, body, "", context)
    rendered["subject"] = " ".join(rendered["subject"].splitlines())
    return rendered


def _template(key, label, description, subject, body, statuses, attendance="any", design="classic"):
    return {"key": key, "label": label, "description": description, "subject": subject, "body": body,
            "statuses": list(statuses), "attendance": attendance, "design": design}


# Original Space Works copy. A template only prefills subject, body, audience and design;
# the organiser still previews and confirms the live audience before anything is sent.
EVENT_STARTER_TEMPLATES = (
    _template("welcome", "Welcome aboard", "Confirmed guests, right after they sign up.",
              "You're in for {{ event_title }}",
              "Hi {{ name }},\n\nYour place at **{{ event_title }}** is confirmed. Keep your ticket handy: "
              "{{ ticket_url }}\n\nWe'll share anything you need before {{ event_date }}.",
              ("registered",)),
    _template("week_before", "One week to go", "Confirmed guests, a week ahead.",
              "{{ event_title }} is one week away",
              "Hi {{ name }},\n\n{{ event_title }} is coming up on {{ event_date }} at {{ event_location }}.\n\n"
              "- Check the schedule: {{ schedule_url }}\n- Bring your ticket: {{ ticket_url }}",
              ("registered",), "not_attended"),
    _template("day_before", "See you tomorrow", "Confirmed guests, the day before.",
              "See you tomorrow at {{ event_title }}",
              "Hi {{ name }},\n\nWe're getting the space ready. {{ event_title }} starts {{ event_date }} "
              "at {{ event_location }}.\n\nYour ticket: {{ ticket_url }}",
              ("registered",), "not_attended", "accent_band"),
    _template("doors_open", "Doors are open", "Confirmed guests, on the day.",
              "Doors are open for {{ event_title }}",
              "Hi {{ name }},\n\nWe're open and ready for you. Show your ticket at the desk: {{ ticket_url }}",
              ("registered",), "not_attended", "bold"),
    _template("logistics", "Getting here", "Confirmed guests: venue and travel notes.",
              "Getting to {{ event_title }}",
              "Hi {{ name }},\n\nHere is how to find us at {{ event_location }}.\n\n- Arrive a few minutes "
              "early to check in\n- Event page: {{ event_url }}",
              ("registered",), "not_attended"),
    _template("schedule", "Schedule is live", "Confirmed and waitlisted guests.",
              "The schedule for {{ event_title }} is live",
              "Hi {{ name }},\n\nThe running order for {{ event_title }} is ready. Plan your day: "
              "{{ schedule_url }}",
              ("registered", "waitlisted"), "any", "photo_header"),
    _template("time_change", "Time change", "Everyone still expecting to come.",
              "Updated time for {{ event_title }}",
              "Hi {{ name }},\n\nWe've moved {{ event_title }}. It now starts {{ event_date }} at "
              "{{ event_location }}.\n\nIf the new time doesn't suit you, you can cancel from your ticket: "
              "{{ ticket_url }}",
              ("registered", "waitlisted", "pending_approval"), "not_attended"),
    _template("waitlist", "Still on the waitlist", "Waitlisted guests.",
              "You're on the waitlist for {{ event_title }}",
              "Hi {{ name }},\n\nYou're still on the waitlist for {{ event_title }}. If a place opens up "
              "you'll hear from us straight away.",
              ("waitlisted",)),
    _template("reviewing", "We're reviewing", "Guests waiting for approval.",
              "We're reviewing your sign-up for {{ event_title }}",
              "Hi {{ name }},\n\nThanks for signing up for {{ event_title }}. The organisers at "
              "{{ organization }} are reviewing requests and will reply soon.",
              ("pending_approval",), "any", "minimal"),
    _template("thanks", "Thanks for coming", "Guests who checked in.",
              "Thank you for joining {{ event_title }}",
              "Hi {{ name }},\n\nThank you for making {{ event_title }} what it was. We hope you left with "
              "something new to build.\n\n{{ organization }}",
              ("attended",), "attended", "letter"),
    _template("missed_you", "Sorry we missed you", "Confirmed guests who didn't check in.",
              "We missed you at {{ event_title }}",
              "Hi {{ name }},\n\nWe kept a seat for you at {{ event_title }}. Keep an eye on "
              "{{ organization }} for the next one: {{ event_url }}",
              ("registered",), "not_attended", "letter"),
    _template("feedback", "Share your feedback", "Guests who checked in.",
              "How was {{ event_title }}?",
              "Hi {{ name }},\n\nTwo minutes of feedback helps us plan the next one: {{ feedback_url }}",
              ("attended",), "attended", "accent_band"),
    _template("next_steps", "What's next", "Guests who checked in.",
              "After {{ event_title }}: what's next",
              "Hi {{ name }},\n\nThanks again for coming to {{ event_title }}.\n\n- Notes and updates: "
              "{{ event_url }}\n- Tell us how it went: {{ feedback_url }}",
              ("attended",), "attended", "minimal"),
)
