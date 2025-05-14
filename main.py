import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import yt_dlp

# توکن از Railway Environment Variables خوانده می‌شود
API_TOKEN = os.environ.get("YOUR_BOT_TOKEN")
CHANNEL_USERNAME = "amirnafarieh_co"
CHANNEL_ID = f"@{CHANNEL_USERNAME}"

logging.basicConfig(level=logging.INFO)

async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.error(f"خطا در بررسی عضویت: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await check_subscription(user_id, context):
        keyboard = [
            [InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{CHANNEL_USERNAME}")],
            [InlineKeyboardButton("✅ عضو شدم", callback_data="check_joined")]
        ]
        await update.message.reply_text("برای استفاده از ربات، ابتدا در کانال زیر عضو شوید:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    await update.message.reply_text("سلام! 🎬 لینک ویدیوی یوتیوب را برای دانلود ارسال کن.")

async def handle_youtube_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    keyboard = [
        [InlineKeyboardButton("🎧 MP3", callback_data=f"mp3|{url}"), InlineKeyboardButton("📹 360p", callback_data=f"360p|{url}")],
        [InlineKeyboardButton("🎥 720p", callback_data=f"720p|{url}"), InlineKeyboardButton("🎞 1080p", callback_data=f"1080p|{url}")],
        [InlineKeyboardButton("🎬 4K", callback_data=f"4k|{url}")]
    ]
    await update.message.reply_text("✅ کیفیت مورد نظر را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

async def process_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    quality, url = query.data.split("|")
    await query.edit_message_text("⏳ در حال آماده‌سازی فایل...")

    formats = {
        "mp3": "bestaudio/best",
        "360p": "18",
        "720p": "22",
        "1080p": "137+140",
        "4k": "313+140"
    }

    ydl_opts = {
        "format": formats.get(quality, "22"),
        "quiet": True,
        "outtmpl": "%(id)s.%(ext)s"
    }

    if quality == "mp3":
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128"
        }]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if quality == "mp3":
                filename = filename.rsplit(".", 1)[0] + ".mp3"

        await context.bot.send_document(chat_id=query.from_user.id, document=open(filename, "rb"), caption="✅ فایل شما آماده است!")
        os.remove(filename)
    except Exception as e:
        await query.edit_message_text(f"❌ خطا در دانلود: {e}")

async def check_joined(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if await check_subscription(user_id, context):
        await query.edit_message_text("✅ تایید شد! حالا لینک ویدیو را بفرست.")
    else:
        await query.answer("❌ هنوز عضو کانال نشدی!", show_alert=True)

if __name__ == "__main__":
    app = ApplicationBuilder().token(API_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_youtube_link))
    app.add_handler(CallbackQueryHandler(process_download, pattern=r"^(mp3|360p|720p|1080p|4k)\|"))
    app.add_handler(CallbackQueryHandler(check_joined, pattern="^check_joined$"))
    app.run_polling()
