"""Telegram commands for the assistant: /brief, /calendar, and the scheduled morning brief."""
import asyncio
import os
from datetime import time
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from . import brief, calendar_builder, canvas


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
    await _send_brief(context.bot, int(os.environ["BRIEF_CHAT_ID"]))


def attach(app: Application):
    """Add the assistant's commands to a Telegram app and schedule the daily brief."""
    app.add_handler(CommandHandler("brief", brief_cmd))
    app.add_handler(CommandHandler("calendar", calendar_cmd))
    chat_id = os.environ.get("BRIEF_CHAT_ID")
    if chat_id and app.job_queue:
        hh, mm = os.environ.get("BRIEF_TIME", "07:30").split(":")
        tz = ZoneInfo(os.environ.get("BRIEF_TZ", "America/New_York"))
        app.job_queue.run_daily(morning_job, time=time(int(hh), int(mm), tzinfo=tz), name="morning_brief")
