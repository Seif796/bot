import os
import sys
import asyncio
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
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
# 1. Start & Dashboard Command
# -------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🚀 **Utility & Scheduler Control Bot**\n\n"
        "Here are your primary tools:\n"
        "• 🔍 **Find User ID:** `/findid` - Get User ID of any contact\n"
        "• 📅 **Telegram Scheduler:** `/schedule <HH:MM> <user_id> <message>`\n"
        "• ⏰ **Alarm:** `/alarm <HH:MM> <label>` (Spams 10 alerts when triggered)\n"
        "• ⏳ **Timer:** `/timer <seconds> <label>` (Spams 10 alerts when finished)\n"
        "• 🕒 **Clock:** `/clock` - View server time\n"
        "• ⏱ **Stopwatch:** `/stopwatch` - Interactive stopwatch"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

# -------------------------------------------------------------------
# 2. Find User ID Tool
# -------------------------------------------------------------------
async def find_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact_button = KeyboardButton(text="🎴 Share Contact to Get User ID", request_contact=True)
    custom_keyboard = ReplyKeyboardMarkup([[contact_button]], resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "🔎 **Find User ID Tool**\n\n"
        "Click the button below to select and share a contact from your phone, "
        "and I will instantly show you their Telegram User ID.",
        reply_markup=custom_keyboard
    )

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    user_id = contact.user_id
    first_name = contact.first_name or ""
    last_name = contact.last_name or ""
    phone = contact.phone_number or "N/A"

    if user_id:
        response = (
            f"✅ **User ID Found!**\n\n"
            f"• **Name:** {first_name} {last_name}\n"
            f"• **Phone:** `{phone}`\n"
            f"• **Telegram User ID:** `{user_id}`\n\n"
            f"💡 *You can now use this User ID in `/schedule` command.*"
        )
    else:
        response = (
            f"⚠️ **Contact Details Received:**\n\n"
            f"• **Name:** {first_name} {last_name}\n"
            f"• **Phone:** `{phone}`\n\n"
            f"❌ This contact does not have an active Telegram account or privacy settings prevent fetching ID."
        )

    await update.message.reply_text(response, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())

# -------------------------------------------------------------------
# 3. Telegram Message Scheduler Tool (By User ID)
# -------------------------------------------------------------------
async def send_scheduled_telegram_msg(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    target_user_id = job.data["target_user_id"]
    message_text = job.data["message"]
    
    try:
        await context.bot.send_message(chat_id=target_user_id, text=message_text)
        logger.info(f"Scheduled message delivered to User ID: {target_user_id}")
    except Exception as e:
        logger.error(f"Failed to send scheduled message to {target_user_id}: {e}")

async def schedule_telegram_tool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text(
            "⚠️ **Usage:** `/schedule <HH:MM> <user_id> <message>`\n"
            "Example: `/schedule 18:30 123456789 Hello my friend!`",
            parse_mode="Markdown"
        )
        return

    time_str = context.args[0]
    user_id_str = context.args[1]
    msg_text = " ".join(context.args[2:])

    if not user_id_str.isdigit():
        await update.message.reply_text("❌ User ID must be a numeric ID (e.g. `123456789`). Use `/findid` to get it.")
        return

    target_user_id = int(user_id_str)

    try:
        target_time = datetime.strptime(time_str, "%H:%M").time()
        now = datetime.now()
        scheduled_dt = datetime.combine(now.date(), target_time)

        if scheduled_dt <= now:
            scheduled_dt += timedelta(days=1)

        delay_seconds = (scheduled_dt - now).total_seconds()

        context.job_queue.run_once(
            send_scheduled_telegram_msg,
            when=delay_seconds,
            data={"target_user_id": target_user_id, "message": msg_text},
            name=f"sched_{update.effective_user.id}_{scheduled_dt.timestamp()}"
        )

        await update.message.reply_text(
            f"📅 **Telegram Message Scheduled!**\n\n"
            f"• **Target User ID:** `{target_user_id}`\n"
            f"• **Scheduled Time:** `{scheduled_dt.strftime('%Y-%m-%d %H:%M:%S')}`\n"
            f"• **Message:** `{msg_text}`",
            parse_mode="Markdown"
        )
    except ValueError:
        await update.message.reply_text("❌ Invalid time format! Use `HH:MM` in 24-hour format (e.g., 15:30).")

# -------------------------------------------------------------------
# 4. Alarm Tool (Sends 10 Burst Notifications)
# -------------------------------------------------------------------
async def alarm_callback(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.data["chat_id"]
    label = job.data["label"]
    
    for i in range(1, 11):
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⏰ **ALARM TRIGGERED! ({i}/10)**\n🔔 `{label}` - TIME IS UP!",
            parse_mode="Markdown"
        )
        await asyncio.sleep(0.3)

async def alarm_tool(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            f"⏰ **Alarm Set!**\n\n"
            f"• **Time:** `{scheduled_dt.strftime('%H:%M')}`\n"
            f"• **Label:** `{label}`\n"
            f"⚡ *Will send 10 consecutive alerts when triggered.*",
            parse_mode="Markdown"
        )
    except ValueError:
        await update.message.reply_text("❌ Invalid format! Use `HH:MM` (e.g. 08:00).")

# -------------------------------------------------------------------
# 5. Timer Tool (Sends 10 Burst Notifications)
# -------------------------------------------------------------------
async def timer_callback(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.data["chat_id"]
    label = job.data["label"]
    
    for i in range(1, 11):
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⏳ **TIMER FINISHED! ({i}/10)**\n🎯 `{label}` - TIME EXPIRED!",
            parse_mode="Markdown"
        )
        await asyncio.sleep(0.3)

async def timer_tool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("⚠️ **Usage:** `/timer <seconds> <optional_label>`\nExample: `/timer 60 Pizza ready`", parse_mode="Markdown")
        return

    try:
        seconds = int(context.args[0])
        label = " ".join(context.args[1:]) if len(context.args) > 1 else "Timer"

        context.job_queue.run_once(
            timer_callback,
            when=seconds,
            data={"chat_id": update.effective_chat.id, "label": label}
        )

        await update.message.reply_text(
            f"⏳ **Timer Started!**\n\n"
            f"• **Duration:** `{seconds}s`\n"
            f"• **Label:** `{label}`\n"
            f"⚡ *Will send 10 consecutive alerts when finished.*",
            parse_mode="Markdown"
        )
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number of seconds.")

# -------------------------------------------------------------------
# 6. Clock Tool
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
# 7. Stopwatch Tool
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
    app.add_handler(CommandHandler("findid", find_id_command))
    app.add_handler(CommandHandler("schedule", schedule_telegram_tool))
    app.add_handler(CommandHandler("alarm", alarm_tool))
    app.add_handler(CommandHandler("timer", timer_tool))
    app.add_handler(CommandHandler("clock", clock_tool))
    app.add_handler(CommandHandler("stopwatch", stopwatch_tool))

    # Contact Handler & Callbacks
    app.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    app.add_handler(CallbackQueryHandler(stopwatch_callback, pattern="^sw_"))

    logger.info("Bot initialized successfully!")
    app.run_polling()

if __name__ == "__main__":
    main()