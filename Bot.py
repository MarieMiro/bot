import os
import re
import json
import logging
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

import gspread
from google.oauth2.service_account import Credentials
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, ContextTypes, filters

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


BOT_TOKEN = os.environ["BOT_TOKEN"]
SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
CREDENTIALS_FILE = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
SHEET_NAME = "Задача 2"

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_worksheet():
   
    creds = get_credentials()
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)
    try:
        ws = sh.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_NAME, rows=1000, cols=3)
        ws.append_row(["Дата/время", "От кого (Telegram)", "Email"])
    return ws


def get_credentials() -> Credentials:
 
    raw_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if raw_json:
        info = json.loads(raw_json)
        return Credentials.from_service_account_info(info, scopes=SCOPES)
    return Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Пришли мне email — я сохраню его в таблицу на лист «Задача 2»."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    match = EMAIL_RE.search(text)

    if not match:
        await update.message.reply_text(
            "Не нашёл email в сообщении. Пришли просто адрес, например: name@example"
        )
        return

    email = match.group(0)
    user = update.effective_user
    who = f"@{user.username}" if user.username else str(user.id)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        ws = get_worksheet()
        ws.append_row([timestamp, who, email])
        await update.message.reply_text(f"Email сохранён в таблицу ✅\n{email}")
        logger.info("Saved email %s from %s", email, who)
    except Exception:
        logger.exception("Не удалось записать в Google Sheets")
        await update.message.reply_text(
            "Не получилось записать в таблицу. Проверь, что сервисному аккаунту "
            "выдан доступ редактора к таблице, и попробуй ещё раз."
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
