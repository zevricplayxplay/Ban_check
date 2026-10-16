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
def home(): return "ZEVRIC - ONLY RANK NAME HEROIC GRANDMASTER BRONZE - LIVE"
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

FF_CHAR_MAP = {
    "1":"Wolfrahh","2":"Kelly","3":"Hayato","4":"Moco","5":"Wukong","6":"Alok","7":"Chrono",
    "8":"K","9":"A124","10":"Skyler","11":"Xayne","12":"Dimitri","13":"D-Bee","14":"Thiva",
    "15":"Leon","16":"Nairi","17":"Otho","18":"Kenta","19":"Homer","20":"Tatsuya","21":"J.Biebs",
    "22":"Ignis","23":"Luna","24":"Santino","25":"Iris","26":"Jota","27":"Clu","28":"Kapella",
    "29":"Alvaro","30":"Steffie","31":"Notora","32":"Olivia","33":"Rafael","34":"A-Patroa",
    "35":"Caroline","36":"Andrew","37":"Antonio","38":"Ford","39":"Nikita","40":"Misha",
    "41":"Maxim","42":"Kla","43":"Paloma","44":"Miguel"
}

# ===== FREE FIRE ALL RANKS - INTERNATIONAL STANDARD =====
# User wants ONLY name like BRONZE, HEROIC, GRANDMASTER - NO numbers
def get_rank_name_only(score):
    """Return ONLY rank name like BRONZE, HEROIC, GRANDMASTER - NO score"""
    try:
        s = int(str(score).replace(",", "").strip().split()[0])
        if s > 100000:  # This is exp not rank
            return None
        # Free Fire BR Ranks - Main tiers only (as user wants)
        if s < 1300:
            return "BRONZE"
        elif s < 1500:
            return "SILVER"
        elif s < 1700:
            return "GOLD"
        elif s < 2000:
            return "PLATINUM"
        elif s < 2300:
            return "DIAMOND"
        elif s < 3000:
            return "HEROIC"
        else:
            return "GRANDMASTER"
    except:
        return None

# CS Ranks also
def get_cs_rank_name_only(score):
    try:
        s = int(str(score).replace(",", "").strip().split()[0])
        if s > 100000:
            return None
        if s < 1300:
            return "BRONZE"
        elif s < 1500:
            return "SILVER"
        elif s < 1700:
            return "GOLD"
        elif s < 2000:
            return "PLATINUM"
        elif s < 2300:
            return "DIAMOND"
        elif s < 2600:
            return "MASTER"
        else:
            return "GRANDMASTER"
    except:
        return None

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

def safe_json(url,timeout=10):
    try:
        headers = {"User-Agent":"Mozilla/5.0","Accept":"application/json"}
        r=requests.get(url,headers=headers,timeout=timeout)
        if not r.text or r.text.strip().startswith("<"): return None
        if len(r.text.strip())<15: return None
        try: return r.json()
        except:
            txt=r.text
            start=txt.find('{'); end=txt.rfind('}')+1
            if start>=0 and end>start: return json.loads(txt[start:end])
            return None
    except: return None

def get_player_international(uid):
    apis = [
        f"https://wzapi.vercel.app/get_all?uid={uid}&region=IND",
        f"https://wzapiinfo.vercel.app/get_all?uid={uid}&region=IND",
        f"https://free-fire-api.vercel.app/api/info?uid={uid}&region=ind",
        f"https://ff-info-api.vercel.app/api/account?uid={uid}",
        f"https://api-ff-bd.vercel.app/api/info?uid={uid}&region=ind",
    ]
    best_data=None
    for url in apis:
        try:
            d=safe_json(url,8)
            if d:
                ss=json.dumps(d).lower()
                if "player not found" in ss and len(ss)<1000: continue
                if any(k in ss for k in ["nickname","basicinfo"]):
                    score=len(ss)
                    if "clan" in ss: score+=500
                    if "rank" in ss: score+=500
                    if best_data is None or score>best_data[0]:
                        best_data=(score,d,url)
            time.sleep(0.2)
        except: continue
    if best_data: return best_data[1]
    for url in [f"https://wzapi.vercel.app/get?uid={uid}&region=IND",f"https://wzapi.vercel.app/get?uid={uid}&region=SG"]:
        d=safe_json(url,8)
        if d and "nickname" in json.dumps(d).lower(): return d
    return None

def parse_player_deep(raw):
    if not raw: return None
    data=raw
    if isinstance(raw,dict) and "data" in raw and isinstance(raw["data"],dict): data=raw["data"]
    
    def deep_find(keys,default="?"):
        keys_lower=[k.lower() for k in keys]
        if isinstance(data,dict):
            for k in keys:
                if k in data and data[k] not in [None,"","null"]:
                    v=data[k]
                    if isinstance(v,(str,int,float)) and str(v).strip()!="": return v
            for dk,dv in data.items():
                if dk.lower() in keys_lower:
                    if isinstance(dv,(str,int,float)) and str(dv).strip()!="": return dv
        def search_obj(obj,depth=0):
            if depth>10: return None
            if isinstance(obj,dict):
                for kk,vv in obj.items():
                    if kk.lower() in keys_lower:
                        if isinstance(vv,(str,int,float)) and str(vv).strip()!="": return vv
                    r=search_obj(vv,depth+1)
                    if r: return r
            elif isinstance(obj,list):
                for it in obj:
                    r=search_obj(it,depth+1)
                    if r: return r
            return None
        r=search_obj(data)
        if r: return r
        return default
    
    nick=deep_find(["nickname","accountName","playerName","name"],"Unknown")
    lvl=deep_find(["level","AccountLevel"],"?" )
    likes=deep_find(["liked","likes"],"?" )
    region=deep_find(["region","server"],"IND")
    
    # Guild
    guild="No Guild"
    guild_sources=[
        data.get("clanBasicInfo",{}).get("clanName") if isinstance(data.get("clanBasicInfo"),dict) else None,
        data.get("clanInfo",{}).get("clanName") if isinstance(data.get("clanInfo"),dict) else None,
        deep_find(["clanName","guildName"],None),
    ]
    for g in guild_sources:
        if g and str(g).strip() and str(g).lower() not in ["null","none",""]: guild=str(g)[:25]; break
    
    # Rank - try to find actual rank name first
    rank_name=None
    # 1. Try direct rank name like "Heroic", "Grandmaster"
    direct = deep_find(["rankName","tier","currentRank","brRankName","csRankName"],None)
    if direct and isinstance(direct,str) and len(direct)<20:
        dl=direct.lower()
        if any(x in dl for x in ["bronze","silver","gold","platinum","diamond","heroic","grandmaster","master"]):
            rank_name=direct.upper()
    
    # 2. Try score to name
    if not rank_name:
        rank_score=None
        rank_data=data.get("rankInfo",data.get("rankingInfo",{})) if isinstance(data,dict) else {}
        if isinstance(rank_data,dict):
            for k in ["rankScore","brRankScore","rankingPoints","points","score"]:
                if k in rank_data and str(rank_data[k]).isdigit():
                    v=int(str(rank_data[k]))
                    if 0<v<10000: rank_score=v; break
        if rank_score is None:
            basic=data.get("basicInfo",{}) if isinstance(data,dict) else {}
            if isinstance(basic,dict):
                for k in ["rank","rankingPoints","rankScore"]:
                    if k in basic and str(basic[k]).isdigit():
                        v=int(str(basic[k]))
                        if 0<v<10000: rank_score=v; break
        # Deep search for any rank score
        if rank_score is None:
            candidates=[]
            def find_ranks(obj,depth=0):
                if depth>8: return
                if isinstance(obj,dict):
                    for kk,vv in obj.items():
                        kkl=kk.lower()
                        if ("rank" in kkl or "tier" in kkl) and isinstance(vv,(int,str)):
                            vs=str(vv)
                            if vs.isdigit():
                                vi=int(vs)
                                if 100<vi<10000: candidates.append((kk,vi))
                        find_ranks(vv,depth+1)
                elif isinstance(obj,list):
                    for it in obj: find_ranks(it,depth+1)
            find_ranks(data)
            for name,score in candidates:
                if "score" in name.lower() or "points" in name.lower():
                    rank_score=score; break
            if rank_score is None and candidates:
                valid=[c for c in candidates if 100<c[1]<5000]
                if valid: rank_score=max(valid,key=lambda x:x[1])[1]
        
        if rank_score is not None:
            rn=get_rank_name_only(rank_score)
            if rn: rank_name=rn
    
    if not rank_name: rank_name="UNRANKED"
    
    return {
        "nickname":str(nick)[:22],
        "level":str(lvl),
        "likes":str(likes),
        "region":str(region),
        "guild":str(guild)[:25],
        "rank":str(rank_name),  # ONLY name like HEROIC, GRANDMASTER
    }

def detect_char_deep(raw,outfit):
    def find_char_id(obj,depth=0):
        if depth>10: return None
        if isinstance(obj,dict):
            for k,v in obj.items():
                kl=k.lower()
                if kl in ["characterid","equippedcharacterid","avatarid","character"]:
                    if isinstance(v,(int,str)):
                        vs=str(v)
                        if vs.isdigit() and 1<=int(vs)<=60: return vs
                    if isinstance(v,dict):
                        for subk in ["id","characterId"]:
                            if subk in v and str(v[subk]).isdigit(): return str(v[subk])
                r=find_char_id(v,depth+1)
                if r: return r
        elif isinstance(obj,list):
            for it in obj:
                r=find_char_id(it,depth+1)
                if r: return r
        return None
    cid=None
    if raw: cid=find_char_id(raw)
    if not cid and outfit: cid=find_char_id(outfit)
    if cid and cid in FF_CHAR_MAP: return FF_CHAR_MAP[cid]
    return "K"

def get_player(uid): return get_player_international(uid)
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

def get_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton(B("Ban Check"))],
        [KeyboardButton(B("Player Info"))],
        [KeyboardButton(B("Owner Info"))]
    ],resize_keyboard=True,is_persistent=True)

def get_inline_clean():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(B("Again"),callback_data="again"),InlineKeyboardButton(B("Menu"),callback_data="menu")],
        [InlineKeyboardButton(B("Subscribe YouTube Channel"),url=YT_LINK)]
    ])

async def start(update,context):
    user=update.effective_user
    first_name=user.first_name or "Player"
    txt=f"<b>🔥 {B('WELCOME TO ZEVRIC PLAY')} 🔥</b>\n\n👋 {B('Hey')} <b>{first_name}!</b>\n\n👇 <b>{B('SELECT MENU OPTION')}</b> 👇"
    await update.message.reply_text(txt,parse_mode=ParseMode.HTML,reply_markup=get_main_keyboard())

async def owner_info(update,context):
    txt=f"<b>👑 {B('OWNER INFO')} 👑</b>\n\n👤 <b>{B('Telegram')}:</b> @just_zevric\n📺 <b>{B('YouTube')}:</b> zevricxplay\n\n🔥 {B('Contact for any help!')}"
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton(B("Subscribe YouTube Channel"),url=YT_LINK)],
        [InlineKeyboardButton(B("Contact Owner"),url="https://t.me/just_zevric")],
        [InlineKeyboardButton(B("Menu"),callback_data="menu")]
    ])
    await update.message.reply_text(txt,parse_mode=ParseMode.HTML,reply_markup=kb)

user_modes={}
async def handle_uid(update,context,uids):
    uid=uids[0]; chat_id=update.effective_chat.id; mode=user_modes.get(chat_id,"info")
    await context.bot.send_chat_action(chat_id=chat_id,action=ChatAction.TYPING)
    msg=await update.message.reply_text(f"🔍 <b>{B('Checking')} <code>{uid}</code></b>\n\n<code>[░░░░░░░░░░] 0%</code>",parse_mode=ParseMode.HTML)
    steps=[(20,"Fetching"),(45,"Loading player"),(70,"Checking guild"),(85,"Checking rank"),(100,"Completed")]
    for percent,text in steps:
        await asyncio.sleep(0.4)
        bar="█"*int(percent/10)+"░"*(10-int(percent/10))
        try:
            await msg.edit_text(f"🔍 <b>{B('Checking')} <code>{uid}</code></b>\n\n⚡ {B(text)}...\n<code>[{bar}] {percent}%</code>",parse_mode=ParseMode.HTML)
        except: pass
    raw=get_player(uid)
    if not raw:
        await msg.edit_text(f"❌ <b>{B('UID')} <code>{uid}</code> {B('Not Found')}</b>",parse_mode=ParseMode.HTML,reply_markup=get_inline_clean())
        return
    outfit=get_outfit(uid); ban=get_ban(uid); cname=detect_char_deep(raw,outfit); parsed=parse_player_deep(raw)
    if not parsed: parsed={"nickname":"Unknown","level":"?","likes":"?","region":"IND","guild":"No Guild","rank":"UNRANKED"}
    is_banned,ban_status,banned_bool=ban
    try:
        await msg.edit_text(f"✨ <b>{B('Success')}!</b>\n<code>[██████████] 100%</code>",parse_mode=ParseMode.HTML)
        await asyncio.sleep(0.3)
    except: pass
    if mode=="ban":
        cap=f"<b>🔴 {B('BAN CHECK')} 🔴</b>\n\n🆔 <b>{B('ID')}:</b> <code>{uid}</code>\n👤 <b>{B('Name')}:</b> {parsed['nickname']}\n👥 <b>{B('Guild')}:</b> {parsed['guild']}\n\n{'🚫' if banned_bool else '✅'} <b>{B(ban_status)}</b>"
    else:
        cap=f"<b>🟢 {B('PLAYER INFO')} 🟢</b>\n\n🆔 <b>{B('ID')}:</b> <code>{uid}</code>\n👤 <b>{B('Name')}:</b> {parsed['nickname']}\n⭐ <b>{B('Level')}:</b> {parsed['level']} | ❤️ <b>{B('Likes')}:</b> {parsed['likes']}\n🌍 <b>{B('Region')}:</b> {parsed['region']}\n👥 <b>{B('Guild')}:</b> {parsed['guild']}\n🎭 <b>{B('Character')}:</b> {cname}\n🏆 <b>{B('Rank')}:</b> {parsed['rank']}\n\n{'🚫' if banned_bool else '✅'} <b>{B(ban_status)}</b>"
    await msg.edit_text(cap,parse_mode=ParseMode.HTML,reply_markup=get_inline_clean())

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
    txt=update.message.text.strip(); chat_id=update.effective_chat.id
    if "Ban Check" in txt or txt==B("Ban Check"):
        user_modes[chat_id]="ban"
        await update.message.reply_text(f"🔴 <b>{B('Ban Check Mode')}</b>\n\n{B('Send UID')}: <code>12345678</code>",parse_mode=ParseMode.HTML,reply_markup=get_main_keyboard())
        return
    elif "Player Info" in txt or txt==B("Player Info"):
        user_modes[chat_id]="info"
        await update.message.reply_text(f"🟢 <b>{B('Player Info Mode')}</b>\n\n{B('Send UID')}: <code>12345678</code>",parse_mode=ParseMode.HTML,reply_markup=get_main_keyboard())
        return
    elif "Owner Info" in txt or txt==B("Owner Info"):
        await owner_info(update,context)
        return
    found=re.findall(r'\d{6,15}',txt); valid=[u for u in found if 6<=len(u)<=15]
    if valid: await handle_uid(update,context,valid)
    else: await update.message.reply_text(f"📝 <b>{B('Send UID')}:</b> <code>12345678</code>",parse_mode=ParseMode.HTML,reply_markup=get_main_keyboard())

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
    print("ONLY RANK NAME - HEROIC GRANDMASTER BRONZE - NO NUMBERS")
    app.run_polling(close_loop=False)

if __name__=="__main__": main()
