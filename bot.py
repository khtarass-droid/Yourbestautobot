import os
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("yourbestauto")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1002681585680"))
DISCUSSION_GROUP_ID = int(os.getenv("DISCUSSION_GROUP_ID", "-1004435080882"))
CREDIT_URL = os.getenv("CREDIT_URL", "https://ref.best/Your_best_autoLV")
LOCATION_URL = os.getenv("LOCATION_URL", "https://maps.google.com/?q=49.22654,23.81327")
VIBER_URL = os.getenv("VIBER_URL", "viber://chat?number=%2B380676755121")
TIKTOK_URL = os.getenv("TIKTOK_URL", "https://www.tiktok.com/@yourbestauto")
MAX_MEDIA = int(os.getenv("MAX_MEDIA", "80"))

FIELDS = [
    ("name", "🚗 Назва авто?\nНаприклад: Ford Escape Titanium"),
    ("year", "📅 Рік?\nНаприклад: 2019"),
    ("engine", "⚙️ Двигун?\nНаприклад: 2.0"),
    ("drive", "🚘 Привід?\nНаприклад: AWD / FWD / RWD"),
    ("gearbox", "🔄 Коробка?\nНаприклад: Автомат"),
    ("mileage", "🛣 Пробіг?\nНаприклад: 100 000\nБез км."),
    ("price", "💵 Ціна в доларах?\nНаприклад: 14 700"),
]

@dataclass
class MediaItem:
    kind: str  # photo | video
    file_id: str

@dataclass
class Draft:
    media: List[MediaItem] = field(default_factory=list)
    data: Dict[str, str] = field(default_factory=dict)
    step: int = 0
    collecting_media: bool = False

sessions: Dict[int, Draft] = {}


def buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Кредит", url=CREDIT_URL), InlineKeyboardButton("📍 Локація", url=LOCATION_URL)],
        [InlineKeyboardButton("📲 Viber", url=VIBER_URL), InlineKeyboardButton("🎵 TikTok", url=TIKTOK_URL)],
    ])


def clean_price(value: str) -> str:
    v = value.replace("$", "").strip()
    return f"{v} $"


def format_caption(d: Draft) -> str:
    name = d.data.get("name", "")
    return (
        f"🚙 <b>{name}</b>\n\n"
        f"📅 <b>Рік:</b> {d.data.get('year','')}\n"
        f"⚙️ <b>Двигун:</b> {d.data.get('engine','')}\n"
        f"🚘 <b>Привід:</b> {d.data.get('drive','')}\n"
        f"🔄 <b>Коробка:</b> {d.data.get('gearbox','')}\n"
        f"🛣 <b>Пробіг:</b> {d.data.get('mileage','')}\n"
        f"💵 <b>Ціна:</b> {clean_price(d.data.get('price',''))}\n\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"✅ Можливий кредит / лізинг\n"
        f"📸 Більше фото та відео в коментарях ⬇️"
    )


def media_to_input(items: List[MediaItem]):
    result = []
    for item in items:
        if item.kind == "photo":
            result.append(InputMediaPhoto(media=item.file_id))
        elif item.kind == "video":
            result.append(InputMediaVideo(media=item.file_id))
    return result


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sessions[update.effective_user.id] = Draft(collecting_media=True)
    await update.message.reply_text(
        "🚗 Починаємо нове оголошення.\n\n"
        f"Надішли фото/відео авто. Можна до {MAX_MEDIA} файлів.\n"
        "Коли закінчиш — напиши /done"
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sessions.pop(update.effective_user.id, None)
    await update.message.reply_text("Скасовано. Щоб почати заново — /new")


async def new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def collect_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    d = sessions.get(uid)
    if not d or not d.collecting_media:
        return
    if len(d.media) >= MAX_MEDIA:
        await update.message.reply_text(f"Ліміт {MAX_MEDIA} фото/відео вже досягнуто. Напиши /done")
        return
    if update.message.photo:
        d.media.append(MediaItem("photo", update.message.photo[-1].file_id))
    elif update.message.video:
        d.media.append(MediaItem("video", update.message.video.file_id))
    else:
        return
    if len(d.media) in (1, 5, 10, 20, 40, 60, 80):
        await update.message.reply_text(f"✅ Прийнято медіа: {len(d.media)}. Коли все — /done")


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    d = sessions.get(uid)
    if not d or not d.media:
        await update.message.reply_text("Спочатку надішли хоча б одне фото або відео. /new")
        return
    d.collecting_media = False
    d.step = 0
    await update.message.reply_text(FIELDS[0][1])


async def collect_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    d = sessions.get(uid)
    if not d or d.collecting_media:
        return
    if d.step >= len(FIELDS):
        return
    key, _ = FIELDS[d.step]
    d.data[key] = update.message.text.strip()
    d.step += 1
    if d.step < len(FIELDS):
        await update.message.reply_text(FIELDS[d.step][1])
    else:
        preview = format_caption(d)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Опублікувати", callback_data="publish"), InlineKeyboardButton("❌ Скасувати", callback_data="cancel")]])
        await update.message.reply_text("Перевір опис:\n\n" + preview, parse_mode=ParseMode.HTML, reply_markup=kb)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    if q.data == "cancel":
        sessions.pop(uid, None)
        await q.edit_message_text("Скасовано. /new")
        return
    if q.data == "publish":
        d = sessions.get(uid)
        if not d:
            await q.edit_message_text("Чернетку не знайдено. Почни заново /new")
            return
        await q.edit_message_text("Публікую... ⏳")
        try:
            await publish_draft(d, context)
            sessions.pop(uid, None)
            await q.message.reply_text("✅ Оголошення опубліковано.")
        except Exception as e:
            log.exception("publish failed")
            await q.message.reply_text(f"❌ Помилка публікації: {e}")


async def publish_draft(d: Draft, context: ContextTypes.DEFAULT_TYPE):
    caption = format_caption(d)
    first = d.media[0]
    if first.kind == "photo":
        msg = await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=first.file_id,
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=buttons(),
        )
    else:
        msg = await context.bot.send_video(
            chat_id=CHANNEL_ID,
            video=first.file_id,
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=buttons(),
        )

    # Give Telegram a moment to create discussion thread for the channel post.
    await asyncio.sleep(1.5)
    rest = d.media[1:]
    if not rest:
        return

    # In linked discussion groups, reply_to_message_id is usually the same as the channel post id.
    # If Telegram changes this mapping, bot will still publish in the group, but not threaded.
    for i in range(0, len(rest), 10):
        chunk = rest[i:i+10]
        try:
            await context.bot.send_media_group(
                chat_id=DISCUSSION_GROUP_ID,
                media=media_to_input(chunk),
                reply_to_message_id=msg.message_id,
                allow_sending_without_reply=True,
            )
        except TypeError:
            await context.bot.send_media_group(
                chat_id=DISCUSSION_GROUP_ID,
                media=media_to_input(chunk),
            )
        await asyncio.sleep(0.8)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Команди:\n"
        "/new — нове оголошення\n"
        "/done — закінчив надсилати фото/відео\n"
        "/cancel — скасувати"
    )


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler(["start", "new"], new))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, collect_media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, collect_text))
    log.info("Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
