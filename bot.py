import asyncio
import logging
import os
import re
import tempfile

import yt_dlp
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO
)
log = logging.getLogger("tiktok-bot")

TOKEN = os.environ["8631682312:AAEg5mv3QEOuyyJ_4T2vYtJoy25ZEUjtdeE"]
MAX_BYTES = 50 * 1024 * 1024  # Telegram bot upload limit
URL_RE = re.compile(r"https?://(?:[\w-]+\.)?tiktok\.com/\S+", re.I)


def download_video(url: str, outdir: str) -> tuple[str, str]:
    opts = {
        "outtmpl": os.path.join(outdir, "%(id)s.%(ext)s"),
        "format": "best[ext=mp4][filesize<50M]/best[ext=mp4]/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "max_filesize": MAX_BYTES,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info), (info.get("description") or "")[:900]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Send me a TikTok link and I'll download the video for you."
    )


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    match = URL_RE.search(update.message.text or "")
    if not match:
        await update.message.reply_text("Please send a valid TikTok link.")
        return

    status = await update.message.reply_text("⏳ Downloading…")
    await update.message.chat.send_action(ChatAction.UPLOAD_VIDEO)

    try:
        with tempfile.TemporaryDirectory() as tmp:
            path, caption = await asyncio.to_thread(
                download_video, match.group(0), tmp
            )
            if not os.path.exists(path) or os.path.getsize(path) > MAX_BYTES:
                raise ValueError("File missing or larger than 50 MB")
            with open(path, "rb") as f:
                await update.message.reply_video(
                    video=f,
                    caption=caption or None,
                    supports_streaming=True,
                    read_timeout=120,
                    write_timeout=120,
                )
        await status.delete()
    except Exception as e:
        log.exception("Download failed: %s", e)
        await status.edit_text(
            "❌ Couldn't download that video. It may be private, removed, or too large."
        )


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    log.info("Bot started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
