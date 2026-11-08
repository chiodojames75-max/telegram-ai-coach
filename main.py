import os
import json
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import anthropic

# ─────────────────────────────────────────────
# CONFIGURATION — keys come from environment variables, never from code
# ─────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

LIFTING_TOKEN   = os.environ.get("LIFTING_TOKEN")
NUTRITION_TOKEN = os.environ.get("NUTRITION_TOKEN")
ACADEMIC_TOKEN  = os.environ.get("ACADEMIC_TOKEN")
HABIT_TOKEN     = os.environ.get("HABIT_TOKEN")

REQUIRED = ["ANTHROPIC_API_KEY", "LIFTING_TOKEN", "NUTRITION_TOKEN", "ACADEMIC_TOKEN", "HABIT_TOKEN"]

def check_config():
    missing = [k for k in REQUIRED if not os.environ.get(k)]
    if missing:
        raise SystemExit("Missing environment variables: " + ", ".join(missing) + " (see .env.example)")

# ─────────────────────────────────────────────
# MEMORY SYSTEM — saves everything to a JSON file
# ─────────────────────────────────────────────
MEMORY_FILE = "memory.json"

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    return {}

def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)

def get_history(bot_name: str):
    memory = load_memory()
    return memory.get(bot_name, {}).get("history", [])

def add_to_history(bot_name: str, role: str, content: str):
    memory = load_memory()
    if bot_name not in memory:
        memory[bot_name] = {"history": []}
    memory[bot_name]["history"].append({"role": role, "content": content})
    # Keep last 40 messages so context stays rich but doesn't get too long
    memory[bot_name]["history"] = memory[bot_name]["history"][-40:]
    save_memory(memory)

def clear_history(bot_name: str):
    memory = load_memory()
    if bot_name in memory:
        memory[bot_name]["history"] = []
    save_memory(memory)

# ─────────────────────────────────────────────
# SYSTEM PROMPTS — each bot's personality lives in prompts/<name>.md
# Copy prompts/example/*.md into prompts/ and fill in your own details.
# Your filled-in prompts are git-ignored so personal info never gets committed.
# ─────────────────────────────────────────────
PROMPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")

def load_prompt(name: str) -> str:
    for folder in (PROMPT_DIR, os.path.join(PROMPT_DIR, "example")):
        path = os.path.join(folder, f"{name}.md")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
    raise FileNotFoundError(f"No prompt found for '{name}' in {PROMPT_DIR}")

LIFTING_SYSTEM   = load_prompt("lifting")
NUTRITION_SYSTEM = load_prompt("nutrition")
ACADEMIC_SYSTEM  = load_prompt("academic")
HABIT_SYSTEM     = load_prompt("habit")

# ─────────────────────────────────────────────
# CORE AI FUNCTION — sends message to Claude
# ─────────────────────────────────────────────
def ask_claude(system_prompt: str, history: list, user_message: str) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    messages = history + [{"role": "user", "content": user_message}]
    
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1000,
        system=system_prompt,
        messages=messages
    )
    
    return response.content[0].text

# ─────────────────────────────────────────────
# TELEGRAM HANDLERS — one set per bot
# ─────────────────────────────────────────────
def make_handlers(bot_name: str, system_prompt: str, welcome_message: str):
    
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(welcome_message)

    async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
        clear_history(bot_name)
        await update.message.reply_text("🧹 Memory cleared! Starting fresh.")

    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_message = update.message.text
        
        # Show typing indicator
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )
        
        try:
            history = get_history(bot_name)
            response = ask_claude(system_prompt, history, user_message)
            
            # Save both sides to memory
            add_to_history(bot_name, "user", user_message)
            add_to_history(bot_name, "assistant", response)
            
            await update.message.reply_text(response)
            
        except Exception as e:
            await update.message.reply_text(f"Something went wrong: {str(e)}\n\nTry again in a second.")

    return start, clear, handle_message

# ─────────────────────────────────────────────
# BUILD EACH BOT APP
# ─────────────────────────────────────────────
def build_bot(token: str, bot_name: str, system_prompt: str, welcome: str):
    start_fn, clear_fn, message_fn = make_handlers(bot_name, system_prompt, welcome)
    
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start_fn))
    app.add_handler(CommandHandler("clear", clear_fn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_fn))
    
    return app

# ─────────────────────────────────────────────
# RUN ALL BOTS AT THE SAME TIME
# ─────────────────────────────────────────────
async def main():
    lifting_app = build_bot(
        LIFTING_TOKEN, "lifting",
        LIFTING_SYSTEM,
        "💪 Lifting Bot online! Tell me about your workout, ask about your program, or log your lifts. Type /clear to reset memory."
    )
    nutrition_app = build_bot(
        NUTRITION_TOKEN, "nutrition",
        NUTRITION_SYSTEM,
        "🥗 Nutrition Bot online! Tell me what you've eaten today and I'll track your macros, or ask me what to eat next. Type /clear to reset memory."
    )
    academic_app = build_bot(
        ACADEMIC_TOKEN, "academic",
        ACADEMIC_SYSTEM,
        "📚 Academic Bot online! Ask me to explain a concept, help with an essay, or track a deadline. Type /clear to reset memory."
    )
    habit_app = build_bot(
        HABIT_TOKEN, "habit",
        HABIT_SYSTEM,
        "📅 Habit Tracker online! Check in with me every morning and night. I'll track your habits, keep you accountable, and help you stay consistent. Type /clear to reset memory."
    )

    # Start all bots concurrently
    async with lifting_app, nutrition_app, academic_app, habit_app:
        await lifting_app.initialize()
        await nutrition_app.initialize()
        await academic_app.initialize()
        await habit_app.initialize()

        await lifting_app.start()
        await nutrition_app.start()
        await academic_app.start()
        await habit_app.start()

        await lifting_app.updater.start_polling()
        await nutrition_app.updater.start_polling()
        await academic_app.updater.start_polling()
        await habit_app.updater.start_polling()

        print("✅ All 4 bots are running!")
        print("💪 Lifting Bot — active")
        print("🥗 Nutrition Bot — active")
        print("📚 Academic Bot — active")
        print("📅 Habit Tracker — active")

        # Run forever
        await asyncio.Event().wait()

if __name__ == "__main__":
    check_config()
    asyncio.run(main())
