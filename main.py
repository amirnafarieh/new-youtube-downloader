import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

user_links = {}  # ذخیره لینک‌های کاربران
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

@bot.message_handler(commands=['start'])
def welcome(message):
    bot.send_message(
        message.chat.id,
        "👋 سلام! خوش اومدی به ربات دانلود از یوتیوب.\n\n📥 لطفاً لینک ویدیوی یوتیوب رو بفرست تا بتونی با کیفیت دلخواه دریافتش کنی."
    )

@bot.message_handler(func=lambda m: 'youtube.com' in m.text or 'youtu.be' in m.text)
def get_youtube_link(message):
    user_links[message.chat.id] = message.text

    # مرحله اول: انتخاب «ویدیو»
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎥 ویدیو", callback_data="video"))
    bot.send_message(
        message.chat.id,
        "✅ لینک یوتیوب دریافت شد!\nبرای ادامه روی دکمه زیر کلیک کن:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "video")
def show_qualities(call):
    chat_id = call.message.chat.id
    url = user_links.get(chat_id)

    if not url:
        bot.send_message(chat_id, "❌ لینک پیدا نشد. لطفاً مجدد لینک رو ارسال کن.")
        return

    # استخراج لیست کیفیت‌ها
    try:
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'forcejson': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])

        # ساخت دکمه‌های کیفیت
        markup = InlineKeyboardMarkup(row_width=2)
        added = set()
        for f in formats:
            if f.get('ext') == 'mp4' and f.get('height'):
                label = f"{f['height']}p"
                if label not in added:
                    added.add(label)
                    callback_data = f"quality|{f['format_id']}"
                    markup.add(InlineKeyboardButton(label, callback_data=callback_data))

        bot.send_message(chat_id, "⬇️ لطفاً کیفیت مورد نظر را انتخاب کن:", reply_markup=markup)

    except Exception as e:
        bot.send_message(chat_id, f"❌ خطا در دریافت کیفیت‌ها:\n{e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("quality|"))
def download_by_quality(call):
    chat_id = call.message.chat.id
    url = user_links.get(chat_id)
    format_id = call.data.split("|")[1]

    bot.send_message(chat_id, f"📥 در حال دانلود با کیفیت انتخابی... لطفاً صبر کن.")

    try:
        ydl_opts = {
            'quiet': True,
            'format': format_id,
            'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filepath = ydl.prepare_filename(info)

        with open(filepath, 'rb') as f:
            bot.send_video(chat_id, f)

        os.remove(filepath)

    except Exception as e:
        bot.send_message(chat_id, f"❌ خطا در دانلود یا ارسال فایل:\n{e}")
