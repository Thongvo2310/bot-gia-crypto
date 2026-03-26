import requests
import asyncio
import sqlite3
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- THÔNG TIN CỦA THÔNG ---
TOKEN = "8268708834:AAH9kN-VM0J-zq2BV_B7yaqMhQBGJtxdUgQ"
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
    help_text = """
✅ *TRỢ LÝ BÁO GIÁ ĐÃ SẴN SÀNG!*

📌 *CÁC LỆNH:*
• `/price btc` - Xem giá hiện tại
• `/alert btc 65000` - Đặt cảnh báo
• `/list` - Xem các cảnh báo đang chạy
• `/clear` - Xóa tất cả cảnh báo
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def check_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID: return
    if not context.args:
        await update.message.reply_text("⚠️ Ví dụ: `/price btc`", parse_mode='Markdown')
        return
    symbol = context.args[0].upper()
    price = get_price(symbol)
    if price:
        await update.message.reply_text(f"💰 *{symbol}*: `${price:,.2f}`", parse_mode='Markdown')
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
        await update.message.reply_text(f"✅ Đã đặt báo động *{symbol}* tại ngưỡng `${target_price:,.2f}`", parse_mode='Markdown')
    except:
        await update.message.reply_text("⚠️ Lỗi cú pháp! Thử lại: `/alert btc 65000`", parse_mode='Markdown')

async def list_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID: return
    conn = sqlite3.connect('alerts.db')
    c = conn.cursor()
    c.execute("SELECT * FROM alerts")
    alerts = c.fetchall()
    conn.close()
    
    if not alerts:
        await update.message.reply_text("📭 Chưa có cảnh báo nào.")
        return
    
    text = "🔔 *CÁC CẢNH BÁO ĐANG CHẠY:*\n\n"
    for alert in alerts:
        aid, sym, target, direct = alert
        arrow = "📈" if direct == "above" else "📉"
        text += f"{arrow} `{sym}`: ${target:,.2f} ({direct})\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def clear_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID: return
    conn = sqlite3.connect('alerts.db')
    c = conn.cursor()
    c.execute("DELETE FROM alerts")
    conn.commit()
    conn.close()
    await update.message.reply_text("🗑️ Đã xóa tất cả cảnh báo!")

# --- LUỒNG KIỂM TRA GIÁ ---
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
                    await app.bot.send_message(chat_id=USER_ID, text=f"🚨 BÁO ĐỘNG: *{sym}* đã chạm `${curr:,.2f}`!", parse_mode='Markdown')
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
    
    print("🚀 Bot đang chạy...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
