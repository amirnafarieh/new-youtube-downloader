import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp
import subprocess

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

user_links = {}
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

@bot.message_handler(commands=['start'])
def welcome(message):
    bot.send_message(
        message.chat.id,
        "👋 سلام! به ربات دانلود یوتیوب خوش اومدی.\n\n📥 لطفاً لینک ویدیوی یوتیوب رو بفرست."
    )

@bot.message_handler(func=lambda m: 'youtube.com' in m.text or 'youtu.be' in m.text)
def receive_link(message):
    user_links[message.chat.id] = message.text

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎥 ویدیو", callback_data="video"))
    bot.send_message(message.chat.id, "✅ لینک دریافت شد. لطفاً ادامه بده:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "video")
def list_formats(call):
    chat_id = call.message.chat.id
    url = user_links.get(chat_id)

    if not url:
        bot.send_message(chat_id, "❌ لینک پیدا نشد. لطفاً مجدد ارسال کن.")
        return

    try:
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'forcejson': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])

        markup = InlineKeyboardMarkup(row_width=2)
        added = set()
        for f in formats:
            if f.get('ext') and f.get('height') and f['ext'] != 'webm':
                label = f"{f['height']}p"
                if label not in added:
                    added.add(label)
                    cb = f"q|{f['format_id']}"
                    markup.add(InlineKeyboardButton(label, callback_data=cb))

        bot.send_message(chat_id, "⬇️ کیفیت مورد نظر را انتخاب کن:", reply_markup=markup)

    except Exception as e:
        bot.send_message(chat_id, f"❌ خطا در دریافت کیفیت‌ها:\n{e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("q|"))
def download_and_send(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    url = user_links.get(chat_id)
    format_id = call.data.split("|")[1]

    bot.send_message(chat_id, "⏳ در حال دانلود و تبدیل به MP4...")

    try:
        ydl_opts = {
            'quiet': True,
            'format': format_id,
            'outtmpl': f'{DOWNLOAD_DIR}/input.%(ext)s'
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            input_path = ydl.prepare_filename(info)

        # مسیر خروجی تبدیل‌شده
        output_path = os.path.join(DOWNLOAD_DIR, 'output.mp4')

        # اجرای ffmpeg برای تبدیل فایل به MP4
        subprocess.run([
            'ffmpeg', '-i', input_path,
            '-c:v', 'libx264', '-preset', 'fast', '-c:a', 'aac',
            '-strict', 'experimental', output_path
        ], check=True)

        # ارسال به Saved Messages کاربر (با استفاده از user_id)
        with open(output_path, 'rb') as f:
            bot.send_document(user_id, f, caption="✅ فایل شما با موفقیت آماده شد.")

        # پاکسازی فایل‌ها
        os.remove(input_path)
        os.remove(output_path)

    except Exception as e:
        bot.send_message(chat_id, f"❌ خطا در تبدیل یا ارسال:\n{e}")
