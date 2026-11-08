"""Builds the morning brief: gathers every connected source, then has Claude write it."""
import os

import anthropic

from . import canvas, gmail, outlook

BRIEF_PROMPT = """You write a short morning brief for a college student, sent as a Telegram message.
Sections, in this order, skipping any that are empty:
1. Due soon: assignments, soonest first, with the day and time due.
2. Email that needs you: only messages that need a reply or action, one line each. Skip newsletters and notifications.
3. Today's focus: the one or two things to do first.
Plain text, no markdown tables, under 180 words. If a source failed to load, say so in one line at the end."""


def gather() -> dict:
    data = {"assignments": [], "emails": [], "errors": []}
    for name, mod, key, fn in (
        ("Canvas", canvas, "assignments", lambda: canvas.upcoming_assignments()),
        ("Gmail", gmail, "emails", lambda: gmail.recent_unread()),
        ("Outlook", outlook, "emails", lambda: outlook.recent_unread()),
    ):
        if not mod.configured():
            continue
        try:
            data[key] += fn()
        except Exception as e:  # one broken source shouldn't stop the brief
            data["errors"].append(f"{name}: {e}")
    return data


def as_text(data: dict) -> str:
    lines = ["ASSIGNMENTS:"]
    lines += [f"- {a['course']}: {a['title']} (due {a['due']:%a %b %d %I:%M %p})" for a in data["assignments"]] or ["- none"]
    lines.append("EMAILS:")
    lines += [f"- [{e['source']}] {e['from']}: {e['subject']} | {e['snippet'][:120]}" for e in data["emails"]] or ["- none"]
    if data["errors"]:
        lines.append("ERRORS: " + "; ".join(data["errors"]))
    return "\n".join(lines)


def write_brief(data: dict, client=None) -> str:
    client = client or anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model=os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5"),
        max_tokens=600,
        system=BRIEF_PROMPT,
        messages=[{"role": "user", "content": as_text(data)}],
    )
    return resp.content[0].text
