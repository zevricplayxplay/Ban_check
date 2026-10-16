
import os, time, asyncio, requests, random, json
from collections import OrderedDict
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode, ChatAction

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN") or "8818367722:AAEr2DhzztY4KjHu92CNiu4P9hNoIL83bSg"
OWNER = "@just_zevric"
YT = "zevricxplay"

# Cache - same UID dobara check nahi karega 5 min tak, Garena limit bachega
CACHE = OrderedDict()
CACHE_TIME = 300  # 5 min

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

# Deep Research - No Limit System
# Garena alag-alag lang endpoint se limit bypass hota hai
def get_ban_no_limit(uid):
    # 1. Check cache first - limit hi nahi lagega same UID pe
    cached = get_cache(uid)
    if cached:
        return cached[0], cached[1], cached[2] + " (Cached ⚡)"

    headers_list = [
        {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36", "Referer": "https://ff.garena.com/", "Accept": "application/json"},
        {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64) AppleWebKit/537.36", "Referer": "https://ff.garena.com/", "Accept": "application/json"},
        {"User-Agent": "FreeFire/1.0", "Referer": "https://ff.garena.com/", "Accept": "*/*"},
    ]

    # Garena ke 6 alag lang endpoints - ek block hua to dusra chalega = NO LIMIT
    garena_endpoints = [
        f"https://ff.garena.com/api/antihack/check_banned?lang=en&uid={uid}",
        f"https://ff.garena.com/api/antihack/check_banned?lang=id&uid={uid}",
        f"https://ff.garena.com/api/antihack/check_banned?lang=th&uid={uid}",
        f"https://ff.garena.com/api/antihack/check_banned?lang=vn&uid={uid}",
        f"https://ff.garena.com/api/antihack/check_banned?lang=ar&uid={uid}",
        f"https://ff.garena.com/api/antihack/check_banned?lang=pt&uid={uid}",
        f"https://ff.garena.com/api/antihack/check_banned?lang=es&uid={uid}",
    ]

    # Fallback APIs - Garena sab fail ho to ye chalenge
    fallback_apis = [
        f"https://ff-banned-check.vercel.app/check_banned?uid={uid}",
        f"https://api-free-fire-ban.vercel.app/api/ban?uid={uid}",
    ]

    session = requests.Session()
    
    # Try Garena endpoints in random order - limit bypass trick
    random.shuffle(garena_endpoints)
    for endpoint in garena_endpoints:
        try:
            h = random.choice(headers_list)
            r = session.get(endpoint, headers=h, timeout=6)
            if r.status_code == 200 and r.text.strip() and r.text.strip().startswith("{"):
                j = r.json()
                data = j.get("data", j)
                ib = data.get("is_banned", data.get("banned"))
                if ib is not None:
                    ib_val = 1 if str(ib).lower() in ["1","true"] or ib==True else 0
                    period = data.get("period") or data.get("ban_period") or 0
                    result = (ib_val, period, "Garena Official ⚡")
                    set_cache(uid, result)
                    return result
        except:
            pass
        time.sleep(0.25)  # Chhota gap, user ko pata nahi chalega

    # Agar Garena ke sab fail, to fallback try karo
    for fb in fallback_apis:
        try:
            h = random.choice(headers_list)
            r = session.get(fb, headers=h, timeout=7)
            if r.status_code == 200 and r.text.strip().startswith("{"):
                j = r.json()
                d = j.get("data", j)
                ib = d.get("is_banned", d.get("banned"))
                if ib is not None:
                    ib_val = 1 if str(ib).lower() in ["1","true"] or ib==True else 0
                    result = (ib_val, d.get("period",0), "Fallback API")
                    set_cache(uid, result)
                    return result
        except:
            pass
        time.sleep(0.2)

    # Last retry after 2 sec wait - deep research trick
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
<b>⚡⚡⚡ NO LIMIT PRO MAX ⚡⚡⚡</b>
<b>👑 {OWNER} | ▶️ {YT}</b>

<b>Ab Limit Nahi Lagega! 🚀</b>

Chahe 100 UID ek saath bhejo, sab check hoga!

<b>Deep Research Features:</b>
├ ⚡ 7 Garena Endpoints Rotation
├ 🔄 Auto Retry System
├ 💾 5 Min Cache - Fast
├ ♾️ No User Cooldown
├ 🔥 Bulk UID Support
└ 👑 {OWNER} Special

<b>Use:</b>
<code>/id 12345678 87654321 12345679</code>
Ya ek-ek karke bhejo - No Limit!

Keyboard dabao!
"""
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=main_kb())

async def owner(update, context):
    kb = [[InlineKeyboardButton("📱 @just_zevric", url="https://t.me/just_zevric")]]
    await update.message.reply_text(f"👑 {OWNER} | ▶️ {YT}", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

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
    # Bulk support - kitne bhi UID ek saath
    results = []
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    # Scanning animation - ek baar
    await send_anim(update, random.choice(["bijli", "hacker"]), f"⚡ Scanning {len(uid_list)} UID...")

    status_msg = await update.message.reply_text(f"⚡ <b>Checking {len(uid_list)} UID... No Limit Mode ON ♾️</b>", parse_mode=ParseMode.HTML)

    for idx, uid in enumerate(uid_list):
        if not uid.isdigit():
            continue
        
        # Progress update - live jaise
        try:
            await status_msg.edit_text(f"⚡ <b>Checking {idx+1}/{len(uid_list)}: <code>{uid}</code></b>\n♾️ No Limit Mode", parse_mode=ParseMode.HTML)
        except:
            pass

        banned, period, src = get_ban_no_limit(uid)

        if banned is None:
            res_txt = f"⚠️ UID <code>{uid}</code> - Retry karo, Garena busy"
            results.append((uid, None))
        elif banned == 1:
            res_txt = f"🚫 <code>{uid}</code> - BANNED ({period if period else 'Perma'})"
            results.append((uid, 1))
        else:
            res_txt = f"✅ <code>{uid}</code> - NOT BANNED"
            results.append((uid, 0))

        # Har UID ke liye alag result nahi, ek saath final me bhejenge

    # Final bulk result
    final_lines = [f"<b>⚡⚡ NO LIMIT RESULTS ⚡⚡</b>\n"]
    banned_count = 0
    safe_count = 0
    for uid, st in results:
        if st == 1:
            final_lines.append(f"🚫 <code>{uid}</code> - <b>BANNED</b>")
            banned_count += 1
        elif st == 0:
            final_lines.append(f"✅ <code>{uid}</code> - <b>SAFE</b>")
            safe_count += 1
        else:
            final_lines.append(f"⚠️ <code>{uid}</code> - <b>Retry</b>")

    final_lines.append(f"\n<b>Total: {len(results)} | 🚫 {banned_count} | ✅ {safe_count}</b>")
    final_lines.append(f"\n👑 {OWNER} | ▶️ {YT} | ♾️ No Limit")

    final_text = "\n".join(final_lines)

    # Final animation based on results
    if banned_count > 0 and safe_count == 0:
        await send_anim(update, "banned", "🚫 Banned IDs Found")
    elif safe_count > 0 and banned_count == 0:
        await send_anim(update, "safe", "✅ All IDs Safe")
    else:
        await send_anim(update, "bijli", "⚡ Check Complete")

    kb = [[InlineKeyboardButton("⚡ Check Again", callback_data="again")]]
    await status_msg.edit_text(final_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

async def check_cmd(update, context):
    # Support: /id 123 456 789 bulk
    uids = []
    if context.args:
        for a in context.args:
            # split by comma, space
            for part in a.replace(",", " ").split():
                if part.strip().isdigit():
                    uids.append(part.strip())
    if not uids:
        await update.message.reply_text("UID bhejo: <code>/id 12345678 87654321</code>\nKitne bhi bhejo, No Limit!", parse_mode=ParseMode.HTML, reply_markup=main_kb())
        return
    await check_logic(update, context, uids)

async def text_handler(update, context):
    txt = update.message.text.strip()
    if txt == "⚡ Check Ban ⚡":
        await update.message.reply_text("Kitne bhi UID bhejo: <code>/id 123 456 789</code>\nNo Limit!", parse_mode=ParseMode.HTML, reply_markup=main_kb())
        return
    if txt == "👑 Owner":
        await owner(update, context)
        return
    if txt == "🔴 Banned Anim":
        await send_anim(update, "banned", "🔴 Banned")
        return
    if txt == "🟢 Safe Anim":
        await send_anim(update, "safe", "🟢 Safe")
        return
    if txt == "💻 Hacker Scan":
        await send_anim(update, "hacker", "💻 Hacker Scan")
        return
    if txt == "⚡ Bijli Scan":
        await send_anim(update, "bijli", "⚡ Bijli Scan")
        return
    if txt in ["ℹ️ Help", "🚀 Start", "▶️ YouTube"]:
        await start(update, context)
        return
    
    # Extract UIDs from any text - bulk support
    import re
    found = re.findall(r'\d{6,}', txt)
    if found:
        await check_logic(update, context, found)
    else:
        await update.message.reply_text("UID bhejo! Bulk bhi chalega: <code>12345678 87654321</code>", parse_mode=ParseMode.HTML, reply_markup=main_kb())

async def cb(update, context):
    q = update.callback_query
    await q.answer()
    if q.data == "again":
        await q.message.reply_text("Naye UID bhejo, kitne bhi: <code>/id 123 456 789</code>", parse_mode=ParseMode.HTML, reply_markup=main_kb())

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("owner", owner))
    app.add_handler(CommandHandler("id", check_cmd))
    app.add_handler(CommandHandler("check", check_cmd))
    app.add_handler(CommandHandler("ban", check_cmd))
    app.add_handler(CallbackQueryHandler(cb))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    print(f"NO LIMIT PRO Running - Owner {OWNER} - Bulk + No Cooldown")
    app.run_polling()

if __name__ == "__main__":
    main()
