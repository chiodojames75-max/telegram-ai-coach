# Telegram AI Coach

Four personal AI assistants on Telegram, each powered by the Claude API and each with its own memory:

| Bot | What it does |
|---|---|
| **Lifting** | Logs workouts, suggests progressive overload, adjusts training to recovery |
| **Nutrition** | Tracks calories and protein from what you say you ate, suggests meals around your schedule |
| **Academic** | Explains class concepts, helps outline essays, tracks deadlines, quizzes you |
| **Habit** | Runs morning and evening check-ins and tracks daily habits |

All four run from one Python process and share one deployment.

## How it works

- **One process, four bots:** each bot gets its own Telegram app and token, started together with `asyncio`.
- **Personalities as files:** each bot's system prompt lives in `prompts/<name>.md`, so you can change how a bot behaves without touching code.
- **Memory:** every conversation is saved to `memory.json`, keeping the last 40 messages per bot so it remembers context between chats. `/clear` wipes a bot's memory.
- **Secrets stay out of the code:** API keys and bot tokens are read from environment variables, and the app refuses to start if any are missing.

## Commands

- `/start`: welcome message
- `/clear`: reset that bot's memory

## Setup

1. Create four bots with [@BotFather](https://t.me/BotFather) on Telegram and copy each token.
2. Get an Anthropic API key at [console.anthropic.com](https://console.anthropic.com).
3. Copy `prompts/example/*.md` into `prompts/` and fill in your own details. Your filled-in prompts are git-ignored, so personal info never gets committed.
4. Set the variables from `.env.example`, then run:

```bash
pip install -r requirements.txt
python main.py
```

### Deploying

It's set up for [Railway](https://railway.app): connect the repo, add the five variables, and it deploys with `nixpacks.toml` (Python 3.11). Running it on Python 3.13 with an older Telegram library crashed on startup, so the library is pinned to a version that supports both.

## How I built it

I built this with Claude as my coding partner. I decided what each bot should do and how it should talk, wrote the profiles, set it up on GitHub and Railway, and worked through the deployment errors until all four bots were running.

## Project structure

```
main.py            Bots, memory, Claude API calls
prompts/example/   Template personality for each bot
requirements.txt   Python dependencies
nixpacks.toml      Railway build settings
.env.example       Required environment variables
```

## License

Copyright © 2026. All rights reserved. See [LICENSE](LICENSE).
