import os, time, asyncio, requests, threading, re, json
from collections import OrderedDict
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.constants import ParseMode, ChatAction

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN") or "8818367722:AAEr2DhzztY4KjHu92CNiu4P9hNoIL83bSg"
OWNER = "@just_zevric"
YT_LINK = "https://youtube.com/@zevricxplay?si=b2Txy7j1S3l-q9_P"

app_flask = Flask(__name__)
@app_flask.route('/')
def home(): return "LIVE"
@app_flask.route('/health')
def health(): return "OK", 200
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

CACHE = OrderedDict()
def get_cache(uid):
    if uid in CACHE:
        ts, data = CACHE[uid]
        if time.time() - ts < 300: return data
        del CACHE[uid]
    return None
def set_cache(uid, data):
    CACHE[uid] = (time.time(), data)
    if len(CACHE) > 200: CACHE.popitem(last=False)

def safe_json(url, timeout=13):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
        if not r.text or r.text.strip().startswith("<"): return None
        if len(r.text.strip()) < 5: return None
        return r.json()
    except: return None

def deep_find(obj, keys, max_depth=10, _depth=0):
    if _depth > max_depth: return None
    low = [k.lower() for k in keys]
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in low:
                if isinstance(v, (str,int,float)) and str(v).strip() != "": return v
        for v in obj.values():
            res = deep_find(v, keys, max_depth, _depth+1)
            if res: return res
    elif isinstance(obj, list):
        for item in obj:
            res = deep_find(item, keys, max_depth, _depth+1)
            if res: return res
    return None

def deep_find_all(obj, results=None, _depth=0):
    if results is None: results = []
    if _depth > 10: return results
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in ["name","itemname","displayname"]:
                if isinstance(v, str) and 2 < len(v) < 60:
                    if v.lower() not in ["ind","sg","bd","pk","no guild","unknown"]: results.append(v)
        for vv in obj.values(): deep_find_all(vv, results, _depth+1)
    elif isinstance(obj, list):
        for it in obj: deep_find_all(it, results, _depth+1)
    return results

FF_CHARS = {"1":"Wolfrahh","2":"Kelly","3":"Hayato","4":"Moco","5":"Wukong","6":"Alok","7":"Chrono","8":"K","9":"A124","10":"Skyler","11":"Xayne","12":"Dimitri","13":"D-Bee","14":"Thiva","15":"Leon","16":"Nairi","17":"Otho","18":"Kenta","19":"Homer","20":"Tatsuya","21":"J.Biebs","22":"Ignis","23":"Luna","24":"Santino","25":"Iris","26":"Jota","27":"Clu","28":"Kapella","29":"Alvaro","30":"Steffie","31":"Notora","32":"Olivia","33":"Rafael","34":"A-Patroa","35":"Caroline","36":"Andrew","37":"Antonio","38":"Ford","39":"Nikita","40":"Misha","41":"Maxim","42":"Kla","43":"Paloma","44":"Miguel"}

def detect_char(raw, outfit):
    cid = deep_find(raw, ["characterId","CharacterId","equippedCharacterId"])
    cname = deep_find(raw, ["characterName","CharacterName","equippedCharacter"])
    if not cid and outfit:
        cid = deep_find(outfit, ["characterId","CharacterId"])
        if not cname: cname = deep_find(outfit, ["characterName"])
    if cid:
        s = str(cid)
        if s in FF_CHARS: return FF_CHARS[s], s
        return f"Char {s}", s
    if cname:
        name = str(cname).strip()
        for k,v in FF_CHARS.items():
            if v.lower() in name.lower(): return v, k
        return name, "?"
    raw_str = json.dumps(raw).lower() if raw else ""
    if outfit: raw_str += json.dumps(outfit).lower()
    for k,v in FF_CHARS.items():
        if v.lower() in raw_str: return v, k
    return "Default", "?"

def get_player(uid):
    for url in [
        f"https://wzapi.vercel.app/get_all?uid={uid}&region=IND",
        f"https://wzapi.vercel.app/get?uid={uid}&region=IND",
        f"https://wzapi.vercel.app/get?uid={uid}&region=SG",
    ]:
        d = safe_json(url, 13)
        if d and any(k in json.dumps(d).lower() for k in ["nickname","basicinfo"]):
            if "player not found" not in json.dumps(d).lower() or len(json.dumps(d))>500:
                return d
        time.sleep(0.25)
    return None

def get_outfit(uid):
    for url in [
        f"https://wzapi.vercel.app/outfit?uid={uid}&region=IND",
        f"https://wzapi.vercel.app/outfit?uid={uid}&region=SG",
    ]:
        d = safe_json(url, 11)
        if d and len(str(d))>20: return d
        time.sleep(0.2)
    return None

def get_ban_timer(uid):
    cached = get_cache(uid)
    if cached: return cached
    for url in [f"https://wzapi.vercel.app/check_ban?uid={uid}", f"https://wzapiinfo.vercel.app/check_ban?uid={uid}"]:
        d = safe_json(url, 10)
        if d:
            try:
                data = d.get("data", d) if isinstance(d, dict) else d
                if isinstance(data, dict):
                    is_banned = data.get("is_banned", data.get("banned", data.get("isBanned")))
                    period = data.get("period", data.get("ban_period", data.get("duration", 0)))
                    if is_banned is None and str(data.get("status","")).upper()=="OK": is_banned=False
                    if is_banned is not None:
                        banned = 1 if str(is_banned).lower() in ["1","true","banned","yes"] else 0
                        status_text=""; timer_text=""; expire_str=""
                        if banned==0:
                            status_text="SAFE - NOT BANNED"
                            timer_text="No Ban"
                        else:
                            try:
                                p=int(str(period)) if period else 0
                                if p==0 or p>=9999 or p>3650:
                                    status_text="PERMANENT BANNED"
                                    timer_text="Permanent - Never Expires"
                                    expire_str="Never"
                                else:
                                    now=datetime.now()
                                    exp=now+timedelta(days=p)
                                    expire_str=exp.strftime("%d %b %Y, %I:%M %p")
                                    hours=p*24
                                    minutes=hours*60
                                    if p>=30:
                                        m=p//30; rd=p%30
                                        if rd>0:
                                            status_text=f"TEMPORARY BANNED - {m}M {rd}D"
                                            timer_text=f"{p} Days ({m}M {rd}D) | {hours} Hours"
                                        else:
                                            status_text=f"TEMPORARY BANNED - {m} MONTHS"
                                            timer_text=f"{p} Days | {hours} Hours"
                                    else:
                                        status_text=f"TEMPORARY BANNED - {p} DAYS"
                                        timer_text=f"{p} Days | {hours} Hours | {minutes} Min"
                            except:
                                ps=str(period).lower()
                                if "permanent" in ps or "perm" in ps:
                                    status_text="PERMANENT BANNED"
                                    timer_text="Permanent"
                                    expire_str="Never"
                                elif ps and ps!="0":
                                    status_text=f"TEMPORARY BANNED - {period}"
                                    timer_text=f"Duration: {period}"
                                else:
                                    status_text="BANNED"
                                    timer_text="Unknown"
                        res=(banned,period,status_text,timer_text,expire_str)
                        set_cache(uid,res)
                        return res
            except: pass
        time.sleep(0.2)
    try:
        r=requests.get(f"https://ff.garena.com/api/antihack/check_banned?lang=en&uid={uid}", headers={"Referer":"https://ff.garena.com/"}, timeout=6)
        if r.text.strip().startswith("{"):
            j=r.json(); d=j.get("data",j); ib=d.get("is_banned"); period=d.get("period",0)
            if ib is not None:
                banned=1 if str(ib)=="1" else 0
                if banned==0:
                    res=(banned,period,"SAFE - NOT BANNED","No Ban","-")
                else:
                    try:
                        p=int(period)
                        if p==0 or p>3650:
                            res=(banned,period,"PERMANENT BANNED","Permanent","Never")
                        else:
                            now=datetime.now(); exp=now+timedelta(days=p); exp_str=exp.strftime("%d %b %Y")
                            res=(banned,period,f"TEMPORARY BANNED - {p} DAYS",f"{p} Days | Exp: {exp_str}",exp_str)
                    except:
                        res=(banned,period,"BANNED","Unknown","Unknown")
                set_cache(uid,res)
                return res
    except: pass
    return None

def gen_image(player, items, char, template="character_template.jpg"):
    if not HAS_PIL: return None
    base=template
    if not os.path.exists(base):
        for p in ["character_template.jpg","/mnt/data/render-24x7-bot/character_template.jpg"]:
            if os.path.exists(p): base=p; break
    try:
        if os.path.exists(base):
            img = Image.open(base).convert("RGB")
            W,H = img.size
        else:
            W,H = 900,1200
            img = Image.new('RGB',(W,H),(12,6,32))
        draw = ImageDraw.Draw(img,'RGBA')
        try:
            f1 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",22)
            f2 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",16)
            f3 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",13)
        except:
            f1=f2=f3=ImageFont.load_default()
        draw.rectangle([0,0,W,95], fill=(0,0,0,210))
        draw.text((15,10), f"{player['uid']} | {player['name']} | Lv:{player['level']} | {player['likes']} Likes", fill=(0,255,255), font=f2)
        draw.text((15,34), f"{player['region']} | {player['guild'][:18]} | Pet:{player['pet']}", fill=(255,255,0), font=f3)
        draw.rectangle([0,72,W,95], fill=(120,0,220,170))
        draw.text((W//2-130,76), f"{char[0]} | {player['ban_status'][:22]}", fill=(255,255,255), font=f2)
        cx,cy=W//2,H//2+40
        pos=[(cx-200,cy-180),(cx-280,cy-80),(cx-240,cy+40),(cx-180,cy+160),(cx+200,cy-180),(cx+280,cy-80),(cx+240,cy+40),(cx+180,cy+160)]
        if items:
            for i,(hx,hy) in enumerate(pos):
                if i < len(items):
                    name=items[i][:15]
                    tw=len(name)*6
                    draw.rectangle([hx-tw//2-4, hy+34, hx+tw//2+4, hy+48], fill=(0,0,0,190))
                    draw.text((hx-tw//2, hy+35), name, fill=(255,255,255), font=f3)
        draw.rectangle([0,H-40,W,H], fill=(0,0,0,220))
        draw.text((W//2-90,H-28), f"@just_zevric | zevricxplay", fill=(0,255,255), font=f2)
        return img
    except Exception as e:
        print(f"Image error: {e}")
        return None

def menu():
    # COLOR BUTTONS - Telegram new update inline color style
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔴 1. Ban Check", callback_data="ban")],
        [InlineKeyboardButton("🟢 2. Player Info", callback_data="info")],
        [InlineKeyboardButton("👑 3. Owner Info", callback_data="owner")]
    ])

def again():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔴 1. Ban Check", callback_data="ban")],
        [InlineKeyboardButton("🟢 2. Player Info", callback_data="info")],
        [InlineKeyboardButton("👑 3. Owner Info", callback_data="owner")],
        [InlineKeyboardButton("▶️ YouTube", url=YT_LINK)]
    ])

async def start(update, context):
    txt = "<b>ZEVRIC PLAY</b>\n\n🔴 1. Ban Check\n🟢 2. Player Info\n👑 3. Owner Info\n\nExample: <code>12345678</code>"
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=menu())

async def owner_info(update, context):
    txt = f"<b>👑 3. Owner Info</b>\n\n{OWNER}\nzevricxplay"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ YouTube Channel", url=YT_LINK)],
        [InlineKeyboardButton("💬 @just_zevric", url="https://t.me/just_zevric")],
        [InlineKeyboardButton("🔙 Menu", callback_data="main")]
    ])
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

async def handle_uid(update, context, uid_list, mode):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    status = await update.message.reply_text(f"Checking <code>{uid_list[0]}</code>...", parse_mode=ParseMode.HTML)
    for uid in uid_list[:2]:
        raw = get_player(uid)
        if not raw:
            await status.edit_text(f"UID <code>{uid}</code> busy, retry", parse_mode=ParseMode.HTML, reply_markup=menu())
            continue
        outfit = get_outfit(uid)
        ban_data = get_ban_timer(uid)
        cname,cid = detect_char(raw, outfit)
        name = deep_find(raw, ["nickname","AccountName"]) or "Unknown"
        level = deep_find(raw, ["level","AccountLevel"]) or "?"
        likes = deep_find(raw, ["liked","likes"]) or "?"
        region = deep_find(raw, ["region"]) or "?"
        guild = deep_find(raw, ["clanName","guildName"]) or "No Guild"
        pet = deep_find(raw, ["petName","PetName","equippedPet"]) or (deep_find(outfit, ["petName"]) if outfit else None) or "?"
        items = deep_find_all(outfit) if outfit else []
        seen=set(); uniq=[]
        for it in items:
            if it not in seen and it.lower()!=cname.lower() and len(it)>2:
                seen.add(it); uniq.append(it)
        items=uniq[:8]
        ban_status="SAFE"; timer_text="No Ban"; expire_str="-"; is_banned=0; period=0
        if ban_data:
            is_banned, period, ban_status, timer_text, expire_str = ban_data
        else:
            ban_status="SAFE - NOT BANNED"
        player={"uid":uid,"name":str(name),"level":str(level),"likes":str(likes),"region":str(region),"guild":str(guild),"pet":str(pet) if pet else "?","ban_status":ban_status,"timer":timer_text,"expire":expire_str}
        img = gen_image(player, items, (cname,cid)) if HAS_PIL else None
        if mode=="ban":
            if is_banned==0:
                cap=f"<b>🔴 1. Ban Check</b>\n\n<code>{uid}</code>\n{name}\n\n🟢 {ban_status}\nTimer: {timer_text}"
            else:
                if "PERMANENT" in ban_status:
                    cap=f"<b>🔴 1. Ban Check</b>\n\n<code>{uid}</code>\n{name}\n\n🔴 {ban_status}\nTimer: {timer_text}\nExpire: Never\n\nPermanent Ban"
                else:
                    cap=f"<b>🔴 1. Ban Check</b>\n\n<code>{uid}</code>\n{name}\n\n🔴 {ban_status}\nTimer: {timer_text}\nExpire: {expire_str}"
        else:
            cap=f"<b>🟢 2. Player Info</b>\n<code>{uid}</code> | {name}\nLv:{level} | {likes} Likes | {region}\n{guild[:15]} | Char:{cname} | Pet:{pet}\n\n"
            if items:
                for it in items[:7]: cap+=f"├ {it}\n"
            cap+=f"\n<b>Ban:</b> {ban_status}\nTimer: {timer_text}\nExpire: {expire_str}"
        try:
            if img:
                path=f"/tmp/ff_{uid}.jpg"
                img.save(path,"JPEG",quality=90)
                with open(path,'rb') as f:
                    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=f, caption=cap, parse_mode=ParseMode.HTML, reply_markup=again())
                await status.delete()
            else:
                await status.edit_text(cap, parse_mode=ParseMode.HTML, reply_markup=again())
        except Exception as e:
            await status.edit_text(f"{cap}\n\n{str(e)[:60]}", parse_mode=ParseMode.HTML, reply_markup=again())

async def check_cmd(update, context):
    uids=[p for a in context.args for p in a.replace(","," ").split() if p.isdigit() and 6<=len(p)<=15]
    if not uids:
        await update.message.reply_text("<code>12345678</code>", parse_mode=ParseMode.HTML, reply_markup=menu())
        return
    await handle_uid(update, context, uids, mode="info")

async def text_handler(update, context):
    found=re.findall(r'\d{6,15}', update.message.text.strip())
    valid=[u for u in found if 6<=len(u)<=15]
    if valid: await handle_uid(update, context, valid, mode="info")
    else: await update.message.reply_text("<code>12345678</code>", parse_mode=ParseMode.HTML, reply_markup=menu())

async def cb(update, context):
    q=update.callback_query
    await q.answer()
    d=q.data
    if d=="ban": await q.message.reply_text("Ban Check Ke Liye UID Bhejo:\n<code>12345678</code>", parse_mode=ParseMode.HTML, reply_markup=menu())
    elif d=="info": await q.message.reply_text("Player Info Ke Liye UID Bhejo:\n<code>12345678</code>", parse_mode=ParseMode.HTML, reply_markup=menu())
    elif d=="owner": await owner_info(q, context)
    elif d=="main": await start(q, context)
    elif d=="again": await q.message.reply_text("<code>12345678</code>", parse_mode=ParseMode.HTML, reply_markup=menu())

def main():
    try: asyncio.get_event_loop()
    except RuntimeError: asyncio.set_event_loop(asyncio.new_event_loop())
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
    print(f"FINAL COLOR - 3 Options with Color - PIL:{HAS_PIL}")
    app.run_polling(close_loop=False)

if __name__ == "__main__": main()
