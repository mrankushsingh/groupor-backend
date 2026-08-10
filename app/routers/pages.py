from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog import CATEGORIES, COUNTRIES, LANGUAGES, category_name
from app.config import get_settings
from app.db import get_db
from app.seo import absolute_url, find_path, group_jsonld, group_path, group_seo
from app.services import (
    create_group,
    get_group_by_slug,
    list_groups,
    pagination_meta,
    peek_ip_quota,
    record_ip_quota,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
settings = get_settings()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def render(
    request: Request,
    name: str,
    context: dict[str, Any],
    *,
    status_code: int = 200,
    cache_control: str = "public, max-age=60, stale-while-revalidate=300",
) -> HTMLResponse:
    ctx = {
        "request": request,
        "site_name": settings.site_name,
        "site_url": settings.site_url,
        "categories": CATEGORIES,
        "countries": COUNTRIES,
        "languages": LANGUAGES,
        "category_name": category_name,
        **context,
    }
    response = templates.TemplateResponse(request, name, ctx, status_code=status_code)
    response.headers["Cache-Control"] = cache_control
    return response


@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    groups, total = await list_groups(db, page=page, page_size=settings.page_size)
    pager = pagination_meta(total, page, settings.page_size)
    return render(
        request,
        "index.html",
        {
            "groups": groups,
            "pager": pager,
            "seo": {
                "title": f"WhatsApp Group Links — Join Active Groups | {settings.site_name}",
                "description": "Find and join active WhatsApp groups by category, country and language.",
                "canonical": absolute_url("/"),
            },
            "filters": {"category": "", "country": "", "language": ""},
        },
        cache_control="public, max-age=30, stale-while-revalidate=120",
    )


@router.get("/group/find", response_class=HTMLResponse)
async def find_groups(
    request: Request,
    category: str = "",
    country: str = "",
    language: str = "",
    q: str = "",
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    groups, total = await list_groups(
        db,
        category=category,
        country=country,
        language=language,
        q=q,
        page=page,
        page_size=settings.page_size,
    )
    pager = pagination_meta(total, page, settings.page_size)
    label_bits = [
        category_name(category) if category else "",
        country,
        language,
        f"“{q}”" if q else "",
    ]
    label = " · ".join(b for b in label_bits if b) or "All filters"
    path = find_path(category=category, country=country, language=language, q=q)
    return render(
        request,
        "find.html",
        {
            "groups": groups,
            "pager": pager,
            "filters": {
                "category": category,
                "country": country,
                "language": language,
                "q": q,
            },
            "query_string": urlencode(
                {k: v for k, v in {
                    "category": category,
                    "country": country,
                    "language": language,
                    "q": q,
                }.items() if v}
            ),
            "seo": {
                "title": f"Find WhatsApp Groups — {label} | {settings.site_name}",
                "description": f"Browse WhatsApp groups filtered by {label} on {settings.site_name}.",
                "canonical": absolute_url(path),
            },
        },
        cache_control="public, max-age=30, stale-while-revalidate=120",
    )


@router.get("/group/addgroup", response_class=HTMLResponse)
async def add_group_form(request: Request):
    return render(
        request,
        "addgroup.html",
        {
            "error": request.query_params.get("error", ""),
            "seo": {
                "title": f"Add Your WhatsApp Group — {settings.site_name}",
                "description": "Add your WhatsApp group invite link for free.",
                "canonical": absolute_url("/group/addgroup"),
                "robots": "noindex, follow",
            },
        },
        cache_control="private, no-store",
    )


@router.post("/group/addgroup")
async def add_group_submit(
    request: Request,
    link: str = Form(...),
    name: str = Form(""),
    description: str = Form(""),
    category: str = Form(""),
    country: str = Form(...),
    language: str = Form(""),
    tags: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    ip = client_ip(request)
    ok, message = await peek_ip_quota(db, ip, "upload")
    if not ok:
        return RedirectResponse(
            url=f"/group/addgroup?error={message}",
            status_code=303,
        )

    tag_list = [t.strip() for t in tags.split(",") if t.strip()][:10]
    display_name = name.strip() or "WhatsApp Group"
    try:
        group = await create_group(
            db,
            name=display_name,
            link=link,
            description=description,
            category=category or "all",
            country=country,
            language=language,
            tags=tag_list or None,
        )
    except ValueError as exc:
        return RedirectResponse(
            url=f"/group/addgroup?error={exc}",
            status_code=303,
        )

    await record_ip_quota(db, ip, "upload")
    return RedirectResponse(url=group_path(group.slug), status_code=303)


@router.get("/group/{slug}", response_class=HTMLResponse)
async def group_detail(
    request: Request,
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    group = await get_group_by_slug(db, slug)
    if not group:
        return render(
            request,
            "not_found.html",
            {
                "seo": {
                    "title": f"Group not found — {settings.site_name}",
                    "description": "This group may have been removed.",
                    "canonical": absolute_url(f"/group/{slug}"),
                    "robots": "noindex",
                }
            },
            status_code=404,
            cache_control="public, max-age=60",
        )

    seo = group_seo(group)
    if group.status == "reported":
        seo["robots"] = "noindex, follow"

    related, _ = await list_groups(
        db,
        category=group.category,
        page=1,
        page_size=6,
    )
    related = [g for g in related if g.id != group.id][:5]

    return render(
        request,
        "group_detail.html",
        {
            "group": group,
            "related": related,
            "seo": seo,
            "jsonld": json.dumps(group_jsonld(group), ensure_ascii=False),
            "reported": group.status == "reported",
        },
        cache_control="public, max-age=120, stale-while-revalidate=600",
    )


@router.get("/sitemap.xml")
async def sitemap(db: AsyncSession = Depends(get_db)):
    groups, _ = await list_groups(db, page=1, page_size=50_000)
    urls = [
        absolute_url("/"),
        absolute_url("/group/find"),
        absolute_url("/group/addgroup"),
        *[absolute_url(group_path(g.slug)) for g in groups if g.status == "active"],
    ]
    body = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for url in urls:
        body.append("<url>")
        body.append(f"<loc>{escape(url)}</loc>")
        body.append("<changefreq>daily</changefreq>")
        body.append("</url>")
    body.append("</urlset>")
    return Response(
        content="\n".join(body),
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=300, stale-while-revalidate=900"},
    )


@router.get("/robots.txt")
async def robots():
    content = f"User-agent: *\nAllow: /\nSitemap: {absolute_url('/sitemap.xml')}\n"
    return Response(
        content=content,
        media_type="text/plain",
        headers={"Cache-Control": "public, max-age=3600"},
    )
