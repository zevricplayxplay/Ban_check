
import os, time, asyncio, requests, random, threading, re
from collections import OrderedDict
from dotenv import load_dotenv
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.constants import ParseMode, ChatAction

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN") or "8818367722:AAEr2DhzztY4KjHu92CNiu4P9hNoIL83bSg"
OWNER = "@just_zevric"
YT_LINK = "https://youtube.com/@zevricxplay?si=b2Txy7j1S3l-q9_P"

# === RENDER 24/7 ===
flask_app = Flask(__name__)
@flask_app.route('/')
def home():
    return "ZEVRIC PLAY BOT - LIVE 24/7"
@flask_app.route('/health')
def health():
    return "OK", 200
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# Cache
CACHE = OrderedDict()
def get_cache(uid):
    if uid in CACHE:
        ts, data = CACHE[uid]
        if time.time() - ts < 300:
            return data
        del CACHE[uid]
    return None
def set_cache(uid, data):
    CACHE[uid] = (time.time(), data)
    if len(CACHE) > 200:
        CACHE.popitem(last=False)

def safe_json(url, timeout=10):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
        if not r.text or r.text.strip().startswith("<"):
            return None
        return r.json()
    except:
        return None

# === APIS - Fixed for Render ===
def get_player(uid):
    for ep in [f"https://wzapiinfo.vercel.app/get?uid={uid}", f"https://free-fire-api-one.vercel.app/api/info?uid={uid}&region=ind"]:
        d = safe_json(ep, 12)
        if d and len(str(d)) > 10:
            return d
        time.sleep(0.2)
    return None

def get_ban(uid):
    cached = get_cache(uid)
    if cached:
        return cached
    for ep in [f"https://wzapiinfo.vercel.app/check_ban?uid={uid}", f"https://ff-ban-check-api.vercel.app/api/ban?uid={uid}"]:
        d = safe_json(ep, 10)
        if d:
            try:
                data = d.get("data", d)
                ib = data.get("is_banned", data.get("banned"))
                if ib is not None:
                    bv = 1 if str(ib).lower() in ["1","true"] else 0
                    period = data.get("period", 0)
                    res = (bv, period)
                    set_cache(uid, res)
                    return res
            except:
                pass
        time.sleep(0.2)
    # Garena fallback
    try:
        r = requests.get(f"https://ff.garena.com/api/antihack/check_banned?lang=en&uid={uid}", headers={"Referer":"https://ff.garena.com/"}, timeout=6)
        if r.text.strip().startswith("{"):
            j = r.json().get("data", r.json())
            ib = j.get("is_banned")
            if ib is not None:
                bv = 1 if str(ib)=="1" else 0
                res = (bv, j.get("period",0))
                set_cache(uid, res)
                return res
    except:
        pass
    return None

def parse_info(raw, uid):
    if not raw:
        return None
    info = {"uid": uid}
    try:
        b = raw.get("basicInfo") or raw.get("AccountInfo") or raw
        info["name"] = b.get("nickname") or b.get("AccountName") or b.get("name") or raw.get("nickname") or "Unknown"
        info["level"] = b.get("level") or b.get("AccountLevel") or raw.get("level") or "?"
        info["likes"] = b.get("liked") or b.get("likes") or raw.get("likes") or "?"
        info["region"] = b.get("region") or raw.get("region") or "?"
        clan = raw.get("clanBasicInfo") or raw.get("GuildInfo") or {}
        info["guild"] = clan.get("clanName") or clan.get("guildName") or raw.get("guild") or "No Guild"
        info["bio"] = raw.get("signature") or b.get("signature") or "—"
        info["last"] = raw.get("AccountLastLogin") or raw.get("lastLogin") or "?"
    except:
        pass
    return info

# === PREMIUM KEYBOARD - Only 3 as you said ===
def premium_kb():
    kb = [
        [KeyboardButton("1. Ban Check")],
        [KeyboardButton("2. Player Info")],
        [KeyboardButton("3. Owner Info")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True, is_persistent=True)

async def start(update, context):
    txt = f"""<b>⚡ ZEVRIC PLAY ⚡</b>

<b>Premium Ban & Info Bot</b>

<b>1.</b> Ban Check
<b>2.</b> Player Info
<b>3.</b> Owner Info

UID bhejo → <code>/id 12345678</code>"""
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=premium_kb())

async def owner_premium(update, context):
    txt = f"""<b>👑 OWNER INFO</b>

<b>Owner:</b> @just_zevric
<b>YouTube:</b> zevricxplay

<b>24/7 Live • No Limit • Premium</b>"""
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ YouTube", url=YT_LINK)],
        [InlineKeyboardButton("💬 Telegram", url="https://t.me/just_zevric")]
    ])
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

async def ban_check_logic(update, context, uid_list, mode="ban"):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    status = await update.message.reply_text(f"⚡ Checking <code>{uid_list[0]}</code>...", parse_mode=ParseMode.HTML)
    
    for uid in uid_list[:5]:  # Max 5 at once for premium clean look
        player_raw = get_player(uid)
        ban_res = get_ban(uid)
        player = parse_info(player_raw, uid) if player_raw else None
        
        if mode == "ban":
            # PREMIUM BAN CHECK DESIGN - No extra text
            lines = [f"<b>🚫 BAN CHECK</b>", ""]
            lines.append(f"<b>UID:</b> <code>{uid}</code>")
            if player:
                lines.append(f"<b>Name:</b> {player.get('name','?')}")
            lines.append("")
            if ban_res:
                is_banned, period = ban_res
                if is_banned == 1:
                    lines.append(f"<b>Status:</b> 🔴 BANNED")
                    if period and period != 0:
                        lines.append(f"<b>Period:</b> {period}")
                else:
                    lines.append(f"<b>Status:</b> 🟢 NOT BANNED")
            else:
                lines.append(f"<b>Status:</b> ⚠️ Try again")
            lines.append(f"\n<b>{OWNER}</b>")
            txt = "\n".join(lines)
        
        else:  # Player Info mode
            lines = [f"<b>👤 PLAYER INFO</b>", ""]
            lines.append(f"<b>UID:</b> <code>{uid}</code>")
            if player:
                lines.append(f"<b>Name:</b> {player.get('name','Unknown')}")
                lines.append(f"<b>Level:</b> {player.get('level','?')}")
                lines.append(f"<b>Likes:</b> {player.get('likes','?')}")
                lines.append(f"<b>Region:</b> {player.get('region','?')}")
                lines.append(f"<b>Guild:</b> {player.get('guild','No Guild')}")
                if player.get('last') != "?":
                    lines.append(f"<b>Last:</b> {player.get('last')}")
            else:
                lines.append(f"<b>Name:</b> Not found (API busy)")
            
            if ban_res:
                is_banned, period = ban_res
                status_emoji = "🔴 BANNED" if is_banned==1 else "🟢 SAFE"
                lines.append(f"")
                lines.append(f"<b>Ban:</b> {status_emoji}")
            
            lines.append(f"\n<b>{OWNER}</b>")
            txt = "\n".join(lines)
        
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ YouTube", url=YT_LINK)],
            [InlineKeyboardButton("⚡ Check Again", callback_data="again")]
        ])
        
        await status.edit_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
        if len(uid_list) > 1 and uid != uid_list[0]:
            await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

async def check_cmd(update, context):
    uids = []
    for a in context.args:
        for p in a.replace(","," ").split():
            if p.isdigit() and 6 <= len(p) <= 15:
                uids.append(p)
    if not uids:
        await update.message.reply_text("UID: <code>/id 3635825799</code>", parse_mode=ParseMode.HTML, reply_markup=premium_kb())
        return
    # Default to full info if /id used
    await ban_check_logic(update, context, uids, mode="info")

async def text_handler(update, context):
    txt = update.message.text.strip()
    
    if txt == "1. Ban Check":
        await update.message.reply_text("UID bhejo for Ban Check:\n<code>3635825799</code> ya <code>/id 3635825799</code>", parse_mode=ParseMode.HTML, reply_markup=premium_kb())
        return
    if txt == "2. Player Info":
        await update.message.reply_text("UID bhejo for Player Info:\n<code>3635825799</code> ya <code>/id 3635825799</code>", parse_mode=ParseMode.HTML, reply_markup=premium_kb())
        return
    if txt == "3. Owner Info":
        await owner_premium(update, context)
        return
    
    # Detect mode from last button? For now, if user just sends UID, show both ban + info premium
    found = re.findall(r'\d{6,15}', txt)
    valid = [u for u in found if 6 <= len(u) <= 15]
    if valid:
        # If they previously clicked Ban Check, show ban mode, else player info
        # Simple: always show premium combined (both info)
        await ban_check_logic(update, context, valid, mode="info")
    else:
        await update.message.reply_text("UID bhejo", parse_mode=ParseMode.HTML, reply_markup=premium_kb())

async def cb(update, context):
    q = update.callback_query
    await q.answer()
    if q.data == "again":
        await q.message.reply_text("UID bhejo: <code>/id 12345678</code>", parse_mode=ParseMode.HTML, reply_markup=premium_kb())

def main():
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    threading.Thread(target=run_flask, daemon=True).start()
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("owner", owner_premium))
    app.add_handler(CommandHandler("id", check_cmd))
    app.add_handler(CommandHandler("check", check_cmd))
    app.add_handler(CommandHandler("ban", check_cmd))
    app.add_handler(CommandHandler("info", check_cmd))
    app.add_handler(CallbackQueryHandler(cb))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    print(f"⚡ PREMIUM BOT - 3 Options Only - {OWNER} - Render 24/7")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
