import os
import logging
import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.error import TelegramError
import yt_dlp

# تنظیم لاگر برای نمایش زمان، سطح و پیام
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# دریافت تنظیمات از متغیرهای محیطی
TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("TOKEN")
CHANNEL = os.environ.get("CHANNEL_ID") or os.environ.get("CHANNEL_USERNAME") or os.environ.get("CHANNEL")
if not TOKEN:
    logging.error("Bot token not provided in environment variables!")
    raise SystemExit("Error: BOT_TOKEN is not set.")
# اگر CHANNEL به صورت عدد (آیدی) باشد، به int تبدیل شود
if CHANNEL and CHANNEL.isdigit():
    CHANNEL = int(CHANNEL)
elif CHANNEL and not CHANNEL.startswith("@"):
    CHANNEL = "@" + CHANNEL  # اضافه کردن @ در صورت نیاز

# تابع کمکی برای بررسی عضویت کاربر در کانال
async def is_user_subscribed(user_id: int, bot) -> bool:
    """بررسی می‌کند آیا user_id در CHANNEL عضو است یا خیر."""
    if not CHANNEL:
        return True  # اگر کانالی تعریف نشده، دسترسی آزاد است
    try:
        member = await bot.get_chat_member(CHANNEL, user_id)
        status = member.status  # وضعیت کاربر در کانال
        # وضعیت‌های معتبر عضویت: member, administrator, creator (owner)
        if status in ("member", "administrator", "creator", "owner"):
            return True
        else:
            return False
    except TelegramError as e:
        # هر گونه خطا (مانند کاربر پیدا نشد یا عدم دسترسی ربات) را به منزله عدم عضویت می‌گیریم
        logging.warning(f"Membership check failed: {e}")
        return False

# هندلر دستور /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    # بررسی عضویت کاربر در کانال (اگر CHANNEL تنظیم شده باشد)
    if not await is_user_subscribed(user.id, context.bot):
        await update.message.reply_text(
            "⚠️ برای استفاده از این ربات، ابتدا باید عضو کانال ما شوید.\n"
            f"کانال: {CHANNEL}\nپس از عضویت، دوباره /start را ارسال کنید."
        )
        return
    # خوشامدگویی و راهنمایی کاربر
    await update.message.reply_text("سلام! 👋\nلینک ویدیوی YouTube موردنظر خود را ارسال کنید تا آن را برای شما دانلود کنم.")

# هندلر دریافت پیام‌های متنی (لینک‌ها)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text = (update.message.text or "").strip()

    # ابتدا عضویت کاربر بررسی شود
    if not await is_user_subscribed(user.id, context.bot):
        await update.message.reply_text(
            "⚠️ شما هنوز عضو کانال تعیین‌شده نیستید!\n"
            f"لطفاً ابتدا در کانال {CHANNEL} عضو شوید و سپس دوباره تلاش کنید."
        )
        return

    # بررسی اینکه پیام حاوی لینک YouTube باشد
    if "youtu.be" not in text and "youtube.com" not in text:
        await update.message.reply_text("❗ لطفاً یک لینک معتبر از YouTube ارسال کنید.")
        return

    # ذخیره لینک YouTube در داده کاربر برای استفاده در مرحله بعد
    context.user_data["youtube_url"] = text

    # ساخت دکمه‌های انتخاب کیفیت/فرمت
    buttons = [
        [InlineKeyboardButton("دانلود به‌صورت MP3 🎵", callback_data="MP3")],
        [InlineKeyboardButton("کیفیت 360p", callback_data="360p"),
         InlineKeyboardButton("کیفیت 720p", callback_data="720p")],
        [InlineKeyboardButton("کیفیت 1080p", callback_data="1080p"),
         InlineKeyboardButton("کیفیت 4K", callback_data="4K")]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("لطفاً کیفیت مورد نظر را انتخاب کنید:", reply_markup=reply_markup)

# هندلر کال‌بک برای انتخاب کیفیت و دانلود
async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data  # داده‌ای که از دکمه دریافت شده (یکی از کیفیت‌ها)
    user = update.effective_user

    await query.answer()  # پاسخ سریع به CallbackQuery (حذف حالت "در انتظار")
    # دوباره بررسی عضویت (اختیاری، معمولاً لازم نیست چون قبلاً چک شده)
    if not await is_user_subscribed(user.id, context.bot):
        await query.message.reply_text("⚠️ دسترسی غیرمجاز: ابتدا باید در کانال عضو شوید.")
        return

    # بازیابی لینک ویدیو از داده‌های کاربر
    url = context.user_data.get("youtube_url")
    if not url:
        await query.edit_message_text("❗ لینک ویدیو یافت نشد، لطفاً مجدداً لینک را ارسال کنید.")
        return

    # اطلاع دادن به کاربر که دانلود شروع شده
    if data == "MP3":
        await query.edit_message_text("در حال دانلود به‌صورت MP3، لطفاً منتظر بمانید... 🎧")
    else:
        await query.edit_message_text(f"در حال دانلود ویدیو با کیفیت {data}، لطفاً منتظر بمانید... ⏳")

    # تنظیمات عمومی yt_dlp
    download_dir = os.path.join(os.getcwd(), "downloads")
    os.makedirs(download_dir, exist_ok=True)
    ydl_opts = {
        "outtmpl": os.path.join(download_dir, "%(id)s.%(ext)s"),
        "quiet": True,
        "noprogress": True  # عدم نمایش پروگرس (تا لاگ تمیز بماند)
    }

    # انتخاب format بر اساس کیفیت موردنظر
    if data == "MP3":
        # دانلود بهترین کیفیت صدا و تبدیل به MP3
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }]
        })
    else:
        # استخراج عدد کیفیت (برای 4K -> 2160p)
        if data.upper() == "4K":
            height = 2160
        else:
            # حذف پسوند 'p' و تبدیل به int
            try:
                height = int(data.replace("p", ""))
            except:
                height = 0
        if height > 0:
            fmt = f"bestvideo[height<={height}]+bestaudio/best[height<={height}]"
        else:
            fmt = "best"  # به طور پیشفرض
        ydl_opts["format"] = fmt

    file_path = None
    try:
        # ایجاد شیء دانلودر و اجرای دانلود در ترد جداگانه
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            # تعیین مسیر فایل دانلود شده
            file_path = ydl.prepare_filename(info)
            # اگر پس از postprocessing پسوند mp3 تولید شده باشد، نام فایل را اصلاح می‌کنیم
            if data == "MP3":
                file_path = os.path.splitext(file_path)[0] + ".mp3"
    except Exception as e:
        logging.exception(f"Error downloading video: {e}")
        await query.edit_message_text("⚠️ خطایی در دانلود ویدیو رخ داد. لطفاً بعداً دوباره امتحان کنید.")
        return

    # ارسال فایل به کاربر
    try:
        chat_id = update.effective_chat.id
        # باز کردن فایل در حالت باینری و ارسال به عنوان Document
        with open(file_path, "rb") as f:
            await context.bot.send_document(chat_id=chat_id, document=f)
        # ویرایش پیام به متن موفقیت (اختیاری - می‌توان این بخش را حذف کرد)
        await query.edit_message_text("✅ فایل آماده شد و برای شما ارسال گردید.")
    except Exception as e:
        logging.exception(f"Error sending file: {e}")
        await query.edit_message_text("⚠️ ارسال فایل با مشکل مواجه شد.")
    finally:
        # حذف فایل موقت از سرور
        if file_path:
            try:
                os.remove(file_path)
            except OSError as e:
                logging.warning(f"Could not delete file: {e}")

# تابع main برای راه‌اندازی ربات
async def main():
    application = ApplicationBuilder().token(TOKEN).build()

    # افزودن هندلرها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(download_callback, pattern="^(MP3|360p|720p|1080p|4K)$"))

    # ثبت یک هندلر عمومی خطا (اختیاری – برای لاگ کردن خطاهای پیش‌بینی‌نشده)
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logging.error("Unexpected error occurred:", exc_info=context.error)
        # اطلاع به کاربر در صورت امکان
        try:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="⚠️ یک خطای پیش‌بینی‌نشده رخ داد.")
        except:
            pass
    application.add_error_handler(error_handler)

    # اجرای polling
    logging.info("Bot is polling...")  # لاگ شروع
    await application.run_polling()

# اجرای main در صورت اجرا شدن این فایل
if __name__ == "__main__":
    asyncio.run(main())
