import os
import asyncio
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from dotenv import load_dotenv

from telegram import (
    Update,
    ReplyKeyboardMarkup,
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


# =========================================================
# НАЛАШТУВАННЯ
# =========================================================

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

log = logging.getLogger("yourbestautobot")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@yourbestauto1")

MAX_MEDIA = 80

sessions = {}

CHANNEL_NUMERIC_ID = None
DISCUSSION_CHAT_ID = None

# Тут бот чекатиме автоматичний пост у групі обговорення
pending_discussion_posts = {}


# =========================================================
# WEB SERVER ДЛЯ БЕЗКОШТОВНОГО RENDER
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

    log.info("Web server started on port %s", port)

    server.serve_forever()


# =========================================================
# КНОПКИ В САМОМУ БОТІ
# =========================================================

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🚘 Нове оголошення"]
    ],
    resize_keyboard=True
)

CREATE_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🚀 Опублікувати"],
        ["❌ Скасувати"],
    ],
    resize_keyboard=True
)


# =========================================================
# СЕСІЇ
# =========================================================

def new_session(user_id):
    sessions[user_id] = {
        "media": [],
        "caption": "",
    }


def cancel_session(user_id):
    sessions.pop(user_id, None)


# =========================================================
# ПЕРЕВІРКА КАНАЛУ ТА ГРУПИ КОМЕНТАРІВ
# =========================================================

async def post_init(application: Application):

    global CHANNEL_NUMERIC_ID
    global DISCUSSION_CHAT_ID

    try:
        channel = await application.bot.get_chat(CHANNEL_ID)

        CHANNEL_NUMERIC_ID = channel.id

        DISCUSSION_CHAT_ID = getattr(
            channel,
            "linked_chat_id",
            None
        )

        log.info(
            "Channel ID: %s",
            CHANNEL_NUMERIC_ID
        )

        log.info(
            "Discussion chat ID: %s",
            DISCUSSION_CHAT_ID
        )

        if not DISCUSSION_CHAT_ID:
            log.warning(
                "У каналу не знайдено прив'язану групу коментарів."
            )

    except Exception as e:
        log.exception(
            "Помилка визначення каналу: %s",
            e
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
        "Натисни «🚘 Нове оголошення».",
        reply_markup=MAIN_KEYBOARD,
    )


# =========================================================
# ТЕКСТОВІ КНОПКИ
# =========================================================

async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id
    text = update.message.text.strip()

    # -----------------------------------------------------
    # НОВЕ ОГОЛОШЕННЯ
    # -----------------------------------------------------

    if text == "🚘 Нове оголошення":

        new_session(user_id)

        await update.message.reply_text(
            "📸 Надішли перше фото або відео автомобіля "
            "ОДРАЗУ разом з описом оголошення.\n\n"
            "Після цього можеш додати решту фото/відео.\n"
            "Коли все готово — натисни «🚀 Опублікувати».",
            reply_markup=CREATE_KEYBOARD,
        )

        return

    # -----------------------------------------------------
    # СКАСУВАТИ
    # -----------------------------------------------------

    if text == "❌ Скасувати":

        cancel_session(user_id)

        await update.message.reply_text(
            "❌ Оголошення скасовано.",
            reply_markup=MAIN_KEYBOARD,
        )

        return

    # -----------------------------------------------------
    # ОПУБЛІКУВАТИ
    # -----------------------------------------------------

    if text == "🚀 Опублікувати":

        session = sessions.get(user_id)

        if not session:
            await update.message.reply_text(
                "Спочатку натисни «🚘 Нове оголошення».",
                reply_markup=MAIN_KEYBOARD,
            )
            return

        if not session["media"]:
            await update.message.reply_text(
                "Спочатку надішли фото або відео з описом."
            )
            return

        if not session["caption"]:
            await update.message.reply_text(
                "На першому фото або відео немає опису.\n\n"
                "Скасуй це оголошення та надішли перше "
                "фото/відео одразу з текстом."
            )
            return

        await update.message.reply_text(
            "⏳ Публікую..."
        )

        try:
            comments_ok = await publish_post(
                context,
                session
            )

            cancel_session(user_id)

            if comments_ok:
                await update.message.reply_text(
                    "✅ Оголошення опубліковано.\n"
                    "📸 Додаткові фото/відео додані в коментарі.",
                    reply_markup=MAIN_KEYBOARD,
                )
            else:
                await update.message.reply_text(
                    "✅ Основне оголошення опубліковано.\n\n"
                    "⚠️ Додаткові фото не вдалося додати "
                    "в коментарі.",
                    reply_markup=MAIN_KEYBOARD,
                )

        except Exception as e:

            log.exception(
                "Publish error: %s",
                e
            )

            await update.message.reply_text(
                f"❌ Помилка публікації:\n{e}",
                reply_markup=CREATE_KEYBOARD,
            )

        return

    # -----------------------------------------------------
    # ІНШИЙ ТЕКСТ
    # -----------------------------------------------------

    if user_id in sessions:

        await update.message.reply_text(
            "Опис не потрібно надсилати окремо.\n\n"
            "Він має бути підписом саме до першого "
            "фото або відео.",
            reply_markup=CREATE_KEYBOARD,
        )

    else:

        await update.message.reply_text(
            "Натисни «🚘 Нове оголошення».",
            reply_markup=MAIN_KEYBOARD,
        )


# =========================================================
# ПРИЙОМ ФОТО / ВІДЕО
# =========================================================

async def media_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    session = sessions.get(user_id)

    if not session:

        await update.message.reply_text(
            "Спочатку натисни «🚘 Нове оголошення».",
            reply_markup=MAIN_KEYBOARD,
        )

        return

    if len(session["media"]) >= MAX_MEDIA:

        await update.message.reply_text(
            f"⚠️ Максимум {MAX_MEDIA} фото/відео."
        )

        return

    # -----------------------------------------------------
    # ФОТО
    # -----------------------------------------------------

    if update.message.photo:

        file_id = update.message.photo[-1].file_id

        session["media"].append(
            ("photo", file_id)
        )

    # -----------------------------------------------------
    # ВІДЕО
    # -----------------------------------------------------

    elif update.message.video:

        file_id = update.message.video.file_id

        session["media"].append(
            ("video", file_id)
        )

    # -----------------------------------------------------
    # ПЕРШЕ МЕДІА = БЕРЕМО ОПИС
    # -----------------------------------------------------

    if len(session["media"]) == 1:

        caption = update.message.caption or ""

        if not caption.strip():

            # Перше фото без опису не зберігаємо
            session["media"].clear()

            await update.message.reply_text(
                "⚠️ Перше фото або відео потрібно "
                "надіслати РАЗОМ з описом оголошення.\n\n"
                "Надішли його ще раз і встав опис "
                "у поле підпису.",
                reply_markup=CREATE_KEYBOARD,
            )

            return

        session["caption"] = caption

        await update.message.reply_text(
            "✅ Головне фото/відео та опис додані.\n\n"
            "Тепер можеш надсилати додаткові фото/відео.\n"
            "Коли все готово — натисни «🚀 Опублікувати».",
            reply_markup=CREATE_KEYBOARD,
        )

        return

    # -----------------------------------------------------
    # ДОДАТКОВІ ФОТО / ВІДЕО
    # -----------------------------------------------------

    count = len(session["media"])

    await update.message.reply_text(
        f"✅ Додано: {count}/{MAX_MEDIA}",
        reply_markup=CREATE_KEYBOARD,
    )


# =========================================================
# ЛОВИМО АВТОМАТИЧНИЙ ПОСТ У ГРУПІ КОМЕНТАРІВ
# =========================================================

async def discussion_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.message

    if not message:
        return

    if not getattr(
        message,
        "is_automatic_forward",
        False
    ):
        return

    if DISCUSSION_CHAT_ID:
        if message.chat_id != DISCUSSION_CHAT_ID:
            return

    original_message_id = None
    original_chat_id = None

    # -----------------------------------------------------
    # НОВІ ВЕРСІЇ TELEGRAM API
    # -----------------------------------------------------

    origin = getattr(
        message,
        "forward_origin",
        None
    )

    if origin:

        original_message_id = getattr(
            origin,
            "message_id",
            None
        )

        origin_chat = getattr(
            origin,
            "chat",
            None
        )

        if origin_chat:
            original_chat_id = origin_chat.id

    # -----------------------------------------------------
    # СТАРІША СУМІСНІСТЬ
    # -----------------------------------------------------

    if original_message_id is None:

        original_message_id = getattr(
            message,
            "forward_from_message_id",
            None
        )

        forward_chat = getattr(
            message,
            "forward_from_chat",
            None
        )

        if forward_chat:
            original_chat_id = forward_chat.id

    if not original_message_id:
        return

    if (
        CHANNEL_NUMERIC_ID
        and original_chat_id
        and original_chat_id != CHANNEL_NUMERIC_ID
    ):
        return

    pending = pending_discussion_posts.get(
        original_message_id
    )

    if not pending:
        return

    pending["discussion_chat_id"] = message.chat_id
    pending["discussion_message_id"] = message.message_id

    pending["event"].set()

    log.info(
        "Found discussion post: channel=%s discussion=%s",
        original_message_id,
        message.message_id
    )


# =========================================================
# ПУБЛІКАЦІЯ ОСНОВНОГО ПОСТА
# =========================================================

async def publish_post(
    context: ContextTypes.DEFAULT_TYPE,
    session
):

    media = session["media"]
    caption = session["caption"]

    if not media:
        raise RuntimeError(
            "Немає фото або відео."
        )

    if not caption:
        raise RuntimeError(
            "Немає опису оголошення."
        )

    if len(caption) > 1024:
        raise RuntimeError(
            "Опис задовгий. Telegram дозволяє "
            "до 1024 символів у підписі до фото/відео."
        )

    first_type, first_file = media[0]

    # -----------------------------------------------------
    # ОСНОВНЕ ФОТО + ОПИС
    # -----------------------------------------------------

    if first_type == "photo":

        posted = await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=first_file,
            caption=caption,
            parse_mode="HTML",
        )

    # -----------------------------------------------------
    # ОСНОВНЕ ВІДЕО + ОПИС
    # -----------------------------------------------------

    else:

        posted = await context.bot.send_video(
            chat_id=CHANNEL_ID,
            video=first_file,
            caption=caption,
            parse_mode="HTML",
        )

    log.info(
        "Main post published: %s",
        posted.message_id
    )

    remaining = media[1:]

    # Якщо додаткових фото немає —
    # основний пост уже готовий.
    if not remaining:
        return True

    # -----------------------------------------------------
    # ЧЕКАЄМО АВТОМАТИЧНИЙ ПОСТ У ГРУПІ ОБГОВОРЕННЯ
    # -----------------------------------------------------

    event = asyncio.Event()

    pending_discussion_posts[
        posted.message_id
    ] = {
        "event": event,
        "discussion_chat_id": None,
        "discussion_message_id": None,
    }

    try:

        await asyncio.wait_for(
            event.wait(),
            timeout=15
        )

    except asyncio.TimeoutError:

        pending_discussion_posts.pop(
            posted.message_id,
            None
        )

        log.warning(
            "Discussion post was not detected."
        )

        return False

    pending = pending_discussion_posts.pop(
        posted.message_id
    )

    discussion_chat_id = pending[
        "discussion_chat_id"
    ]

    discussion_message_id = pending[
        "discussion_message_id"
    ]

    if not discussion_chat_id:
        return False

    # -----------------------------------------------------
    # ДОДАТКОВІ ФОТО / ВІДЕО ЙДУТЬ В КОМЕНТАРІ
    # -----------------------------------------------------

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

            elif kind == "video":

                group.append(
                    InputMediaVideo(
                        media=file_id
                    )
                )

        if group:

            await context.bot.send_media_group(
                chat_id=discussion_chat_id,
                media=group,
                reply_to_message_id=discussion_message_id,
            )

            await asyncio.sleep(1)

    return True


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
        .post_init(post_init)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    # Ловимо автоматичні пости з каналу
    # у прив'язаній групі обговорення
    app.add_handler(
        MessageHandler(
            filters.ALL,
            discussion_handler
        ),
        group=-1
    )

    # Фото / відео від тебе
    app.add_handler(
        MessageHandler(
            filters.PHOTO | filters.VIDEO,
            media_handler
        ),
        group=0
    )

    # Кнопки / текст
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler
        ),
        group=0
    )

    log.info(
        "Your Best Auto Bot started"
    )

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
