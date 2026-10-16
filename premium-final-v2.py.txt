
import os, time, asyncio, requests, threading, re
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
    return "ZEVRIC PLAY BOT LIVE 24/7"
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

def safe_json(url, timeout=12):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}, timeout=timeout)
        if not r.text:
            return None
        txt = r.text.strip()
        if txt.startswith("<") or txt.startswith("<!DOCTYPE"):
            return None
        # Some APIs return text with extra
        if len(txt) < 5:
            return None
        return r.json()
    except Exception as e:
        # print(f"safe_json fail {url} {e}")
        return None

def get_player_deep(uid):
    """Deep research player info - tries 8+ endpoints with regions"""
    # Research found these endpoints work from Render
    endpoints = [
        f"https://wzapi.vercel.app/get?uid={uid}&region=IND",
        f"https://wzapi.vercel.app/get?uid={uid}&region=SG",
        f"https://wzapi.vercel.app/get?uid={uid}&region=BD",
        f"https://wzapi.vercel.app/get?uid={uid}&region=PK",
        f"https://wzapiinfo.vercel.app/get?uid={uid}&region=IND",
        f"https://wzapiinfo.vercel.app/get?uid={uid}&region=SG",
        f"https://wzapiinfo.vercel.app/get?uid={uid}",
        f"https://freefire-api-six.vercel.app/get_player_personal_show?server=ind&uid={uid}",
        f"https://anuj-free-fire-api.vercel.app/player-info?id={uid}",
        f"https://free-fire-api-one.vercel.app/api/info?uid={uid}&region=ind",
        f"https://freefireinfo.site/api/player?uid={uid}",
    ]
    for url in endpoints:
        data = safe_json(url, 12)
        if data:
            # Check if valid player data - must have some key
            txt = str(data).lower()
            if any(k in txt for k in ["nickname", "accountname", "basicinfo", "accountinfo", "level", "region"]):
                # Avoid error responses
                if "error" in txt and len(txt) < 200:
                    continue
                if isinstance(data, dict) and data.get("message") == "Player not found":
                    continue
                return data
        time.sleep(0.25)
    return None

def get_ban_deep(uid):
    cached = get_cache(uid)
    if cached:
        return cached
    apis = [
        f"https://wzapi.vercel.app/check_ban?uid={uid}",
        f"https://wzapi.vercel.app/check_ban?uid={uid}&lang=en",
        f"https://wzapiinfo.vercel.app/check_ban?uid={uid}",
        f"https://ff-ban-check-api.vercel.app/api/ban?uid={uid}",
    ]
    for url in apis:
        d = safe_json(url, 10)
        if d:
            try:
                data = d.get("data", d) if isinstance(d, dict) else d
                if isinstance(data, dict):
                    ib = data.get("is_banned")
                    if ib is None:
                        ib = data.get("banned")
                    if ib is None:
                        ib = data.get("status")
                        # status OK means not banned
                        if isinstance(ib, str) and ib.upper() == "OK":
                            ib = False
                    if ib is not None:
                        bv = 1 if str(ib).lower() in ["1","true","banned"] or ib==True else 0
                        # If status was string OK, set 0
                        if str(data.get("status","")).upper() == "OK":
                            bv = 0
                        period = data.get("period", data.get("ban_period", 0))
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

def parse_player(raw, uid):
    if not raw:
        return None
    info = {"uid": uid, "name": "Unknown", "level": "?", "likes": "?", "region": "?", "guild": "No Guild", "bio": "", "last": "?"}
    try:
        # The raw can be deeply nested, try all possible paths
        # Path 1: basicInfo at top
        b = None
        if "basicInfo" in raw:
            b = raw["basicInfo"]
        elif "AccountInfo" in raw:
            b = raw["AccountInfo"]
        elif "data" in raw and isinstance(raw["data"], dict):
            d = raw["data"]
            b = d.get("basicInfo") or d.get("AccountInfo") or d
        elif "player" in raw:
            b = raw["player"]
        else:
            b = raw

        # If b is still dict containing basicInfo again
        if isinstance(b, dict) and "basicInfo" in b:
            b = b["basicInfo"]

        # Extract name
        if isinstance(b, dict):
            info["name"] = b.get("nickname") or b.get("AccountName") or b.get("accountName") or b.get("name") or b.get("playerName") or raw.get("nickname") or raw.get("name") or "Unknown"
            # Level
            info["level"] = b.get("level") or b.get("AccountLevel") or b.get("accountLevel") or b.get("lvl") or raw.get("level") or raw.get("AccountLevel") or "?"
            # Likes
            info["likes"] = b.get("liked") or b.get("likes") or b.get("like") or b.get("AccountLikes") or raw.get("likes") or "?"
            # Region
            info["region"] = b.get("region") or b.get("AccountRegion") or raw.get("region") or raw.get("Region") or "?"
            # Exp
            info["exp"] = b.get("exp") or b.get("Exp") or "?"
            # Bio
            info["bio"] = b.get("signature") or b.get("bio") or raw.get("signature") or raw.get("bio") or ""

        # Guild
        clan = raw.get("clanBasicInfo") or raw.get("clanInfo") or raw.get("GuildInfo") or raw.get("guildInfo") or {}
        if isinstance(clan, dict):
            info["guild"] = clan.get("clanName") or clan.get("guildName") or clan.get("name") or info["guild"]
        if info["guild"] == "No Guild":
            info["guild"] = raw.get("guildName") or raw.get("clanName") or "No Guild"

        # Last login
        info["last"] = raw.get("AccountLastLogin") or raw.get("lastLogin") or (b.get("lastLogin") if isinstance(b, dict) else None) or "?"

        # If still Unknown, try deeper search in stringified json for nickname pattern
        if info["name"] == "Unknown":
            # Try to find nickname in raw recursively
            def find_key(obj, keys):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if k.lower() in [x.lower() for x in keys]:
                            if isinstance(v, str) and len(v) > 1:
                                return v
                        res = find_key(v, keys)
                        if res:
                            return res
                elif isinstance(obj, list):
                    for item in obj:
                        res = find_key(item, keys)
                        if res:
                            return res
                return None
            found_name = find_key(raw, ["nickname", "accountname", "name"])
            if found_name:
                info["name"] = found_name

    except Exception as e:
        print(f"parse error {e}")
    return info

def premium_kb():
    kb = [
        [KeyboardButton("1. Ban Check")],
        [KeyboardButton("2. Player Info")],
        [KeyboardButton("3. Owner Info")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True, is_persistent=True)

async def start(update, context):
    txt = f"""<b>⚡ ZEVRIC PLAY - PREMIUM ⚡</b>

<b>1.</b> Ban Check
<b>2.</b> Player Info
<b>3.</b> Owner Info

UID: <code>/id 1257303458</code>"""
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=premium_kb())

async def owner_info(update, context):
    txt = f"""<b>👑 OWNER INFO</b>

<b>Owner:</b> @just_zevric
<b>YouTube:</b> zevricxplay
<b>Link:</b> https://youtube.com/@zevricxplay?si=b2Txy7j1S3l-q9_P

<b>Premium • 24/7 • No Limit</b>"""
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ YouTube", url=YT_LINK)],
        [InlineKeyboardButton("💬 Telegram", url="https://t.me/just_zevric")]
    ])
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

async def handle_uid(update, context, uid_list, mode):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    status = await update.message.reply_text(f"⚡ Checking <code>{uid_list[0]}</code>...", parse_mode=ParseMode.HTML)
    
    for uid in uid_list[:3]:
        # Deep research fetch
        player_raw = get_player_deep(uid)
        ban_res = get_ban_deep(uid)
        player = parse_player(player_raw, uid) if player_raw else None
        
        if mode == "ban":
            lines = [f"<b>🚫 BAN CHECK</b>", ""]
            lines.append(f"<b>UID:</b> <code>{uid}</code>")
            if player and player.get("name") != "Unknown":
                lines.append(f"<b>Name:</b> {player['name']}")
                lines.append(f"<b>Level:</b> {player['level']}")
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
                lines.append(f"<b>Status:</b> ⚠️ API Busy - Retry")
            lines.append(f"\n<b>{OWNER}</b>")
        else:
            lines = [f"<b>👤 PLAYER INFO</b>", ""]
            lines.append(f"<b>UID:</b> <code>{uid}</code>")
            if player:
                # If name still Unknown, show raw keys for debug but try best
                name = player.get("name","Unknown")
                if name == "Unknown" and player_raw:
                    # Try to extract any readable name from raw
                    lines.append(f"<b>Name:</b> {name}")
                    lines.append(f"<b>Level:</b> {player.get('level','?')}")
                    lines.append(f"<b>Likes:</b> {player.get('likes','?')}")
                    lines.append(f"<b>Region:</b> {player.get('region','?')}")
                    lines.append(f"<b>Guild:</b> {player.get('guild','No Guild')}")
                    if player.get('last') and player.get('last') != "?":
                        lines.append(f"<b>Last Login:</b> {player.get('last')}")
                    if player.get('bio'):
                        bio = str(player.get('bio'))[:80]
                        if bio and bio != "":
                            lines.append(f"<b>Bio:</b> {bio}")
                else:
                    lines.append(f"<b>Name:</b> {name}")
                    lines.append(f"<b>Level:</b> {player.get('level','?')}")
                    lines.append(f"<b>Likes:</b> {player.get('likes','?')}")
                    lines.append(f"<b>Region:</b> {player.get('region','?')}")
                    lines.append(f"<b>Guild:</b> {player.get('guild','No Guild')}")
                    if player.get('last') and player.get('last') != "?":
                        lines.append(f"<b>Last:</b> {player.get('last')}")
                    if player.get('bio'):
                        bio = str(player.get('bio'))[:80]
                        if bio:
                            lines.append(f"<b>Bio:</b> {bio}")
            else:
                lines.append(f"<b>Name:</b> API Busy - Try again")
                lines.append(f"<b>Tip:</b> Garena limits Render IP, retry after 5 sec")
            
            if ban_res:
                is_banned, _ = ban_res
                lines.append(f"")
                lines.append(f"<b>Ban:</b> {'🔴 BANNED' if is_banned==1 else '🟢 SAFE'}")
            
            lines.append(f"\n<b>{OWNER}</b>")
        
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
        await update.message.reply_text("UID: <code>/id 1257303458</code>", parse_mode=ParseMode.HTML, reply_markup=premium_kb())
        return
    await handle_uid(update, context, uids, mode="info")

async def text_handler(update, context):
    txt = update.message.text.strip()
    if txt == "1. Ban Check":
        await update.message.reply_text("Ban Check ke liye UID bhejo:\n<code>1257303458</code>", parse_mode=ParseMode.HTML, reply_markup=premium_kb())
        return
    if txt == "2. Player Info":
        await update.message.reply_text("Player Info ke liye UID bhejo:\n<code>1257303458</code>", parse_mode=ParseMode.HTML, reply_markup=premium_kb())
        return
    if txt == "3. Owner Info":
        await owner_info(update, context)
        return
    found = re.findall(r'\d{6,15}', txt)
    valid = [u for u in found if 6 <= len(u) <= 15]
    if valid:
        # Determine mode based on last button? For now use Player Info as default (includes ban)
        await handle_uid(update, context, valid, mode="info")
    else:
        await update.message.reply_text("UID bhejo: <code>1257303458</code>", parse_mode=ParseMode.HTML, reply_markup=premium_kb())

async def cb(update, context):
    q = update.callback_query
    await q.answer()
    if q.data == "again":
        await q.message.reply_text("UID: <code>/id 1257303458</code>", parse_mode=ParseMode.HTML, reply_markup=premium_kb())

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
    app.add_handler(CommandHandler("ban", lambda u,c: handle_uid(u,c, [a for a in c.args if a.isdigit()], "ban")))
    app.add_handler(CommandHandler("info", check_cmd))
    app.add_handler(CallbackQueryHandler(cb))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    print("⚡ PREMIUM V2 - Deep Research - Player Info Fixed")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
