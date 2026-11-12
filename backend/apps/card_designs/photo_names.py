"""File-name normalisation and holder matching for the bulk photo upload (D314c addendum).

A file name is reduced to a comparable form: directory and extension dropped, diacritics folded where that is
safe (NFKD, combining marks removed), case folded, spaces / underscores / dashes / dots treated alike. A file is
matched to a holder in this order, and the FIRST level that finds anyone decides:

  1. card number   `TNK-0042.jpg`, `tnk_0042 priya.jpg` (whole number as leading tokens of the name)
  2. email         the local part (`priya.raman.jpg` for priya.raman@x.org) or the whole address
  3. full name     `Priya Raman.jpg`, `priya_raman.jpg`, `Raman Priya.jpg` (same words, any order)

One holder at a level is a match; several are AMBIGUOUS (staff pick); none is UNMATCHED. Pure functions, no I/O.
"""
import re
import unicodedata

_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".jfif")
_SEPARATORS = re.compile(r"[^0-9a-z]+")


def _fold(text):
    text = unicodedata.normalize("NFKD", str(text or "")).casefold()
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def stem(filename):
    """The file name without directory or extension."""
    name = str(filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if name.lower().endswith(_EXTENSIONS):
        name = name.rsplit(".", 1)[0]
    return name


def tokens(text):
    return tuple(part for part in _SEPARATORS.split(_fold(text)) if part)


def collapse(text):
    return "".join(tokens(text))


def _email_forms(email):
    email = str(email or "").strip()
    if "@" not in email:
        return set()
    local = email.split("@", 1)[0]
    return {collapse(local), collapse(email)} - {""}


class HolderIndex:
    """Lookup tables over `holders` (dicts with id, name, number, email), built once per upload."""

    def __init__(self, holders):
        self.number_exact, self.number_tokens, self.email, self.name_exact, self.name_set = {}, {}, {}, {}, {}
        for holder in holders:
            hid = holder["id"]
            number = holder.get("number") or ""
            if number:
                self.number_exact.setdefault(collapse(number), set()).add(hid)
                self.number_tokens.setdefault(tokens(number), set()).add(hid)
            for form in _email_forms(holder.get("email")):
                self.email.setdefault(form, set()).add(hid)
            name_tokens = tokens(holder.get("name"))
            if name_tokens:
                self.name_exact.setdefault(name_tokens, set()).add(hid)
                self.name_set.setdefault(tuple(sorted(name_tokens)), set()).add(hid)

    def match(self, filename):
        """-> (match_kind, sorted candidate ids). match_kind is "" when nothing fits."""
        base = stem(filename)
        words = tokens(base)
        if not words:
            return "", []
        found = self.number_exact.get(collapse(base))
        for size in range(len(words), 0, -1):  # the number as the leading tokens: "tnk 0042 priya"
            found = found or self.number_tokens.get(words[:size])
        if found:
            return "number", sorted(found)
        found = self.email.get(collapse(base)) or (self.email.get(collapse(base.rsplit(".", 1)[0]))
                                                   if "@" in base else None)
        if found:
            return "email", sorted(found)
        found = self.name_exact.get(words) or self.name_set.get(tuple(sorted(words)))
        return ("name", sorted(found)) if found else ("", [])
