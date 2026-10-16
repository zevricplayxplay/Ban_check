
import os, time, asyncio, requests, random, json, threading
from collections import OrderedDict
from dotenv import load_dotenv
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode, ChatAction

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN") or "8818367722:AAEr2DhzztY4KjHu92CNiu4P9hNoIL83bSg"
OWNER = "@just_zevric"
YT = "zevricxplay"

# === RENDER 24/7 KEEPALIVE SERVER ===
# Render Web Service ko PORT bind karna padta hai, isliye Flask health check
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return f"""
    <h1>⚡ ZEVRIC PLAY BOT 24/7 RUNNING ⚡</h1>
    <p>👑 Owner: @just_zevric</p>
    <p>▶️ YT: zevricxplay</p>
    <p>♾️ No Limit Mode: ON</p>
    <p>🔥 Status: Live & Running</p>
    <p>Bot Telegram pe active hai!</p>
    """

@flask_app.route('/health')
def health():
    return "OK - Bot Running 24/7", 200

@flask_app.route('/ping')
def ping():
    return "Pong! Bot Alive", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 Flask Keepalive running on port {port} - Render 24/7")
    flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# Cache & No Limit Logic (Deep Research)
CACHE = OrderedDict()
CACHE_TIME = 300

ANIM_FILES = {
    "bijli": "bijli-scan.gif",
    "banned": "banned-red.gif",
    "safe": "safe-green.gif",
    "hacker": "hacker-scan.gif"
}

def main_kb():
    kb = [
        [KeyboardButton("⚡ Check Ban ⚡"), KeyboardButton("👑 Owner")],
        [KeyboardButton("🔴 Banned Anim"), KeyboardButton("🟢 Safe Anim")],
        [KeyboardButton("💻 Hacker Scan"), KeyboardButton("⚡ Bijli Scan")],
        [KeyboardButton("ℹ️ Help"), KeyboardButton("▶️ YouTube")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True, is_persistent=True)

def get_cache(uid):
    if uid in CACHE:
        ts, data = CACHE[uid]
        if time.time() - ts < CACHE_TIME:
            return data
        else:
            del CACHE[uid]
    return None

def set_cache(uid, data):
    CACHE[uid] = (time.time(), data)
    if len(CACHE) > 200:
        CACHE.popitem(last=False)

def get_ban_no_limit(uid):
    cached = get_cache(uid)
    if cached:
        return cached[0], cached[1], cached[2] + " (Cached ⚡)"

    headers_list = [
        {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36", "Referer": "https://ff.garena.com/", "Accept": "application/json"},
        {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64) AppleWebKit/537.36", "Referer": "https://ff.garena.com/", "Accept": "application/json"},
    ]

    garena_endpoints = [
        f"https://ff.garena.com/api/antihack/check_banned?lang=en&uid={uid}",
        f"https://ff.garena.com/api/antihack/check_banned?lang=id&uid={uid}",
        f"https://ff.garena.com/api/antihack/check_banned?lang=th&uid={uid}",
        f"https://ff.garena.com/api/antihack/check_banned?lang=vn&uid={uid}",
        f"https://ff.garena.com/api/antihack/check_banned?lang=ar&uid={uid}",
        f"https://ff.garena.com/api/antihack/check_banned?lang=pt&uid={uid}",
        f"https://ff.garena.com/api/antihack/check_banned?lang=es&uid={uid}",
    ]

    session = requests.Session()
    random.shuffle(garena_endpoints)
    for endpoint in garena_endpoints:
        try:
            h = random.choice(headers_list)
            r = session.get(endpoint, headers=h, timeout=6)
            if r.status_code == 200 and r.text.strip().startswith("{"):
                j = r.json()
                data = j.get("data", j)
                ib = data.get("is_banned", data.get("banned"))
                if ib is not None:
                    ib_val = 1 if str(ib).lower() in ["1","true"] or ib==True else 0
                    period = data.get("period") or 0
                    result = (ib_val, period, "Garena Official ⚡")
                    set_cache(uid, result)
                    return result
        except:
            pass
        time.sleep(0.25)

    # Retry
    time.sleep(2)
    try:
        r = session.get(f"https://ff.garena.com/api/antihack/check_banned?lang=en&uid={uid}", headers=headers_list[0], timeout=8)
        if r.text.strip().startswith("{"):
            j = r.json()
            d = j.get("data", j)
            ib = d.get("is_banned")
            if ib is not None:
                ib_val = 1 if str(ib).lower() in ["1","true"] else 0
                result = (ib_val, d.get("period",0), "Garena Retry ⚡")
                set_cache(uid, result)
                return result
    except:
        pass
    return None, None, None

async def start(update, context):
    txt = f"""
<b>⚡⚡⚡ RENDER 24/7 NO LIMIT ⚡⚡⚡</b>
<b>👑 {OWNER} | ▶️ {YT}</b>

<b>Ab 24/7 Render pe chalega!</b>
♾️ No Limit | 🔥 Bulk | ⚡ Animations

<b>Use:</b>
<code>/id 123 456 789</code> - Kitne bhi!
"""
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=main_kb())

async def owner_cmd(update, context):
    kb = [[InlineKeyboardButton("📱 @just_zevric", url="https://t.me/just_zevric")]]
    await update.message.reply_text(f"👑 {OWNER} | ▶️ {YT} - 24/7 Running", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

async def send_anim(update, key, cap=""):
    try:
        p = ANIM_FILES.get(key)
        if os.path.exists(p):
            with open(p, 'rb') as f:
                await update.message.reply_animation(animation=f, caption=cap, parse_mode=ParseMode.HTML)
            return True
    except:
        pass
    return False

async def check_logic(update, context, uid_list):
    results = []
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    await send_anim(update, random.choice(["bijli", "hacker"]), f"⚡ Scanning {len(uid_list)} UID... 24/7 Mode")
    status_msg = await update.message.reply_text(f"⚡ <b>Checking {len(uid_list)} UID... 24/7 No Limit ♾️</b>", parse_mode=ParseMode.HTML)

    for idx, uid in enumerate(uid_list):
        if not uid.isdigit():
            continue
        try:
            await status_msg.edit_text(f"⚡ <b>{idx+1}/{len(uid_list)}: <code>{uid}</code></b>\n♾️ 24/7 No Limit", parse_mode=ParseMode.HTML)
        except:
            pass
        banned, period, src = get_ban_no_limit(uid)
        results.append((uid, banned, period))

    final_lines = [f"<b>⚡⚡ 24/7 RESULTS ⚡⚡</b>\n"]
    bc = sc = 0
    for uid, st, per in results:
        if st == 1:
            final_lines.append(f"🚫 <code>{uid}</code> - <b>BANNED</b>")
            bc+=1
        elif st == 0:
            final_lines.append(f"✅ <code>{uid}</code> - <b>SAFE</b>")
            sc+=1
        else:
            final_lines.append(f"⚠️ <code>{uid}</code> - <b>Retry</b>")

    final_lines.append(f"\n<b>Total: {len(results)} | 🚫 {bc} | ✅ {sc}</b>")
    final_lines.append(f"\n👑 {OWNER} | ▶️ {YT} | 🌐 Render 24/7")
    final_text = "\n".join(final_lines)

    if bc>0 and sc==0:
        await send_anim(update, "banned", "🚫 Banned Found")
    elif sc>0 and bc==0:
        await send_anim(update, "safe", "✅ All Safe")
    else:
        await send_anim(update, "bijli", "⚡ Done")

    kb = [[InlineKeyboardButton("⚡ Again", callback_data="again")]]
    await status_msg.edit_text(final_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

async def check_cmd(update, context):
    uids = []
    if context.args:
        for a in context.args:
            for part in a.replace(",", " ").split():
                if part.strip().isdigit():
                    uids.append(part.strip())
    if not uids:
        await update.message.reply_text("UID: <code>/id 123 456 789</code> - No Limit!", parse_mode=ParseMode.HTML, reply_markup=main_kb())
        return
    await check_logic(update, context, uids)

async def text_handler(update, context):
    txt = update.message.text.strip()
    if txt == "⚡ Check Ban ⚡":
        await update.message.reply_text("Kitne bhi UID: <code>/id 123 456 789</code>", parse_mode=ParseMode.HTML, reply_markup=main_kb())
        return
    if txt in ["👑 Owner", "ℹ️ Help", "▶️ YouTube", "🚀 Start"]:
        await start(update, context)
        return
    if "Banned Anim" in txt:
        await send_anim(update, "banned", "🔴 Banned")
        return
    if "Safe Anim" in txt:
        await send_anim(update, "safe", "🟢 Safe")
        return
    if "Hacker Scan" in txt:
        await send_anim(update, "hacker", "💻 Hacker")
        return
    if "Bijli Scan" in txt:
        await send_anim(update, "bijli", "⚡ Bijli")
        return
    import re
    found = re.findall(r'\d{6,}', txt)
    if found:
        await check_logic(update, context, found)
    else:
        await update.message.reply_text("UID bhejo! Bulk: <code>123 456 789</code>", parse_mode=ParseMode.HTML, reply_markup=main_kb())

async def cb(update, context):
    q = update.callback_query
    await q.answer()
    if q.data == "again":
        await q.message.reply_text("Naye UID bhejo: <code>/id 123 456 789</code>", parse_mode=ParseMode.HTML, reply_markup=main_kb())

def main():
    # Start Flask in separate thread for Render 24/7 keepalive
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print(f"🌐 Flask Keepalive Started for Render 24/7")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("owner", owner_cmd))
    app.add_handler(CommandHandler("id", check_cmd))
    app.add_handler(CommandHandler("check", check_cmd))
    app.add_handler(CommandHandler("ban", check_cmd))
    app.add_handler(CallbackQueryHandler(cb))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    print(f"⚡ NO LIMIT 24/7 BOT Running - Owner {OWNER} - Render Ready")
    app.run_polling()

if __name__ == "__main__":
    main()
