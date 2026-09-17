import os
import sys
import asyncio
import logging
from datetime import datetime, timedelta
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButtonRequestContact
)
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
        "🚀 **البوت شغال وبجاهزية كاملة!**\n\n"
        "الأوامر المتاحة:\n"
        "• 🔍 `/findid` - اختر صديقك من جهات الاتصال أو اعمل Forward لرسالته لجلبت الـ User ID\n"
        "• 📅 `/schedule <HH:MM> <user_id> <message>` - جدولة رسالة لشخص معين\n"
        "• ⏰ `/alarm <HH:MM> <label>` - ضبط منبه (يرسل 10 رسائل متتالية)\n"
        "• ⏳ `/timer <seconds> <label>` - مؤقت تنازلي (يرسل 10 رسائل متتالية)\n"
        "• 🕒 `/clock` - عرض وقت السيرفر الحالي\n"
        "• ⏱ `/stopwatch` - أداة الستوب ووتش"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

# -------------------------------------------------------------------
# 2. Find User ID Tool (Select Contact or Forward Message)
# -------------------------------------------------------------------
async def find_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact_button = KeyboardButton(
        text="🎴 اختر صديقك من جهات الاتصال",
        request_contact=KeyboardButtonRequestContact(request_id=1)
    )
    custom_keyboard = ReplyKeyboardMarkup([[contact_button]], resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "🔎 **أداة استخراج الـ User ID:**\n\n"
        "1️⃣ اضغط على الزر بالأسفل واختر الصديق من جهات الاتصال.\n"
        "2️⃣ أو قم بعمل **Forward (توجيه)** لأي رسالة من صديقك إلى البوت مباشرة وسيقوم باستخراج الـ ID فوراً.",
        reply_markup=custom_keyboard,
        parse_mode="Markdown"
    )

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    user_id = contact.user_id
    first_name = contact.first_name or ""
    last_name = contact.last_name or ""
    phone = contact.phone_number or "N/A"

    if user_id:
        response = (
            f"✅ **تم جلب الـ User ID بنجاح!**\n\n"
            f"• **الاسم:** {first_name} {last_name}\n"
            f"• **الهاتف:** `{phone}`\n"
            f"• **User ID:** `{user_id}`\n\n"
            f"💡 يمكنك استخدام هذا الـ ID في أمر الجدولة `/schedule`."
        )
    else:
        response = (
            f"⚠️ **تفاصيل جهة الاتصال:**\n\n"
            f"• **الاسم:** {first_name} {last_name}\n"
            f"• **الهاتف:** `{phone}`\n\n"
            f"❌ هذا الشخص ليس لديه حساب نشط أو إعدادات الخصوصية تمنع إظهار الـ ID."
        )

    await update.message.reply_text(response, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())

async def forwarded_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    forward_info = update.message.forward_from
    if forward_info:
        await update.message.reply_text(
            f"🆔 **User ID للشخص الموجه منه الرسالة:**\n\n"
            f"• **الاسم:** {forward_info.first_name}\n"
            f"• **User ID:** `{forward_info.id}`",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "⚠️ لا يمكن استخراج الـ ID لأن حساب هذا الشخص مخصص برفض إظهار الرابط عند إعادة التوجيه (Privacy Settings)."
        )

# -------------------------------------------------------------------
# 3. Telegram Message Scheduler Tool
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
            "⚠️ **الاستخدام:** `/schedule <HH:MM> <user_id> <الرسالة>`\n"
            "مثال: `/schedule 18:30 123456789 السلام عليكم`",
            parse_mode="Markdown"
        )
        return

    time_str = context.args[0]
    user_id_str = context.args[1]
    msg_text = " ".join(context.args[2:])

    if not user_id_str.isdigit():
        await update.message.reply_text("❌ الـ User ID يجب أن يكون أرقام فقط. استخدم `/findid` لاختيار صديقك.")
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
            f"📅 **تم جدولة الرسالة بنجاح!**\n\n"
            f"• **المستلم (User ID):** `{target_user_id}`\n"
            f"• **الوقت:** `{scheduled_dt.strftime('%Y-%m-%d %H:%M:%S')}`\n"
            f"• **الرسالة:** `{msg_text}`",
            parse_mode="Markdown"
        )
    except ValueError:
        await update.message.reply_text("❌ صيغة الوقت غير صحيحة! استخدم صيغة 24 ساعة مثل `15:30`.")

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
            text=f"⏰ **الوقت خلص! ({i}/10)**\n🔔 `{label}`",
            parse_mode="Markdown"
        )
        await asyncio.sleep(0.3)

async def alarm_tool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("⚠️ **الاستخدام:** `/alarm <HH:MM> <اسم المنبه>`\nمثال: `/alarm 07:30 صحيان`", parse_mode="Markdown")
        return

    time_str = context.args[0]
    label = " ".join(context.args[1:]) if len(context.args) > 1 else "المنبه"

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

        time_formatted = scheduled_dt.strftime('%H:%M')
        await update.message.reply_text(
            f"هبعتلك رساله الساعه {time_formatted} و 10 مرات",
            parse_mode="Markdown"
        )
    except ValueError:
        await update.message.reply_text("❌ صيغة الوقت غير صحيحة! استخدم `HH:MM` (مثال 08:00).")

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
            text=f"⏳ **الوقت خلص! ({i}/10)**\n🎯 `{label}`",
            parse_mode="Markdown"
        )
        await asyncio.sleep(0.3)

async def timer_tool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("⚠️ **الاستخدام:** `/timer <عدد_الثواني> <ملاحظة>`\nمثال: `/timer 60 الأكل`", parse_mode="Markdown")
        return

    try:
        seconds = int(context.args[0])
        label = " ".join(context.args[1:]) if len(context.args) > 1 else "المؤقت"

        target_dt = datetime.now() + timedelta(seconds=seconds)
        time_formatted = target_dt.strftime('%H:%M:%S')

        context.job_queue.run_once(
            timer_callback,
            when=seconds,
            data={"chat_id": update.effective_chat.id, "label": label}
        )

        await update.message.reply_text(
            f"هبعتلك رساله الساعه {time_formatted} و 10 مرات",
            parse_mode="Markdown"
        )
    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال عدد ثواني صحيح.")

# -------------------------------------------------------------------
# 6. Clock Tool
# -------------------------------------------------------------------
async def clock_tool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    current_date = now.strftime("%A, %Y-%m-%d")

    clock_text = (
        f"🕒 **وقت السيرفر الحالي:**\n\n"
        f"• **الوقت:** `{current_time}`\n"
        f"• **التاريخ:** `{current_date}`"
    )
    await update.message.reply_text(clock_text, parse_mode="Markdown")

# -------------------------------------------------------------------
# 7. Stopwatch Tool
# -------------------------------------------------------------------
async def stopwatch_tool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("▶️ تشغيل", callback_data="sw_start"),
            InlineKeyboardButton("⏹ إيقاف", callback_data="sw_stop"),
            InlineKeyboardButton("🔄 إعادة ضبط", callback_data="sw_reset"),
        ]
    ])

    if user_id in STOPWATCHES:
        elapsed = int((datetime.now() - STOPWATCHES[user_id]).total_seconds())
        msg = f"⏱ **الستوب ووتش شغال:** `{elapsed} ثانية`"
    else:
        msg = "⏱ **الستوب ووتش متوقف.** اضغط تشغيل للبدء."

    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)

async def stopwatch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    action = query.data

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("▶️ تشغيل", callback_data="sw_start"),
            InlineKeyboardButton("⏹ إيقاف", callback_data="sw_stop"),
            InlineKeyboardButton("🔄 إعادة ضبط", callback_data="sw_reset"),
        ]
    ])

    if action == "sw_start":
        STOPWATCHES[user_id] = datetime.now()
        await query.edit_message_text("⏱ **تم بدء الستوب ووتش!**", reply_markup=kb, parse_mode="Markdown")

    elif action == "sw_stop":
        if user_id in STOPWATCHES:
            elapsed = int((datetime.now() - STOPWATCHES.pop(user_id)).total_seconds())
            await query.edit_message_text(f"⏹ **تم الإيقاف!** الوقت الإجمالي: `{elapsed} ثانية`", reply_markup=kb, parse_mode="Markdown")
        else:
            await query.edit_message_text("⚠️ الستوب ووتش غير شغال حالياً.", reply_markup=kb, parse_mode="Markdown")

    elif action == "sw_reset":
        STOPWATCHES.pop(user_id, None)
        await query.edit_message_text("🔄 **تمت إعادة الضبط.**", reply_markup=kb, parse_mode="Markdown")

# -------------------------------------------------------------------
# Main Initialization
# -------------------------------------------------------------------
def main():
    if TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE" or not TOKEN:
        logger.error("BOT_TOKEN is invalid or missing.")
        sys.exit(1)

    app = Application.builder().token(TOKEN).build()

    # Register Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", start_command))
    app.add_handler(CommandHandler("findid", find_id_command))
    app.add_handler(CommandHandler("schedule", schedule_telegram_tool))
    app.add_handler(CommandHandler("alarm", alarm_tool))
    app.add_handler(CommandHandler("timer", timer_tool))
    app.add_handler(CommandHandler("clock", clock_tool))
    app.add_handler(CommandHandler("stopwatch", stopwatch_tool))

    # Handlers for Contacts, Forwarded Messages, and Callbacks
    app.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    app.add_handler(MessageHandler(filters.FORWARDED, forwarded_message_handler))
    app.add_handler(CallbackQueryHandler(stopwatch_callback, pattern="^sw_"))

    logger.info("Bot initialized and ready!")
    app.run_polling()

if __name__ == "__main__":
    main()
