import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils import executor
from aiogram.dispatcher.filters import CommandStart
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.dispatcher.handler import CancelHandler
from aiogram.dispatcher import FSMContext
import yt_dlp
import asyncio

API_TOKEN = os.environ.get('YOUR_BOT_TOKEN', 'YOUR_BOT_TOKEN')
CHANNEL_ID = -1002134567890  # ID کانال @amirnafarieh_co
CHANNEL_USERNAME = 'amirnafarieh_co'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Middleware برای بررسی عضویت
class CheckSubscription(BaseMiddleware):
    async def on_pre_process_update(self, update: types.Update, data: dict):
        if update.message:
            user_id = update.message.from_user.id
        elif update.callback_query:
            user_id = update.callback_query.from_user.id
        else:
            return

        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status not in ['member', 'creator', 'administrator']:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{CHANNEL_USERNAME}"))
            markup.add(InlineKeyboardButton("✅ عضو شدم", callback_data="check_joined"))
            if update.message:
                await update.message.answer("برای استفاده از ربات ابتدا در کانال زیر عضو شوید:", reply_markup=markup)
            elif update.callback_query:
                await update.callback_query.message.answer("برای استفاده از ربات ابتدا در کانال زیر عضو شوید:", reply_markup=markup)
            raise CancelHandler()

dp.middleware.setup(CheckSubscription())

@dp.message_handler(CommandStart())
async def start_cmd(message: types.Message):
    await message.reply("سلام! 🎬 لینک ویدیوی یوتیوب را برای دانلود ارسال کن.")

@dp.message_handler(lambda message: 'youtube.com' in message.text or 'youtu.be' in message.text)
async def handle_youtube_link(message: types.Message, state: FSMContext):
    url = message.text.strip()

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🎧 MP3 (128kbps)", callback_data=f"mp3|{url}"),
        InlineKeyboardButton("📹 MP4 (360p)", callback_data=f"360p|{url}"),
        InlineKeyboardButton("🎥 MP4 (720p)", callback_data=f"720p|{url}"),
        InlineKeyboardButton("🎞 MP4 (1080p)", callback_data=f"1080p|{url}"),
        InlineKeyboardButton("🎬 MP4 (4K)", callback_data=f"4k|{url}")
    )
    await message.reply("کیفیت مورد نظر را انتخاب کنید:", reply_markup=markup)

@dp.callback_query_handler(lambda call: call.data.startswith(('mp3', '360p', '720p', '1080p', '4k')))
async def process_download(call: types.CallbackQuery):
    quality, url = call.data.split('|')
    await call.message.edit_text("⏳ در حال آماده‌سازی فایل... لطفاً منتظر بمانید.")

    ydl_opts = {
        'outtmpl': f'{call.from_user.id}_%(title)s.%(ext)s',
        'quiet': True,
    }

    if quality == 'mp3':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128'
            }]
        })
    elif quality == '360p':
        ydl_opts['format'] = '18'
    elif quality == '720p':
        ydl_opts['format'] = '22'
    elif quality == '1080p':
        ydl_opts['format'] = '137+140'
    elif quality == '4k':
        ydl_opts['format'] = '313+140'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if quality == 'mp3':
                filename = filename.rsplit('.', 1)[0] + '.mp3'

        await bot.send_document(chat_id=call.from_user.id, document=types.InputFile(filename),
                                 caption=f"✅ فایل آماده شد!")
        os.remove(filename)
    except Exception as e:
        await call.message.edit_text(f"❌ خطا در دانلود: {e}")

@dp.callback_query_handler(lambda call: call.data == "check_joined")
async def check_joined(call: types.CallbackQuery):
    user_id = call.from_user.id
    member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
    if member.status in ['member', 'creator', 'administrator']:
        await call.message.edit_text("✅ تایید شد! حالا لینک ویدیو را بفرست.")
    else:
        await call.answer("هنوز عضو نیستی!", show_alert=True)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
