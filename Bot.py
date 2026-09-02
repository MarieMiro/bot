import os
import re
import logging
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

import requests
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, ContextTypes, filters

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


BOT_TOKEN = os.environ["BOT_TOKEN"]
SHEET_WEBHOOK_URL = os.environ["SHEET_WEBHOOK_URL"]  
SHEET_SECRET = os.environ["SHEET_SECRET"]           

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def save_email_to_sheet(email: str, who: str, timestamp: str) -> None:
   
    payload = {"secret": SHEET_SECRET, "email": email, "who": who, "timestamp": timestamp}
    resp = requests.post(SHEET_WEBHOOK_URL, json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("error", "unknown error from Apps Script"))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Пришли мне email — я сохраню его в таблицу на лист «Задача 2»."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    match = EMAIL_RE.search(text)

    if not match:
        await update.message.reply_text(
            "Не нашёл email в сообщении. Пришли просто адрес, например: name@example.com"
        )
        return

    email = match.group(0)
    user = update.effective_user
    who = f"@{user.username}" if user.username else str(user.id)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        save_email_to_sheet(email, who, timestamp)
        await update.message.reply_text(f"Email сохранён в таблицу ✅\n{email}")
        logger.info("Saved email %s from %s", email, who)
    except Exception:
        logger.exception("Не удалось записать в таблицу через Apps Script")
        await update.message.reply_text(
            "Не получилось записать в таблицу. Проверь SHEET_WEBHOOK_URL и SHEET_SECRET, "
            "и попробуй ещё раз."
        )


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if render_url:
       
        port = int(os.environ.get("PORT", "10000"))
        logger.info("Запуск в режиме webhook на Render (порт %s)", port)
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=BOT_TOKEN,
            webhook_url=f"{render_url}/{BOT_TOKEN}",
            allowed_updates=Update.ALL_TYPES,
        )
    else:
        
        logger.info("Запуск в режиме long polling (локально)")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
