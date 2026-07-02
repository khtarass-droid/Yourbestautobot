import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("yourbestautobot")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1002681585680"))
DISCUSSION_GROUP_ID = int(os.getenv("DISCUSSION_GROUP_ID", "-1004435080882"))
CREDIT_URL = os.getenv("CREDIT_URL", "https://ref.best/Your_best_autoLV")
LOCATION_URL = os.getenv("LOCATION_URL", "https://maps.google.com/?q=49.22654,23.81327")
VIBER_URL = os.getenv("VIBER_URL", "viber://chat?number=%2B380676755121")
TIKTOK_URL = os.getenv("TIKTOK_URL", "https://www.tiktok.com/@yourbestauto")
MAX_MEDIA = int(os.getenv("MAX_MEDIA", "80"))

ASKS = [
    ("car", "🚗 Назва авто?\nНаприклад: Ford Escape Titanium"),
    ("year", "📅 Рік?\nНаприклад: 2019"),
    ("engine", "⚙️ Двигун?\nНаприклад: 2.0"),
    ("drive", "🚘 Привід?\nНаприклад: AWD"),
    ("gearbox", "🔄 Коробка?\nНаприклад: Автомат"),
    ("mileage", "🛣 Пробіг?\nНаприклад: 100 000"),
    ("price", "💵 Ціна в доларах?\nНаприклад: 14 700"),
]

@dataclass
class MediaItem:
    kind: str  # photo/video
    file_id: str

@dataclass
class Session:
    media: List[MediaItem] = field(default_factory=list)
    data: Dict[str, str] = field(default_factory=dict)
    step: str = "media"  # media/fields/confirm
    ask_index: int = 0

sessions: Dict[int, Session] = {}


def keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Кредит", url=CREDIT_URL), InlineKeyboardButton("📍 Локація", url=LOCATION_URL)],
        [InlineKeyboardButton("📲 Viber", url=VIBER_URL), InlineKeyboardButton("🎵 TikTok", url=TIKTOK_URL)],
    ])


def fmt_price(raw: str) -> str:
    s = raw.replace("$", "").strip()
    return f"{s} $"


def make_caption(data: Dict[str, str]) -> str:
    return (
        f"🚗 <b>{data.get('car','')}</b>\n\n"
        f"📅 Рік: <b>{data.get('year','')}</b>\n"
        f"⚙️ Двигун: <b>{data.get('engine','')}</b>\n"
        f"🚘 Привід: <b>{data.get('drive','')}</b>\n"
        f"🔄 Коробка: <b>{data.get('gearbox','')}</b>\n"
        f"🛣 Пробіг: <b>{data.get('mileage','')}</b>\n"
        f"💵 Ціна: <b>{fmt_price(data.get('price',''))}</b>\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "✅ Можливий кредит / лізинг\n"
        "📸 Більше фото та відео в коментарях ⬇️"
    )


def chunks(items: List[MediaItem], size: int = 10):
    for i in range(0, len(items), size):
        yield items[i:i+size]


def to_input_media(batch: List[MediaItem]):
    media = []
    for item in batch:
        if item.kind == "photo":
            media.append(InputMediaPhoto(media=item.file_id))
        else:
            media.append(InputMediaVideo(media=item.file_id))
    return media


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привіт. Я бот Your Best Auto.\n\n"
        "Натисни /new, щоб створити нове оголошення.\n"
        "Можна надсилати до 80 фото/відео."
    )


async def new_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    sessions[user_id] = Session()
    await update.message.reply_text(
        "📸 Надішли фото/відео автомобіля.\n"
        "Перше фото буде в основному пості, решта піде в коментарі.\n\n"
        "Коли завершиш надсилати медіа — напиши /done."
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sessions.pop(update.effective_user.id, None)
    await update.message.reply_text("Скасовано. Щоб почати заново — /new")


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    s = sessions.get(user_id)
    if not s or s.step != "media":
        await update.message.reply_text("Спочатку натисни /new")
        return
    if len(s.media) >= MAX_MEDIA:
        await update.message.reply_text(f"Ліміт {MAX_MEDIA} фото/відео. Напиши /done або видали зайві.")
        return
    msg = update.message
    if msg.photo:
        s.media.append(MediaItem("photo", msg.photo[-1].file_id))
    elif msg.video:
        s.media.append(MediaItem("video", msg.video.file_id))
    await update.message.reply_text(f"✅ Додано: {len(s.media)}/{MAX_MEDIA}. Коли все — /done")


async def done_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    s = sessions.get(user_id)
    if not s:
        await update.message.reply_text("Спочатку натисни /new")
        return
    if not s.media:
        await update.message.reply_text("Спочатку надішли хоча б 1 фото або відео.")
        return
    s.step = "fields"
    s.ask_index = 0
    await update.message.reply_text(ASKS[0][1])


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    s = sessions.get(user_id)
    if not s:
        await update.message.reply_text("Для нового оголошення натисни /new")
        return
    if s.step != "fields":
        return
    key, _ = ASKS[s.ask_index]
    s.data[key] = update.message.text.strip()
    s.ask_index += 1
    if s.ask_index < len(ASKS):
        await update.message.reply_text(ASKS[s.ask_index][1])
        return
    s.step = "confirm"
    caption = make_caption(s.data)
    await update.message.reply_text(
        "Перевір оголошення:\n\n" + caption + "\n\n"
        "Якщо все правильно — /publish\n"
        "Якщо скасувати — /cancel",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def publish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    s = sessions.get(user_id)
    if not s or s.step != "confirm":
        await update.message.reply_text("Немає готового оголошення. Натисни /new")
        return
    caption = make_caption(s.data)
    first = s.media[0]
    try:
        if first.kind == "photo":
            posted = await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=first.file_id,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard(),
            )
        else:
            posted = await context.bot.send_video(
                chat_id=CHANNEL_ID,
                video=first.file_id,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard(),
            )

        extra = s.media[1:]
        for batch in chunks(extra, 10):
            if not batch:
                continue
            try:
                await context.bot.send_media_group(
                    chat_id=DISCUSSION_GROUP_ID,
                    media=to_input_media(batch),
                    reply_to_message_id=posted.message_id,
                    allow_sending_without_reply=True,
                )
            except TelegramError as e:
                log.warning("Reply media failed, sending without reply: %s", e)
                await context.bot.send_media_group(chat_id=DISCUSSION_GROUP_ID, media=to_input_media(batch))
            await asyncio.sleep(1)

        sessions.pop(user_id, None)
        await update.message.reply_text("✅ Оголошення опубліковано.")
    except TelegramError as e:
        log.exception("Publish error")
        await update.message.reply_text(f"❌ Помилка публікації: {e}")


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is empty")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new", new_post))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("done", done_media))
    app.add_handler(CommandHandler("publish", publish))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, handle_media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    log.info("Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
