"""Gmail: unread messages from the last day (read-only).

First run opens a browser to sign in and saves gmail_token.json. Needs a
Google Cloud OAuth "Desktop app" client saved as google_credentials.json.
"""
import os
from datetime import datetime

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CREDS_FILE = os.environ.get("GOOGLE_CREDENTIALS", "google_credentials.json")
TOKEN_FILE = os.environ.get("GMAIL_TOKEN", "gmail_token.json")


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
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def recent_unread(limit: int = 15, service=None) -> list[dict]:
    svc = service or _service()
    res = svc.users().messages().list(userId="me", q="is:unread newer_than:1d -category:promotions -category:social", maxResults=limit).execute()
    out = []
    for m in res.get("messages", []):
        msg = svc.users().messages().get(userId="me", id=m["id"], format="metadata", metadataHeaders=["From", "Subject"]).execute()
        h = {x["name"]: x["value"] for x in msg.get("payload", {}).get("headers", [])}
        out.append({
            "source": "Gmail",
            "from": h.get("From", ""),
            "subject": h.get("Subject", "(no subject)"),
            "snippet": msg.get("snippet", ""),
            "time": datetime.fromtimestamp(int(msg.get("internalDate", "0")) / 1000),
        })
    return out
