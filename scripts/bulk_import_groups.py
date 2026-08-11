#!/usr/bin/env python3
"""
Bulk-import WhatsApp group invite links into Groupor.

Each link is created like the manual form: the API fetches the WhatsApp
group name + photo (Open Graph) automatically.

Usage:
  1. Put one invite URL per line in links.txt
  2. On Railway, set BULK_API_KEY to a long secret
  3. Run:

     python scripts/bulk_import_groups.py \\
       --api https://YOUR-SERVICE.up.railway.app \\
       --key YOUR_BULK_API_KEY \\
       --file links.txt \\
       --country India \\
       --category social-friendship-community

Optional columns (CSV):
  link,country,category,language,tags,description
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def read_rows(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return []

    if path.suffix.lower() == ".csv" or "," in text.splitlines()[0]:
        reader = csv.DictReader(text.splitlines())
        rows = []
        for row in reader:
            link = (row.get("link") or row.get("url") or "").strip()
            if not link:
                continue
            rows.append(
                {
                    "link": link,
                    "country": (row.get("country") or "").strip(),
                    "category": (row.get("category") or "").strip(),
                    "language": (row.get("language") or "").strip(),
                    "tags": (row.get("tags") or "").strip(),
                    "description": (row.get("description") or "").strip(),
                    "name": (row.get("name") or "").strip(),
                }
            )
        return rows

    rows = []
    for line in text.splitlines():
        link = line.strip()
        if not link or link.startswith("#"):
            continue
        rows.append({"link": link})
    return rows


def post_json(url: str, payload: dict, api_key: str) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-Key": api_key,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc


def chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def main() -> int:
    parser = argparse.ArgumentParser(description="Bulk import WhatsApp groups into Groupor")
    parser.add_argument("--api", required=True, help="Railway API base, e.g. https://xxx.up.railway.app")
    parser.add_argument("--key", required=True, help="BULK_API_KEY value")
    parser.add_argument("--file", required=True, help="links.txt or groups.csv")
    parser.add_argument("--country", default="India")
    parser.add_argument("--category", default="social-friendship-community")
    parser.add_argument("--language", default="")
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--delay", type=float, default=0.6, help="Seconds between WhatsApp scrapes")
    args = parser.parse_args()

    base = args.api.rstrip("/")
    rows = read_rows(Path(args.file))
    if not rows:
        print("No links found.", file=sys.stderr)
        return 1

    print(f"Loaded {len(rows)} links from {args.file}")
    total_created = 0
    total_failed = 0

    for batch_index, batch in enumerate(chunks(rows, max(1, min(args.batch_size, 50))), start=1):
        payload = {
            "fetch_preview": True,
            "delay_seconds": args.delay,
            "groups": [
                {
                    "link": row["link"],
                    "name": row.get("name") or "",
                    "description": row.get("description") or "",
                    "category": row.get("category") or args.category,
                    "country": row.get("country") or args.country,
                    "language": row.get("language") or args.language,
                    "tags": row.get("tags") or "",
                }
                for row in batch
            ],
        }
        print(f"Batch {batch_index}: sending {len(batch)} groups…")
        try:
            result = post_json(f"{base}/api/groups/bulk", payload, args.key)
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR: {exc}", file=sys.stderr)
            total_failed += len(batch)
            time.sleep(2)
            continue

        created = int(result.get("created") or 0)
        failed = int(result.get("failed") or 0)
        total_created += created
        total_failed += failed
        print(f"  created={created} failed={failed}")
        for err in result.get("errors") or []:
            print(f"  - {err.get('link')}: {err.get('error')}")

    print(f"Done. created={total_created} failed={total_failed}")
    return 0 if total_failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
