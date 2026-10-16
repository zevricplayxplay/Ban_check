import os, time, asyncio, requests, threading, re, json
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

flask_app = Flask(__name__)
@flask_app.route('/')
def home():
    return "ZEVRIC PLAY BOT LIVE"
@flask_app.route('/health')
def health():
    return "OK", 200
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

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

def safe_json(url, timeout=14):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
        if not r.text or r.text.strip().startswith("<"):
            return None
        if len(r.text.strip()) < 5:
            return None
        return r.json()
    except:
        return None

def deep_find(obj, keys, max_depth=9, _depth=0):
    if _depth > max_depth:
        return None
    low = [k.lower() for k in keys]
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in low:
                if isinstance(v, (str,int,float)) and str(v).strip() != "":
                    return v
        for v in obj.values():
            res = deep_find(v, keys, max_depth, _depth+1)
            if res is not None:
                return res
    elif isinstance(obj, list):
        for item in obj:
            res = deep_find(item, keys, max_depth, _depth+1)
            if res is not None:
                return res
    return None

def deep_find_all_names(obj, results=None, _depth=0):
    if results is None:
        results = []
    if _depth > 9:
        return results
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in ["name","itemname","displayname","clothname","outfitname"]:
                if isinstance(v, str) and 2 < len(v) < 45:
                    results.append(v)
            deep_find_all_names(v, results, _depth+1)
    elif isinstance(obj, list):
        for it in obj:
            deep_find_all_names(it, results, _depth+1)
    return results

def get_player_deep(uid):
    endpoints = [
        f"https://wzapi.vercel.app/get_all?uid={uid}&region=IND",
        f"https://wzapi.vercel.app/get?uid={uid}&region=IND",
        f"https://wzapi.vercel.app/get?uid={uid}&region=SG",
        f"https://wzapiinfo.vercel.app/get?uid={uid}&region=IND",
        f"https://freefire-api-six.vercel.app/get_player_personal_show?server=ind&uid={uid}",
    ]
    for url in endpoints:
        data = safe_json(url, 14)
        if data:
            s = json.dumps(data).lower()
            if "player not found" in s and len(s) < 500:
                continue
            if any(k in s for k in ["nickname","basicinfo","accountinfo"]):
                return data
        time.sleep(0.3)
    return None

def get_outfit_deep(uid):
    for url in [
        f"https://wzapi.vercel.app/outfit?uid={uid}&region=IND",
        f"https://wzapi.vercel.app/outfit?uid={uid}&region=SG",
        f"https://wzapiinfo.vercel.app/outfit?uid={uid}&region=IND",
    ]:
        data = safe_json(url, 12)
        if data and len(str(data)) > 20:
            return data
        time.sleep(0.2)
    return None

def get_ban_deep(uid):
    cached = get_cache(uid)
    if cached:
        return cached
    for url in [
        f"https://wzapi.vercel.app/check_ban?uid={uid}",
        f"https://wzapiinfo.vercel.app/check_ban?uid={uid}",
    ]:
        d = safe_json(url, 10)
        if d:
            try:
                data = d.get("data", d) if isinstance(d, dict) else d
                if isinstance(data, dict):
                    ib = data.get("is_banned", data.get("banned"))
                    if ib is None and str(data.get("status","")).upper() == "OK":
                        ib = False
                    if ib is not None:
                        bv = 1 if str(ib).lower() in ["1","true","banned"] else 0
                        res = (bv, data.get("period",0))
                        set_cache(uid, res)
                        return res
            except:
                pass
        time.sleep(0.2)
    try:
        r = requests.get(f"https://ff.garena.com/api/antihack/check_banned?lang=en&uid={uid}", headers={"Referer":"https://ff.garena.com/"}, timeout=6)
        if r.text.strip().startswith("{"):
            j = r.json()
            d = j.get("data", j)
            ib = d.get("is_banned")
            if ib is not None:
                bv = 1 if str(ib)=="1" else 0
                res = (bv, d.get("period",0))
                set_cache(uid, res)
                return res
    except:
        pass
    return None

def parse_v5(raw, outfit_raw, uid):
    if not raw:
        return None
    name = deep_find(raw, ["nickname", "AccountName", "accountName", "playerName"]) or "Unknown"
    level = deep_find(raw, ["level", "AccountLevel", "accountLevel", "PlayerLevel", "lvl"]) or "?"
    likes = deep_find(raw, ["liked", "likes", "AccountLikes", "accountLikes"]) or "?"
    region = deep_find(raw, ["region", "AccountRegion"]) or "?"
    guild = deep_find(raw, ["clanName", "guildName", "ClanName", "GuildName"]) or "No Guild"
    bio = deep_find(raw, ["signature", "bio", "AccountSignature"]) or ""
    last = deep_find(raw, ["AccountLastLogin", "lastLogin", "LastLogin"]) or "?"
    pet = deep_find(raw, ["petName", "PetName", "pet", "Pet", "equippedPet"])
    if not pet and outfit_raw:
        pet = deep_find(outfit_raw, ["petName", "PetName", "pet", "Pet"])
    if not pet:
        pet = "?"
    
    dress = []
    if outfit_raw:
        names = deep_find_all_names(outfit_raw)
        seen = set()
        for n in names:
            if n.lower() not in [str(name).lower(), str(guild).lower(), "ind","sg","bd","pk"]:
                if n not in seen and 2 < len(n) < 40:
                    seen.add(n)
                    dress.append(n)
    if not dress and isinstance(raw, dict):
        pi = raw.get("profileInfo") or raw.get("ProfileInfo") or {}
        if isinstance(pi, dict):
            eq = pi.get("equippedOutfit") or pi.get("outfit") or []
            if isinstance(eq, list):
                for it in eq:
                    if isinstance(it, dict):
                        nn = it.get("name") or it.get("itemName")
                        if nn:
                            dress.append(nn)
    uniq = []
    seen2 = set()
    for d in dress:
        if d not in seen2:
            seen2.add(d)
            uniq.append(d)
    
    return {
        "uid": uid,
        "name": str(name),
        "level": str(level),
        "likes": str(likes),
        "region": str(region),
        "guild": str(guild),
        "bio": str(bio)[:70] if bio else "",
        "last": str(last),
        "pet": str(pet) if pet else "?",
        "dress": uniq[:6]
    }

def premium_kb():
    kb = [
        [KeyboardButton("🔴 1. Ban Check")],
        [KeyboardButton("🟢 2. Player Info")],
        [KeyboardButton("👑 3. Owner Info")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True, is_persistent=True)

async def start(update, context):
    txt = "<b>⚡ ZEVRIC PLAY ⚡</b>\n\n🔴 <b>1. Ban Check</b>\n🟢 <b>2. Player Info</b>\n👑 <b>3. Owner Info</b>\n\nExample: <code>12345678</code>"
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=premium_kb())

async def owner_info(update, context):
    txt = f"<b>👑 OWNER INFO</b>\n\n<b>Owner:</b> {OWNER}\n<b>YouTube:</b> zevricxplay\n\n🔗 Link below"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ YouTube Channel", url=YT_LINK)],
        [InlineKeyboardButton("💬 @just_zevric", url="https://t.me/just_zevric")]
    ])
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

async def handle_uid(update, context, uid_list, mode):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    status = await update.message.reply_text(f"⚡ Checking <code>{uid_list[0]}</code>...", parse_mode=ParseMode.HTML)
    
    for uid in uid_list[:2]:
        player_raw = get_player_deep(uid)
        outfit_raw = get_outfit_deep(uid)
        ban_res = get_ban_deep(uid)
        player = parse_v5(player_raw, outfit_raw, uid) if player_raw else None
        
        if mode == "ban":
            lines = []
            lines.append("<b>🚫 BAN CHECK</b>")
            lines.append("")
            lines.append(f"<b>UID:</b> <code>{uid}</code>")
            if player and player.get("name") != "Unknown":
                lines.append(f"<b>Name:</b> {player['name']}")
            lines.append("")
            if ban_res:
                is_banned, period = ban_res
                if is_banned == 1:
                    lines.append("<b>Status:</b> 🔴 BANNED")
                    if period and str(period) != "0":
                        lines.append(f"<b>Period:</b> {period}")
                else:
                    lines.append("<b>Status:</b> 🟢 NOT BANNED")
            else:
                lines.append("<b>Status:</b> ⚠️ Retry")
        else:
            lines = []
            lines.append("<b>👤 PLAYER INFO</b>")
            lines.append("")
            lines.append(f"<b>UID:</b> <code>{uid}</code>")
            if player:
                lines.append(f"<b>Name:</b> {player.get('name','Unknown')}")
                lines.append(f"<b>Level:</b> {player.get('level','?')}")
                lines.append(f"<b>Likes:</b> {player.get('likes','?')}")
                lines.append(f"<b>Region:</b> {player.get('region','?')}")
                lines.append(f"<b>Guild:</b> {player.get('guild','No Guild')}")
                if player.get('pet') and player.get('pet') not in ["?",""]:
                    lines.append(f"<b>🐾 Pet:</b> {player.get('pet')}")
                if player.get('dress'):
                    lines.append("")
                    lines.append("<b>👗 Dress:</b>")
                    for d in player.get('dress')[:5]:
                        lines.append(f"├ {d}")
                if player.get('last') and player.get('last') != "?":
                    lines.append("")
                    lines.append(f"<b>Last:</b> {player.get('last')}")
            else:
                lines.append("<b>Name:</b> API Busy - Retry after 5 sec")
            
            if ban_res:
                is_banned, _ = ban_res
                lines.append("")
                if is_banned == 1:
                    lines.append("<b>Ban:</b> 🔴 BANNED")
                else:
                    lines.append("<b>Ban:</b> 🟢 SAFE")
        
        txt = "\n".join(lines)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ YouTube", url=YT_LINK)],
            [InlineKeyboardButton("⚡ Again", callback_data="again")]
        ])
        await status.edit_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
        if len(uid_list) > 1 and uid != uid_list[0]:
            await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

async def check_cmd(update, context):
    uids = [p for a in context.args for p in a.replace(","," ").split() if p.isdigit() and 6 <= len(p) <= 15]
    if not uids:
        await update.message.reply_text("Example: <code>12345678</code>\n<code>/id 12345678</code>", parse_mode=ParseMode.HTML, reply_markup=premium_kb())
        return
    await handle_uid(update, context, uids, mode="info")

async def text_handler(update, context):
    txt = update.message.text.strip()
    if txt == "🔴 1. Ban Check":
        await update.message.reply_text("Ban Check Ke Liye UID Bhejo:\n<code>12345678</code>", parse_mode=ParseMode.HTML, reply_markup=premium_kb())
        return
    if txt == "🟢 2. Player Info":
        await update.message.reply_text("Player Info Ke Liye UID Bhejo:\n<code>12345678</code>\n(Dress + Pet)", parse_mode=ParseMode.HTML, reply_markup=premium_kb())
        return
    if txt == "👑 3. Owner Info":
        await owner_info(update, context)
        return
    found = re.findall(r'\d{6,15}', txt)
    valid = [u for u in found if 6 <= len(u) <= 15]
    if valid:
        await handle_uid(update, context, valid, mode="info")
    else:
        await update.message.reply_text("Example: <code>12345678</code>", parse_mode=ParseMode.HTML, reply_markup=premium_kb())

async def cb(update, context):
    q = update.callback_query
    await q.answer()
    if q.data == "again":
        await q.message.reply_text("Ban Check Ke Liye UID Bhejo: <code>12345678</code>", parse_mode=ParseMode.HTML, reply_markup=premium_kb())

def main():
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    threading.Thread(target=run_flask, daemon=True).start()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("owner", owner_info))
    app.add_handler(CommandHandler("id", check_cmd))
    app.add_handler(CommandHandler("check", check_cmd))
    app.add_handler(CommandHandler("ban", check_cmd))
    app.add_handler(CommandHandler("info", check_cmd))
    app.add_handler(CallbackQueryHandler(cb))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    print("PREMIUM V5 - Dress+Pet + Color Buttons + Clean Owner")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
