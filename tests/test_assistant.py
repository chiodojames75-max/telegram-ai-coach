"""Tests for the morning-brief assistant. Every external service is faked, so no accounts are needed."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

import pytest

from assistant import brief, calendar_builder, canvas, gmail, outlook


class FakeResp:
    def __init__(self, payload):
        self.payload = payload
        self.text = payload if isinstance(payload, str) else ""

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload):
        self.payload, self.calls = payload, []

    def get(self, url, **kw):
        self.calls.append((url, kw))
        return FakeResp(self.payload)


@pytest.fixture
def canvas_env(monkeypatch):
    monkeypatch.setenv("CANVAS_BASE_URL", "https://school.instructure.com/")
    monkeypatch.setenv("CANVAS_TOKEN", "t")


def test_canvas_keeps_unsubmitted_work_sorted_by_due(canvas_env):
    s = FakeSession([
        {"plannable_type": "assignment", "context_name": "ECON 104", "html_url": "/a/2",
         "plannable": {"title": "Problem Set 4", "due_at": "2026-11-12T03:59:00Z"}, "submissions": {"submitted": False}},
        {"plannable_type": "quiz", "context_name": "MKTG 301", "html_url": "/a/1",
         "plannable": {"title": "Ch 9 Quiz", "due_at": "2026-11-10T03:59:00Z"}, "submissions": {}},
        {"plannable_type": "assignment", "context_name": "MGMT 301", "html_url": "/a/3",
         "plannable": {"title": "Done already", "due_at": "2026-11-09T03:59:00Z"}, "submissions": {"submitted": True}},
        {"plannable_type": "announcement", "context_name": "X", "plannable": {"title": "Not work"}},
    ])
    out = canvas.upcoming_assignments(session=s)
    assert [a["title"] for a in out] == ["Ch 9 Quiz", "Problem Set 4"]
    assert out[0]["url"] == "https://school.instructure.com/a/1"
    assert s.calls[0][1]["headers"]["Authorization"] == "Bearer t"


def test_outlook_parses_graph_messages():
    s = FakeSession({"value": [{"subject": "Meeting moved", "from": {"emailAddress": {"name": "Prof. Lee"}},
                                "bodyPreview": "Office hours are now 3pm", "receivedDateTime": "2026-11-07T14:00:00Z"}]})
    out = outlook.recent_unread(token="x", session=s)
    assert out[0]["from"] == "Prof. Lee" and out[0]["source"] == "Outlook"
    assert "isRead eq false" in s.calls[0][1]["params"]["$filter"]


def test_gmail_reads_headers():
    svc = mock.MagicMock()
    users = svc.users.return_value.messages.return_value
    users.list.return_value.execute.return_value = {"messages": [{"id": "1"}]}
    users.get.return_value.execute.return_value = {
        "snippet": "Can you send the deck?", "internalDate": "1794000000000",
        "payload": {"headers": [{"name": "From", "value": "Sam"}, {"name": "Subject", "value": "Deck"}]}}
    out = gmail.recent_unread(service=svc)
    assert out == [{"source": "Gmail", "from": "Sam", "subject": "Deck", "snippet": "Can you send the deck?",
                    "time": datetime.fromtimestamp(1794000000)}]


def _assignment(i=1):
    return {"course": "ECON 104", "title": f"PS {i}", "url": f"https://x/a/{i}",
            "due": datetime(2026, 11, 12, 23, 59, tzinfo=timezone.utc)}


def test_study_block_is_a_day_before_and_tagged():
    ev = calendar_builder.study_block(_assignment())
    assert ev["summary"] == "Study: PS 1"
    assert ev["start"]["dateTime"].startswith("2026-11-11T23:59")
    assert ev["extendedProperties"]["private"][calendar_builder.TAG] == "https://x/a/1"


def test_calendar_skips_assignments_that_already_have_a_block():
    svc = mock.MagicMock()
    ev = svc.events.return_value
    ev.list.return_value.execute.side_effect = [{"items": [{"id": "old"}]}, {"items": []}]
    assert calendar_builder.add_study_blocks([_assignment(1), _assignment(2)], service=svc) == 1
    assert ev.insert.call_count == 1


def test_gather_skips_unconnected_sources_and_survives_failures(monkeypatch):
    monkeypatch.setattr(canvas, "configured", lambda: True)
    monkeypatch.setattr(canvas, "upcoming_assignments", lambda: [_assignment()])
    monkeypatch.setattr(gmail, "configured", lambda: True)
    monkeypatch.setattr(gmail, "recent_unread", mock.Mock(side_effect=RuntimeError("token expired")))
    monkeypatch.setattr(outlook, "configured", lambda: False)
    data = brief.gather()
    assert len(data["assignments"]) == 1 and data["emails"] == []
    assert data["errors"] == ["Gmail: token expired"]


def test_brief_sends_everything_to_claude():
    client = mock.MagicMock()
    client.messages.create.return_value = SimpleNamespace(content=[SimpleNamespace(text="Good morning")])
    data = {"assignments": [_assignment()], "errors": [],
            "emails": [{"source": "Gmail", "from": "Sam", "subject": "Deck", "snippet": "send it", "time": None}]}
    assert brief.write_brief(data, client=client) == "Good morning"
    sent = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "ECON 104: PS 1" in sent and "[Gmail] Sam: Deck" in sent


def test_assistant_bot_registers_commands_and_daily_job(monkeypatch):
    from telegram.ext import ApplicationBuilder
    from assistant import bot
    monkeypatch.setenv("BRIEF_CHAT_ID", "123")
    monkeypatch.setenv("BRIEF_TIME", "07:15")
    app = ApplicationBuilder().token("1:a").build()
    bot.attach(app)
    cmds = {c for h in app.handlers[0] for c in h.commands}
    assert {"start", "brief", "calendar"} <= cmds
    job = app.job_queue.jobs()
    assert len(job) == 0 or job[0].name == "morning_brief"  # jobs list fills once the app starts


def test_brief_chat_id_comes_from_start(tmp_path, monkeypatch):
    from assistant import bot
    monkeypatch.delenv("BRIEF_CHAT_ID", raising=False)
    monkeypatch.setattr(bot, "CHAT_FILE", str(tmp_path / "chat.txt"))
    assert bot.brief_chat_id() is None
    (tmp_path / "chat.txt").write_text("4242")
    assert bot.brief_chat_id() == 4242


ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:{soon}
SUMMARY:Problem Set 4 [ECON 104 Section 4]
URL;VALUE=URI:https://psu.instructure.com/courses/1/assignments/9
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:{later}
SUMMARY:Chapter 9 Quiz [MKTG 301]
URL;VALUE=URI:https://psu.instructure.com/courses/2/assignments/3
END:VEVENT
BEGIN:VEVENT
DTSTART:20200101T120000Z
SUMMARY:Old thing [X]
END:VEVENT
END:VCALENDAR"""


def test_canvas_calendar_feed_works_without_a_token(monkeypatch):
    from datetime import timedelta
    monkeypatch.delenv("CANVAS_TOKEN", raising=False)
    monkeypatch.setenv("CANVAS_ICS_URL", "https://psu.instructure.com/feeds/calendars/user_x.ics")
    now = datetime.now(timezone.utc)
    feed = ICS.format(soon=(now + timedelta(days=1)).strftime("%Y%m%dT%H%M%SZ"),
                      later=(now + timedelta(days=3)).strftime("%Y%m%d"))
    assert canvas.configured()
    out = canvas.upcoming_assignments(session=FakeSession(feed))
    assert [(a["course"], a["title"]) for a in out] == [("ECON 104 Section 4", "Problem Set 4"), ("MKTG 301", "Chapter 9 Quiz")]
    assert out[0]["url"].endswith("/assignments/9")
