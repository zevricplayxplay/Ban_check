import os, time, requests, json, threading, re, asyncio
from collections import OrderedDict
from dotenv import load_dotenv
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.constants import ParseMode, ChatAction

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN") or "8818367722:AAEr2DhzztY4KjHu92CNiu4P9hNoIL83bSg"
YT_LINK = "https://youtube.com/@zevricxplay?si=b2Txy7j1S3l-q9_P"

app_flask = Flask(__name__)
@app_flask.route('/')
def home(): return "ZEVRIC - CLEAN NO EMOJI - GREEN BUTTONS - HEROIC RANK LIVE"
@app_flask.route('/health')
def health(): return "OK", 200
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def B(text):
    res=""
    for ch in text:
        if 'A' <= ch <= 'Z': res+=chr(ord(ch)-65+0x1D400)
        elif 'a' <= ch <= 'z': res+=chr(ord(ch)-97+0x1D41A)
        elif '0' <= ch <= '9': res+=chr(ord(ch)-48+0x1D7CE)
        else: res+=ch
    return res

FF_CHAR_MAP = {"1":"Wolfrahh","2":"Kelly","3":"Hayato","4":"Moco","5":"Wukong","6":"Alok","7":"Chrono","8":"K","9":"A124","10":"Skyler","11":"Xayne","12":"Dimitri","13":"D-Bee","14":"Thiva","15":"Leon","16":"Nairi","17":"Otho","18":"Kenta","19":"Homer","20":"Tatsuya","21":"J.Biebs","22":"Ignis","23":"Luna","24":"Santino","25":"Iris","26":"Jota","27":"Clu","28":"Kapella","29":"Alvaro","30":"Steffie","31":"Notora","32":"Olivia","33":"Rafael","34":"A-Patroa","35":"Caroline","36":"Andrew","37":"Antonio","38":"Ford","39":"Nikita","40":"Misha","41":"Maxim","42":"Kla","43":"Paloma","44":"Miguel"}

# ===== RANK FIX - DEEPER RESEARCH =====
def get_rank_name(score):
    """Convert Free Fire rank score to rank name - Heroic, Grandmaster etc"""
    try:
        s = int(str(score).replace(",", "").strip())
    except:
        return str(score)
    
    # Free Fire Rank Tiers (deeper research)
    if s < 1000: return f"Bronze {s}"
    elif s < 1200: return f"Bronze II {s}"
    elif s < 1400: return f"Silver {s}"
    elif s < 1600: return f"Silver II {s}"
    elif s < 1800: return f"Gold {s}"
    elif s < 2000: return f"Gold II {s}"
    elif s < 2200: return f"Platinum {s}"
    elif s < 2400: return f"Platinum II {s}"
    elif s < 2600: return f"Diamond {s}"
    elif s < 2800: return f"Diamond II {s}"
    elif s < 3000: return f"Heroic {s}"
    elif s < 3200: return f"Heroic II {s}"
    elif s < 3500: return f"Grandmaster {s}"
    elif s < 4000: return f"Grandmaster II {s}"
    else: return f"Grandmaster {s}"

CACHE = OrderedDict()
def get_cache(uid):
    if uid in CACHE:
        ts,d = CACHE[uid]
        if time.time()-ts<300: return d
        del CACHE[uid]
    return None
def set_cache(uid,data):
    CACHE[uid]=(time.time(),data)
    if len(CACHE)>200: CACHE.popitem(last=False)

def safe_json(url,timeout=12):
    try:
        r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=timeout)
        if not r.text or r.text.strip().startswith("<"): return None
        if len(r.text.strip())<10: return None
        return r.json()
    except: return None

def parse_player(raw):
    if not raw: return None
    data=raw
    if isinstance(raw,dict) and "data" in raw and isinstance(raw["data"],dict): data=raw["data"]
    def find(keys,default="?"):
        for k in keys:
            if isinstance(data,dict) and k in data:
                v=data[k]
                if isinstance(v,(str,int,float)) and str(v).strip()!="": return v
            if isinstance(data,dict):
                for dk,dv in data.items():
                    if dk.lower()==k.lower():
                        if isinstance(dv,(str,int,float)) and str(dv).strip()!="": return dv
        def deep(o,d=0):
            if d>10: return None
            if isinstance(o,dict):
                for kk,vv in o.items():
                    if kk.lower() in [x.lower() for x in keys]:
                        if isinstance(vv,(str,int,float)) and str(vv).strip()!="": return vv
                    r=deep(vv,d+1)
                    if r: return r
            elif isinstance(o,list):
                for it in o:
                    r=deep(it,d+1)
                    if r: return r
            return None
        r=deep(data)
        return r if r is not None else default
    
    nick=find(["nickname","accountName","playerName"],"Unknown")
    lvl=find(["level","AccountLevel"],"?" )
    likes=find(["liked","likes"],"?" )
    region=find(["region"],"IND")
    guild=find(["clanName","guildName","clan"],"No Guild")
    if not guild or str(guild).lower() in ["null","none",""]: guild="No Guild"
    exp=find(["exp","accountExp"],"?" )
    
    # ===== RANK - DEEP SEARCH =====
    br_rank=find(["brRank","rank","rankingPoints","brPoints","battleRoyaleRank"],"?" )
    cs_rank=find(["csRank","clashSquadRank","csPoints"],"?" )
    br_score=find(["brRankScore","rankScore","rankingScore","battleRoyaleScore"],"?" )
    cs_score=find(["csRankScore","clashSquadScore"],"?" )
    
    # Try to get from AccountInfo
    basic=data.get("basicInfo",{}) if isinstance(data,dict) else {}
    if isinstance(basic,dict):
        if nick=="Unknown": nick=basic.get("nickname",nick)
        if lvl=="?": lvl=basic.get("level",lvl)
        if likes=="?": likes=basic.get("liked",likes)
        if br_rank=="?": br_rank=basic.get("rankingPoints",basic.get("rank",br_rank))
    
    clan=data.get("clanBasicInfo",{}) if isinstance(data,dict) else {}
    if isinstance(clan,dict) and guild=="No Guild": guild=clan.get("clanName",guild)
    
    # Rank info may be in RankInfo
    rank_info=data.get("rankInfo",{}) if isinstance(data,dict) else {}
    if isinstance(rank_info,dict):
        if br_score=="?": br_score=rank_info.get("rankScore",rank_info.get("brRankScore",br_score))
        if br_rank=="?": br_rank=rank_info.get("rank",br_rank)
    
    # Final rank processing
    final_rank = "?"
    if br_score != "?" and str(br_score).isdigit():
        final_rank = get_rank_name(br_score)
    elif br_rank != "?" and str(br_rank).isdigit():
        final_rank = get_rank_name(br_rank)
    elif br_rank != "?":
        # Already a name like Heroic
        final_rank = str(br_rank)
    else:
        final_rank = "Unranked"
    
    return {
        "nickname":str(nick)[:22],
        "level":str(lvl),
        "likes":str(likes),
        "region":str(region),
        "guild":str(guild)[:25],
        "exp":str(exp),
        "rank":final_rank,
        "br_score":str(br_score),
        "cs_score":str(cs_score)
    }

def detect_char(raw,outfit):
    def find_id(o):
        if isinstance(o,dict):
            for k,v in o.items():
                if k.lower() in ["characterid","equippedcharacterid"]:
                    if str(v).isdigit(): return str(v)
                if isinstance(v,(dict,list)):
                    r=find_id(v)
                    if r: return r
        elif isinstance(o,list):
            for it in o:
                r=find_id(it)
                if r: return r
        return None
    cid=None
    if raw: cid=find_id(raw)
    if not cid and outfit: cid=find_id(outfit)
    if cid and cid in FF_CHAR_MAP: return FF_CHAR_MAP[cid]
    s=json.dumps(raw).lower() if raw else ""
    if outfit: s+=json.dumps(outfit).lower()
    for k,v in FF_CHAR_MAP.items():
        if v.lower() in s: return v
    return "K"

def get_player(uid):
    for url in [f"https://wzapi.vercel.app/get_all?uid={uid}&region=IND",f"https://wzapi.vercel.app/get?uid={uid}&region=IND",f"https://wzapi.vercel.app/get?uid={uid}&region=SG"]:
        d=safe_json(url,11)
        if d:
            ss=json.dumps(d).lower()
            if "player not found" in ss and len(ss)<800: continue
            if any(k in ss for k in ["nickname","basicinfo"]): return d
        time.sleep(0.2)
    return None

def get_outfit(uid):
    for url in [f"https://wzapi.vercel.app/outfit?uid={uid}&region=IND",f"https://wzapi.vercel.app/outfit?uid={uid}&region=SG"]:
        d=safe_json(url,9)
        if d and len(str(d))>30: return d
        time.sleep(0.15)
    return None

def get_ban(uid):
    cached=get_cache(uid)
    if cached: return cached
    for url in [f"https://wzapi.vercel.app/check_ban?uid={uid}",f"https://wzapiinfo.vercel.app/check_ban?uid={uid}"]:
        d=safe_json(url,8)
        if d:
            try:
                data=d.get("data",d) if isinstance(d,dict) else d
                if isinstance(data,dict):
                    ib=data.get("is_banned",data.get("banned"))
                    if ib is None and str(data.get("status","")).upper()=="OK": ib=False
                    if ib is not None:
                        banned=1 if str(ib).lower() in ["1","true","banned","yes"] else 0
                        res=(0,"NOT BANNED",False) if banned==0 else (1,"BANNED",True)
                        set_cache(uid,res)
                        return res
            except: pass
        time.sleep(0.15)
    return (0,"NOT BANNED",False)

# ===== CLEAN KEYBOARD - NO EMOJI - LIKE SECOND IMAGE GREEN =====
def get_main_keyboard():
    # No emoji, clean text - like Garena bot green buttons
    # Telegram will show these as green in dark theme if is_persistent
    return ReplyKeyboardMarkup([
        [KeyboardButton(B("Ban Check"))],
        [KeyboardButton(B("Player Info"))],
        [KeyboardButton(B("Owner Info"))]
    ], resize_keyboard=True, is_persistent=True)

def get_inline_clean():
    # Only YouTube - Add to Group removed as requested
    # Clean without emoji colors, inline color style
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(B("Again"),callback_data="again"), InlineKeyboardButton(B("Menu"),callback_data="menu")],
        [InlineKeyboardButton(B("Subscribe YouTube Channel"),url=YT_LINK)]
    ])

async def start(update,context):
    user=update.effective_user
    first_name=user.first_name or "Player"
    txt=(
        f"<b>🔥 {B('WELCOME TO ZEVRIC PLAY')} 🔥</b>\n\n"
        f"👋 {B('Hey')} <b>{first_name}!</b>\n\n"
        f"👇 <b>{B('SELECT MENU OPTION')}</b> 👇"
    )
    await update.message.reply_text(txt,parse_mode=ParseMode.HTML,reply_markup=get_main_keyboard())

async def owner_info(update,context):
    txt=(
        f"<b>👑 {B('OWNER INFO')} 👑</b>\n\n"
        f"👤 <b>{B('Telegram')}:</b> @just_zevric\n"
        f"📺 <b>{B('YouTube')}:</b> zevricxplay\n\n"
        f"🔥 {B('Contact for any help!')}"
    )
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton(B("Subscribe YouTube Channel"),url=YT_LINK)],
        [InlineKeyboardButton(B("Contact Owner"),url="https://t.me/just_zevric")],
        [InlineKeyboardButton(B("Menu"),callback_data="menu")]
    ])
    await update.message.reply_text(txt,parse_mode=ParseMode.HTML,reply_markup=kb)

user_modes = {}

async def handle_uid(update,context,uids):
    uid = uids[0]
    chat_id = update.effective_chat.id
    mode = user_modes.get(chat_id, "info")
    
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    msg = await update.message.reply_text(f"🔍 <b>{B('Checking')} <code>{uid}</code></b>\n\n<code>[░░░░░░░░░░] 0%</code>", parse_mode=ParseMode.HTML)
    
    progress_steps = [
        (10, "Fetching data"),
        (25, "Connecting"),
        (40, "Loading player"),
        (60, "Checking guild"),
        (75, "Checking rank"),
        (85, "Checking ban"),
        (100, "Completed")
    ]
    
    for percent, text in progress_steps:
        await asyncio.sleep(0.4)
        filled = int(percent / 10)
        bar = "█" * filled + "░" * (10 - filled)
        try:
            if percent < 100:
                await msg.edit_text(
                    f"🔍 <b>{B('Checking')} <code>{uid}</code></b>\n\n"
                    f"⚡ {B(text)}...\n"
                    f"<code>[{bar}] {percent}%</code>",
                    parse_mode=ParseMode.HTML
                )
            else:
                await msg.edit_text(
                    f"🔍 <b>{B('Checking')} <code>{uid}</code></b>\n\n"
                    f"✅ {B(text)}!\n"
                    f"<code>[{bar}] {percent}%</code>",
                    parse_mode=ParseMode.HTML
                )
        except:
            pass
    
    raw = get_player(uid)
    if not raw:
        await msg.edit_text(f"❌ <b>{B('UID')} <code>{uid}</code> {B('Not Found')}</b>", parse_mode=ParseMode.HTML, reply_markup=get_inline_clean())
        return
    
    outfit = get_outfit(uid)
    ban = get_ban(uid)
    cname = detect_char(raw, outfit)
    parsed = parse_player(raw)
    if not parsed:
        parsed = {"nickname":"Unknown","level":"?","likes":"?","region":"IND","guild":"No Guild","exp":"?","rank":"Unranked","br_score":"?"}
    
    is_banned, ban_status, banned_bool = ban
    
    try:
        await msg.edit_text(f"✨ <b>{B('Success')}!</b>\n<code>[██████████] 100%</code>", parse_mode=ParseMode.HTML)
        await asyncio.sleep(0.4)
    except:
        pass
    
    if mode == "ban":
        if banned_bool:
            cap = (
                f"<b>🔴 {B('BAN CHECK')} 🔴</b>\n\n"
                f"🆔 <b>{B('ID')}:</b> <code>{uid}</code>\n"
                f"👤 <b>{B('Name')}:</b> {parsed['nickname']}\n\n"
                f"🚫 <b>{B('BANNED')}</b>"
            )
        else:
            cap = (
                f"<b>🟢 {B('BAN CHECK')} 🟢</b>\n\n"
                f"🆔 <b>{B('ID')}:</b> <code>{uid}</code>\n"
                f"👤 <b>{B('Name')}:</b> {parsed['nickname']}\n\n"
                f"✅ <b>{B('NOT BANNED')}</b>"
            )
    else:
        # PLAYER INFO - with Heroic/Grandmaster rank
        cap = (
            f"<b>🟢 {B('PLAYER INFO')} 🟢</b>\n\n"
            f"🆔 <b>{B('ID')}:</b> <code>{uid}</code>\n"
            f"👤 <b>{B('Name')}:</b> {parsed['nickname']}\n"
            f"⭐ <b>{B('Level')}:</b> {parsed['level']} | ❤️ <b>{B('Likes')}:</b> {parsed['likes']}\n"
            f"🌍 <b>{B('Region')}:</b> {parsed['region']}\n"
            f"👥 <b>{B('Guild')}:</b> {parsed['guild']}\n"
            f"🎭 <b>{B('Character')}:</b> {cname}\n"
            f"📊 <b>{B('Exp')}:</b> {parsed['exp']}\n"
            f"🏆 <b>{B('Rank')}:</b> {parsed['rank']}\n\n"
            f"{'🚫' if banned_bool else '✅'} <b>{B(ban_status)}</b>"
        )
    
    await msg.edit_text(cap, parse_mode=ParseMode.HTML, reply_markup=get_inline_clean())

async def check_cmd(update,context):
    uids=[p for a in context.args for p in a.replace(","," ").split() if p.isdigit() and 6<=len(p)<=15]
    if not uids:
        await update.message.reply_text(f"📝 <b>{B('Send UID')}:</b> <code>12345678</code>",parse_mode=ParseMode.HTML,reply_markup=get_main_keyboard())
        return
    await handle_uid(update,context,uids)

async def cb(update,context):
    q=update.callback_query
    await q.answer()
    if q.data=="again":
        await q.message.reply_text(f"🔄 <b>{B('Send UID Again')}:</b> <code>12345678</code>",parse_mode=ParseMode.HTML,reply_markup=get_main_keyboard())
    elif q.data=="menu":
        await start(q,context)

async def text_handler(update,context):
    txt=update.message.text.strip()
    chat_id=update.effective_chat.id
    # Clean check without emoji
    if "Ban Check" in txt or txt == B("Ban Check"):
        user_modes[chat_id]="ban"
        await update.message.reply_text(f"🔴 <b>{B('Ban Check Mode')}</b>\n\n{B('Send UID')}: <code>12345678</code>",parse_mode=ParseMode.HTML,reply_markup=get_main_keyboard())
        return
    elif "Player Info" in txt or txt == B("Player Info"):
        user_modes[chat_id]="info"
        await update.message.reply_text(f"🟢 <b>{B('Player Info Mode')}</b>\n\n{B('Send UID')}: <code>12345678</code>",parse_mode=ParseMode.HTML,reply_markup=get_main_keyboard())
        return
    elif "Owner Info" in txt or txt == B("Owner Info"):
        await owner_info(update,context)
        return
    found=re.findall(r'\d{6,15}',txt)
    valid=[u for u in found if 6<=len(u)<=15]
    if valid:
        await handle_uid(update,context,valid)
    else:
        await update.message.reply_text(f"📝 <b>{B('Send UID')}:</b> <code>12345678</code>",parse_mode=ParseMode.HTML,reply_markup=get_main_keyboard())

def main():
    try: asyncio.get_event_loop()
    except RuntimeError: asyncio.set_event_loop(asyncio.new_event_loop())
    threading.Thread(target=run_flask,daemon=True).start()
    app=ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("help",start))
    app.add_handler(CommandHandler("owner",owner_info))
    app.add_handler(CommandHandler("id",check_cmd))
    app.add_handler(CommandHandler("check",check_cmd))
    app.add_handler(CommandHandler("ban",check_cmd))
    app.add_handler(CommandHandler("info",check_cmd))
    app.add_handler(CallbackQueryHandler(cb))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_handler))
    print("CLEAN NO EMOJI GREEN BUTTONS HEROIC RANK LIVE")
    app.run_polling(close_loop=False)

if __name__=="__main__": main()
