"""Privacy and terms content: shipped defaults, a platform override, an optional per-space override (parity E-B8).

Order for a reader: the space's own text -> the platform operator's text for the reader's language -> the
operator's language-neutral text -> the shipped, translated default. Everything is Markdown; the UI must render it
without raw HTML. Writes are audited by the callers (`platform.legal_page_updated`, `makerspace.legal_page_updated`).
"""

from django.utils import translation

from .legal_defaults import DEFAULTS

SLUGS = tuple(DEFAULTS)
MAX_LENGTH = 50_000
BRANDING_KEY = "legal_pages"


def clean_markdown(value) -> str:
    return str(value or "").replace("\x00", "").replace("\r\n", "\n").strip()


def _platform_row(slug, language):
    from apps.integrations.models_legal import PlatformLegalPage
    rows = {row.language: row for row in PlatformLegalPage.objects.filter(slug=slug, language__in=[language, ""])}
    return rows.get(language) or rows.get("")


def space_pages_enabled(makerspace) -> bool:
    from apps.makerspaces.platform import feature_enabled
    return feature_enabled(makerspace, "legal.space_pages")


def space_override(makerspace, slug) -> str:
    if not space_pages_enabled(makerspace):
        return ""
    return clean_markdown(((makerspace.branding_config or {}).get(BRANDING_KEY) or {}).get(slug))


def resolve(slug, *, makerspace=None, language=None) -> dict:
    language = (language or translation.get_language() or "en").split("-")[0].lower()
    if makerspace is not None:
        text = space_override(makerspace, slug)
        if text:
            return {"slug": slug, "markdown": text, "source": "space", "language": "", "updated_at": makerspace.updated_at}
    row = _platform_row(slug, language)
    if row is not None:
        return {"slug": slug, "markdown": row.markdown, "source": "platform", "language": row.language,
                "updated_at": row.updated_at}
    return {"slug": slug, "markdown": DEFAULTS[slug](), "source": "default", "language": language, "updated_at": None}


def set_platform_page(slug, language, markdown):
    """Create or replace the operator's text. Returns the row."""
    from apps.integrations.models_legal import PlatformLegalPage
    row, _created = PlatformLegalPage.objects.update_or_create(
        slug=slug, language=language, defaults={"markdown": clean_markdown(markdown)})
    return row


def reset_platform_page(slug, language) -> bool:
    from apps.integrations.models_legal import PlatformLegalPage
    return bool(PlatformLegalPage.objects.filter(slug=slug, language=language).delete()[0])


def set_space_override(makerspace, slug, markdown) -> str:
    """Store (or, when blank, remove) a space's own text in `branding_config`; the caller wraps the audit."""
    text = clean_markdown(markdown)
    branding = dict(makerspace.branding_config or {})
    pages = dict(branding.get(BRANDING_KEY) or {})
    if text:
        pages[slug] = text
    else:
        pages.pop(slug, None)
    if pages:
        branding[BRANDING_KEY] = pages
    else:
        branding.pop(BRANDING_KEY, None)
    makerspace.branding_config = branding
    makerspace.save(update_fields=["branding_config", "updated_at"])
    return text
