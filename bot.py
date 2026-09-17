import os
import sys
import asyncio
import logging
import urllib.parse
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# -------------------------------------------------------------------
# Logging Setup
# -------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")

# Global stopwatches tracking: user_id -> start_time
STOPWATCHES = {}

# -------------------------------------------------------------------
# Helper Utilities
# -------------------------------------------------------------------
def build_whatsapp_link(phone_number: str, message: str) -> str:
    clean_number = "".join(filter(str.isdigit, phone_number))
    encoded_message = urllib.parse.quote(message)
    return f"https://wa.me/{clean_number}?text={encoded_message}"

# -------------------------------------------------------------------
# 1. Start & Help Dashboard
# -------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🚀 **Utility & Scheduler Control Bot**\n\n"
        "Here are your primary modular tools:\n"
        "• 💬 **WhatsApp:** `/wa <phone> <message>`\n"
        "• 📅 **Telegram Scheduler:** `/schedule <HH:MM> <chat_id/username> <message>`\n"
        "• ⏰ **Alarm:** `/alarm <HH:MM> <label>`\n"
        "• ⏳ **Timer:** `/timer <seconds> <label>`\n"
        "• 🕒 **Clock:** `/clock`\n"
        "• ⏱ **Stopwatch:** `/stopwatch` (start/stop/reset)"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

# -------------------------------------------------------------------
# 2. WhatsApp Direct Link Tool
# -------------------------------------------------------------------
async def whatsapp_tool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        note_text = (
            "⚠️ **Usage:** `/wa <phone> <message>`\n\n"
            "📌 *Note on WhatsApp Automation:* WhatsApp strict privacy policies prevent cloud bots "
            "from sending personal chats automatically without user interaction. "
            "This tool generates an instant trigger button to send your exact text in 1-tap."
        )
        await update.message.reply_text(note_text, parse_mode="Markdown")
        return

    phone = context.args[0]
    msg = " ".join(context.args[1:])
    wa_url = build_whatsapp_link(phone, msg)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📲 Open WhatsApp & Send Now", url=wa_url)]
    ])
    await update.message.reply_text(
        f"✅ **WhatsApp Action Ready**\n\n📱 **To:** `{phone}`\n💬 **Message:** `{msg}`",
        parse_mode="Markdown",
        reply_markup=kb
    )

# -------------------------------------------------------------------
# 3. Automatic Telegram Scheduler Tool
# -------------------------------------------------------------------
async def send_scheduled_telegram_msg(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    target_chat = job.data["target"]
    message_text = job.data["message"]
    
    try:
        await context.bot.send_message(chat_id=target_chat, text=message_text)
        logger.info(f"Scheduled message delivered to {target_chat}")
    except Exception as e:
        logger.error(f"Failed to send scheduled message: {e}")

async def schedule_telegram_tool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /schedule 14:30 @username Hello there"""
    if len(context.args) < 3:
        await update.message.reply_text(
            "⚠️ **Usage:** `/schedule <HH:MM> <chat_id_or_username> <message>`\n"
            "Example: `/schedule 18:00 @friend_username Happy Birthday!`",
            parse_mode="Markdown"
        )
        return

    time_str = context.args[0]
    target_chat = context.args[1]
    msg_text = " ".join(context.args[2:])

    try:
        target_time = datetime.strptime(time_str, "%H:%M").time()
        now = datetime.now()
        scheduled_dt = datetime.combine(now.date(), target_time)

        # If time is earlier today, schedule for tomorrow
        if scheduled_dt <= now:
            scheduled_dt += timedelta(days=1)

        delay_seconds = (scheduled_dt - now).total_seconds()

        context.job_queue.run_once(
            send_scheduled_telegram_msg,
            when=delay_seconds,
            data={"target": target_chat, "message": msg_text},
            name=f"sched_{update.effective_user.id}_{scheduled_dt.timestamp()}"
        )

        await update.message.reply_text(
            f"📅 **Telegram Message Scheduled!**\n\n"
            f"• **Target:** `{target_chat}`\n"
            f"• **Scheduled Time:** `{scheduled_dt.strftime('%Y-%m-%d %H:%M:%S')}`\n"
            f"• **Message:** `{msg_text}`",
            parse_mode="Markdown"
        )
    except ValueError:
        await update.message.reply_text("❌ Invalid time format! Please use `HH:MM` 24-hour format (e.g., 15:30).")

# -------------------------------------------------------------------
# 4. Independent Alarm Tool
# -------------------------------------------------------------------
async def alarm_callback(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.data["chat_id"]
    label = job.data["label"]
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"⏰ **ALARM TRIGGERED!**\n\n🔔 `{label}`",
        parse_mode="Markdown"
    )

async def alarm_tool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /alarm 07:30 Wake up!"""
    if len(context.args) < 1:
        await update.message.reply_text("⚠️ **Usage:** `/alarm <HH:MM> <optional_label>`\nExample: `/alarm 07:30 Wake up`", parse_mode="Markdown")
        return

    time_str = context.args[0]
    label = " ".join(context.args[1:]) if len(context.args) > 1 else "Alarm"

    try:
        target_time = datetime.strptime(time_str, "%H:%M").time()
        now = datetime.now()
        scheduled_dt = datetime.combine(now.date(), target_time)

        if scheduled_dt <= now:
            scheduled_dt += timedelta(days=1)

        delay = (scheduled_dt - now).total_seconds()

        context.job_queue.run_once(
            alarm_callback,
            when=delay,
            data={"chat_id": update.effective_chat.id, "label": label}
        )

        await update.message.reply_text(
            f"⏰ **Alarm Set Successfully!**\n\n"
            f"• **Time:** `{scheduled_dt.strftime('%H:%M')}`\n"
            f"• **Label:** `{label}`",
            parse_mode="Markdown"
        )
    except ValueError:
        await update.message.reply_text("❌ Invalid format! Use `HH:MM` (e.g. 08:00).")

# -------------------------------------------------------------------
# 5. Independent Timer Tool
# -------------------------------------------------------------------
async def timer_callback(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.data["chat_id"]
    label = job.data["label"]
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"⏳ **TIMER FINISHED!**\n\n🎯 `{label}`",
        parse_mode="Markdown"
    )

async def timer_tool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /timer 60 Tea is ready"""
    if len(context.args) < 1:
        await update.message.reply_text("⚠️ **Usage:** `/timer <seconds> <optional_label>`\nExample: `/timer 300 Pizza in oven`", parse_mode="Markdown")
        return

    try:
        seconds = int(context.args[0])
        label = " ".join(context.args[1:]) if len(context.args) > 1 else "Timer"

        context.job_queue.run_once(
            timer_callback,
            when=seconds,
            data={"chat_id": update.effective_chat.id, "label": label}
        )

        await update.message.reply_text(f"⏳ **Timer started for {seconds} seconds** (`{label}`).", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ Please enter valid seconds as a number.")

# -------------------------------------------------------------------
# 6. Independent Clock Tool
# -------------------------------------------------------------------
async def clock_tool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    current_date = now.strftime("%A, %Y-%m-%d")

    clock_text = (
        f"🕒 **Current System Time**\n\n"
        f"• **Time:** `{current_time}`\n"
        f"• **Date:** `{current_date}`\n"
        f"• **Timezone:** UTC/Server Local"
    )
    await update.message.reply_text(clock_text, parse_mode="Markdown")

# -------------------------------------------------------------------
# 7. Independent Stopwatch Tool
# -------------------------------------------------------------------
async def stopwatch_tool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("▶️ Start", callback_data="sw_start"),
            InlineKeyboardButton("⏹ Stop", callback_data="sw_stop"),
            InlineKeyboardButton("🔄 Reset", callback_data="sw_reset"),
        ]
    ])

    if user_id in STOPWATCHES:
        elapsed = int((datetime.now() - STOPWATCHES[user_id]).total_seconds())
        msg = f"⏱ **Stopwatch Running:** `{elapsed}s`"
    else:
        msg = "⏱ **Stopwatch Idle.** Click Start to begin tracking."

    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)

async def stopwatch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    action = query.data

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("▶️ Start", callback_data="sw_start"),
            InlineKeyboardButton("⏹ Stop", callback_data="sw_stop"),
            InlineKeyboardButton("🔄 Reset", callback_data="sw_reset"),
        ]
    ])

    if action == "sw_start":
        STOPWATCHES[user_id] = datetime.now()
        await query.edit_message_text("⏱ **Stopwatch Started!**", reply_markup=kb, parse_mode="Markdown")

    elif action == "sw_stop":
        if user_id in STOPWATCHES:
            elapsed = int((datetime.now() - STOPWATCHES.pop(user_id)).total_seconds())
            await query.edit_message_text(f"⏹ **Stopwatch Stopped!** Total time: `{elapsed}s`", reply_markup=kb, parse_mode="Markdown")
        else:
            await query.edit_message_text("⚠️ Stopwatch is not running.", reply_markup=kb, parse_mode="Markdown")

    elif action == "sw_reset":
        STOPWATCHES.pop(user_id, None)
        await query.edit_message_text("🔄 **Stopwatch Reset.**", reply_markup=kb, parse_mode="Markdown")

# -------------------------------------------------------------------
# Main Initialization
# -------------------------------------------------------------------
def main():
    if TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE" or not TOKEN:
        logger.error("BOT_TOKEN is invalid or missing.")
        sys.exit(1)

    app = Application.builder().token(TOKEN).build()

    # Tool Handlers Registration
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", start_command))
    app.add_handler(CommandHandler("wa", whatsapp_tool))
    app.add_handler(CommandHandler("schedule", schedule_telegram_tool))
    app.add_handler(CommandHandler("alarm", alarm_tool))
    app.add_handler(CommandHandler("timer", timer_tool))
    app.add_handler(CommandHandler("clock", clock_tool))
    app.add_handler(CommandHandler("stopwatch", stopwatch_tool))

    # Callbacks
    app.add_handler(CallbackQueryHandler(stopwatch_callback, pattern="^sw_"))

    logger.info("Bot tools initialized successfully!")
    app.run_polling()

if __name__ == "__main__":
    main()