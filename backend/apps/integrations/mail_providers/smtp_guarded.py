"""Django's SMTP backend, refusing a connection that lands on a non-public address.

``validate_smtp_endpoint`` resolves the host once; smtplib resolves it again when it
connects, so a host with a short-lived DNS answer could pass the check and then reach an
internal relay (DNS rebinding). The socket's real peer is checked here, right after the TCP
connect and before the greeting, EHLO or AUTH: nothing is sent to a refused peer.
"""
import ipaddress
import smtplib

from django.core.mail.backends.smtp import EmailBackend as DjangoSMTPBackend

from apps.integrations.smtp_validation import peer_address_allowed


def _checked(sock):
    peer = ipaddress.ip_address(sock.getpeername()[0].split("%", 1)[0])
    if not peer_address_allowed(peer):
        sock.close()
        raise smtplib.SMTPConnectError(-1, "SMTP host resolved to a blocked address.")
    return sock


class GuardedSMTP(smtplib.SMTP):
    def _get_socket(self, host, port, timeout):
        return _checked(super()._get_socket(host, port, timeout))


class GuardedSMTPSSL(smtplib.SMTP_SSL):
    def _get_socket(self, host, port, timeout):
        # SMTP_SSL wraps the plain socket; check that socket before the TLS handshake.
        plain = _checked(smtplib.SMTP._get_socket(self, host, port, timeout))
        return self.context.wrap_socket(plain, server_hostname=self._host)


class EmailBackend(DjangoSMTPBackend):
    @property
    def connection_class(self):
        return GuardedSMTPSSL if self.use_ssl else GuardedSMTP
