import os
import io
import logging
from PIL import Image
import img2pdf
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Fetch Bot Token from Environment Variables (Set in Railway)
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")


async def post_init(application):
    """Sets up the bot's command menu button inside Telegram."""
    commands = [
        BotCommand("start", "Start the bot and see instructions"),
        BotCommand("help", "How to use this bot"),
        BotCommand("status", "Check queued images"),
        BotCommand("clear", "Clear queued images"),
    ]
    await application.bot.set_my_commands(commands)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command."""
    context.user_data["user_images"] = []
    await update.message.reply_text(
        "👋 **Welcome!**\n\n"
        "Send me one or more images (as photos or files).\n"
        "When you are ready, tap **📄 Convert to PDF** below!",
        parse_mode="Markdown",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /help command."""
    await update.message.reply_text(
        "ℹ️ **How to use this bot:**\n\n"
        "1. Send your images (as photo or compressed/uncompressed file).\n"
        "2. Click **📄 Convert to PDF** when finished.\n"
        "3. Use /status to see how many images are queued.\n"
        "4. Use /clear to discard stored images.\n"
        "5. Use /start to reset.",
        parse_mode="Markdown",
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /status command."""
    images = context.user_data.get("user_images", [])
    count = len(images)

    if count == 0:
        await update.message.reply_text("📥 Your image queue is currently empty.")
    else:
        keyboard = [
            [
                InlineKeyboardButton("📄 Convert to PDF", callback_data="convert_pdf"),
                InlineKeyboardButton("🗑️ Clear Images", callback_data="clear_images"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"📊 You currently have **{count}** image(s) queued.",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /clear command."""
    context.user_data["user_images"] = []
    await update.message.reply_text("🗑️ Your image queue has been cleared.")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles standard Telegram photo uploads."""
    if "user_images" not in context.user_data:
        context.user_data["user_images"] = []

    photo_file = await update.message.photo[-1].get_file()
    image_bytes = await photo_file.download_as_bytearray()
    context.user_data["user_images"].append(bytes(image_bytes))

    count = len(context.user_data["user_images"])

    keyboard = [
        [
            InlineKeyboardButton("📄 Convert to PDF", callback_data="convert_pdf"),
            InlineKeyboardButton("🗑️ Clear Images", callback_data="clear_images"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"✅ Photo received! Total queued: **{count}**",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


async def handle_document_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles uncompressed images sent as document files."""
    doc = update.message.document
    if doc.mime_type and doc.mime_type.startswith("image/"):
        if "user_images" not in context.user_data:
            context.user_data["user_images"] = []

        file = await doc.get_file()
        image_bytes = await file.download_as_bytearray()
        context.user_data["user_images"].append(bytes(image_bytes))

        count = len(context.user_data["user_images"])

        keyboard = [
            [
                InlineKeyboardButton("📄 Convert to PDF", callback_data="convert_pdf"),
                InlineKeyboardButton("🗑️ Clear Images", callback_data="clear_images"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"✅ File image received! Total queued: **{count}**",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "⚠️ Please send a valid image file (JPG, PNG, WEBP, etc.)."
        )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes button actions."""
    query = update.callback_query
    await query.answer()

    images = context.user_data.get("user_images", [])

    if query.data == "convert_pdf":
        if not images:
            await query.edit_message_text(
                "❌ No images queued. Please send some photos first."
            )
            return

        await query.edit_message_text("⏳ Converting images into PDF...")
        await context.bot.send_chat_action(
            chat_id=query.message.chat_id, action=ChatAction.UPLOAD_DOCUMENT
        )

        try:
            converted_images = []
            for img_bytes in images:
                image = Image.open(io.BytesIO(img_bytes))
                if image.mode != "RGB":
                    image = image.convert("RGB")

                buf = io.BytesIO()
                image.save(buf, format="JPEG")
                converted_images.append(buf.getvalue())

            # Convert images to PDF
            pdf_bytes = img2pdf.convert(converted_images)

            pdf_file = io.BytesIO(pdf_bytes)
            pdf_file.name = "converted.pdf"

            await query.message.reply_document(
                document=pdf_file,
                filename="converted.pdf",
                caption="🎉 Here is your converted PDF document!",
            )

            # Reset queue after conversion
            context.user_data["user_images"] = []

        except Exception as e:
            logger.error(f"Error during PDF conversion: {e}")
            await query.message.reply_text(
                "❌ Failed to convert images to PDF. Please try again."
            )

    elif query.data == "clear_images":
        context.user_data["user_images"] = []
        await query.edit_message_text("🗑️ Queue cleared. Send new images anytime.")


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fallback handler for unrecognized commands."""
    await update.message.reply_text(
        "❓ Unrecognized command. Use /help to see available commands."
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler."""
    logger.error("Exception while handling update:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ An unexpected error occurred while processing your request."
        )


def main():
    # Fallback check for either variable name
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN")

    if not token:
        raise ValueError("Neither TELEGRAM_BOT_TOKEN nor BOT_TOKEN environment variable is set!")

    app = (
        ApplicationBuilder()
        .token(token)
        .post_init(post_init)
        .build()
    )

    # Registered Command Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("clear", clear_command))

    # Media and Button Handlers
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.IMAGE, handle_document_photo))
    app.add_handler(CallbackQueryHandler(button_callback))

    # Unknown Command Fallback (must be added last among command handlers)
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    # Error Handler
    app.add_error_handler(error_handler)

    logger.info("Bot started successfully...")
    app.run_polling()


if __name__ == "__main__":
    main()
