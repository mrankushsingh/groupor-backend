from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Group(Base):
    __tablename__ = "groups"
    __table_args__ = (
        Index("ix_groups_status_created", "status", "created_at"),
        Index("ix_groups_category", "category"),
        Index("ix_groups_country", "country"),
        Index("ix_groups_language", "language"),
        Index("ix_groups_invite_code", "invite_code", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    platform: Mapped[str] = mapped_column(String(32), default="whatsapp")
    category: Mapped[str] = mapped_column(String(80), default="all")
    country: Mapped[str] = mapped_column(String(80), default="")
    language: Mapped[str] = mapped_column(String(80), default="")
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    link: Mapped[str] = mapped_column(String(300))
    invite_code: Mapped[str] = mapped_column(String(128))
    image: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    members: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="active")  # active | reported | inactive
    source: Mapped[str] = mapped_column(String(32), default="user_submission")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, index=True)
    invite_code: Mapped[str] = mapped_column(String(128), index=True)
    reason: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IpRateLimit(Base):
    """Simple durable counters — replace/augment with Redis later."""

    __tablename__ = "ip_rate_limits"
    __table_args__ = (Index("ix_ip_rate_kind_ip", "kind", "ip"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(16))  # upload | report
    ip: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AppMeta(Base):
    """Key/value bag for future cache versioning without Redis."""

    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)
