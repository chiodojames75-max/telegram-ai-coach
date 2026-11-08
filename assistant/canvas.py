"""Canvas LMS: upcoming assignments for the signed-in student.

Two ways to connect:
- CANVAS_ICS_URL: your Canvas calendar feed (Calendar > "Calendar Feed"). Works even when
  your school blocks personal access tokens. No submission status, so finished work still shows.
- CANVAS_BASE_URL + CANVAS_TOKEN: the Canvas API (Account > Settings > New Access Token).
  Hides work you've already submitted.
"""
import re
import os
from datetime import datetime, timedelta, timezone

import requests


def configured() -> bool:
    return bool(os.environ.get("CANVAS_ICS_URL") or (os.environ.get("CANVAS_BASE_URL") and os.environ.get("CANVAS_TOKEN")))


def _parse_ics_time(value: str) -> datetime:
    value = value.strip()
    if len(value) == 8:  # all-day item: treat as due at 11:59 PM UTC that day
        return datetime.strptime(value, "%Y%m%d").replace(hour=23, minute=59, tzinfo=timezone.utc)
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    return datetime.strptime(value[:15], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)


def parse_ics(text: str) -> list[dict]:
    """Turn a Canvas calendar feed into assignment dicts."""
    text = re.sub(r"\r?\n[ \t]", "", text)  # unfold wrapped lines
    out = []
    for block in text.split("BEGIN:VEVENT")[1:]:
        fields = {}
        for line in block.split("END:VEVENT")[0].splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                fields[key.split(";")[0]] = val.strip()
        if "DTSTART" not in fields:
            continue
        summary = fields.get("SUMMARY", "Untitled").replace("\\,", ",")
        m = re.match(r"^(.*?)\s*\[(.+)\]$", summary)
        title, course = (m.group(1), m.group(2)) if m else (summary, "")
        out.append({"course": course, "title": title, "due": _parse_ics_time(fields["DTSTART"]),
                    "url": fields.get("URL", "")})
    return out


def upcoming_assignments(days: int = 7, session=requests) -> list[dict]:
    """Assignments due in the next `days` days, soonest first."""
    now = datetime.now(timezone.utc)
    if os.environ.get("CANVAS_ICS_URL") and not os.environ.get("CANVAS_TOKEN"):
        r = session.get(os.environ["CANVAS_ICS_URL"], timeout=15)
        r.raise_for_status()
        items = [a for a in parse_ics(r.text) if now <= a["due"] <= now + timedelta(days=days)]
        return sorted(items, key=lambda x: x["due"])
    base = os.environ["CANVAS_BASE_URL"].rstrip("/")
    headers = {"Authorization": f"Bearer {os.environ['CANVAS_TOKEN']}"}
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
