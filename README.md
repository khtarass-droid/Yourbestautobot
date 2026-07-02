# Your Best Auto Bot

Telegram-бот для каналу Your Best Auto.

## Що робить

- приймає до 80 фото/відео;
- перше фото/відео публікує в канал з описом і кнопками;
- решту медіа публікує в групу коментарів альбомами по 10;
- кнопки: Кредит, Локація, Viber, TikTok;
- оформлення без VIN, без AUTO.RIA, пробіг без "км", двигун без EcoBoost.

## Команди

- `/new` — нове оголошення
- `/done` — закінчив надсилати фото/відео
- `/cancel` — скасувати

## Render

Build command:
```bash
pip install -r requirements.txt
```

Start command:
```bash
python bot.py
```

Environment variables:
```env
BOT_TOKEN=токен від BotFather
CHANNEL_ID=-1002681585680
DISCUSSION_GROUP_ID=-1004435080882
CREDIT_URL=https://ref.best/Your_best_autoLV
LOCATION_URL=https://maps.google.com/?q=49.22654,23.81327
VIBER_URL=viber://chat?number=%2B380676755121
TIKTOK_URL=https://www.tiktok.com/@yourbestauto
MAX_MEDIA=80
```

## Важливо

Бот має бути адміністратором каналу і групи коментарів.
Права: публікувати повідомлення, додавати медіа, читати повідомлення в групі.
