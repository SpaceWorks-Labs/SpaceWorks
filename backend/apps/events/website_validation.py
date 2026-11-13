"""Typed validation for owner edits; SQL triggers remain the direct-writer backstop."""

from django.utils.translation import gettext
from django.core.exceptions import ValidationError
from django.db.models import F, Q

from .models_website import EventPage
from .website_projection import window


def validate_owner_window(target):
    from .models import EventSeries
    if isinstance(target, EventSeries):
        page = EventPage.objects.filter(series_id=target.pk).first() if target.pk else None
    else:
        page = EventPage.objects.filter(event_id=target.pk).first() if target.pk else None
        if page is None and target.series_id:
            page = EventPage.objects.filter(series_id=target.series_id).select_related("series").first()
            if page:
                start, end = window(target)
                anchor, _ = window(page.series)
                if any(row.ends_at - anchor > end - start for row in page.sessions.all()):
                    raise ValidationError(gettext("The new event window excludes inherited website sessions. Edit the website programme first."))
                _released_window(target, page, inherited=True)
                return
    if page:
        _released_window(target, page)
        start, end = window(target)
        if page.sessions.filter(Q(starts_at__lt=start) | Q(ends_at__gt=end)).exists():
            raise ValidationError(gettext("The new window excludes website sessions. Edit the website programme first."))
        if isinstance(target, EventSeries):
            # Projection rebases sessions on the new anchor, including retained occurrences.
            latest_end = page.sessions.order_by("-ends_at").values_list("ends_at", flat=True).first()
            if latest_end is not None and target.occurrences.filter(website_page__isnull=True).alias(
                website_duration=F("ends_at") - F("starts_at"),
            ).filter(website_duration__lt=latest_end - start).exists():
                raise ValidationError(gettext("The new series window excludes inherited website sessions. Edit the website programme first."))


def _released_window(target, page, *, inherited=False):
    if not page.released or not page.published_revision_id:
        return
    from .website_revisions import validate_snapshot_window
    from rest_framework.exceptions import ValidationError as ApiValidationError
    from .models import EventSeries
    try:
        validate_snapshot_window(target, page.published_revision, inherited=inherited)
        if isinstance(target, EventSeries):
            for occurrence in target.occurrences.filter(website_page__isnull=True):
                validate_snapshot_window(occurrence, page.published_revision, inherited=True)
    except ApiValidationError as exc:
        raise ValidationError(gettext("The new window excludes the released website. Release a fitting draft or unrelease first.")) from exc
