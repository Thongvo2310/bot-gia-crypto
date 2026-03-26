import logging
import os
import sqlite3
import threading
import time
from contextlib import closing

import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


DB_PATH = "alerts.db"
TOKEN = os.getenv("8268708834:AAE2coMuFQVWIn7-PFB1PRG6xOArTar202A", "").strip()
USER_ID_RAW = os.getenv("8268708834", "").strip()
BINANCE_URLS = [
    "https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT",
    "https://api1.binance.com/api/v3/ticker/price?symbol={symbol}USDT",
    "https://api2.binance.com/api/v3/ticker/price?symbol={symbol}USDT",
    "https://api3.binance.com/api/v3/ticker/price?symbol={symbol}USDT",
]


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("crypto-alert-bot")


def parse_user_id(raw_value: str) -> int | None:
    if not raw_value:
        return None
    try:
        return int(raw_value)
    except ValueError:
        logger.error("TELEGRAM_USER_ID must be an integer, got: %s", raw_value)
        return None


USER_ID = parse_user_id(USER_ID_RAW)


def init_db() -> None:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                direction TEXT NOT NULL CHECK(direction IN ('above', 'below'))
            )
            """
        )
        conn.commit()


def fetch_price(symbol: str) -> float | None:
    symbol = symbol.upper().strip()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
    }

    for template in BINANCE_URLS:
        url = template.format(symbol=symbol)
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            payload = response.json()
            price = payload.get("price")
            if price is not None:
                return float(price)
        except requests.RequestException as exc:
            logger.warning("Price request failed for %s via %s: %s", symbol, url, exc)
        except (TypeError, ValueError, KeyError) as exc:
            logger.warning("Invalid Binance payload for %s via %s: %s", symbol, url, exc)

    return None


def is_authorized(update: Update) -> bool:
    user = update.effective_user
    if user is None:
        return False

    if USER_ID is None:
        return True

    return user.id == USER_ID


async def unauthorized_reply(update: Update) -> None:
    if update.message:
        await update.message.reply_text(
            "Ban khong co quyen dung bot nay. Kiem tra TELEGRAM_USER_ID trong moi truong."
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await unauthorized_reply(update)
        return

    await update.message.reply_text(
        "Bot bao gia da san sang.\n"
        "/price btc - xem gia\n"
        "/alert btc 65000 - dat canh bao\n"
        "/list - xem danh sach canh bao\n"
        "/clear - xoa tat ca canh bao"
    )


async def check_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await unauthorized_reply(update)
        return

    if not context.args:
        await update.message.reply_text("Cach dung: /price btc")
        return

    symbol = context.args[0].upper()
    price = fetch_price(symbol)
    if price is None:
        await update.message.reply_text(
            f"Khong lay duoc gia {symbol}. Kiem tra mang, token Binance, hoac ky hieu coin."
        )
        return

    await update.message.reply_text(f"{symbol}/USDT: ${price:,.2f}")


async def set_alert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await unauthorized_reply(update)
        return

    if len(context.args) < 2:
        await update.message.reply_text("Cach dung: /alert btc 65000")
        return

    symbol = context.args[0].upper()
    try:
        target_price = float(context.args[1])
    except ValueError:
        await update.message.reply_text("Gia canh bao phai la so. Vi du: /alert btc 65000")
        return

    current_price = fetch_price(symbol)
    if current_price is None:
        await update.message.reply_text(f"Khong lay duoc gia hien tai cua {symbol}.")
        return

    direction = "above" if target_price > current_price else "below"

    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute(
            "INSERT INTO alerts (symbol, price, direction) VALUES (?, ?, ?)",
            (symbol, target_price, direction),
        )
        conn.commit()

    arrow = "tang len" if direction == "above" else "giam xuong"
    await update.message.reply_text(
        f"Da dat canh bao {symbol} tai ${target_price:,.2f}. "
        f"Gia hien tai ${current_price:,.2f}, bot se bao khi {arrow} moc nay."
    )


async def list_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await unauthorized_reply(update)
        return

    with closing(sqlite3.connect(DB_PATH)) as conn:
        alerts = conn.execute(
            "SELECT id, symbol, price, direction FROM alerts ORDER BY id ASC"
        ).fetchall()

    if not alerts:
        await update.message.reply_text("Chua co canh bao nao.")
        return

    lines = ["Danh sach canh bao:"]
    for alert_id, symbol, target_price, direction in alerts:
        sign = ">= " if direction == "above" else "<= "
        lines.append(f"{alert_id}. {symbol} {sign}${target_price:,.2f}")

    await update.message.reply_text("\n".join(lines))


async def clear_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await unauthorized_reply(update)
        return

    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute("DELETE FROM alerts")
        conn.commit()

    await update.message.reply_text("Da xoa tat ca canh bao.")


def monitor_prices(bot_token: str, chat_id: int) -> None:
    bot_api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    while True:
        try:
            with closing(sqlite3.connect(DB_PATH)) as conn:
                alerts = conn.execute(
                    "SELECT id, symbol, price, direction FROM alerts ORDER BY id ASC"
                ).fetchall()

                for alert_id, symbol, target_price, direction in alerts:
                    current_price = fetch_price(symbol)
                    if current_price is None:
                        continue

                    hit_target = (
                        direction == "above" and current_price >= target_price
                    ) or (
                        direction == "below" and current_price <= target_price
                    )

                    if not hit_target:
                        continue

                    message = (
                        f"Canh bao gia.\n{symbol}/USDT da cham ${current_price:,.2f}\n"
                        f"Moc canh bao: ${target_price:,.2f}"
                    )
                    response = requests.post(
                        bot_api_url,
                        data={"chat_id": chat_id, "text": message},
                        timeout=15,
                    )
                    response.raise_for_status()

                    conn.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
                    conn.commit()
                    logger.info("Triggered alert %s for %s", alert_id, symbol)
        except Exception:
            logger.exception("Unexpected error in monitor thread")

        time.sleep(20)


def validate_config() -> None:
    if not TOKEN:
        raise RuntimeError(
            "Missing TELEGRAM_BOT_TOKEN. Set environment variable before running the bot."
        )

    if USER_ID is None:
        logger.warning(
            "TELEGRAM_USER_ID is empty or invalid. Bot will answer everyone until you set it."
        )


def main() -> None:
    validate_config()
    init_db()

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("price", check_price))
    application.add_handler(CommandHandler("alert", set_alert))
    application.add_handler(CommandHandler("list", list_alerts))
    application.add_handler(CommandHandler("clear", clear_alerts))

    if USER_ID is not None:
        monitor_thread = threading.Thread(
            target=monitor_prices,
            args=(TOKEN, USER_ID),
            daemon=True,
            name="price-monitor",
        )
        monitor_thread.start()

    logger.info("Starting Telegram bot polling")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
