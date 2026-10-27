"""Safe, bounded fetching for link previews."""

import asyncio
import html
import ipaddress
import socket
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

from app.core.errors import AppError

MAX_BYTES = 512 * 1024
TIMEOUT = httpx.Timeout(3.0, connect=1.0)


class _Metadata(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.description = ""
        self._title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "title":
            self._title = True
        if tag == "meta" and (values.get("name") or "").lower() == "description":
            self.description = (values.get("content") or "")[:500]

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._title = False

    def handle_data(self, data: str) -> None:
        if self._title:
            self.title = (self.title + data).strip()[:200]


def _public_addresses(hostname: str) -> list[str]:
    addresses = {
        result[4][0]
        for result in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        if isinstance(result[4][0], str)
    }
    if not addresses:
        raise AppError("chat.link_preview_unavailable", 422)
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if any((ip.is_private, ip.is_loopback, ip.is_link_local, ip.is_multicast, ip.is_reserved)):
            raise AppError("chat.link_preview_forbidden", 422)
    return sorted(addresses)


class LinkPreviewService:
    def __init__(self, client: httpx.AsyncClient, allowed_domains: set[str]) -> None:
        self.client = client
        self.allowed_domains = {domain.lower().strip(".") for domain in allowed_domains}

    async def fetch(self, url: str) -> dict[str, str]:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().strip(".")
        if parsed.scheme not in {"http", "https"} or not host:
            raise AppError("chat.link_preview_forbidden", 422)
        if not any(
            host == domain or host.endswith(f".{domain}") for domain in self.allowed_domains
        ):
            raise AppError("chat.link_preview_forbidden", 422)
        await asyncio.to_thread(_public_addresses, host)
        try:
            response = await self.client.get(
                url, follow_redirects=False, timeout=TIMEOUT, headers={"Accept": "text/html"}
            )
        except (httpx.HTTPError, OSError) as exc:
            raise AppError("chat.link_preview_unavailable", 422) from exc
        if response.is_redirect or response.status_code >= 400:
            raise AppError("chat.link_preview_unavailable", 422)
        if int(response.headers.get("content-length", "0") or 0) > MAX_BYTES:
            raise AppError("chat.link_preview_too_large", 422)
        content = response.content
        if len(content) > MAX_BYTES:
            raise AppError("chat.link_preview_too_large", 422)
        parser = _Metadata()
        parser.feed(content.decode(response.encoding or "utf-8", errors="replace"))
        return {
            "url": url,
            "title": html.unescape(parser.title),
            "description": html.unescape(parser.description),
        }
