"""Module purge for `analytics`: the space's connection row; its login is dropped on commit
(``signals.drop_login_after_delete``). Nothing else is stored: the views are derived."""

from apps.makerspaces.module_purge_collectors_single_model import _counts, _delete


def analytics_delete(makerspace, cursor):
    from .models import AnalyticsConnection

    connections, labels = _delete(AnalyticsConnection.objects.filter(makerspace=makerspace))
    return _counts(model_labels=labels, analytics_connections=connections)
