"""Outlook (school or personal Microsoft account): unread mail from the last day, via Microsoft Graph.

Needs OUTLOOK_CLIENT_ID from an Azure app registration (public client, Mail.Read).
First run prints a sign-in code; the token is cached in outlook_token.json.
"""
import os
from datetime import datetime, timedelta, timezone

import requests

SCOPES = ["Mail.Read"]
CACHE_FILE = os.environ.get("OUTLOOK_TOKEN", "outlook_token.json")


def configured() -> bool:
    return bool(os.environ.get("OUTLOOK_CLIENT_ID"))


def _token() -> str:
    import msal
    cache = msal.SerializableTokenCache()
    if os.path.exists(CACHE_FILE):
        cache.deserialize(open(CACHE_FILE).read())
    app = msal.PublicClientApplication(
        os.environ["OUTLOOK_CLIENT_ID"],
        authority=f"https://login.microsoftonline.com/{os.environ.get('OUTLOOK_TENANT', 'common')}",
        token_cache=cache,
    )
    accounts = app.get_accounts()
    result = app.acquire_token_silent(SCOPES, account=accounts[0]) if accounts else None
    if not result:
        flow = app.initiate_device_flow(scopes=SCOPES)
        print(flow["message"])  # one-time sign-in in the terminal
        result = app.acquire_token_by_device_flow(flow)
    if cache.has_state_changed:
        with open(CACHE_FILE, "w") as f:
            f.write(cache.serialize())
    if "access_token" not in result:
        raise RuntimeError(result.get("error_description", "Outlook sign-in failed"))
    return result["access_token"]


def recent_unread(limit: int = 15, token=None, session=requests) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = session.get(
        "https://graph.microsoft.com/v1.0/me/messages",
        headers={"Authorization": f"Bearer {token or _token()}"},
        params={
            "$filter": f"isRead eq false and receivedDateTime ge {since}",
            "$select": "subject,from,bodyPreview,receivedDateTime",
            "$orderby": "receivedDateTime desc",
            "$top": limit,
        },
        timeout=15,
    )
    r.raise_for_status()
    return [{
        "source": "Outlook",
        "from": ((m.get("from") or {}).get("emailAddress") or {}).get("name", ""),
        "subject": m.get("subject") or "(no subject)",
        "snippet": (m.get("bodyPreview") or "")[:200],
        "time": datetime.fromisoformat(m["receivedDateTime"].replace("Z", "+00:00")),
    } for m in r.json().get("value", [])]
