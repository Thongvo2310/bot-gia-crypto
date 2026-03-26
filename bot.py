import requests
import asyncio
import sqlite3
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- THÔNG TIN ---
TOKEN = "8268708834:AAE2coMuFQVWIn7-PFB1PRG6xOArTar202A"
USER_ID = 8268708834

def init_db():
    conn = sqlite3.connect('alerts.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS alerts 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, price REAL, direction TEXT)''')
    conn.commit()
    conn.close()

# --- BỘ LỌC LÁCH LUẬT BINANCE ---
def get_price(symbol):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    symbol_upper = symbol.upper()
    # Dùng nhiều link dự phòng để tránh bị Binance chặn IP của server
    urls = [
        f"https://api.binance.com/api/v3/ticker/price?symbol={symbol_upper}USDT",
        f"https://api1.binance.com/api/v3/ticker/price?symbol={symbol_upper}USDT",
        f"https://api2.binance.com/api/v3/ticker/price?symbol={symbol_upper}USDT",
        f"https://api3.binance.com/api/v3/ticker/price?symbol={symbol_upper}USDT"
    ]
    
    for url in urls:
        try:
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                return float(res.json()['price'])
        except:
            continue
            
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID: return
    await update.message.reply_text("✅ TRỢ LÝ BÁO GIÁ ĐÃ SẴN SÀNG!\n- Gõ /price btc\n- Gõ /alert btc 65000\n- Gõ /list để xem lệnh\n- Gõ /clear để xóa lệnh")

async def check_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID: return
    if not context.args:
        await update.message.reply_text("⚠️ Ví dụ: /price btc")
        return
    symbol = context.args[0].upper()
    price = get_price(symbol)
    if price:
        await update.message.reply_text(f"💰 {symbol}: ${price:,.2f}")
    else:
        await update.message.reply_text("❌ Mạng lỗi hoặc Binance đang chặn. Thử lại sau nhé!")

async def set_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID: return
    try:
        symbol = context.args[0].upper()
        target_price = float(context.args[1])
        current_price = get_price(symbol)
        if not current_price:
            await update.message.reply_text("❌ Lỗi mạng không lấy được giá. Thử lại sau!")
            return
        direction = "above" if target_price > current_price else "below"
        conn = sqlite3.connect('alerts.db')
        c = conn.cursor()
        c.execute("INSERT INTO alerts (symbol, price, direction) VALUES (?, ?, ?)", (symbol, target_price, direction))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ Đã đặt báo động {symbol} tại ${target_price:,.2f}")
    except:
        await update.message.reply_text("⚠️ Lỗi! Thử lại: /alert btc 65000")

async def list_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID: return
    conn = sqlite3.connect('alerts.db')
    c = conn.cursor()
    c.execute("SELECT * FROM alerts")
    alerts = c.fetchall()
    conn.close()
    
    if not alerts:
        await update.message.reply_text("📭 Chưa có báo động nào.")
        return
    
    text = "🔔 *CÁC BÁO ĐỘNG ĐANG CHỜ:*\n\n"
    for alert in alerts:
        aid, sym, target, direct = alert
        arrow = "📈" if direct == "above" else "📉"
        text += f"{arrow} {sym}: ${target:,.2f} ({direct})\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def clear_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID: return
    conn = sqlite3.connect('alerts.db')
    c = conn.cursor()
    c.execute("DELETE FROM alerts")
    conn.commit()
    conn.close()
    await update.message.reply_text("🗑️ Đã xóa tất cả báo động!")

async def monitor_prices(app):
    await asyncio.sleep(5)
    while True:
        try:
            conn = sqlite3.connect('alerts.db')
            c = conn.cursor()
            c.execute("SELECT * FROM alerts")
            alerts = c.fetchall()
            for alert in alerts:
                aid, sym, target, direct = alert
                curr = get_price(sym)
                if not curr: continue
                if (direct == "above" and curr >= target) or (direct == "below" and curr <= target):
                    await app.bot.send_message(chat_id=USER_ID, text=f"🚨 BÁO ĐỘNG: {sym} đạt ${curr:,.2f}!")
                    c.execute("DELETE FROM alerts WHERE id=?", (aid,))
                    conn.commit()
            conn.close()
        except:
            pass
        await asyncio.sleep(20)

async def main():
    init_db()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("price", check_price))
    application.add_handler(CommandHandler("alert", set_alert))
    application.add_handler(CommandHandler("list", list_alerts))
    application.add_handler(CommandHandler("clear", clear_alerts))
    
    asyncio.create_task(monitor_prices(application))
    print("🚀 Bot đang chạy và chờ tin nhắn...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
