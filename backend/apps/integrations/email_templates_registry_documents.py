"""Payer-only document notices shared by email and personal chat delivery."""
from .email_templates_registry_helpers import EmailTemplateRegistryEntry, bag

DOCUMENT_LABELS = {"receipt": "Receipt", "credit_note": "Credit note", "bill": "Bill"}


def build_entries():
    fields = [
        {"name": "document.number", "description": "Issued document number."},
        {"name": "document.kind", "description": "Receipt, credit_note or bill."},
        {"name": "document.label", "description": "Document title."},
        {"name": "document.amount", "description": "Gross document amount."},
        {"name": "document.currency", "description": "Document currency."},
        {"name": "download_url", "description": "Authenticated payment navigation; never a bearer URL."},
        {"name": "makerspace.name", "description": "Makerspace name."},
    ]
    return {("payments", "requester", "document_" + kind): EmailTemplateRegistryEntry(
        label=label + " issued", description=f"Personal payer notice with the {label.lower()} PDF attached.",
        fields=fields, default_subject="{{ document.label }} {{ document.number }}",
        default_text="Your {{ document.label|lower }} {{ document.number }} is available.\n"
                     "{{ document.currency }} {{ document.amount }}\n"
                     "Sign in to download the PDF: {{ download_url }}",
        default_html="<p>Your {{ document.label|lower }} {{ document.number }} is available.</p>"
                     "<p>{{ document.currency }} {{ document.amount }}</p>"
                     '<p><a href="{{ download_url }}">Download your document</a></p>',
        sample_context={"document": bag(number="DEMO-1", kind=kind, label=label, amount="25.00", currency="USD"),
                        "makerspace": bag(name="Demo workshop"), "download_url": "https://example.test/member/payments"},
    ) for kind, label in DOCUMENT_LABELS.items()}
