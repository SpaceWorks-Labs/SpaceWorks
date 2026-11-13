import socketserver
from threading import Thread
from unittest.mock import patch

import pytest
from django.core.mail import EmailMultiAlternatives

from apps.integrations.email import makerspace_mail_connection, platform_mail_connection
from apps.integrations.models_email import PlatformEmailSettings
from apps.integrations.mail_providers.config import validate_config
from apps.integrations.mail_providers.connections import connection_for


def test_broken_explicit_platform_transport_never_uses_environment(settings):
    settings.EMAIL_PROVIDER = "brevo"
    row = PlatformEmailSettings(email_provider="resend", from_email="mail@example.org")
    with patch.object(PlatformEmailSettings, "load", return_value=row):
        with patch("apps.integrations.mail_providers.selection.environment_config") as fallback:
            with pytest.raises(Exception):
                platform_mail_connection()
    fallback.assert_not_called()


@pytest.mark.django_db  # a space's platform fallback reads the platform-allowed switch (decision 281)
def test_tenant_inheritance_and_explicit_transport_remain_separate():
    from apps.makerspaces.models import Makerspace
    tenant = Makerspace(name="Tenant", slug="tenant", smtp_host="stale.invalid")
    tenant.email_provider = "inherit"
    with patch("apps.integrations.email.platform_mail_connection", return_value=("platform", "mail@example.org")):
        assert makerspace_mail_connection(tenant)[0] == "platform"


class SmtpHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.wfile.write(b"220 localhost test SMTP\r\n")
        data = False
        while line := self.rfile.readline(65536):
            if data:
                if line == b".\r\n":
                    data = False
                    self.wfile.write(b"250 accepted\r\n")
                else:
                    self.server.messages.append(line)
                continue
            command = line.split(b" ")[0].strip().upper()
            if command == b"DATA":
                self.wfile.write(b"354 end with dot\r\n")
                data = True
            elif command == b"QUIT":
                self.wfile.write(b"221 bye\r\n")
                break
            else:
                self.wfile.write(b"250 OK\r\n")


def test_smtp_roundtrip_local_server(settings):
    settings.DEBUG = True
    settings.ALLOW_PRIVATE_SMTP_HOSTS = True
    with socketserver.TCPServer(("127.0.0.1", 0), SmtpHandler) as server:
        server.messages = []
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            row = PlatformEmailSettings(smtp_host="127.0.0.1", smtp_port=server.server_address[1],
                smtp_use_tls=False, smtp_use_ssl=False, from_email="mail@example.org")
            connection, sender = connection_for(validate_config("smtp", {}, row.from_email), row)
            msg = EmailMultiAlternatives("SMTP receipt", "Plain", sender, ["to@example.org"], connection=connection)
            msg.attach("receipt.pdf", b"%PDF", "application/pdf")
            assert msg.send() == 1
        finally:
            server.shutdown()
            thread.join(timeout=5)
    assert b"receipt.pdf" in b"".join(server.messages)
