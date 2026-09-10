#!/usr/bin/env python3
"""
Utility script to repair lowercased invite codes/links in the database.

Usage:
  python scripts/repair_invite_casing.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Ensure root directory is on python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app.db import AsyncSessionLocal
from app.models import Group
from app.seo import invite_code_of


async def repair_group_casing():
    print("Checking group invite links in database for casing repairs...")
    async with AsyncSessionLocal() as session:
        groups = (await session.scalars(select(Group))).all()
        updated_count = 0

        for group in groups:
            code = invite_code_of(group.link)
            if code and group.invite_code != code:
                print(f"Updating Group ID {group.id} ({group.slug}): '{group.invite_code}' -> '{code}'")
                group.invite_code = code
                group.link = f"https://chat.whatsapp.com/{code}"
                updated_count += 1

        if updated_count > 0:
            await session.commit()
            print(f"Successfully repaired {updated_count} groups in the database.")
        else:
            print("All group invite codes in the database already match their link casing.")


if __name__ == "__main__":
    asyncio.run(repair_group_casing())
