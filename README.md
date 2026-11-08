# Telegram AI Coach

Personal AI assistants on Telegram, powered by the Claude API: a morning-brief assistant connected to Canvas, Gmail, Outlook and Google Calendar, plus four coaching bots that each keep their own memory.

## Morning-brief assistant

Every morning it texts me a short brief written by Claude:

- **Due soon:** upcoming Canvas assignments and quizzes I haven't submitted, soonest first
- **Email that needs me:** unread Gmail and Outlook messages from the last day, filtered to the ones that need a reply
- **Today's focus:** the one or two things to do first

`/calendar` adds a study block to Google Calendar the day before each upcoming assignment. Each block is tagged with the assignment link, so running it again never makes duplicates.

| Source | How it connects |
|---|---|
| Canvas | Canvas REST API with a personal access token |
| Gmail | Gmail API, read-only, Google sign-in |
| Outlook | Microsoft Graph, read-only, Microsoft sign-in |
| Google Calendar | Calendar API, creates events only |

If one source fails (say, an expired sign-in), the brief still goes out and says which source didn't load.

## Coaching bots

| Bot | What it does |
|---|---|
| **Lifting** | Logs workouts, suggests progressive overload, adjusts training to recovery |
| **Nutrition** | Tracks calories and protein from what you say you ate, suggests meals around your schedule |
| **Academic** | Explains class concepts, helps outline essays, tracks deadlines, quizzes you |
| **Habit** | Runs morning and evening check-ins and tracks daily habits |

All of the bots run from one Python process and share one deployment.

## How it works

- **One process, four bots:** each bot gets its own Telegram app and token, started together with `asyncio`.
- **Personalities as files:** each bot's system prompt lives in `prompts/<name>.md`, so you can change how a bot behaves without touching code.
- **Memory:** every conversation is saved to `memory.json`, keeping the last 40 messages per bot so it remembers context between chats. `/clear` wipes a bot's memory.
- **Secrets stay out of the code:** API keys and bot tokens are read from environment variables, and the app refuses to start if any are missing.

## Commands

- `/brief`: send the morning brief now (assistant)
- `/calendar`: add study blocks for upcoming assignments (assistant)
- `/start`: welcome message (coaching bots)
- `/clear`: reset that bot's memory (coaching bots)

## Setup

1. Create four bots with [@BotFather](https://t.me/BotFather) on Telegram and copy each token.
2. Get an Anthropic API key at [console.anthropic.com](https://console.anthropic.com).
3. Copy `prompts/example/*.md` into `prompts/` and fill in your own details. Your filled-in prompts are git-ignored, so personal info never gets committed.
4. For the morning brief (optional): create a fifth bot for `ASSISTANT_TOKEN`, add a Canvas access token, an Azure app ID for Outlook, and a Google OAuth desktop client saved as `google_credentials.json`. The first run asks you to sign in to Google and Microsoft once; after that the sign-ins are cached locally and never committed.
5. Set the variables from `.env.example`, then run:

```bash
pip install -r requirements.txt
python -m pytest -q        # 8 tests; every outside service is faked
python main.py
```

### Deploying

It's set up for [Railway](https://railway.app): connect the repo, add the five variables, and it deploys with `nixpacks.toml` (Python 3.11). Running it on Python 3.13 with an older Telegram library crashed on startup, so the library is pinned to a version that supports both.

## How I built it

I built this with Claude as my coding partner. I decided what each bot should do and how it should talk, wrote the profiles, set it up on GitHub and Railway, and worked through the deployment errors. The morning-brief assistant was added in November 2026.

## Project structure

```
main.py            Bots, memory, Claude API calls
assistant/
  canvas.py        Upcoming assignments
  gmail.py         Unread Gmail
  outlook.py       Unread Outlook mail (Microsoft Graph)
  calendar_builder.py  Study blocks in Google Calendar
  brief.py         Gathers sources and has Claude write the brief
  bot.py           /brief, /calendar, and the daily schedule
tests/             Tests for the assistant
prompts/example/   Template personality for each bot
requirements.txt   Python dependencies
nixpacks.toml      Railway build settings
.env.example       Required environment variables
```

## License

Copyright © 2026. All rights reserved. See [LICENSE](LICENSE).
