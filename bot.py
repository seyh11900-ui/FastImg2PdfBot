import logging
import os
import tempfile
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from moviepy.editor import VideoFileClip

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Retrieve Telegram Bot Token from Environment Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")


async def post_init(application: Application) -> None:
    """Set bot commands menu on startup."""
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("help", "How to use the bot"),
        BotCommand("about", "Information about the bot"),
        BotCommand("cancel", "Cancel current action"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Bot command menu registered successfully.")


async def start_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Respond to the /start command in Khmer."""
    if not update.message:
        return

    welcome_text = (
        "👋 **សូមស្វាគមន៍មកកាន់ Video to MP3 Converter Bot!**\n\n"
        "សូមផ្ញើ ឬ Forward ឯកសារ **វីដេអូ**, **Video Note (វីដេអូមូល)** ឬ **ឯកសារវីដេអូ** ផ្សេងៗមកកាន់ Chat នេះ "
        "ខ្ញុំនឹងធ្វើការទាញយកសំឡេង និងផ្ញើជូនអ្នកវិញជាឯកសារ **MP3** ដោយស្វ័យប្រវត្តិ។\n\n"
        "ចុច /help ដើម្បីមើលការណែនាំ និងបញ្ជាផ្សេងៗ។"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def help_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Respond to the /help command."""
    if not update.message:
        return

    help_text = (
        "🤖 **How to Use This Bot:**\n\n"
        "1. Send or forward any video or video note file.\n"
        "2. Wait a few moments for conversion.\n"
        "3. Download your converted MP3 file.\n\n"
        "📌 **Available Commands:**\n"
        "• `/start` - Start or restart the bot\n"
        "• `/help` - Show instructions and commands\n"
        "• `/about` - Technical details and specs\n"
        "• `/cancel` - Reset or cancel current operation"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def about_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Respond to the /about command."""
    if not update.message:
        return

    about_text = (
        "ℹ️ **About Video to MP3 Bot**\n\n"
        "• **Output Format:** MP3 (libmp3lame)\n"
        "• **Supported Inputs:** MP4, MOV, AVI, MKV, Video Notes, Telegram Video Files\n"
        "• **Processing:** Automated audio extraction via FFmpeg & MoviePy\n"
        "• **Privacy:** Files are processed securely in temporary storage and deleted immediately."
    )
    await update.message.reply_text(about_text, parse_mode="Markdown")


async def cancel_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Respond to the /cancel command."""
    if not update.message:
        return

    await update.message.reply_text(
        "🚫 Operation canceled. Send a new video whenever you are ready!",
        parse_mode="Markdown",
    )


async def handle_video(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Process incoming videos and extract audio to MP3."""
    message = update.message
    if not message:
        return

    video_obj = message.video or message.video_note or message.document

    if not video_obj:
        await message.reply_text(
            "⚠️ Please send a valid video file or video note."
        )
        return

    status_msg = await message.reply_text(
        "⏳ *Downloading video...*", parse_mode="Markdown"
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = os.path.join(temp_dir, "input_video")
        output_path = os.path.join(temp_dir, "audio.mp3")

        try:
            # Download file from Telegram
            telegram_file = await context.bot.get_file(video_obj.file_id)
            await telegram_file.download_to_drive(custom_path=input_path)

            await status_msg.edit_text(
                "⚙️ *Converting video to MP3...*", parse_mode="Markdown"
            )

            # Extract audio using moviepy
            clip = VideoFileClip(input_path)

            if clip.audio is None:
                await status_msg.edit_text(
                    "❌ *No audio track detected in this video file.*",
                    parse_mode="Markdown",
                )
                clip.close()
                return

            clip.audio.write_audiofile(
                output_path, codec="libmp3lame", logger=None
            )
            clip.close()

            await status_msg.edit_text(
                "📤 *Uploading MP3 file...*", parse_mode="Markdown"
            )

            # Send back converted audio file
            with open(output_path, "rb") as audio_file:
                await message.reply_audio(
                    audio=audio_file,
                    title="Converted Audio",
                    performer="Video to MP3 Bot",
                    caption="✅ Here is your converted MP3 file!",
                )

            await status_msg.delete()

        except Exception as e:
            logger.error(f"Error processing video: {e}")
            await status_msg.edit_text(
                "❌ *An error occurred while processing the video.* Please ensure the file is supported and try again.",
                parse_mode="Markdown",
            )


def main() -> None:
    """Initialize and start the Telegram bot."""
    if not BOT_TOKEN:
        logger.error("FATAL: 'BOT_TOKEN' environment variable is missing.")
        return

    # Build bot application with startup command registration
    application = (
        Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    )

    # Command Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("cancel", cancel_command))

    # Media Handler for Videos, Video Notes, and Document Videos
    application.add_handler(
        MessageHandler(
            filters.VIDEO | filters.VIDEO_NOTE | filters.Document.VIDEO,
            handle_video,
        )
    )

    logger.info("Bot is active and listening for updates...")
    application.run_polling()


if __name__ == "__main__":
    main()
