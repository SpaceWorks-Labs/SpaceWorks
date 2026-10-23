from django.core.exceptions import ValidationError
from django.db import models


class EventBound(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE)
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        abstract = True
        app_label = "events"

    def clean(self):
        super().clean()
        if self.event_id and self.makerspace_id != self.event.makerspace_id:
            raise ValidationError("The host must match the event.")


class AppendOnly(models.Model):
    class Meta:
        abstract = True
        app_label = "events"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("History is append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("History is append-only.")
