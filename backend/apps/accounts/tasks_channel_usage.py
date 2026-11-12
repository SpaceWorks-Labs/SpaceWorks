"""Beat task: move cached channel/area call counts into ``ChannelUsageDay``."""

from celery import shared_task

from apps.accounts.channel_usage import flush_usage


@shared_task(name="apps.accounts.tasks_channel_usage.flush_channel_usage_task")
def flush_channel_usage_task():
    return flush_usage()
