"""A pay link for a guest staff just added (release 2 L6, G33).

"Add guest" registers a real account; when the ticket has a price, its charge is raised
on that account. This hands staff the link the guest pays through -- the live hosted
checkout when the space takes online payments, else the guest's own payments page -- and
can email it to the guest's account address. An account charge never gets an L5
bearer pay link (those are for account-less charges only): the guest signs in to pay.
"""

from apps.audit.services import record


def member_payments_url(makerspace):
    from apps.integrations.notification_links import local_link
    return local_link(makerspace, "member", "payments")


def pay_link(registration, *, actor, send=False):
    from apps.operations.notifications_p2 import direct_mail_unless_routed
    from apps.payments.availability import online_payments_enabled
    from .orders_errors import OrderRefused
    from .services_checkin import pending_ticket_charge
    payment = pending_ticket_charge(registration)
    if payment is None or registration.member_id is None:
        raise OrderRefused("nothing_to_collect", "This ticket has nothing left to pay.")
    url = ""
    if online_payments_enabled(payment.makerspace, "events"):
        from apps.payments.services import create_checkout_url
        try:
            url = create_checkout_url(payment.pk, actor=actor) or ""
        except Exception:
            url = ""
    url = url or member_payments_url(payment.makerspace)
    event, member = registration.event, registration.member
    if send:
        text = (f"{event.makerspace.name} added you to {event.title}. Your ticket costs "
                f"{payment.currency.upper()} {payment.amount}.\nSign in and pay here: {url}\n")
        direct_mail_unless_routed(space=event.makerspace, source_kind="events.ticket_pay_link", row=payment,
                                  revision=str(payment.pk), event="ticket_pay_link", owner=member,
                                  to_email=member.email, subject=f"Payment for {event.title}", text=text,
                                  stream="events", audience="requester", feature="", persist_body=False)
    record(actor, "event.pay_link_issued", makerspace=event.makerspace, target=registration,
           meta={"registration_id": registration.pk, "payment_id": payment.pk, "emailed": bool(send)})
    return url
