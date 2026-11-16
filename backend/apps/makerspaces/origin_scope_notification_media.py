"""Resolve a media grant's tenant without consuming or authorizing the grant."""

def media_grant_targets(token):
    from apps.integrations.notification_media import media_source_targets
    return media_source_targets(token)
