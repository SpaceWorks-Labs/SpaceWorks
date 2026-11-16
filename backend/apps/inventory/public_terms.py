"""Public borrowing terms reuse the actual loan policy, without stock/history."""

from apps.makerspaces.loan_policy import loan_days


def borrowing_terms(product, *, cache=None):
    from apps.makerspaces.models_loan_policy import MakerspaceLoanPolicy
    from apps.payments.availability import charge_tracking_enabled
    from apps.payments.models import MakerspacePaymentSettings
    cache = {} if cache is None else cache
    if product.makerspace_id not in cache:
        space = product.makerspace
        cache[space.pk] = (space, MakerspaceLoanPolicy.for_makerspace(space),
                          MakerspacePaymentSettings.for_makerspace(space)
                          if charge_tracking_enabled(space, "loans") else None)
    space, policy, settings = cache[product.makerspace_id]
    days = loan_days(space, (product,), policy=policy)
    terms = [f"Loan period: {days} days."]
    if settings:
        # Lane L15: the deposit comes from the pricing kernel, so a per-item override, a
        # Free item or a free lending default reads here exactly as it will be charged.
        from apps.payments.pricing import quote
        from apps.payments.pricing.resolver import rate_card
        card = cache.get(("pricing", space.pk)) or cache.setdefault(("pricing", space.pk), rate_card(space, "loans"))
        amount = quote(space, "loans", params={"items": [(product, 1)], "components": ("deposit",)},
                       discounts=False, card=card).total
        if amount and amount > 0:
            basis = "per loan" if settings.loan_deposit_mode == "fixed" else "per item"
            terms.append(f"Deposit: {settings.default_currency.upper()} {amount:.2f} {basis}.")
    if product.borrowing_terms.strip():
        terms.append(product.borrowing_terms.strip())
    return " ".join(terms)
