"""Validate free-only values after explicit profile selection in settings.py."""


def free_settings(values) -> dict:
    interval = values["FREE_TICK_INTERVAL_SECONDS"]
    budget = values["FREE_TICK_BUDGET_SECONDS"]
    rate = values["FREE_TICK_RATE_LIMIT_PER_MINUTE"]
    db_cap = values["FREE_DB_CAP_BYTES"]
    object_cap = values["FREE_OBJECT_CAP_BYTES"]
    mail_cap = values["FREE_EMAIL_DAILY_CAP"]
    if not 60 <= interval <= 86400:
        raise ValueError("FREE_TICK_INTERVAL_SECONDS must be between 60 and 86400.")
    if not 3 <= budget <= 20:
        raise ValueError("FREE_TICK_BUDGET_SECONDS must be between 3 and 20.")
    if not 1 <= rate <= 60:
        raise ValueError("FREE_TICK_RATE_LIMIT_PER_MINUTE must be between 1 and 60.")
    for name, value in (
        ("FREE_DB_CAP_BYTES", db_cap), ("FREE_OBJECT_CAP_BYTES", object_cap),
        ("FREE_EMAIL_DAILY_CAP", mail_cap),
    ):
        if value is not None and value <= 0:
            raise ValueError(f"{name} must be positive when configured.")
    # Caps absent at runtime mean UNKNOWN, never unlimited/zero/healthy. R requires
    # verified caps before setup completion; E refuses sends without a mail budget.
    return dict(values)
