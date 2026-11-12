"""Capability purge plan for DISPLAY-2 (decision 325c): `display.anthias_push`.

Deletes the space's registered Anthias players (host, username and the encrypted password go with the row)
and the asset links that map its screens to asset ids on those players. Display screens, their settings and
their addresses stay. Nothing is sent to a player: assets SpaceWorks created stay on the Pi until someone
removes them there. Superadmin-only, previewed and audited like every capability purge.
"""


def _owned(space):
    from apps.presence.models_anthias import AnthiasAssetLink, AnthiasPlayer
    return AnthiasAssetLink.objects.filter(player__makerspace=space), AnthiasPlayer.objects.filter(makerspace=space)


def _preview(space):
    links, players = _owned(space)
    return {"players": players.count(), "asset_links": links.count()}


def _delete(space, cursor):
    from .module_purge_collectors_single_model import _counts, _delete as delete
    links, players = _owned(space)
    link_count, link_labels = delete(links)
    player_count, player_labels = delete(players)
    return _counts(model_labels=link_labels | player_labels, asset_links=link_count, players=player_count)


def plans(plan):
    return (
        plan("display.anthias_push", "Registered Anthias players (including their stored credentials) and the "
             "asset links to them. Screens stay; assets already on a player are not removed.", _delete, _preview),
    )
