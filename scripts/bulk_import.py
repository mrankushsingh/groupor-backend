"""
Bulk-import up to 1000 WhatsApp groups into Groupor.

Usage:
  1. On Railway → Variables, set ADMIN_API_KEY to a long random secret.
  2. Put your groups in groups.json (see format below).
  3. Run:

     python scripts/bulk_import.py --api https://YOUR-SERVICE.up.railway.app --key YOUR_ADMIN_API_KEY --file groups.json

groups.json format:
[
  {
    "link": "https://chat.whatsapp.com/AbCdEfGhIjK",
    "name": "Job Alerts India",
    "description": "Daily job updates",
    "category": "jobs-career",
    "country": "India",
    "language": "Hindi",
    "tags": "jobs,sarkari,recruitment"
  }
]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Bulk import groups via /api/groups/bulk")
    parser.add_argument("--api", required=True, help="Railway API base URL, no trailing slash")
    parser.add_argument("--key", required=True, help="ADMIN_API_KEY value")
    parser.add_argument("--file", required=True, help="Path to JSON array of groups")
    parser.add_argument("--chunk", type=int, default=200, help="Groups per request (max 1000)")
    args = parser.parse_args()

    path = Path(args.file)
    groups = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(groups, list):
        print("JSON root must be an array of groups", file=sys.stderr)
        return 1

    base = args.api.rstrip("/")
    chunk = max(1, min(args.chunk, 1000))
    total_created = total_skipped = total_failed = 0

    for start in range(0, len(groups), chunk):
        batch = groups[start : start + chunk]
        payload = json.dumps({"groups": batch}).encode("utf-8")
        req = urllib.request.Request(
            f"{base}/api/groups/bulk",
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Admin-Key": args.key,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as res:
                body = json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            print(f"Batch {start}-{start + len(batch) - 1} failed: {exc.code} {detail}", file=sys.stderr)
            return 1

        created = int(body.get("created") or 0)
        skipped = int(body.get("skipped") or 0)
        failed = int(body.get("failed") or 0)
        total_created += created
        total_skipped += skipped
        total_failed += failed
        print(
            f"Batch {start}-{start + len(batch) - 1}: "
            f"created={created} skipped={skipped} failed={failed}"
        )

    print(
        f"Done. total={len(groups)} created={total_created} "
        f"skipped={total_skipped} failed={total_failed}"
    )
    return 0 if total_failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
