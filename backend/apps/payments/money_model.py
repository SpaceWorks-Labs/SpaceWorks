"""Model field for money columns: stored at thousandths, read back like a hundredth when exact.

The columns hold three decimals so KWD/BHD/OMR/JOD/TND keep their fils (`money.MONEY`). A USD or
JPY value is the same number with a trailing zero, and the codebase (audit meta, notices, PDFs,
CSV, webhooks) has always rendered `str(amount)` as "12.35". Trimming on the way OUT of the
database keeps every one of those unchanged: `12.350` reads back as `12.35`, `1.255` stays.
Nothing about the stored value or the migration depends on this; it is presentation only.
"""

from django.db import models

from apps.payments.money import trim_money


class MoneyDecimalField(models.DecimalField):
    def from_db_value(self, value, expression, connection):
        return trim_money(value)
