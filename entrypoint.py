"""Railway/Docker entrypoint — binds uvicorn to $PORT with clear boot logs."""

from __future__ import annotations

import os
import sys


def main() -> None:
    port = os.environ.get("PORT", "8000").strip() or "8000"
    print(f"groupor: starting uvicorn on 0.0.0.0:{port}", flush=True)
    print(
        f"groupor: RAILWAY_ENVIRONMENT={os.environ.get('RAILWAY_ENVIRONMENT', '')!r}",
        flush=True,
    )
    print(
        "groupor: DATABASE_URL set="
        + ("yes" if os.environ.get("DATABASE_URL") else "no"),
        flush=True,
    )
    print(
        "groupor: DATABASE_PRIVATE_URL set="
        + ("yes" if os.environ.get("DATABASE_PRIVATE_URL") else "no"),
        flush=True,
    )

    try:
        import uvicorn
    except Exception as exc:  # noqa: BLE001
        print(f"groupor: failed to import uvicorn: {exc}", file=sys.stderr, flush=True)
        raise

    uvicorn.run("app.main:app", host="0.0.0.0", port=int(port), proxy_headers=True)


if __name__ == "__main__":
    main()
