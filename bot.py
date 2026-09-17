import os
import sys
import logging
import urllib.parse
from datetime import datetime
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
# Logging & Environment Setup
# -------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Fetch Token from Environment Variable or define it here
TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")

# In-Memory Database Simulation
USER_NOTES = {}
USER_SETTINGS = {}

# -------------------------------------------------------------------
# Helper Functions & UI Generators
# -------------------------------------------------------------------
def build_whatsapp_link(phone_number: str, message: str) -> str:
    """Generates a direct wa.me link with pre-filled message."""
    clean_number = "".join(filter(str.isdigit, phone_number))
    encoded_message = urllib.parse.quote(message)
    return f"https://wa.me/{clean_number}?text={encoded_message}"

def get_main_menu_keyboard():
    """Builds the main interactive dashboard keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("💬 WhatsApp Tools", callback_data="menu_whatsapp"),
            InlineKeyboardButton("📝 Notes & Tasks", callback_data="menu_notes"),
        ],
        [
            InlineKeyboardButton("🛠 File Tools", callback_data="menu_files"),
            InlineKeyboardButton("🤖 AI Assistant", callback_data="menu_ai"),
        ],
        [
            InlineKeyboardButton("📊 System Status", callback_data="menu_system"),
            InlineKeyboardButton("ℹ️ Help & Setup", callback_data="menu_help"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")]])

# -------------------------------------------------------------------
# Command Handlers
# -------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    welcome_text = (
        f"🚀 **Control Center Online!**\n\n"
        f"Welcome **{user_name}** to your cloud management bot.\n"
        f"Use the buttons below to control WhatsApp quick links, notes, files, and more."
    )
    if update.message:
        await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=get_main_menu_keyboard())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 **Control Center Help Guide**\n\n"
        "• `/start` - Launch the main dashboard\n"
        "• `/wa <phone> <message>` - Instantly create a WhatsApp button\n"
        "• `/note <text>` - Save a quick note to cloud memory\n"
        "• `/getnotes` - Retrieve all your saved notes\n"
        "• `/status` - Check cloud server uptime and status"
    )
    if update.message:
        await update.message.reply_text(help_text, parse_mode="Markdown")

async def whatsapp_cmd_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allows creating instant WhatsApp links via /wa 201xxxxxxxxx Hello"""
    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ **Usage:** `/wa <phone_with_country_code> <message>`\n"
            "Example: `/wa 201234567890 أرسل ق1ا`",
            parse_mode="Markdown"
        )
        return

    phone = context.args[0]
    custom_msg = " ".join(context.args[1:])
    wa_url = build_whatsapp_link(phone, custom_msg)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📲 Send Message on WhatsApp", url=wa_url)],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="menu_main")]
    ])

    await update.message.reply_text(
        f"✅ **WhatsApp Link Generated!**\n\n"
        f"📱 **Target:** `{phone}`\n"
        f"💬 **Message:** `{custom_msg}`\n\n"
        f"Click the button below to open WhatsApp and send immediately:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def add_note_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    note_text = " ".join(context.args)
    
    if not note_text:
        await update.message.reply_text("⚠️ Please enter note content. Example: `/note Meeting at 5 PM`")
        return

    if user_id not in USER_NOTES:
        USER_NOTES[user_id] = []
    
    USER_NOTES[user_id].append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "text": note_text
    })

    await update.message.reply_text(f"✅ Note saved successfully!\n📝 `{note_text}`", parse_mode="Markdown")

async def get_notes_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    notes = USER_NOTES.get(user_id, [])

    if not notes:
        await update.message.reply_text("📭 You have no saved notes.")
        return

    response = "📝 **Your Saved Notes:**\n\n"
    for idx, item in enumerate(notes, 1):
        response += f"{idx}. [{item['time']}] {item['text']}\n"

    await update.message.reply_text(response, parse_mode="Markdown")

# -------------------------------------------------------------------
# Callback Query Handler (Button Logic)
# -------------------------------------------------------------------
async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "menu_main":
        await query.edit_message_text(
            "🚀 **Control Center Dashboard**\nSelect an option to proceed:",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )

    elif data == "menu_whatsapp":
        wa_text = (
            "💬 **WhatsApp Integration & Utilities**\n\n"
            "You can quickly send predefined messages or trigger WhatsApp directly.\n\n"
            "• Use command: `/wa <phone> <message>`\n"
            "Example:\n`/wa 201000000000 ابعت ق1ا`"
        )
        
        # Example Preset Button
        preset_url = build_whatsapp_link("201000000000", "ابعت ق1ا")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📲 Send Preset: 'ابعت ق1ا'", url=preset_url)],
            [InlineKeyboardButton("🔙 Back", callback_data="menu_main")]
        ])
        await query.edit_message_text(wa_text, parse_mode="Markdown", reply_markup=kb)

    elif data == "menu_notes":
        notes_text = (
            "📝 **Notes & Reminders Hub**\n\n"
            "• Save quick notes: `/note Your text here`\n"
            "• View all notes: `/getnotes`\n\n"
            "Everything is stored securely in memory."
        )
        await query.edit_message_text(notes_text, parse_mode="Markdown", reply_markup=get_back_button())

    elif data == "menu_files":
        file_text = (
            "🛠 **File & Media Processing**\n\n"
            "• Send any document to save it to host.\n"
            "• Send photos to process or convert.\n"
            "• Download files remotely using `/download <filename>`"
        )
        await query.edit_message_text(file_text, parse_mode="Markdown", reply_markup=get_back_button())

    elif data == "menu_ai":
        ai_text = (
            "🤖 **AI & Text Assistant**\n\n"
            "Send any text message directly to the bot to get instant feedback, formatting, or automated translation."
        )
        await query.edit_message_text(ai_text, parse_mode="Markdown", reply_markup=get_back_button())

    elif data == "menu_system":
        uptime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sys_text = (
            "📊 **Cloud Server Diagnostics**\n\n"
            f"• **Status:** 🟢 Online (24/7 Cloud)\n"
            f"• **Server Time:** `{uptime}`\n"
            f"• **Environment:** Python {sys.version.split()[0]}\n"
            f"• **Platform:** {sys.platform}"
        )
        await query.edit_message_text(sys_text, parse_mode="Markdown", reply_markup=get_back_button())

    elif data == "menu_help":
        await query.edit_message_text(
            "ℹ️ **Setup & Info**\n\nThis bot is configured to run continuously on Render/Cloud platform.",
            parse_mode="Markdown",
            reply_markup=get_back_button()
        )

# -------------------------------------------------------------------
# Message & Document Handlers
# -------------------------------------------------------------------
async def echo_or_process_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    # Simple intelligent fallback processing
    await update.message.reply_text(
        f"📥 **Message Received:**\n`{user_text}`\n\n"
        f"💡 *Tip:* Use `/wa` to generate a WhatsApp quick-action link.",
        parse_mode="Markdown"
    )

# -------------------------------------------------------------------
# Main Initialization
# -------------------------------------------------------------------
def main():
    if TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE" or not TOKEN:
        logger.error("BOT_TOKEN is missing! Please set it before running.")
        sys.exit(1)

    app = Application.builder().token(TOKEN).build()

    # Core Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("wa", whatsapp_cmd_handler))
    app.add_handler(CommandHandler("note", add_note_handler))
    app.add_handler(CommandHandler("getnotes", get_notes_handler))

    # Callbacks & Messages
    app.add_handler(CallbackQueryHandler(button_callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_or_process_message))

    logger.info("Bot started successfully!")
    app.run_polling()

if __name__ == "__main__":
    main()