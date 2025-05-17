import os
import re
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.error import TelegramError
import yt_dlp
import asyncio

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL = os.environ.get("CHANNEL_USERNAME") or os.environ.get("CHANNEL_ID")

if not TOKEN:
    raise ValueError("❌ BOT_TOKEN not set in environment variables!")

if CHANNEL and not CHANNEL.startswith("@") and not CHANNEL.startswith("-100"):
    CHANNEL = f"@{CHANNEL}"

def clean_title(title):
    return re.sub(r'[\\/*?:"<>|]', "", title).strip()

async def is_user_subscribed(user_id: int, bot) -> bool:
    if not CHANNEL:
        return True
    try:
        member = await bot.get_chat_member(CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except TelegramError as e:
        logging.warning(f"❗️Membership check failed: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await is_user_subscribed(user.id, context.bot):
        buttons = [
            [InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{CHANNEL.replace('@', '')}")],
            [InlineKeyboardButton("✅ عضو شدم", callback_data="check_joined")]
        ]
        await update.message.reply_text(
            "برای استفاده از ربات، ابتدا در کانال زیر عضو شوید:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return
    await update.message.reply_text("سلام! 🎬 لینک ویدیوی یوتیوب را بفرست تا دانلود کنم.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()

    if not await is_user_subscribed(user.id, context.bot):
        await update.message.reply_text("⚠️ ابتدا در کانال عضو شوید. سپس دوباره امتحان کنید.")
        return

    if "youtu.be" not in text and "youtube.com" not in text:
        await update.message.reply_text("❗ لطفاً لینک معتبر YouTube ارسال کنید.")
        return

    context.user_data["url"] = text
    buttons = [
        [InlineKeyboardButton("🎧 MP3", callback_data="mp3")],
        [InlineKeyboardButton("📹 360p", callback_data="360p"), InlineKeyboardButton("🎥 720p", callback_data="720p")],
        [InlineKeyboardButton("🎞 1080p", callback_data="1080p"), InlineKeyboardButton("🎬 4K", callback_data="4k")]
    ]
    await update.message.reply_text("✅ کیفیت مورد نظر را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(buttons))

async def check_joined(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if await is_user_subscribed(user_id, context.bot):
        await query.edit_message_text("✅ تایید شد! حالا لینک ویدیو را بفرست.")
    else:
        await query.answer("❌ هنوز عضو کانال نشدی!", show_alert=True)

async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    quality = query.data
    url = context.user_data.get("url")

    if not url:
        await query.edit_message_text("❗ لینک ویدیو یافت نشد. لطفاً دوباره لینک را ارسال کنید.")
        return

    await query.edit_message_text("⏳ در حال آماده‌سازی فایل...")

    format_fallback = {
        "mp3": "bestaudio/best",
        "360p": "bestvideo[height<=360]+bestaudio/best/best",
        "720p": "bestvideo[height<=720]+bestaudio/best/best",
        "1080p": "bestvideo[height<=1080]+bestaudio/best/best",
        "4k": "bestvideo[height<=2160]+bestaudio/best/best"
    }

    ext = "mp3" if quality == "mp3" else "mp4"

    ydl_opts = {
        "format": format_fallback.get(quality, "best"),
        "outtmpl": "%(title)s.%(ext)s",
        "quiet": True,
        "geo_bypass": True,
        "cookiefile": "cookies.txt",
        "merge_output_format": "mp4",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
    }

    if quality == "mp3":
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128"
        }]
    else:
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4"
        }]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            title = clean_title(info.get("title", "video"))
            filename = f"{title}.{ext}"

        await context.bot.send_document(chat_id=query.from_user.id, document=open(filename, "rb"), caption="✅ فایل شما آماده است!")
        os.remove(filename)

    except Exception as e:
        logging.exception("Download error")
        await query.edit_message_text(f"❌ خطا در دانلود: {e}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(check_joined, pattern="^check_joined$"))
    app.add_handler(CallbackQueryHandler(download_callback, pattern="^(mp3|360p|720p|1080p|4k)$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("🤖 Bot is running...")
    app.run_polling()
