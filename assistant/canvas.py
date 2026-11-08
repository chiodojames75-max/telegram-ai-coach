"""Canvas LMS: upcoming assignments for the signed-in student.

Needs CANVAS_BASE_URL (e.g. https://psu.instructure.com) and CANVAS_TOKEN
(Canvas > Account > Settings > New Access Token).
"""
import os
from datetime import datetime, timedelta, timezone

import requests


def configured() -> bool:
    return bool(os.environ.get("CANVAS_BASE_URL") and os.environ.get("CANVAS_TOKEN"))


def upcoming_assignments(days: int = 7, session=requests) -> list[dict]:
    """Assignments due in the next `days` days, soonest first."""
    base = os.environ["CANVAS_BASE_URL"].rstrip("/")
    headers = {"Authorization": f"Bearer {os.environ['CANVAS_TOKEN']}"}
    now = datetime.now(timezone.utc)
    params = {
        "start_date": now.isoformat(),
        "end_date": (now + timedelta(days=days)).isoformat(),
        "per_page": 100,
    }
    r = session.get(f"{base}/api/v1/planner/items", headers=headers, params=params, timeout=15)
    r.raise_for_status()
    items = []
    for it in r.json():
        if it.get("plannable_type") not in ("assignment", "quiz", "discussion_topic"):
            continue
        due = (it.get("plannable") or {}).get("due_at") or it.get("plannable_date")
        if not due:
            continue
        sub = it.get("submissions") or {}
        if isinstance(sub, dict) and sub.get("submitted"):
            continue
        items.append({
            "course": it.get("context_name", ""),
            "title": (it.get("plannable") or {}).get("title", "Untitled"),
            "due": datetime.fromisoformat(due.replace("Z", "+00:00")),
            "url": base + it.get("html_url", ""),
        })
    return sorted(items, key=lambda x: x["due"])
