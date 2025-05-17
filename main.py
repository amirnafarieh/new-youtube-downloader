import os
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.error import TelegramError
import yt_dlp
import asyncio

# تنظیم لاگ
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# خواندن توکن و اطلاعات کانال از متغیرهای محیطی
TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL = os.environ.get("CHANNEL_USERNAME") or os.environ.get("CHANNEL_ID")

if not TOKEN:
    raise ValueError("❌ BOT_TOKEN not set in environment variables!")

if CHANNEL and not CHANNEL.startswith("@") and not CHANNEL.startswith("-100"):
    CHANNEL = f"@{CHANNEL}"

# تابع بررسی عضویت
async def is_user_subscribed(user_id: int, bot) -> bool:
    if not CHANNEL:
        return True
    try:
        member = await bot.get_chat_member(CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except TelegramError as e:
        logging.warning(f"❗️Membership check failed: {e}")
        return False

# /start command
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

# پیام حاوی لینک یوتیوب
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

# بررسی مجدد عضویت با دکمه "عضو شدم"
async def check_joined(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if await is_user_subscribed(user_id, context.bot):
        await query.edit_message_text("✅ تایید شد! حالا لینک ویدیو را بفرست.")
    else:
        await query.answer("❌ هنوز عضو کانال نشدی!", show_alert=True)

# دانلود و ارسال فایل
async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    quality = query.data
    url = context.user_data.get("url")

    if not url:
        await query.edit_message_text("❗ لینک ویدیو یافت نشد. لطفاً دوباره لینک را ارسال کنید.")
        return

    await query.edit_message_text("⏳ در حال آماده‌سازی فایل...")

    format_map = {
        "mp3": "bestaudio/best",
        "360p": "18",
        "720p": "22",
        "1080p": "137+140",
        "4k": "313+140"
    }

    ydl_opts = {
        "format": format_map.get(quality, "22"),
        "outtmpl": "%(id)s.%(ext)s",
        "quiet": True
    }

    if quality == "mp3":
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128"
        }]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            filename = ydl.prepare_filename(info)
            if quality == "mp3":
                filename = filename.rsplit(".", 1)[0] + ".mp3"

        await context.bot.send_document(chat_id=query.from_user.id, document=open(filename, "rb"), caption="✅ فایل شما آماده است!")
        os.remove(filename)

    except Exception as e:
        logging.exception("Download error")
        await query.edit_message_text(f"❌ خطا در دانلود: {e}")

# اجرای ربات
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(check_joined, pattern="^check_joined$"))
    app.add_handler(CallbackQueryHandler(download_callback, pattern="^(mp3|360p|720p|1080p|4k)$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("🤖 Bot is running...")
    app.run_polling()
