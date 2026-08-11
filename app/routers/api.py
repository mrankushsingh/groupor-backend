from __future__ import annotations

import asyncio
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog import category_name
from app.config import get_settings
from app.db import get_db
from app.seo import absolute_url, group_path, group_seo, invite_code_of
from app.services import (
    create_group,
    get_group_by_slug,
    get_reported_snapshot,
    list_groups,
    pagination_meta,
    peek_ip_quota,
    record_ip_quota,
    submit_group_report,
)
from app.whatsapp_preview import fetch_whatsapp_preview

router = APIRouter(prefix="/api", tags=["api"])
settings = get_settings()


class GroupOut(BaseModel):
    id: int
    slug: str
    name: str
    description: str
    platform: str
    category: str
    category_name: str
    country: str
    language: str
    tags: list[str] | None = None
    link: str
    invite_code: str
    image: str | None = None
    members: int
    status: str
    source: str
    created_at: str | None = None
    path: str

    model_config = {"from_attributes": True}


class GroupCreateIn(BaseModel):
    link: str = Field(min_length=10, max_length=300)
    name: str = Field(default="", max_length=80)
    description: str = Field(default="", max_length=6000)
    category: str = Field(default="all", max_length=80)
    country: str = Field(min_length=1, max_length=80)
    language: str = Field(default="", max_length=80)
    tags: str = Field(default="", max_length=500)
    image: str | None = Field(default=None, max_length=1000)
    # When true (default), fetch WhatsApp OG name/photo like the manual form.
    fetch_preview: bool = True


class BulkGroupItem(BaseModel):
    link: str = Field(min_length=10, max_length=300)
    name: str = Field(default="", max_length=80)
    description: str = Field(default="", max_length=6000)
    category: str = Field(default="all", max_length=80)
    country: str = Field(default="India", max_length=80)
    language: str = Field(default="", max_length=80)
    tags: str = Field(default="", max_length=500)
    image: str | None = Field(default=None, max_length=1000)


class BulkCreateIn(BaseModel):
    groups: list[BulkGroupItem] = Field(min_length=1, max_length=50)
    fetch_preview: bool = True
    # Delay between WhatsApp scrapes so bulk imports are less likely to get blocked.
    delay_seconds: float = Field(default=0.6, ge=0, le=5)


class PreviewIn(BaseModel):
    link: str = Field(min_length=10, max_length=300)


class ReportCreateIn(BaseModel):
    group_id: str = Field(min_length=1, max_length=64)
    invite_code: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    reason: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=500)


def serialize_group(group) -> dict:
    return {
        "id": group.id,
        "slug": group.slug,
        "name": group.name,
        "description": group.description or "",
        "platform": group.platform,
        "category": group.category,
        "category_name": category_name(group.category),
        "country": group.country or "",
        "language": group.language or "",
        "tags": group.tags,
        "link": group.link,
        "invite_code": group.invite_code,
        "image": group.image,
        "members": group.members,
        "status": group.status,
        "source": group.source,
        "created_at": group.created_at.isoformat() if group.created_at else None,
        "path": group_path(group.slug),
    }


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def has_bulk_key(x_api_key: str | None) -> bool:
    expected = (settings.bulk_api_key or "").strip()
    if not expected or not x_api_key:
        return False
    return secrets.compare_digest(expected, x_api_key.strip())


def require_bulk_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not has_bulk_key(x_api_key):
        raise HTTPException(
            status_code=401,
            detail="Valid X-API-Key required. Set BULK_API_KEY on Railway and send it as X-API-Key.",
        )


async def enrich_from_whatsapp(
    *,
    link: str,
    name: str,
    image: str | None,
    description: str,
    fetch_preview: bool,
) -> tuple[str, str | None, str, dict | None]:
    """Fill missing name/image/description from WhatsApp OG tags."""
    preview = None
    needs_fetch = fetch_preview and (not name.strip() or not (image or "").strip())
    if needs_fetch:
        preview = await fetch_whatsapp_preview(link)
        if preview.get("ok"):
            if not name.strip():
                name = str(preview.get("name") or "")
            if not (image or "").strip():
                image = str(preview.get("image") or "") or None
            if not description.strip() and preview.get("description"):
                description = str(preview["description"])
    if not name.strip():
        code = invite_code_of(link) or "group"
        name = f"WhatsApp Group {code[:8]}"
    return name, image, description, preview


@router.get("/groups")
async def api_list_groups(
    category: str = "",
    country: str = "",
    language: str = "",
    q: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    groups, total = await list_groups(
        db,
        category=category,
        country=country,
        language=language,
        q=q,
        page=page,
        page_size=page_size,
    )
    return {
        "ok": True,
        "groups": [serialize_group(g) for g in groups],
        "pagination": pagination_meta(total, page, page_size),
    }


@router.get("/groups/{slug}")
async def api_get_group(slug: str, db: AsyncSession = Depends(get_db)):
    group = await get_group_by_slug(db, slug)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return {
        "ok": True,
        "group": serialize_group(group),
        "seo": group_seo(group),
        "url": absolute_url(group_path(group.slug)),
    }


@router.post("/preview")
async def api_preview_group(body: PreviewIn):
    """Fetch WhatsApp invite name + photo (same as manual add-group)."""
    preview = await fetch_whatsapp_preview(body.link)
    return preview


@router.post("/groups")
async def api_create_group(
    request: Request,
    body: GroupCreateIn,
    db: AsyncSession = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    ip = client_ip(request)
    bypass_quota = has_bulk_key(x_api_key)
    if not bypass_quota:
        ok, message = await peek_ip_quota(db, ip, "upload")
        if not ok:
            raise HTTPException(status_code=429, detail=message)

    name, image, description, preview = await enrich_from_whatsapp(
        link=body.link,
        name=body.name,
        image=body.image,
        description=body.description,
        fetch_preview=body.fetch_preview,
    )
    tag_list = [t.strip() for t in body.tags.split(",") if t.strip()][:10]

    try:
        group = await create_group(
            db,
            name=name,
            link=body.link,
            description=description,
            category=body.category or "all",
            country=body.country,
            language=body.language,
            tags=tag_list or None,
            image=image,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not bypass_quota:
        await record_ip_quota(db, ip, "upload")

    return {
        "ok": True,
        "group": serialize_group(group),
        "code": group.invite_code,
        "path": group_path(group.slug),
        "slug": group.slug,
        "preview": preview,
    }


@router.post("/groups/bulk")
async def api_bulk_create_groups(
    body: BulkCreateIn,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_bulk_key),
):
    """
    Import many groups (max 50 per request). Auto-fetches WhatsApp name/photo
    like the manual form. Requires X-API-Key = BULK_API_KEY.
    """
    created: list[dict] = []
    failed: list[dict] = []

    for index, item in enumerate(body.groups):
        if index > 0 and body.fetch_preview and body.delay_seconds > 0:
            await asyncio.sleep(body.delay_seconds)

        name, image, description, preview = await enrich_from_whatsapp(
            link=item.link,
            name=item.name,
            image=item.image,
            description=item.description,
            fetch_preview=body.fetch_preview,
        )
        tag_list = [t.strip() for t in item.tags.split(",") if t.strip()][:10]
        try:
            group = await create_group(
                db,
                name=name,
                link=item.link,
                description=description,
                category=item.category or "all",
                country=item.country or "India",
                language=item.language,
                tags=tag_list or None,
                image=image,
            )
            created.append(
                {
                    "link": item.link,
                    "group": serialize_group(group),
                    "preview_ok": bool(preview and preview.get("ok")),
                }
            )
        except ValueError as exc:
            failed.append({"link": item.link, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            failed.append({"link": item.link, "error": f"{type(exc).__name__}: {exc}"})

    return {
        "ok": True,
        "created": len(created),
        "failed": len(failed),
        "results": created,
        "errors": failed,
    }


@router.get("/reports")
async def api_list_reports(db: AsyncSession = Depends(get_db)):
    snapshot = await get_reported_snapshot(db)
    return {"ok": True, **snapshot}


@router.post("/reports")
async def api_create_report(
    request: Request,
    body: ReportCreateIn,
    db: AsyncSession = Depends(get_db),
):
    ip = client_ip(request)
    ok, message = await peek_ip_quota(db, ip, "report")
    if not ok:
        raise HTTPException(status_code=429, detail=message)

    try:
        result = await submit_group_report(
            db,
            group_id=body.group_id,
            invite_code=body.invite_code,
            reason=body.reason,
            description=body.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await record_ip_quota(db, ip, "report")
    return {
        "ok": True,
        "already": result["already"],
        "invite_code": result["invite_code"],
        "group_id": result["group_id"],
        "ids": result["snapshot"]["ids"],
        "codes": result["snapshot"]["codes"],
        "message": (
            "This group was already reported. It stays removed for everyone."
            if result["already"]
            else "Thanks — the group was reported and removed for all visitors."
        ),
    }
