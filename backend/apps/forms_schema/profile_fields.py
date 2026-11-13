"""Model-free profile descriptors. Sensitivity controls consent, never crypto.

Asset normalization does not authorize use: the owner provider checks references.
"""
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from urllib.parse import urlsplit


class ProfileValueError(ValueError):
    def __init__(self, message, *, fields=None):
        super().__init__(message)
        self.fields = fields


@dataclass(frozen=True)
class ProfileField:
    field_key: str
    question_types: tuple[str, ...]
    max_length: int | None = None
    sensitive: bool = False
    persistable: bool = True

    @property
    def default_save(self):
        return self.persistable and not self.sensitive

    @property
    def all_values_encrypted(self):
        return self.persistable


_TEXT = ("short_text", "long_text")
_FIELDS = (
    ProfileField("name", _TEXT, 200),
    ProfileField("phone", ("phone",), 32),
    ProfileField("institution", _TEXT, 200),
    ProfileField("organization", _TEXT, 200),
    ProfileField("study_level", _TEXT + ("single_choice",), 100),
    ProfileField("country", ("short_text", "single_choice"), 2),
    ProfileField("skills", ("multi_choice",)),
    *(ProfileField(key, ("url",), 2048) for key in
      ("github_url", "linkedin_url", "portfolio_url")),
    ProfileField("resume", ("asset_reference",), sensitive=True),
    ProfileField("shirt_size", ("short_text", "single_choice"), 32),
    ProfileField("dietary_needs", _TEXT, 2000, True),
    ProfileField("accessibility_needs", _TEXT, 2000, True),
    ProfileField("emergency_contact", ("emergency_contact",), sensitive=True),
    ProfileField("date_of_birth", ("date_of_birth",), sensitive=True),
    ProfileField("age_at_event", ("age_at_event",), sensitive=True, persistable=False),
)
PROFILE_FIELDS = MappingProxyType({field.field_key: field for field in _FIELDS})
STANDARD_PROFILE_FIELDS = PROFILE_FIELDS
# ISO 3166-1 alpha-2. No core Accounts import of a tenant module is necessary.
COUNTRY_CODES = frozenset((
    "AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ "
    "CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR "
    "GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP "
    "KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT "
    "MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW "
    "SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ "
    "UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW"
).split())


def descriptor(field_key):
    try:
        return PROFILE_FIELDS[field_key]
    except (KeyError, TypeError):
        raise ProfileValueError("Unknown profile field.") from None


def text(value, maximum, *, blank=False):
    if not isinstance(value, str):
        raise ProfileValueError("Expected a string.")
    value = unicodedata.normalize("NFC", value).strip()
    if not value and not blank:
        raise ProfileValueError("This field is required.")
    if len(value) > maximum:
        raise ProfileValueError(f"Use at most {maximum} characters.")
    if any(unicodedata.category(c) == "Cc" and c not in "\n\t" for c in value):
        raise ProfileValueError("Remove control characters.")
    return value


def normalize_phone(value):
    value = text(value, 32)
    compact = re.sub(r"[\s().-]", "", value)
    if compact.startswith("00"):
        compact = "+" + compact[2:]
    if not re.fullmatch(r"\+[1-9][0-9]{6,14}", compact):
        raise ProfileValueError("Enter a valid phone.")
    return compact


def https_url(value):
    value = text(value, 2048)
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ProfileValueError("Enter a valid HTTPS URL.") from None
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or "\\" in value or any(c.isspace() for c in value)
            or port == 0):
        raise ProfileValueError("Enter a valid HTTPS URL without credentials.")
    return value


def normalize_dob(value, *, today=None):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ProfileValueError("Use YYYY-MM-DD.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ProfileValueError("Enter a valid calendar date.") from None
    if parsed > (today or date.today()):
        raise ProfileValueError("Date of birth cannot be in the future.")
    return parsed.isoformat()


def emergency_contact(value):
    if not isinstance(value, dict):
        raise ProfileValueError("Invalid contact.", fields={"name": ["Expected an object."]})
    limits = {"name": 200, "relationship": 100, "phone": 32}
    errors = {key: ["Unknown field."] for key in value if key not in limits}
    result = {}
    if set(value) == set(limits) and all(isinstance(v, str) and not v.strip() for v in value.values()):
        return None
    for key, limit in limits.items():
        if key not in value:
            errors[key] = ["This field is required."]
            continue
        try:
            item = text(value[key], limit, blank=key == "relationship")
            result[key] = normalize_phone(item) if key == "phone" else item
        except ProfileValueError as exc:
            errors[key] = [str(exc)]
    if errors:
        raise ProfileValueError("Invalid contact.", fields=errors)
    return result


def normalize_profile_value(field_key, value, *, today=None):
    field = descriptor(field_key)
    if not field.persistable:
        raise ProfileValueError("Derived age cannot be saved.")
    if field_key == "emergency_contact":
        return emergency_contact(value)
    if field_key == "date_of_birth":
        return normalize_dob(value, today=today)
    if field_key == "phone":
        return normalize_phone(value)
    if field_key.endswith("_url"):
        return https_url(value)
    if field_key == "resume":
        if (not isinstance(value, dict) or set(value) != {"asset_id", "sha256"}
                or type(value["asset_id"]) is not int or value["asset_id"] < 1
                or not isinstance(value["sha256"], str)
                or not re.fullmatch(r"[a-f0-9]{64}", value["sha256"])):
            raise ProfileValueError("Use a ready owner asset reference.")
        return dict(value)
    if field_key == "skills":
        if not isinstance(value, list) or len(value) > 50:
            raise ProfileValueError("Use at most 50 skills.")
        return list(dict.fromkeys(text(item, 60) for item in value))
    result = text(value, field.max_length)
    if field_key == "country":
        result = result.upper()
        if result not in COUNTRY_CODES:
            raise ProfileValueError("Use a valid ISO country code.")
    return result


def compatible_question(field_key, question_type):
    return question_type in descriptor(field_key).question_types
