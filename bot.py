import requests
import asyncio
import sqlite3
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- THÔNG TIN ---
TOKEN = "8268708834:AAH9kN-VM0J-zq2BV_B7yaqMhQBGJtxdUgQ"
USER_ID = 988502675

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    incoming_id = update.effective_user.id
    print(f"👉 NHẬN ĐƯỢC TIN NHẮN TỪ ID: {incoming_id}")
    
    if incoming_id != USER_ID: 
        await update.message.reply_text(f"⛔ Xin lỗi, bạn đang bị chặn vì sai ID!\n\n👉 ID trong code hiện tại: {USER_ID}\n👉 ID thực tế của bạn là: {incoming_id}\n\nCách sửa: Mở code trên GitHub, sửa lại dòng USER_ID thành {incoming_id} là xong!")
        return
        
    await update.message.reply_text("✅ TRỢ LÝ BÁO GIÁ ĐÃ SẴN SÀNG!\n- Gõ /price btc\n- Gõ /alert btc 65000\n- Gõ /list để xem lệnh")

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
        await update.message.reply_text(f"✅ Đã đặt báo động {symbol} tại ${target_price:,.2f}")
    except:
        await update.message.reply_text("⚠️ Lỗi! Thử lại: /alert btc 65000")

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
    asyncio.create_task(monitor_prices(application))
    print("🚀 Bot đang chạy và chờ tin nhắn...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
