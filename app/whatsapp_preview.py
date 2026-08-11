"""Fetch WhatsApp invite Open Graph name + image (same idea as the manual form)."""

from __future__ import annotations

import html
import re
from urllib.parse import urlparse

import httpx

_META_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?P<prop>[^"\']+)["\'][^>]*content=["\'](?P<content>[^"\']*)["\']',
    re.I,
)
_META_RE_ALT = re.compile(
    r'<meta[^>]+content=["\'](?P<content>[^"\']*)["\'][^>]*(?:property|name)=["\'](?P<prop>[^"\']+)["\']',
    re.I,
)
_TITLE_RE = re.compile(r"<title[^>]*>(?P<title>[^<]*)</title>", re.I)


def _decode(value: str) -> str:
    return html.unescape(value or "").replace("\xa0", " ").strip()


def _meta(html_text: str, property_name: str) -> str:
    needle = property_name.lower()
    for pattern in (_META_RE, _META_RE_ALT):
        for match in pattern.finditer(html_text):
            if match.group("prop").lower() == needle:
                return _decode(match.group("content"))
    return ""


def invite_preview_url(link: str) -> str | None:
    try:
        parsed = urlparse((link or "").strip())
    except Exception:
        return None
    host = parsed.hostname.replace("www.", "").lower() if parsed.hostname else ""
    if host != "chat.whatsapp.com":
        return None
    path = parsed.path or "/"
    return f"https://chat.whatsapp.com{path}"


async def fetch_whatsapp_preview(link: str) -> dict:
    """
    Returns {ok, name, image, description, error?}.
    Mirrors the frontend manual add-group OG scrape.
    """
    preview_url = invite_preview_url(link)
    if not preview_url:
        return {
            "ok": False,
            "name": "",
            "image": "",
            "description": "",
            "error": "Only chat.whatsapp.com invite links are supported",
        }

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client:
            res = await client.get(
                preview_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; WhatsAppBot/1.0; +https://www.whatsapp.com)",
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
    except Exception:
        return {
            "ok": False,
            "name": "",
            "image": "",
            "description": "",
            "error": "Could not reach WhatsApp right now",
        }

    if 300 <= res.status_code < 400:
        return {
            "ok": False,
            "name": "",
            "image": "",
            "description": "",
            "error": "Could not read this invite right now",
        }
    if res.status_code >= 400:
        return {
            "ok": False,
            "name": "",
            "image": "",
            "description": "",
            "error": f"WhatsApp returned {res.status_code}",
        }

    body = res.text[:400_000]
    og_title = _meta(body, "og:title")
    title_match = _TITLE_RE.search(body)
    title = og_title or _decode(title_match.group("title") if title_match else "")
    raw_image = _meta(body, "og:image")
    image = ""
    try:
        image_url = urlparse(raw_image)
        if image_url.scheme == "https":
            image = raw_image
    except Exception:
        image = ""
    description = _meta(body, "og:description")[:300]

    if not title or re.match(r"^whatsapp( group invite)?$", title, re.I):
        return {
            "ok": False,
            "name": "",
            "image": image,
            "description": description,
            "error": "This invite link is invalid or expired",
        }

    return {
        "ok": True,
        "name": title[:80],
        "image": image,
        "description": description,
    }
