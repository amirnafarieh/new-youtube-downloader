import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp

API_TOKEN = os.environ.get('YOUR_BOT_TOKEN')
CHANNEL_ID = -1002134567890
CHANNEL_USERNAME = 'amirnafarieh_co'

logging.basicConfig(level=logging.INFO)

async def check_subscription(user_id, context: ContextTypes.DEFAULT_TYPE):
    member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
    return member.status in ['member', 'creator', 'administrator']

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_subscription(update.effective_user.id, context):
        keyboard = [[InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{CHANNEL_USERNAME}")],
                    [InlineKeyboardButton("✅ عضو شدم", callback_data="check_joined")]]
        await update.message.reply_text("لطفا ابتدا در کانال عضو شوید:", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    await update.message.reply_text("سلام! 🎬 لینک ویدیوی یوتیوب را برای دانلود ارسال کن.")

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    keyboard = [[InlineKeyboardButton("🎧 MP3", callback_data=f"mp3|{url}"),
                 InlineKeyboardButton("📹 360p", callback_data=f"360p|{url}")],
                [InlineKeyboardButton("🎥 720p", callback_data=f"720p|{url}"),
                 InlineKeyboardButton("🎞 1080p", callback_data=f"1080p|{url}")],
                [InlineKeyboardButton("🎬 4K", callback_data=f"4k|{url}")]]
    await update.message.reply_text("کیفیت دانلود را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    quality, url = query.data.split('|')

    await query.edit_message_text(text="⏳ در حال آماده‌سازی فایل...")

    formats = {
        'mp3': 'bestaudio/best',
        '360p': '18',
        '720p': '22',
        '1080p': '137+140',
        '4k': '313+140'
    }

    ydl_opts = {'format': formats.get(quality, '22'), 'quiet': True, 'outtmpl': '%(id)s.%(ext)s'}

    if quality == 'mp3':
        ydl_opts.update({
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128'
            }]
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if quality == 'mp3':
                filename = filename.rsplit('.', 1)[0] + '.mp3'

        await context.bot.send_document(chat_id=query.from_user.id, document=open(filename, 'rb'), caption="✅ دانلود شد!")
        os.remove(filename)
    except Exception as e:
        await query.edit_message_text(f"❌ خطا در دانلود: {e}")

async def check_joined(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if await check_subscription(user_id, context):
        await query.edit_message_text("✅ تایید شد! حالا لینک ویدیو را بفرست.")
    else:
        await query.answer("هنوز عضو نیستی!", show_alert=True)

if __name__ == '__main__':
    app = ApplicationBuilder().token(API_TOKEN).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_link))
    app.add_handler(CallbackQueryHandler(download_video, pattern='^(mp3|360p|720p|1080p|4k)\|'))
    app.add_handler(CallbackQueryHandler(check_joined, pattern='^check_joined$'))

    app.run_polling()
