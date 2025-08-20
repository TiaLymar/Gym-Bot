import os
import logging
import asyncio
import datetime
from zoneinfo import ZoneInfo
from flask import Flask
from threading import Thread
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# --- Secrets come from environment variables on Render ---
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not TOKEN or not CHAT_ID:
    raise RuntimeError("Please set TOKEN and CHAT_ID environment variables.")

# --- Tiny Flask server so Render has an HTTP endpoint (health/keep-alive) ---
app_web = Flask(__name__)

@app_web.get("/")
def home():
    return "Bot is running!"

def run_web():
    # Render exposes a PORT env var; bind to it
    port = int(os.environ.get("PORT", "10000"))
    app_web.run(host="0.0.0.0", port=port)

def keep_alive():
    Thread(target=run_web, daemon=True).start()

# --- UI builders ---
def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Yep 🫡", callback_data="yep"),
          InlineKeyboardButton("Nope 🙈", callback_data="nope"),
          InlineKeyboardButton("Not a gym day 💃", callback_data="skip")]]
    )

def workout_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Arms 💪", callback_data="arms"),
          InlineKeyboardButton("Legs 🦵", callback_data="legs"),
          InlineKeyboardButton("Core", callback_data="core")]]
    )

# --- Bot handlers ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! I’ll remind you every day at 9am 🙂")

async def send_question_to(chat_id: int, bot):
    await bot.send_message(
        chat_id=chat_id,
        text="Did you go to the gym today, lovely?",
        reply_markup=main_keyboard()
    )

async def button_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    if data == "yep":
        await q.edit_message_text("Sweet! What did you do?", reply_markup=workout_keyboard())
    elif data == "nope":
        await q.edit_message_text("Oh, you're a lazy banana ")
    elif data == "skip":
        await q.edit_message_text("Got it, rest day 💆")
    elif data in ("arms", "legs", "core"):
        await q.edit_message_text(f"Awesome! Nice work on {data}! 😎")

async def test_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Manual trigger to test immediately
    await send_question_to(int(CHAT_ID), context.bot)

# --- Daily job (09:00 Europe/London; handles DST automatically) ---
async def daily_job(context: ContextTypes.DEFAULT_TYPE):
    await send_question_to(int(CHAT_ID), context.bot)

def main():
    logging.basicConfig(level=logging.INFO)

    # Start the HTTP server in a side thread (Render health check/URL)
    keep_alive()

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("test", test_cmd))
    application.add_handler(CallbackQueryHandler(button_cb))

    london = ZoneInfo("Europe/London")
    application.job_queue.run_daily(
        daily_job,
        time=datetime.time(hour=9, minute=0, tzinfo=london),
        name="daily_gym"
    )

    application.run_polling()

if __name__ == "__main__":
    main()
