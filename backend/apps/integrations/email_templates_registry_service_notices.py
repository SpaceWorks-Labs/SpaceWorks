"""Default requester copy for the machine-service queue notices (next, cancelled).

Type-neutral wording ("request", not "print request") because these two events cover
every machine type with a service queue. They live in the existing printing stream so
the requester template editor and mute controls apply unchanged.
"""
from django.utils.translation import gettext_noop

SERVICE_NOTICE_SUBJECTS = {
    "next": gettext_noop("Your makerspace request is next in the queue"),
    "cancelled": gettext_noop("Your makerspace request was cancelled"),
}

SERVICE_NOTICE_TEXT = {
    "next": gettext_noop("""Hello,

Your request "{{ print_request.title }}" is next among approved jobs.

Queue: {{ print_request.bucket.name }}
Makerspace: {{ print_request.bucket.makerspace.name }}

Staff start it when a compatible machine is free. Any start time shown is an estimate.
{% if status_url %}
Track your request: {{ status_url }}
{% endif %}
"""),
    "cancelled": gettext_noop("""Hello,

Your request "{{ print_request.title }}" was cancelled. Nothing was charged for it.

Queue: {{ print_request.bucket.name }}
Makerspace: {{ print_request.bucket.makerspace.name }}
{% if status_url %}
View your request: {{ status_url }}
{% endif %}
"""),
}

SERVICE_NOTICE_HTML = {
    "next": gettext_noop("""{% extends "email/base.html" %}

{% block body %}
  <p>Hello,</p>
  <p>Your request <strong>{{ print_request.title }}</strong> is next among approved jobs.</p>
  <p>Queue: {{ print_request.bucket.name }}<br>
  Makerspace: {{ print_request.bucket.makerspace.name }}</p>
  <p>Staff start it when a compatible machine is free. Any start time shown is an estimate.</p>
  {% if status_url %}
    <p>Track your request: <a href="{{ status_url }}">{{ status_url }}</a></p>
  {% endif %}
{% endblock %}
"""),
    "cancelled": gettext_noop("""{% extends "email/base.html" %}

{% block body %}
  <p>Hello,</p>
  <p>Your request <strong>{{ print_request.title }}</strong> was cancelled. Nothing was charged for it.</p>
  <p>Queue: {{ print_request.bucket.name }}<br>
  Makerspace: {{ print_request.bucket.makerspace.name }}</p>
  {% if status_url %}
    <p>View your request: <a href="{{ status_url }}">{{ status_url }}</a></p>
  {% endif %}
{% endblock %}
"""),
}
