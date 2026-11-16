"""SES v2 Anymail transport isolated from storage/KMS environment credentials."""

import boto3
import botocore.session
from anymail.backends.amazon_ses import EmailBackend as SESBackend
from botocore.config import Config
from django.core.exceptions import ImproperlyConfigured


class EmailBackend(SESBackend):
    def __init__(self, *, mail_config, timeout=10, **kwargs):
        # Explicit empty params prevent ANYMAIL global credential inheritance.
        super().__init__(session_params={}, client_params={}, **kwargs)
        self.mail_config, self.mail_timeout = mail_config, timeout

    def open(self):
        if self.client:
            return False
        values = self.mail_config.credentials
        if values.get("workload_identity"):
            session = botocore.session.Session()
            resolver = session.get_component("credential_provider")
            resolver.providers = [p for p in resolver.providers if p.METHOD in {
                "assume-role-with-web-identity", "container-role", "iam-role"}]
            credentials = session.get_credentials()
            if credentials is None:
                raise ImproperlyConfigured("SES workload identity is unavailable.")
            sdk = boto3.session.Session(botocore_session=session, region_name=values["region"])
        else:
            sdk = boto3.session.Session(
                aws_access_key_id=values["access_key_id"],
                aws_secret_access_key=values["secret_access_key"],
                aws_session_token=values.get("session_token"), region_name=values["region"])
        self.client = sdk.client("sesv2", config=Config(
            connect_timeout=self.mail_timeout / 2, read_timeout=self.mail_timeout / 2,
            retries={"total_max_attempts": 1}, parameter_validation=True,
            ignore_configured_endpoint_urls=True))
        return True
