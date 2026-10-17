"""Personal Slack, Discord and Mattermost file delivery; never room webhooks."""
import json
import re
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

from .notification_document_transport import multipart, personal_destination, validate_document
from .notification_providers import ProviderResult
from .notification_slack_http import ProviderFailure, api, credentials_for, failure_result


def slack_document(provider, delivery, *, filename, pdf_bytes, caption):
    def send():
        from .notification_slack import slack_api, workspace_identity
        config = provider.config
        user = personal_destination(config, delivery)
        validate_document(filename, pdf_bytes)
        creds = credentials_for(config)
        token = creds.get("bot_token", "")
        if (not token or workspace_identity(creds.get("team_id", "")) != config.integration_identity
                or slack_api("auth.test", token=token).get("team_id") != creds.get("team_id")):
            raise ProviderFailure("invalid_endpoint")
        channel = slack_api("conversations.open", token=token, data={"users": user})["channel"]["id"]
        if not isinstance(channel, str) or not re.fullmatch(r"D[A-Z0-9]{1,254}", channel):
            raise ProviderFailure("invalid_endpoint")
        upload = slack_api("files.getUploadURLExternal", token=token,
            data={"filename": filename, "length": len(pdf_bytes)})
        url, file_id = upload.get("upload_url"), upload.get("file_id")
        try:
            parts = urlsplit(url)
            valid = (parts.scheme == "https" and parts.hostname == "files.slack.com"
                and parts.path.startswith("/upload/") and not parts.username and not parts.password
                and parts.port in (None, 443) and not parts.fragment)
        except (ValueError, TypeError):
            valid = False
        if not valid or not isinstance(file_id, str) or not re.fullmatch(r"F[A-Z0-9]{1,254}", file_id):
            raise ProviderFailure("provider_error")
        # Upload URL is an ephemeral provider capability; no bot credential goes to it.
        personal_destination(config, delivery)
        api("POST", url, raw_body=pdf_bytes, content_type="application/pdf", raw_response=True)
        personal_destination(config, delivery)
        result = slack_api("files.completeUploadExternal", token=token, data={
            "files": [{"id": file_id, "title": filename}], "channel_id": channel,
            "initial_comment": str(caption)[:40000]})
        files = result.get("files")
        if (not isinstance(files, list) or not files or not isinstance(files[0], dict)
                or files[0].get("id") != file_id):
            raise ProviderFailure("timeout", retryable=True, ambiguous=True)
        return ProviderResult(True, provider_id=file_id)
    return failure_result("slack", send)


def discord_document(provider, delivery, *, filename, pdf_bytes, caption):
    def send():
        from .notification_discord import API
        config = provider.config
        user = personal_destination(config, delivery)
        validate_document(filename, pdf_bytes)
        creds = credentials_for(config)
        provider.check_identity(creds)
        token = creds.get("bot_token", "")
        if not token:
            raise ProviderFailure("not_configured")
        channel = api("POST", API + "/users/@me/channels", token=token, auth="Bot",
                      data={"recipient_id": user})
        channel_id = channel.get("id")
        if not isinstance(channel_id, str) or not channel_id.isdigit():
            raise ProviderFailure("provider_error")
        payload = {"content": str(caption)[:2000], "allowed_mentions": {"parse": []},
            "nonce": str(delivery.pk), "enforce_nonce": True,
            "attachments": [{"id": 0, "filename": filename}]}
        body, content_type = multipart({"payload_json": json.dumps(payload)}, filename=filename,
                                      pdf_bytes=pdf_bytes, field="files[0]")
        personal_destination(config, delivery)
        result = api("POST", API + f"/channels/{channel_id}/messages", token=token, auth="Bot",
                     raw_body=body, content_type=content_type)
        if not isinstance(result.get("id"), str) or not result["id"].isdigit():
            raise ProviderFailure("timeout", retryable=True, ambiguous=True)
        return ProviderResult(True, provider_id=result["id"])
    return failure_result("discord", send)


def mattermost_document(provider, delivery, *, filename, pdf_bytes, caption):
    def send():
        from .notification_mattermost import validated_id
        from .notification_mattermost_http import mattermost_api, server_url
        config = provider.config
        user = personal_destination(config, delivery)
        validate_document(filename, pdf_bytes)
        creds = credentials_for(config)
        base = server_url(creds["server_url"])
        if base != config.integration_identity or not creds.get("bot_token"):
            raise ProviderFailure("not_configured")
        token = creds["bot_token"]
        bot = mattermost_api(base, "GET", "/api/v4/users/me", token=token)
        recipient = mattermost_api(base, "GET", f"/api/v4/users/{validated_id(user)}", token=token)
        if not bot.get("is_bot") or bot.get("delete_at") or recipient.get("delete_at") or not recipient.get("id"):
            raise ProviderFailure("invalid_endpoint")
        channel = mattermost_api(base, "POST", "/api/v4/channels/direct", token=token,
                                 data=[validated_id(bot.get("id")), user])
        channel_id = validated_id(channel.get("id"))
        body, content_type = multipart({"channel_id": channel_id}, filename=filename,
                                      pdf_bytes=pdf_bytes, field="files")
        personal_destination(config, delivery)
        upload = mattermost_api(base, "POST", "/api/v4/files", token=token,
                               raw_body=body, content_type=content_type)
        files = upload.get("file_infos")
        if not isinstance(files, list) or len(files) != 1:
            raise ProviderFailure("provider_error")
        file_id = validated_id(files[0].get("id"))
        personal_destination(config, delivery)
        result = mattermost_api(base, "POST", "/api/v4/posts", token=token, data={
            "channel_id": channel_id, "message": str(caption)[:16383], "file_ids": [file_id],
            "pending_post_id": uuid5(NAMESPACE_URL, f"spaceworks:mm:{config.pk}:{delivery.pk}").hex})
        if not isinstance(result.get("id"), str) or not result["id"]:
            raise ProviderFailure("timeout", retryable=True, ambiguous=True)
        return ProviderResult(True, provider_id=result["id"])
    return failure_result("mattermost", send)
