import os
import asyncio
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from dotenv import load_dotenv

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InputMediaPhoto,
    InputMediaVideo,
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

log = logging.getLogger("yourbestautobot")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Можна залишити CHANNEL_ID у Render.
# Якщо його немає — бот використовує @yourbestauto1
CHANNEL_ID = os.getenv("CHANNEL_ID", "@yourbestauto1")

CREDIT_URL = os.getenv(
    "CREDIT_URL",
    "https://ref.best/Your_best_autoLV"
)

LOCATION_URL = os.getenv(
    "LOCATION_URL",
    "https://maps.google.com/?q=49.22654,23.81327"
)

TIKTOK_URL = os.getenv(
    "TIKTOK_URL",
    "https://www.tiktok.com/@yourbestauto"
)

MAX_MEDIA = 80


# =========================================================
# WEB SERVER ДЛЯ RENDER
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Your Best Auto Bot is running")

    def log_message(self, format, *args):
        return


def run_web_server():
    port = int(os.environ.get("PORT", 10000))

    server = HTTPServer(
        ("0.0.0.0", port),
        HealthHandler
    )

    log.info(
        "Web server started on port %s",
        port
    )

    server.serve_forever()


# =========================================================
# КНОПКИ БОТА
# =========================================================

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🚘 Нове оголошення"]
    ],
    resize_keyboard=True
)

MEDIA_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["✅ Фото/відео готові"],
        ["❌ Скасувати"],
    ],
    resize_keyboard=True
)

PUBLISH_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🚀 Опублікувати"],
        ["❌ Скасувати"],
    ],
    resize_keyboard=True
)


# =========================================================
# КНОПКИ ПІД ОГОЛОШЕННЯМ
# =========================================================

def channel_buttons():

    keyboard = [
        [
            InlineKeyboardButton(
                "💳 Кредит",
                url=CREDIT_URL
            ),
            InlineKeyboardButton(
                "📍 Розташування",
                url=LOCATION_URL
            ),
        ],
        [
            InlineKeyboardButton(
                "🎵 TikTok",
                url=TIKTOK_URL
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# СЕСІЇ
# =========================================================

sessions = {}


def new_session(user_id):

    sessions[user_id] = {
        "media": [],
        "text": "",
        "stage": "media",
    }


def cancel_session(user_id):

    sessions.pop(
        user_id,
        None
    )


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🚘 Your Best Auto\n\n"
        "Натисни кнопку «🚘 Нове оголошення», "
        "щоб створити новий пост.",
        reply_markup=MAIN_KEYBOARD,
    )


# =========================================================
# ОБРОБКА ТЕКСТУ ТА КНОПОК
# =========================================================

async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id
    text = update.message.text.strip()

    # =====================================================
    # НОВЕ ОГОЛОШЕННЯ
    # =====================================================

    if text == "🚘 Нове оголошення":

        new_session(user_id)

        await update.message.reply_text(
            "📸 Надсилай фото та відео автомобіля.\n\n"
            f"Можна додати до {MAX_MEDIA} фото/відео.\n\n"
            "Коли закінчиш — натисни кнопку "
            "«✅ Фото/відео готові».",
            reply_markup=MEDIA_KEYBOARD,
        )

        return

    # =====================================================
    # СКАСУВАТИ
    # =====================================================

    if text == "❌ Скасувати":

        cancel_session(user_id)

        await update.message.reply_text(
            "❌ Створення оголошення скасовано.",
            reply_markup=MAIN_KEYBOARD,
        )

        return

    session = sessions.get(user_id)

    if not session:

        await update.message.reply_text(
            "Натисни «🚘 Нове оголошення».",
            reply_markup=MAIN_KEYBOARD,
        )

        return

    # =====================================================
    # ФОТО / ВІДЕО ГОТОВІ
    # =====================================================

    if text == "✅ Фото/відео готові":

        if not session["media"]:

            await update.message.reply_text(
                "Спочатку надішли хоча б "
                "одне фото або відео."
            )

            return

        session["stage"] = "text"

        await update.message.reply_text(
            "📝 Тепер надішли готовий текст "
            "оголошення одним повідомленням.",
            reply_markup=ReplyKeyboardRemove(),
        )

        return

    # =====================================================
    # ОПУБЛІКУВАТИ
    # =====================================================

    if text == "🚀 Опублікувати":

        if not session.get("text"):

            await update.message.reply_text(
                "Спочатку потрібно надіслати "
                "текст оголошення."
            )

            return

        try:

            await publish_post(
                update,
                context,
                session
            )

        except Exception as e:

            log.exception(
                "Publish error: %s",
                e
            )

            await update.message.reply_text(
                f"❌ Помилка публікації:\n{e}"
            )

            return

        cancel_session(user_id)

        await update.message.reply_text(
            "✅ Оголошення опубліковано.",
            reply_markup=MAIN_KEYBOARD,
        )

        return

    # =====================================================
    # ТЕКСТ ОГОЛОШЕННЯ
    # =====================================================

    if session["stage"] == "text":

        session["text"] = text
        session["stage"] = "ready"

        await update.message.reply_text(
            "✅ Текст збережено.\n\n"
            "Натисни «🚀 Опублікувати».",
            reply_markup=PUBLISH_KEYBOARD,
        )

        return


# =========================================================
# ФОТО / ВІДЕО
# =========================================================

async def media_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id
    session = sessions.get(user_id)

    if not session or session["stage"] != "media":

        await update.message.reply_text(
            "Спочатку натисни "
            "«🚘 Нове оголошення».",
            reply_markup=MAIN_KEYBOARD,
        )

        return

    if len(session["media"]) >= MAX_MEDIA:

        await update.message.reply_text(
            f"⚠️ Максимум {MAX_MEDIA} фото/відео."
        )

        return

    # ФОТО
    if update.message.photo:

        file_id = update.message.photo[-1].file_id

        session["media"].append(
            (
                "photo",
                file_id
            )
        )

    # ВІДЕО
    elif update.message.video:

        file_id = update.message.video.file_id

        session["media"].append(
            (
                "video",
                file_id
            )
        )

    count = len(
        session["media"]
    )

    await update.message.reply_text(
        f"✅ Додано: {count}/{MAX_MEDIA}",
        reply_markup=MEDIA_KEYBOARD,
    )


# =========================================================
# ПУБЛІКАЦІЯ В КАНАЛ
# =========================================================

async def publish_post(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session
):

    media = session["media"]
    caption = session["text"]

    keyboard = channel_buttons()

    first_type, first_file = media[0]

    # =====================================================
    # ПЕРШЕ ФОТО
    # =====================================================

    if first_type == "photo":

        await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=first_file,
            caption=caption,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    # =====================================================
    # ПЕРШЕ ВІДЕО
    # =====================================================

    else:

        await context.bot.send_video(
            chat_id=CHANNEL_ID,
            video=first_file,
            caption=caption,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    # =====================================================
    # РЕШТА ФОТО / ВІДЕО
    # =====================================================

    remaining = media[1:]

    for i in range(
        0,
        len(remaining),
        10
    ):

        batch = remaining[
            i:i + 10
        ]

        group = []

        for kind, file_id in batch:

            if kind == "photo":

                group.append(
                    InputMediaPhoto(
                        media=file_id
                    )
                )

            else:

                group.append(
                    InputMediaVideo(
                        media=file_id
                    )
                )

        if group:

            await context.bot.send_media_group(
                chat_id=CHANNEL_ID,
                media=group,
            )

        await asyncio.sleep(1)


# =========================================================
# MAIN
# =========================================================

def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN is empty"
        )

    if not CHANNEL_ID:

        raise RuntimeError(
            "CHANNEL_ID is empty"
        )

    threading.Thread(
        target=run_web_server,
        daemon=True
    ).start()

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        MessageHandler(
            filters.PHOTO | filters.VIDEO,
            media_handler
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler
        )
    )

    log.info(
        "Your Best Auto Bot started"
    )

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
