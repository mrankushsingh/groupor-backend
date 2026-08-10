from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog import category_name
from app.db import get_db
from app.seo import absolute_url, group_path, group_seo
from app.services import (
    create_group,
    get_group_by_slug,
    list_groups,
    pagination_meta,
    peek_ip_quota,
    record_ip_quota,
)

router = APIRouter(prefix="/api", tags=["api"])


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


@router.post("/groups")
async def api_create_group(
    request: Request,
    body: GroupCreateIn,
    db: AsyncSession = Depends(get_db),
):
    ip = client_ip(request)
    ok, message = await peek_ip_quota(db, ip, "upload")
    if not ok:
        raise HTTPException(status_code=429, detail=message)

    tag_list = [t.strip() for t in body.tags.split(",") if t.strip()][:10]
    name = body.name.strip() or "WhatsApp Group"
    try:
        group = await create_group(
            db,
            name=name,
            link=body.link,
            description=body.description,
            category=body.category or "all",
            country=body.country,
            language=body.language,
            tags=tag_list or None,
            image=body.image,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await record_ip_quota(db, ip, "upload")
    return {
        "ok": True,
        "group": serialize_group(group),
        "code": group.invite_code,
        "path": group_path(group.slug),
        "slug": group.slug,
    }
