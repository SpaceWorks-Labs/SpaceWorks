from django.utils.translation import gettext_noop
HARDWARE_REQUESTER_DEFAULTS = {
    "request_received": {
        "subject": gettext_noop("{{ makerspace.name }} request received"),
        "text": (
            gettext_noop("Your makerspace request #{{ request.id }} was received.\n\n"
            "Status: {{ request.status }}\n"
            "Use your email or phone on the public request page to check status.")
        ),
    },
    "request_accepted": {
        "subject": gettext_noop("{{ makerspace.name }} request approved"),
        "text": (
            gettext_noop("Your makerspace request #{{ request.id }} has been approved."
            "{% if request.return_due_at %}\n\nReturn by: {{ request.return_due_at }}{% endif %}")
        ),
    },
    "request_rejected": {
        "subject": gettext_noop("{{ makerspace.name }} request rejected"),
        "text": (
            gettext_noop("Your makerspace request #{{ request.id }} was rejected."
            "{% if request.rejection_reason %}\n\nReason: {{ request.rejection_reason }}{% endif %}")
        ),
    },
    "request_issued": {
        "subject": gettext_noop("{{ makerspace.name }} request issued"),
        "text": (
            gettext_noop("Your approved makerspace request #{{ request.id }} has been handed out."
            "{% if request.return_due_at %}\n\nReturn by: {{ request.return_due_at }}{% endif %}")
        ),
    },
    "request_returned": {
        "subject": gettext_noop("{{ makerspace.name }} request returned"),
        "text": gettext_noop(
            "{% if request.status == 'partially_returned' %}We recorded a partial return for your makerspace "
            "request #{{ request.id }}. Some items are still out; return them by the due date."
            "{% elif request.status == 'closed_with_issue' %}Your makerspace request #{{ request.id }} was "
            "closed with an issue (an item was lost or damaged). The space will contact you about next steps."
            "{% else %}Your makerspace request #{{ request.id }} has been returned and closed.{% endif %}"
        ),
    },
    "return_reminder": {
        "subject": gettext_noop("{{ makerspace.name }} return reminder"),
        "text": (
            gettext_noop("Your makerspace request #{{ request.id }} is due for return."
            "{% if request.return_due_at %}\n\nReturn due: {{ request.return_due_at }}{% endif %}")
        ),
    },
}

HARDWARE_STAFF_DEFAULTS = {
    "submitted": {
        "subject": gettext_noop("{{ makerspace.name }} hardware request #{{ request.id }} submitted"),
        "text": gettext_noop("A new hardware request needs review.\n\n{{ staff_summary }}"),
    },
    "accepted": {
        "subject": gettext_noop("{{ makerspace.name }} hardware request #{{ request.id }} accepted"),
        "text": gettext_noop("Hardware request #{{ request.id }} was accepted.\n\n{{ staff_summary }}"),
    },
    "rejected": {
        "subject": gettext_noop("{{ makerspace.name }} hardware request #{{ request.id }} rejected"),
        "text": gettext_noop("Hardware request #{{ request.id }} was rejected.\n\n{{ staff_summary }}"),
    },
    "issued": {
        "subject": gettext_noop("{{ makerspace.name }} hardware request #{{ request.id }} issued"),
        "text": gettext_noop("Hardware request #{{ request.id }} was issued.\n\n{{ staff_summary }}"),
    },
    "partially_returned": {
        "subject": gettext_noop("{{ makerspace.name }} hardware request #{{ request.id }} partially returned"),
        "text": gettext_noop("Hardware request #{{ request.id }} was partially returned.\n\n{{ staff_summary }}"),
    },
    "returned": {
        "subject": gettext_noop("{{ makerspace.name }} hardware request #{{ request.id }} returned"),
        "text": gettext_noop("Hardware request #{{ request.id }} was fully returned and closed.\n\n{{ staff_summary }}"),
    },
    "closed_with_issue": {
        "subject": gettext_noop("{{ makerspace.name }} hardware request #{{ request.id }} closed with issue"),
        "text": gettext_noop("Hardware request #{{ request.id }} was closed with damaged or missing items.\n\n{{ staff_summary }}"),
    },
    "return_reminder": {
        "subject": gettext_noop("{{ makerspace.name }} hardware request #{{ request.id }} return reminder"),
        "text": gettext_noop("Hardware request #{{ request.id }} is due for return.\n\n{{ staff_summary }}"),
    },
}

PRINTING_REQUESTER_SUBJECTS = {
    "submitted": gettext_noop("We received your makerspace print request"),
    "accepted": gettext_noop("Your makerspace print request was accepted"),
    "started": gettext_noop("Your makerspace print request is now printing"),
    "rejected": gettext_noop("Your makerspace print request was rejected"),
    "completed": gettext_noop("Your makerspace print request is ready to collect"),
}

PRINTING_REQUESTER_TEXT = {
    "submitted": gettext_noop("""Hello,

We've received your print request "{{ print_request.title }}".

Bucket: {{ print_request.bucket.name }}
Makerspace: {{ print_request.bucket.makerspace.name }}

We'll email you again when its status changes. You can also track it with your request link.
{% if status_url %}
Track your request: {{ status_url }}
{% endif %}
Tracking token: {{ public_token }}
"""),
    "accepted": gettext_noop("""Hello {{ print_request.requester.username }},

Your print request "{{ print_request.title }}" has been accepted.

Bucket: {{ print_request.bucket.name }}
Makerspace: {{ print_request.bucket.makerspace.name }}
{% if status_url %}
Track your request: {{ status_url }}
{% endif %}
Tracking token: {{ public_token }}
"""),
    "started": gettext_noop("""Hello,

Your print request "{{ print_request.title }}" is now printing.

Bucket: {{ print_request.bucket.name }}
Makerspace: {{ print_request.bucket.makerspace.name }}

We'll let you know when it's ready to collect.
{% if status_url %}
Track your request: {{ status_url }}
{% endif %}
Tracking token: {{ public_token }}
"""),
    "rejected": gettext_noop("""Hello {{ print_request.requester.username }},

Your print request "{{ print_request.title }}" has been rejected.

Reason: {{ print_request.reason }}

Bucket: {{ print_request.bucket.name }}
Makerspace: {{ print_request.bucket.makerspace.name }}
{% if status_url %}
Track your request: {{ status_url }}
{% endif %}
Tracking token: {{ public_token }}
"""),
    "completed": gettext_noop("""Hello {{ print_request.requester.username }},

Your print request "{{ print_request.title }}" is complete.

Bucket: {{ print_request.bucket.name }}
Makerspace: {{ print_request.bucket.makerspace.name }}
{% if status_url %}
Track your request: {{ status_url }}
{% endif %}
Tracking token: {{ public_token }}
"""),
}

PRINTING_REQUESTER_HTML = {
    "submitted": gettext_noop("""{% extends "email/base.html" %}

{% block body %}
  <p>Hello,</p>
  <p>We've received your print request <strong>{{ print_request.title }}</strong>.</p>
  <p>Bucket: {{ print_request.bucket.name }}<br>
  Makerspace: {{ print_request.bucket.makerspace.name }}</p>
  <p>We'll email you again when its status changes. You can also track it with your request link.</p>
  {% if status_url %}
    <p>Track your request: <a href="{{ status_url }}">{{ status_url }}</a></p>
  {% endif %}
  <p>Tracking token: <strong>{{ public_token }}</strong></p>
{% endblock %}
"""),
    "accepted": gettext_noop("""{% extends "email/base.html" %}

{% block body %}
  <p>Hello {{ print_request.requester.username }},</p>
  <p>Your print request <strong>{{ print_request.title }}</strong> has been accepted.</p>
  <p>Bucket: {{ print_request.bucket.name }}<br>
  Makerspace: {{ print_request.bucket.makerspace.name }}</p>
  {% if status_url %}
    <p>Track your request: <a href="{{ status_url }}">{{ status_url }}</a></p>
  {% endif %}
  <p>Tracking token: <strong>{{ public_token }}</strong></p>
{% endblock %}
"""),
    "started": gettext_noop("""{% extends "email/base.html" %}

{% block body %}
  <p>Hello,</p>
  <p>Your print request <strong>{{ print_request.title }}</strong> is now printing.</p>
  <p>Bucket: {{ print_request.bucket.name }}<br>
  Makerspace: {{ print_request.bucket.makerspace.name }}</p>
  <p>We'll let you know when it's ready to collect.</p>
  {% if status_url %}
    <p>Track your request: <a href="{{ status_url }}">{{ status_url }}</a></p>
  {% endif %}
  <p>Tracking token: <strong>{{ public_token }}</strong></p>
{% endblock %}
"""),
    "rejected": gettext_noop("""{% extends "email/base.html" %}

{% block body %}
  <p>Hello {{ print_request.requester.username }},</p>
  <p>Your print request <strong>{{ print_request.title }}</strong> has been rejected.</p>
  <p>Reason: {{ print_request.reason }}</p>
  <p>Bucket: {{ print_request.bucket.name }}<br>
  Makerspace: {{ print_request.bucket.makerspace.name }}</p>
  {% if status_url %}
    <p>Track your request: <a href="{{ status_url }}">{{ status_url }}</a></p>
  {% endif %}
  <p>Tracking token: <strong>{{ public_token }}</strong></p>
{% endblock %}
"""),
    "completed": gettext_noop("""{% extends "email/base.html" %}

{% block body %}
  <p>Hello {{ print_request.requester.username }},</p>
  <p>Your print request <strong>{{ print_request.title }}</strong> is complete.</p>
  <p>Bucket: {{ print_request.bucket.name }}<br>
  Makerspace: {{ print_request.bucket.makerspace.name }}</p>
  {% if status_url %}
    <p>Track your request: <a href="{{ status_url }}">{{ status_url }}</a></p>
  {% endif %}
  <p>Tracking token: <strong>{{ public_token }}</strong></p>
{% endblock %}
"""),
}

PRINTING_STAFF_SUBJECTS = {
    "submitted": gettext_noop("{{ makerspace.name }} print request #{{ print_request.id }} submitted"),
    "accepted": gettext_noop("{{ makerspace.name }} print request #{{ print_request.id }} accepted"),
    "started": gettext_noop("{{ makerspace.name }} print request #{{ print_request.id }} started"),
    "completed": gettext_noop("{{ makerspace.name }} print request #{{ print_request.id }} completed"),
    "rejected": gettext_noop("{{ makerspace.name }} print request #{{ print_request.id }} rejected"),
    "failed": gettext_noop("{{ makerspace.name }} print request #{{ print_request.id }} failed"),
    "collected": gettext_noop("{{ makerspace.name }} print request #{{ print_request.id }} collected"),
    "reprinted": gettext_noop("{{ makerspace.name }} reprint request #{{ print_request.id }} accepted"),
}

PRINTING_STAFF_TEXT = gettext_noop("""Print request #{{ print_request.id }} {{ event }}.

Status: {{ print_request.status }}
Title: {{ print_request.title }}
Requester: {% firstof print_request.requester_name print_request.requester.username %}{% if print_request.contact_email %}
Email: {{ print_request.contact_email }}{% elif print_request.requester.email %}
Email: {{ print_request.requester.email }}{% endif %}{% if print_request.contact_phone %}
Phone: {{ print_request.contact_phone }}{% endif %}{% if print_request.material %}
Material: {{ print_request.material }}{% endif %}{% if print_request.color %}
Color: {{ print_request.color }}{% endif %}
Quantity: {{ print_request.quantity }}{% if print_request.reason %}
Reason: {{ print_request.reason }}{% endif %}{% if print_request.reprint_of_id %}
Reprint of: #{{ print_request.reprint_of_id }}{% endif %}""")
