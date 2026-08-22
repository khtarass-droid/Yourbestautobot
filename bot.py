import os
import re
import html
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

# Основний канал з автомобілями
CHANNEL_ID = os.getenv(
    "CHANNEL_ID",
    "@yourbestauto1"
)

# Публічна форум-група з історією автомобілів
HISTORY_CHAT_ID = os.getenv(
    "HISTORY_CHAT_ID",
    "@YourBestAuto_history"
)

# Username без @ — потрібен для створення посилання
HISTORY_USERNAME = os.getenv(
    "HISTORY_USERNAME",
    "YourBestAuto_history"
).lstrip("@")

MAX_MEDIA = 80

sessions = {}

CHANNEL_NUMERIC_ID = None
HISTORY_NUMERIC_ID = None

HISTORY_LINK_TEXT = "📸 Фото та відео автомобіля"


# =========================================================
# WEB SERVER ДЛЯ RENDER
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header(
            "Content-type",
            "text/plain"
        )
        self.end_headers()

        self.wfile.write(
            b"Your Best Auto Bot is running"
        )

    def log_message(
        self,
        format,
        *args
    ):
        return


def run_web_server():

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

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

    sessions.pop(
        user_id,
        None
    )


# =========================================================
# НАЗВА ГІЛКИ
# =========================================================

def make_topic_name(caption):

    if not caption:
        return "Автомобіль"

    # Прибираємо HTML-теги
    clean = re.sub(
        r"<[^>]+>",
        "",
        caption
    )

    clean = html.unescape(clean)

    # Беремо перший нормальний рядок
    lines = [
        line.strip()
        for line in clean.splitlines()
        if line.strip()
    ]

    if lines:
        name = lines[0]
    else:
        name = "Автомобіль"

    # Прибираємо зайві пробіли
    name = re.sub(
        r"\s+",
        " ",
        name
    ).strip()

    # Telegram: назва гілки максимум 128 символів
    if len(name) > 120:
        name = name[:120].rstrip()

    return name or "Автомобіль"


# =========================================================
# ПЕРЕВІРКА КАНАЛУ ТА ФОРУМУ
# =========================================================

async def post_init(
    application: Application
):

    global CHANNEL_NUMERIC_ID
    global HISTORY_NUMERIC_ID

    # -----------------------------------------------------
    # ОСНОВНИЙ КАНАЛ
    # -----------------------------------------------------

    try:

        channel = await application.bot.get_chat(
            CHANNEL_ID
        )

        CHANNEL_NUMERIC_ID = channel.id

        log.info(
            "Main channel: %s (%s)",
            CHANNEL_ID,
            CHANNEL_NUMERIC_ID
        )

    except Exception as e:

        log.exception(
            "Не вдалося отримати основний канал: %s",
            e
        )

    # -----------------------------------------------------
    # ГРУПА ІСТОРІЇ
    # -----------------------------------------------------

    try:

        history_chat = await application.bot.get_chat(
            HISTORY_CHAT_ID
        )

        HISTORY_NUMERIC_ID = history_chat.id

        log.info(
            "History chat: %s (%s)",
            HISTORY_CHAT_ID,
            HISTORY_NUMERIC_ID
        )

        is_forum = getattr(
            history_chat,
            "is_forum",
            False
        )

        if not is_forum:

            log.warning(
                "Група історії не має увімкнених гілок/форуму."
            )

    except Exception as e:

        log.exception(
            "Не вдалося отримати групу історії: %s",
            e
        )


# =========================================================
# /START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.effective_chat:
        return

    if update.effective_chat.type != "private":
        return

    if not update.message:
        return

    await update.message.reply_text(
        "🚘 Your Best Auto\n\n"
        "Натисни «🚘 Нове оголошення».",
        reply_markup=MAIN_KEYBOARD,
    )


# =========================================================
# /CHATID
# ЗАЛИШАЄМО ДЛЯ ДІАГНОСТИКИ
# =========================================================

async def chatid(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.effective_chat:
        return

    if not update.message:
        return

    await update.message.reply_text(
        f"Chat ID: {update.effective_chat.id}"
    )


# =========================================================
# ТЕКСТ / КНОПКИ
# =========================================================

async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    # Бот спілкується з нами тільки приватно
    if not update.effective_chat:
        return

    if update.effective_chat.type != "private":
        return

    if not update.message:
        return

    if not update.effective_user:
        return

    user_id = update.effective_user.id

    text = (
        update.message.text or ""
    ).strip()

    # -----------------------------------------------------
    # НОВЕ ОГОЛОШЕННЯ
    # -----------------------------------------------------

    if text == "🚘 Нове оголошення":

        new_session(user_id)

        await update.message.reply_text(
            "📸 Надішли головне фото або відео "
            "ОДРАЗУ разом з готовим описом.\n\n"
            "Потім надсилай решту фото/відео.\n\n"
            "Коли все готово — натисни "
            "«🚀 Опублікувати».",
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

        session = sessions.get(
            user_id
        )

        if not session:

            await update.message.reply_text(
                "Спочатку натисни "
                "«🚘 Нове оголошення».",
                reply_markup=MAIN_KEYBOARD,
            )

            return

        if not session["media"]:

            await update.message.reply_text(
                "Спочатку надішли "
                "головне фото або відео."
            )

            return

        if not session["caption"]:

            await update.message.reply_text(
                "На головному фото або відео "
                "немає опису оголошення."
            )

            return

        await update.message.reply_text(
            "⏳ Створюю історію автомобіля "
            "та публікую оголошення..."
        )

        try:

            result = await publish_post(
                context,
                session
            )

            cancel_session(
                user_id
            )

            await update.message.reply_text(
                "✅ Оголошення опубліковано.\n\n"
                "📂 Створено окрему гілку "
                "для автомобіля.\n"
                "📸 Фото та відео додані "
                "в історію авто.\n\n"
                f"🔗 {result['history_url']}",
                reply_markup=MAIN_KEYBOARD,
            )

        except Exception as e:

            log.exception(
                "Publish error: %s",
                e
            )

            await update.message.reply_text(
                "❌ Помилка публікації:\n\n"
                f"{e}",
                reply_markup=CREATE_KEYBOARD,
            )

        return

    # -----------------------------------------------------
    # ІНШИЙ ТЕКСТ
    # -----------------------------------------------------

    if user_id in sessions:

        await update.message.reply_text(
            "Опис окремо надсилати не потрібно.\n\n"
            "Встав його прямо в підпис "
            "до головного фото або відео.",
            reply_markup=CREATE_KEYBOARD,
        )

    else:

        await update.message.reply_text(
            "Натисни «🚘 Нове оголошення».",
            reply_markup=MAIN_KEYBOARD,
        )


# =========================================================
# ПРИЙОМ ФОТО / ВІДЕО В ПРИВАТНОМУ ЧАТІ
# =========================================================

async def media_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.effective_chat:
        return

    # Нічого не ловимо з форуму або інших груп
    if update.effective_chat.type != "private":
        return

    if not update.message:
        return

    if not update.effective_user:
        return

    if getattr(
        update.message,
        "is_automatic_forward",
        False
    ):
        return

    user_id = update.effective_user.id

    session = sessions.get(
        user_id
    )

    if not session:

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

    media_type = None
    file_id = None

    # -----------------------------------------------------
    # ФОТО
    # -----------------------------------------------------

    if update.message.photo:

        media_type = "photo"

        file_id = (
            update.message
            .photo[-1]
            .file_id
        )

    # -----------------------------------------------------
    # ВІДЕО
    # -----------------------------------------------------

    elif update.message.video:

        media_type = "video"

        file_id = (
            update.message
            .video
            .file_id
        )

    else:

        return

    # -----------------------------------------------------
    # ГОЛОВНЕ ФОТО / ВІДЕО
    # -----------------------------------------------------

    if len(session["media"]) == 0:

        caption = (
            update.message.caption
            or ""
        )

        if not caption.strip():

            await update.message.reply_text(
                "⚠️ Головне фото або відео "
                "потрібно надіслати РАЗОМ "
                "з описом оголошення.\n\n"
                "Надішли його ще раз і встав "
                "опис у поле підпису.",
                reply_markup=CREATE_KEYBOARD,
            )

            return

        session["media"].append(
            (
                media_type,
                file_id
            )
        )

        session["caption"] = caption

        await update.message.reply_text(
            "✅ Головне фото/відео та опис додані.\n\n"
            "Тепер надсилай додаткові фото/відео.\n"
            "Коли все готово — натисни "
            "«🚀 Опублікувати».",
            reply_markup=CREATE_KEYBOARD,
        )

        return

    # -----------------------------------------------------
    # ДОДАТКОВІ ФОТО / ВІДЕО
    # -----------------------------------------------------

    session["media"].append(
        (
            media_type,
            file_id
        )
    )

    count = len(
        session["media"]
    )

    await update.message.reply_text(
        f"✅ Додано: {count}/{MAX_MEDIA}",
        reply_markup=CREATE_KEYBOARD,
    )


# =========================================================
# НАДСИЛАННЯ ОДНОГО ФАЙЛУ В ГІЛКУ
# =========================================================

async def send_single_media_to_topic(
    context: ContextTypes.DEFAULT_TYPE,
    topic_id,
    media_item
):

    kind, file_id = media_item

    if kind == "photo":

        await context.bot.send_photo(
            chat_id=HISTORY_CHAT_ID,
            photo=file_id,
            message_thread_id=topic_id,
        )

    elif kind == "video":

        await context.bot.send_video(
            chat_id=HISTORY_CHAT_ID,
            video=file_id,
            message_thread_id=topic_id,
        )


# =========================================================
# НАДСИЛАННЯ ФОТО / ВІДЕО В ГІЛКУ
# =========================================================

async def upload_media_to_topic(
    context: ContextTypes.DEFAULT_TYPE,
    topic_id,
    media
):

    if not media:
        return

    index = 0

    while index < len(media):

        remaining_count = (
            len(media) - index
        )

        # Якщо залишився один файл —
        # media_group використовувати не можна
        if remaining_count == 1:

            await send_single_media_to_topic(
                context,
                topic_id,
                media[index]
            )

            index += 1

            await asyncio.sleep(0.5)

            continue

        # Група Telegram: максимум 10
        batch_size = min(
            10,
            remaining_count
        )

        batch = media[
            index:index + batch_size
        ]

        # Якщо з якоїсь причини batch = 1
        if len(batch) == 1:

            await send_single_media_to_topic(
                context,
                topic_id,
                batch[0]
            )

            index += 1

            await asyncio.sleep(0.5)

            continue

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
                chat_id=HISTORY_CHAT_ID,
                message_thread_id=topic_id,
                media=group,
            )

        index += len(batch)

        # Невелика пауза, щоб не впиратися
        # в Telegram rate limits
        await asyncio.sleep(1)


# =========================================================
# СТВОРЕННЯ ГІЛКИ
# =========================================================

async def create_history_topic(
    context: ContextTypes.DEFAULT_TYPE,
    caption
):

    topic_name = make_topic_name(
        caption
    )

    log.info(
        "Creating history topic: %s",
        topic_name
    )

    topic = await context.bot.create_forum_topic(
        chat_id=HISTORY_CHAT_ID,
        name=topic_name,
    )

    topic_id = (
        topic.message_thread_id
    )

    if not topic_id:

        raise RuntimeError(
            "Telegram створив гілку, "
            "але не повернув її ID."
        )

    history_url = (
        f"https://t.me/"
        f"{HISTORY_USERNAME}/"
        f"{topic_id}"
    )

    log.info(
        "Topic created: id=%s url=%s",
        topic_id,
        history_url
    )

    return {
        "topic_id": topic_id,
        "topic_name": topic_name,
        "history_url": history_url,
    }


# =========================================================
# ПУБЛІКАЦІЯ
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

    # -----------------------------------------------------
    # 1. СТВОРЮЄМО ГІЛКУ
    # -----------------------------------------------------

    topic_info = await create_history_topic(
        context,
        caption
    )

    topic_id = topic_info[
        "topic_id"
    ]

    history_url = topic_info[
        "history_url"
    ]

    # -----------------------------------------------------
    # 2. ЗАВАНТАЖУЄМО ВСІ ФОТО / ВІДЕО
    #    В ІСТОРІЮ АВТО
    # -----------------------------------------------------

    await upload_media_to_topic(
        context,
        topic_id,
        media
    )

    # -----------------------------------------------------
    # 3. ДОДАЄМО ПОСИЛАННЯ ДО ОПИСУ
    # -----------------------------------------------------

    caption_with_history = (
        caption.rstrip()
        + "\n\n"
        + f'<a href="{history_url}">'
        + HISTORY_LINK_TEXT
        + "</a>"
    )

    # Telegram обмежує видимий текст caption
    visible_length = (
        len(caption.rstrip())
        + 2
        + len(HISTORY_LINK_TEXT)
    )

    if visible_length > 1024:

        raise RuntimeError(
            "Опис оголошення задовгий. "
            "Після додавання посилання "
            "«Фото та відео автомобіля» "
            "підпис перевищує ліміт Telegram "
            "1024 символи."
        )

    first_type, first_file = media[0]

    # -----------------------------------------------------
    # 4. ПУБЛІКУЄМО ГОЛОВНИЙ ПОСТ
    # -----------------------------------------------------

    if first_type == "photo":

        posted = await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=first_file,
            caption=caption_with_history,
            parse_mode="HTML",
        )

    elif first_type == "video":

        posted = await context.bot.send_video(
            chat_id=CHANNEL_ID,
            video=first_file,
            caption=caption_with_history,
            parse_mode="HTML",
        )

    else:

        raise RuntimeError(
            "Невідомий тип головного медіафайлу."
        )

    log.info(
        "Main post published: %s",
        posted.message_id
    )

    # -----------------------------------------------------
    # ГОТОВО
    # -----------------------------------------------------

    return {
        "channel_message_id": posted.message_id,
        "topic_id": topic_id,
        "history_url": history_url,
    }


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

    if not HISTORY_CHAT_ID:

        raise RuntimeError(
            "HISTORY_CHAT_ID is empty"
        )

    if not HISTORY_USERNAME:

        raise RuntimeError(
            "HISTORY_USERNAME is empty"
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

    # /start
    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    # /chatid
    app.add_handler(
        CommandHandler(
            "chatid",
            chatid
        )
    )

    # Фото / відео
    app.add_handler(
        MessageHandler(
            filters.PHOTO
            | filters.VIDEO,
            media_handler
        ),
        group=0
    )

    # Кнопки та текст
    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
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
