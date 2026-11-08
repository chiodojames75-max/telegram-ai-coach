"""Google Calendar: adds a study block before each upcoming assignment.

Each block is tagged with the assignment's URL, so running it again never creates duplicates.
Uses the same Google sign-in as Gmail, with calendar access added.
"""
import os
from datetime import timedelta

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
CREDS_FILE = os.environ.get("GOOGLE_CREDENTIALS", "google_credentials.json")
TOKEN_FILE = os.environ.get("CALENDAR_TOKEN", "calendar_token.json")
CALENDAR_ID = os.environ.get("CALENDAR_ID", "primary")
TAG = "assistantSource"


def configured() -> bool:
    return os.path.exists(TOKEN_FILE) or os.path.exists(CREDS_FILE)


def _service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES) if os.path.exists(TOKEN_FILE) else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES).run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def study_block(assignment: dict, hours_before: int = 24, length_min: int = 60) -> dict:
    start = assignment["due"] - timedelta(hours=hours_before)
    return {
        "summary": f"Study: {assignment['title']}",
        "description": f"{assignment['course']}\nDue {assignment['due']:%a %b %d %I:%M %p}\n{assignment['url']}",
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": (start + timedelta(minutes=length_min)).isoformat()},
        "extendedProperties": {"private": {TAG: assignment["url"]}},
        "reminders": {"useDefault": True},
    }


def add_study_blocks(assignments: list[dict], service=None) -> int:
    """Create one study block per assignment that doesn't already have one. Returns how many were added."""
    svc = service or _service()
    added = 0
    for a in assignments:
        existing = svc.events().list(
            calendarId=CALENDAR_ID, privateExtendedProperty=f"{TAG}={a['url']}", maxResults=1
        ).execute().get("items", [])
        if existing:
            continue
        svc.events().insert(calendarId=CALENDAR_ID, body=study_block(a)).execute()
        added += 1
    return added
