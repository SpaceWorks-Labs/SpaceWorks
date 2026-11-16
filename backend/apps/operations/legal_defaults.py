"""Shipped default privacy and terms text (parity E-B8, A13). Translated via gettext; one msgid per paragraph.

These describe what Space Works actually does: it stores account details, requests, loans, evidence photos, event
registrations and an audit trail on behalf of the space that runs it, and sends email and notifications for that
space. The operator replaces them from the superadmin console; a space may add its own text on top.
"""

from django.utils.translation import gettext as _


def privacy_default() -> str:
    return "\n\n".join([
        "# " + _("Privacy"),
        _("This site runs Space Works, a system used by makerspaces and community workshops to manage "
          "memberships, equipment loans, bookings and events. The space you use is responsible for the "
          "information you give it; the operator of this installation provides the software."),
        "## " + _("What we keep"),
        _("Your account details (name, email address, optional phone number), the requests, loans, bookings and "
          "event registrations you make, and the payments or charges recorded against you. When equipment is "
          "handed over or returned we keep the scans, remarks and photos taken as evidence, together with the "
          "time and the staff member involved."),
        "## " + _("Why we keep it"),
        _("To run the space: to decide and track requests, to know who holds which equipment, to take part in "
          "events, to keep accurate accounts and to keep an audit trail that protects members and the space "
          "alike. We do not sell your information and do not use it for advertising."),
        "## " + _("Who can see it"),
        _("Staff of the space you deal with, only as far as their role needs. Other spaces on the same "
          "installation cannot see your records. Evidence photos are private and never shown publicly."),
        "## " + _("Email and notifications"),
        _("We send the messages needed to run your membership, requests and events. Optional messages follow "
          "your notification preferences, and you can change them in your account."),
        "## " + _("How long we keep it"),
        _("Account and membership records are kept while you are a member and as long as the space needs them "
          "for its accounts. Evidence photo files expire after the space's retention period; the record that "
          "a handover happened is kept. You can ask to export or delete your account from your account page."),
        "## " + _("Contact"),
        _("Ask the space you use, or the operator of this installation, about any of this."),
    ])


def terms_default() -> str:
    return "\n\n".join([
        "# " + _("Terms of use"),
        _("By using this site you agree to these terms. They are a plain-language summary; the space you use "
          "may add its own rules for its equipment, premises and events."),
        "## " + _("Your account"),
        _("Keep your sign-in details private and tell the space if you think someone else has used them. "
          "You are responsible for what is done with your account."),
        "## " + _("Borrowing equipment and using machines"),
        _("Borrowed equipment must be collected and returned through the space's process, with the scans and "
          "photos it asks for. You are responsible for equipment while it is with you. Lost or damaged items "
          "may be charged to you, and your access may be limited until the matter is settled."),
        "## " + _("Events and bookings"),
        _("Registering for an event or booking a resource is a commitment. Cancel in good time so others can "
          "take your place. The organiser's own rules for the event apply."),
        "## " + _("Payments"),
        _("Fees and charges are set by the space. Payments are recorded against your account, and receipts are "
          "available from it."),
        "## " + _("Acceptable use"),
        _("Do not misuse the site, try to access other people's records or interfere with its operation. The "
          "space may restrict or end access for misuse."),
        "## " + _("Changes"),
        _("These terms may change. Continued use after a change means you accept the new terms."),
    ])


DEFAULTS = {"privacy": privacy_default, "terms": terms_default}
