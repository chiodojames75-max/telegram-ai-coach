"""Telegram commands for the assistant: /brief, /calendar, and the scheduled morning brief."""
import asyncio
import os
from datetime import time
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from . import brief, calendar_builder, canvas

CHAT_FILE = os.environ.get("BRIEF_CHAT_FILE", "brief_chat.txt")


def brief_chat_id():
    """The chat that gets the daily brief: BRIEF_CHAT_ID, or whoever last sent /start."""
    if os.environ.get("BRIEF_CHAT_ID"):
        return int(os.environ["BRIEF_CHAT_ID"])
    if os.path.exists(CHAT_FILE):
        return int(open(CHAT_FILE).read().strip())
    return None


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with open(CHAT_FILE, "w") as f:
        f.write(str(update.effective_chat.id))
    hh = os.environ.get("BRIEF_TIME", "07:30")
    await update.message.reply_text(f"Assistant online. Your morning brief will come here every day at {hh}. "
                                    "Send /brief for one now, or /calendar to add study blocks.")


async def _send_brief(bot, chat_id: int):
    data = await asyncio.to_thread(brief.gather)
    text = await asyncio.to_thread(brief.write_brief, data)
    await bot.send_message(chat_id=chat_id, text=text)


async def brief_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    await _send_brief(context.bot, update.effective_chat.id)


async def calendar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (canvas.configured() and calendar_builder.configured()):
        await update.message.reply_text("Connect Canvas and Google Calendar first (see README).")
        return
    assignments = await asyncio.to_thread(canvas.upcoming_assignments, 14)
    added = await asyncio.to_thread(calendar_builder.add_study_blocks, assignments)
    await update.message.reply_text(f"Added {added} study block(s) for {len(assignments)} upcoming assignment(s).")


async def morning_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = brief_chat_id()
    if chat_id:
        await _send_brief(context.bot, chat_id)


def attach(app: Application):
    """Add the assistant's commands to a Telegram app and schedule the daily brief."""
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("brief", brief_cmd))
    app.add_handler(CommandHandler("calendar", calendar_cmd))
    if app.job_queue:
        hh, mm = os.environ.get("BRIEF_TIME", "07:30").split(":")
        tz = ZoneInfo(os.environ.get("BRIEF_TZ", "America/New_York"))
        app.job_queue.run_daily(morning_job, time=time(int(hh), int(mm), tzinfo=tz), name="morning_brief")
