"""Shared D model behavior. G adds matching PostgreSQL guards before mounting routes."""

from django.db import models


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise RuntimeError("Historical rows are append-only.")

    def bulk_update(self, *args, **kwargs):
        raise RuntimeError("Historical rows are append-only.")

    def delete(self):
        raise RuntimeError("Historical rows require the explicit lifecycle purge.")


class AppendOnly(models.Model):
    objects = models.Manager.from_queryset(AppendOnlyQuerySet)()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Historical rows are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Historical rows require the explicit lifecycle purge.")


class EventOwned(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="+")
    version = models.PositiveIntegerField(default=1)

    class Meta:
        abstract = True


class PrivateRecord(models.Model):
    """Private text is mapped by G into the existing scoped PII encryption registry."""

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")

    class Meta:
        abstract = True
