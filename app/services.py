from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Group, IpRateLimit, Report
from app.seo import invite_code_of, slugify

WINDOW = timedelta(hours=24)
LIMIT = 5


def active_groups_stmt() -> Select[tuple[Group]]:
    return select(Group).where(Group.status == "active")


async def count_groups(session: AsyncSession, stmt: Select) -> int:
    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    return int(total or 0)


async def list_groups(
    session: AsyncSession,
    *,
    category: str = "",
    country: str = "",
    language: str = "",
    q: str = "",
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[Group], int]:
    stmt = active_groups_stmt()
    if category:
        stmt = stmt.where(Group.category == category)
    if country:
        stmt = stmt.where(Group.country == country)
    if language:
        stmt = stmt.where(Group.language == language)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            (Group.name.ilike(like))
            | (Group.description.ilike(like))
            | (Group.country.ilike(like))
            | (Group.language.ilike(like))
        )

    total = await count_groups(session, stmt)
    page = max(1, page)
    offset = (page - 1) * page_size
    rows = (
        await session.scalars(
            stmt.order_by(Group.created_at.desc(), Group.id.desc()).offset(offset).limit(page_size)
        )
    ).all()
    return list(rows), total


async def get_group_by_slug(session: AsyncSession, slug: str) -> Group | None:
    return await session.scalar(select(Group).where(Group.slug == slug))


async def unique_slug(session: AsyncSession, name: str) -> str:
    base = slugify(name)
    candidate = base
    n = 2
    while await session.scalar(select(Group.id).where(Group.slug == candidate)):
        candidate = f"{base}-{n}"
        n += 1
    return candidate


async def create_group(
    session: AsyncSession,
    *,
    name: str,
    link: str,
    description: str = "",
    category: str = "all",
    country: str = "",
    language: str = "",
    tags: list[str] | None = None,
    image: str | None = None,
) -> Group:
    code = invite_code_of(link)
    if not code:
        raise ValueError("Only valid chat.whatsapp.com invite links are supported.")

    existing = await session.scalar(select(Group).where(Group.invite_code == code))
    if existing:
        if existing.status == "reported":
            raise ValueError("This group link was reported and removed. It cannot be submitted again.")
        raise ValueError("This group is already listed.")

    reported = await session.scalar(select(Report.id).where(Report.invite_code == code).limit(1))
    if reported:
        raise ValueError("This group link was reported and removed. It cannot be submitted again.")

    group = Group(
        slug=await unique_slug(session, name),
        name=name.strip()[:80],
        description=(description or "").strip(),
        category=category or "all",
        country=(country or "").strip(),
        language=(language or "").strip(),
        tags=tags or None,
        link=f"https://chat.whatsapp.com/{code}",
        invite_code=code,
        image=image,
        status="active",
        source="user_submission",
    )
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return group


async def peek_ip_quota(session: AsyncSession, ip: str, kind: str) -> tuple[bool, str]:
    since = datetime.now(timezone.utc) - WINDOW
    used = await session.scalar(
        select(func.count())
        .select_from(IpRateLimit)
        .where(IpRateLimit.ip == ip, IpRateLimit.kind == kind, IpRateLimit.created_at >= since)
    )
    used_n = int(used or 0)
    if used_n >= LIMIT:
        noun = "groups" if kind == "upload" else "reports"
        return False, f"You can only {kind} {LIMIT} {noun} every 24 hours. Please wait for 24 hours."
    return True, ""


async def record_ip_quota(session: AsyncSession, ip: str, kind: str) -> None:
    session.add(IpRateLimit(ip=ip, kind=kind))
    await session.commit()


async def get_reported_snapshot(session: AsyncSession) -> dict[str, list[str]]:
    report_rows = (await session.scalars(select(Report))).all()
    reported_groups = (
        await session.scalars(select(Group).where(Group.status == "reported"))
    ).all()

    codes = {
        *(str(r.invite_code).strip().lower() for r in report_rows if r.invite_code),
        *(str(g.invite_code).strip().lower() for g in reported_groups if g.invite_code),
    }
    ids = {
        *(str(r.group_id) for r in report_rows if r.group_id),
        *(str(g.id) for g in reported_groups),
    }
    return {"ids": sorted(ids), "codes": sorted(c for c in codes if c)}


async def submit_group_report(
    session: AsyncSession,
    *,
    group_id: str,
    invite_code: str,
    reason: str,
    description: str,
) -> dict:
    code = (invite_code or "").strip().lower()
    if not code:
        raise ValueError("Invalid invite code.")

    already = await session.scalar(select(Report.id).where(Report.invite_code == code).limit(1))

    group = await session.scalar(select(Group).where(Group.invite_code == code))
    numeric_id = 0
    if group:
        numeric_id = int(group.id)
        group.status = "reported"
    else:
        try:
            numeric_id = int(str(group_id))
        except ValueError:
            # Frontend demo ids like "u123" — still store a report row.
            digits = "".join(ch for ch in str(group_id) if ch.isdigit())
            numeric_id = int(digits) % 2_147_483_647 if digits else 0

    session.add(
        Report(
            group_id=numeric_id,
            invite_code=code,
            reason=(reason or "").strip()[:64],
            description=(description or "").strip()[:500],
        )
    )
    await session.commit()

    snapshot = await get_reported_snapshot(session)
    return {
        "already": bool(already),
        "invite_code": code,
        "group_id": str(group.id if group else group_id),
        "snapshot": snapshot,
    }


def pagination_meta(total: int, page: int, page_size: int) -> dict:
    pages = max(1, (total + page_size - 1) // page_size) if total else 1
    page = min(max(1, page), pages)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
        "has_prev": page > 1,
        "has_next": page < pages,
        "prev_page": page - 1,
        "next_page": page + 1,
    }
