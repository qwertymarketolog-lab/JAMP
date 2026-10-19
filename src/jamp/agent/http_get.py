"""Restricted HTTPS GET executor for explicitly allowlisted public hosts."""

from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit

ALLOWED_HOSTS: frozenset[str] = frozenset({"api.github.com", "example.com"})
TIMEOUT_SECONDS = 5.0
MAX_RESPONSE_BYTES = 1_048_576
USER_AGENT = "JAMP/1.0"

_BLOCKED_NETS = (
    ipaddress.ip_network("169.254.0.0/16"),  # cloud metadata and link-local IPv4
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)


def _is_blocked(ip: str) -> bool:
    """Return True for malformed, non-public, or explicitly blocked IP addresses."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    if addr.version == 6 and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    if (
        not addr.is_global
        or addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
    ):
        return True
    return any(addr in net for net in _BLOCKED_NETS if net.version == addr.version)


class ToolError(Exception):
    """A fail-closed tool execution error with a stable machine-readable code."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class HTTPGetExecutor:
    """Fetch one HTTPS URL without redirects, DNS re-resolution, or credentials."""

    ALLOWED_HOSTS: frozenset[str] = ALLOWED_HOSTS

    def __init__(
        self, *, timeout: float = TIMEOUT_SECONDS, max_bytes: int = MAX_RESPONSE_BYTES
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        self._timeout = timeout
        self._max_bytes = max_bytes

    def __call__(self, arguments: dict) -> dict:
        return self.execute(arguments)

    def execute(self, arguments: dict) -> dict:
        """Return {"status": int, "body": str}; reject all unsafe inputs and responses."""
        if not isinstance(arguments, dict) or set(arguments) != {"url"}:
            raise ToolError("INVALID_ARGUMENTS", "arguments must contain only url")
        url = arguments["url"]
        if not isinstance(url, str):
            raise ToolError("INVALID_ARGUMENTS", "url must be a string")
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError as exc:
            raise ToolError("INVALID_ARGUMENTS", "invalid URL") from exc
        if parsed.scheme.lower() != "https":
            raise ToolError("INSECURE_SCHEME", "only HTTPS URLs are allowed")
        host = parsed.hostname
        if (
            not host
            or parsed.username is not None
            or parsed.password is not None
            or (port is not None and port != 443)
            or host.lower() not in self.ALLOWED_HOSTS
        ):
            raise ToolError("NON_ALLOWLISTED_HOST", "URL host or authority is not allowed")

        addresses = self._resolve(host)
        if not addresses:
            raise ToolError("DNS_FAILED", "hostname did not resolve")
        for address in addresses:
            try:
                ipaddress.ip_address(address)
            except ValueError as exc:
                raise ToolError("DNS_FAILED", "resolver returned an invalid IP") from exc
            if _is_blocked(address):
                raise ToolError("PRIVATE_IP", "hostname resolved to a non-public IP")

        last_error: OSError | None = None
        for address in addresses:
            raw_socket = None
            tls_socket = None
            try:
                raw_socket = self._connect(address, 443)
                tls_socket = ssl.create_default_context().wrap_socket(
                    raw_socket, server_hostname=host
                )
                connection = http.client.HTTPConnection(host, 443, timeout=self._timeout)
                connection.sock = tls_socket
                path = parsed.path or "/"
                if parsed.query:
                    path += "?" + parsed.query
                connection.putrequest("GET", path, skip_host=True, skip_accept_encoding=True)
                connection.putheader("Host", host)
                connection.putheader("User-Agent", USER_AGENT)
                connection.endheaders()
                response = connection.getresponse()
                if 300 <= response.status < 400:
                    raise ToolError("REDIRECT_REJECTED", "redirects are not followed")
                declared_length = response.getheader("Content-Length")
                if declared_length is not None:
                    try:
                        if int(declared_length) > self._max_bytes:
                            raise ToolError("TOO_LARGE", "response exceeds size limit")
                    except ValueError as exc:
                        raise ToolError("INVALID_RESPONSE", "invalid Content-Length") from exc
                body = response.read(self._max_bytes + 1)
                if len(body) > self._max_bytes:
                    raise ToolError("TOO_LARGE", "response exceeds size limit")
                return {"status": response.status, "body": body.decode("utf-8", errors="replace")}
            except ToolError:
                raise
            except TimeoutError as exc:
                raise ToolError("TIMEOUT", "HTTP GET timed out") from exc
            except OSError as exc:
                last_error = exc
            finally:
                if tls_socket is not None:
                    tls_socket.close()
                elif raw_socket is not None:
                    raw_socket.close()
        raise ToolError(
            "CONNECTION_FAILED",
            "could not connect to a resolved address",
        ) from last_error

    def _resolve(self, host: str) -> list[str]:
        """Resolve once; connections use only the returned IP addresses."""
        return list(
            dict.fromkeys(
                result[4][0]
                for result in socket.getaddrinfo(
                    host, 443, type=socket.SOCK_STREAM
                )
            )
        )

    def _connect(self, ip: str, port: int) -> socket.socket:
        """Connect to a validated numeric IP, never the hostname."""
        return socket.create_connection((ip, port), timeout=self._timeout)
