"""
Telegram bot to convert landscape videos to vertical 9:16 portrait
Center-crop using FFmpeg
"""

import os
import subprocess
import json
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ===== Settings =====
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
OUTPUT_DIR = "/tmp/video_bot"
os.makedirs(OUTPUT_DIR, exist_ok=True)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def get_video_info(input_path: str) -> dict:
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        input_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)

    for stream in data.get("streams", []):
        if stream["codec_type"] == "video":
            return {
                "width": int(stream["width"]),
                "height": int(stream["height"]),
            }
    raise ValueError("No video stream found")


def convert_to_vertical(input_path: str, output_path: str) -> bool:
    info = get_video_info(input_path)
    src_w, src_h = info["width"], info["height"]

    new_w = int(src_h * 9 / 16)

    if new_w > src_w:
        new_h = int(src_w * 16 / 9)
        crop_filter = f"crop={src_w}:{new_h}:{0}:{(src_h - new_h) // 2}"
    else:
        crop_filter = f"crop={new_w}:{src_h}:{(src_w - new_w) // 2}:{0}"

    crop_filter += ",pad=ceil(iw/2)*2:ceil(ih/2)*2"

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", crop_filter,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]

    logger.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error(f"FFmpeg error: {result.stderr}")
        return False
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello! Send me a landscape video and I will convert it to vertical 9:16 "
        "with center crop - perfect for TikTok and Instagram Reels."
    )


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("Receiving video...")

    video = update.message.video or update.message.document
    if not video:
        await msg.edit_text("Could not detect a video. Try again.")
        return

    if update.message.document:
        mime = update.message.document.mime_type or ""
        if not mime.startswith("video/"):
            await msg.edit_text("File does not appear to be a video.")
            return

    try:
        file = await video.get_file()
        file_ext = ".mp4"
        input_path = os.path.join(OUTPUT_DIR, f"input_{update.message.message_id}{file_ext}")
        output_path = os.path.join(OUTPUT_DIR, f"vertical_{update.message.message_id}{file_ext}")

        await msg.edit_text("Downloading video...")
        await file.download_to_drive(input_path)

        await msg.edit_text("Converting to vertical 9:16...")
        success = convert_to_vertical(input_path, output_path)

        if not success:
            await msg.edit_text("Conversion error. Try a different video.")
            return

        await msg.edit_text("Sending converted video...")
        with open(output_path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=f"vertical_{video.file_name or 'video.mp4'}",
                caption="Video converted to vertical 9:16!",
            )
        await msg.delete()

    except Exception as e:
        logger.error(f"Error: {e}")
        await msg.edit_text(f"Error: {str(e)}")

    finally:
        for path in [input_path, output_path]:
            if os.path.exists(path):
                os.remove(path)


def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("Error: Set your bot token!")
        print("  export TELEGRAM_BOT_TOKEN='your-token'")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))

    print("Bot is running! Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
