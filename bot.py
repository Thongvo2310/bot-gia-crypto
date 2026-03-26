import requests
import asyncio
import sqlite3
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- THÔNG TIN ĐÃ ĐƯỢC ĐIỀN CHUẨN XÁC ---
TOKEN = "8268708834:AAHKv4m3C9yoNHwYXADrjX7oGHHsHjm0k7c"
USER_ID = 52504489

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect('alerts.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS alerts 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, price REAL, direction TEXT)''')
    conn.commit()
    conn.close()

def get_price(symbol):
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol.upper()}USDT"
        res = requests.get(url, timeout=10).json()
        return float(res['price'])
    except:
        return None

# --- CÁC LỆNH TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID: return
    await update.message.reply_text("✅ Trợ lý báo giá đã sẵn sàng!\n- Gõ /price btc để xem giá\n- Gõ /alert btc 65000 để đặt báo động")

async def check_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID: return
    if not context.args:
        await update.message.reply_text("⚠️ Ví dụ: /price btc")
        return
    symbol = context.args[0].upper()
    price = get_price(symbol)
    if price:
        await update.message.reply_text(f"💰 Giá {symbol}: ${price:,}")
    else:
        await update.message.reply_text("❌ Không tìm thấy coin.")

async def set_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID: return
    try:
        symbol = context.args[0].upper()
        target_price = float(context.args[1])
        current_price = get_price(symbol)
        if not current_price:
            await update.message.reply_text("❌ Tên coin sai.")
            return
            
        direction = "above" if target_price > current_price else "below"
        conn = sqlite3.connect('alerts.db')
        c = conn.cursor()
        c.execute("INSERT INTO alerts (symbol, price, direction) VALUES (?, ?, ?)", (symbol, target_price, direction))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ Đã đặt báo động {symbol} tại ngưỡng ${target_price:,}")
    except:
        await update.message.reply_text("⚠️ Lỗi cú pháp! Thử lại: /alert btc 65000")

# --- LUỒNG KIỂM TRA GIÁ ---
async def monitor_prices(app):
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
                    await app.bot.send_message(chat_id=USER_ID, text=f"🚨 BÁO ĐỘNG: {sym} đã chạm {curr:,}!")
                    c.execute("DELETE FROM alerts WHERE id=?", (aid,))
                    conn.commit()
            conn.close()
        except Exception as e:
            pass
        await asyncio.sleep(20)

# --- KHỞI ĐỘNG BOT ---
if __name__ == '__main__':
    init_db()
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("price", check_price))
    application.add_handler(CommandHandler("alert", set_alert))
    
    loop = asyncio.get_event_loop()
    loop.create_task(monitor_prices(application))
    
    print("🚀 Bot đang chạy...")
    application.run_polling()
