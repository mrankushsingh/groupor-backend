from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlencode

from app.config import get_settings
from app.catalog import category_name


def slugify(value: str, max_len: int = 60) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text[:max_len].rstrip("-") or "group"


def invite_code_of(link: str) -> str:
    value = (link or "").strip().replace(" ", "")
    if not value:
        return ""
    if not re.match(r"^https?://", value, re.I):
        value = "https://" + value
    m = re.search(r"chat\.whatsapp\.com/(?:invite/)?([A-Za-z0-9_-]+)", value, re.I)
    return (m.group(1) if m else "").lower()


def canonical_invite(link: str) -> str:
    code = invite_code_of(link)
    return f"https://chat.whatsapp.com/{code}" if code else ""


def absolute_url(path: str) -> str:
    base = get_settings().site_url.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return base + path


def group_path(slug: str) -> str:
    return f"/group/{slug}"


def find_path(**params: str) -> str:
    clean = {k: v for k, v in params.items() if v}
    qs = urlencode(clean)
    return f"/group/find?{qs}" if qs else "/group/find"


def group_seo(group) -> dict:
    cat = category_name(group.category)
    title = f"{group.name} — {cat} WhatsApp Group | {get_settings().site_name}"
    desc = (group.description or "").strip()
    if not desc:
        bits = [cat, group.country, group.language]
        desc = (
            "Join "
            + " ".join(b for b in bits if b)
            + f" WhatsApp group {group.name} on {get_settings().site_name}."
        )
    desc = desc[:160]
    url = absolute_url(group_path(group.slug))
    return {
        "title": title,
        "description": desc,
        "canonical": url,
        "og_title": group.name,
        "og_description": desc,
        "og_url": url,
        "og_image": group.image or absolute_url("/static/og-default.png"),
        "og_type": "website",
    }


def group_jsonld(group) -> dict:
    seo = group_seo(group)
    return {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebPage",
                "name": seo["title"],
                "description": seo["description"],
                "url": seo["canonical"],
                **({"primaryImageOfPage": group.image} if group.image else {}),
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": 1,
                        "name": "Home",
                        "item": absolute_url("/"),
                    },
                    {
                        "@type": "ListItem",
                        "position": 2,
                        "name": category_name(group.category),
                        "item": absolute_url(f"/group/find?category={group.category}"),
                    },
                    {
                        "@type": "ListItem",
                        "position": 3,
                        "name": group.name,
                        "item": seo["canonical"],
                    },
                ],
            },
        ],
    }
