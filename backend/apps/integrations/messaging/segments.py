"""Conservative SMS accounting: multipart 152 septets / 66 UTF-16 units."""
from dataclasses import dataclass
from math import ceil

GSM_BASIC = frozenset(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ\x1bÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM_EXTENSION = frozenset("\f^{}\\[~]|€")


def _encoding(body):
    return "gsm7" if all(char in GSM_BASIC or char in GSM_EXTENSION for char in body) else "ucs2"


def _units(body, encoding):
    return sum(2 if char in GSM_EXTENSION else 1 for char in body) if encoding == "gsm7" else len(body.encode("utf-16-be")) // 2


def count_segments(body):
    encoding = _encoding(body)
    units = _units(body, encoding)
    single, multipart = (160, 152) if encoding == "gsm7" else (70, 66)
    return 0 if not units else 1 if units <= single else ceil(units / multipart)


@dataclass(frozen=True)
class SmsBody:
    body: str
    estimated_segments: int
    encoding: str


def prepare_sms(body):
    if count_segments(body) <= 3:
        return SmsBody(body, count_segments(body), _encoding(body))
    encoding = _encoding(body)
    budget = (152 if encoding == "gsm7" else 66) * 3 - 3
    used, chars = 0, []
    for char in body:
        units = _units(char, encoding)
        if used + units > budget:
            break
        chars.append(char)
        used += units
    result = "".join(chars) + "..."
    return SmsBody(result, count_segments(result), _encoding(result))
