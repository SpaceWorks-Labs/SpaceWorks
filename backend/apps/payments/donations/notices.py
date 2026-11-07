"""Lane L18 notices: the giver's receipt, a pledge's period reminder, and perks coming due (staff).

A giver with an account hears through their own channels (an envelope); a guest gets one
direct email carrying only their own signed status link. Staff hear about perks due through the
`payments` matrix. No message names another person or carries a PAN.
"""

from django.utils.translation import gettext
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.operations.notifications_p2 import body, direct_mail_unless_routed, fanout, revision, safe_notification

SOURCE = "payments.donations"
EVENTS = frozenset({"donation_received", "pledge_due", "perk_due"})


def public_link(space, path, token):
    from apps.makerspaces.website_directory import public_url

    return public_url(space, path, token)


def _send(space, row, event, *, account, email, subject, text, link, marker):
    rendered = body(subject, f"{text}\n\n{link}" if link else text, link)
    if account is not None:
        return fanout(row=row, space=space, feature="payments", stream="payments", event=event, source_kind=SOURCE,
                      revision=revision(type(row).__name__, row.pk, event, marker), owner=account,
                      owner_body=rendered, staff=False, context={"row_kind": type(row).__name__, "row_id": row.pk})
    return direct_mail_unless_routed(space=space, source_kind=SOURCE, row=row, revision=str(marker), event=event,
                                     owner=None, to_email=email, subject=subject, text=rendered["text"],
                                     stream="payments", audience="requester", feature="payments",
                                     persist_body=False, address_owner=False)


@safe_notification
def notify_receipt(donation):
    from .identity import STATUS_SALT, link_token

    space = donation.makerspace
    amount = f"{donation.currency.upper()} {donation.amount}"
    text = f"Thank you for your gift of {amount} to {space.name}. It has been received."
    if donation.tax_receipt:
        text += f" Your {donation.tax_receipt['section']} receipt {donation.tax_receipt['number']} is ready to download."
    link = ("" if donation.donor_id else public_link(space, "donate/gift", link_token(donation, "access_secret",
                                                                                      STATUS_SALT)))
    return _send(space, donation, "donation_received", account=donation.donor, email=donation.donor_email,
                 subject=gettext('Thank you for supporting {name}').format(name=space.name), text=text, link=link, marker=donation.paid_at)


@safe_notification
def notify_pledge_due(pledge, donation):
    from .identity import PLEDGE_SALT, STATUS_SALT, link_token

    space = pledge.makerspace
    amount = f"{donation.currency.upper()} {donation.amount}"
    text = (f"Your pledged gift of {amount} to {space.name} for the period starting "
            f"{donation.period_start.isoformat()} is ready to pay.")
    link = ""
    if not pledge.donor_id:
        link = public_link(space, "donate/gift", link_token(donation, "access_secret", STATUS_SALT))
        text += f"\nManage or cancel your pledge: {public_link(space, 'donate/pledge', link_token(pledge, 'manage_secret', PLEDGE_SALT))}"
    return _send(space, donation, "pledge_due", account=pledge.donor, email=pledge.donor_email,
                 subject=gettext('Your pledge to {name} is due').format(name=space.name), text=text, link=link, marker=donation.period_start)


@safe_notification
def notify_perk_due(perk):
    from apps.operations.notifications_p2 import staff_link

    space = perk.makerspace
    text = f"A sponsor perk is due on {perk.due_on.isoformat()} and is not marked fulfilled yet."
    return fanout(row=perk, space=space, feature="payments", stream="payments", event="perk_due", source_kind=SOURCE,
                  revision=revision("SponsorPerk", perk.pk, "perk_due", perk.due_on), owner=None,
                  staff_body=body("A sponsor perk is due", text, staff_link(space, "finance")),
                  context={"row_kind": "SponsorPerk", "row_id": perk.pk})


def eligible(envelope):
    from apps.makerspaces.platform import feature_enabled
    from apps.makerspaces.servability import is_servable

    from .models import Donation, SponsorPerk

    if envelope.event not in EVENTS:
        return False
    model = SponsorPerk if envelope.event == "perk_due" else Donation
    row = model.objects.select_related("makerspace").filter(
        pk=envelope.context.get("row_id"), makerspace_id=envelope.makerspace_id).first()
    if row is None or not is_servable(row.makerspace):
        return False
    if envelope.event == "perk_due":
        return envelope.audience == "staff" and feature_enabled(row.makerspace, "finance.sponsors")
    return (envelope.audience != "staff" and row.donor_id == envelope.recipient_id
            and feature_enabled(row.makerspace, "finance.donations"))


def register():
    register_source(SOURCE, NotificationSource(eligible))
