import os, time, asyncio, requests, threading, re, json, math
from collections import OrderedDict
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
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

def deep_find(obj, keys, max_depth=12, _depth=0):
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

def deep_find_all_equipment(obj):
    """Deep research - extract all equipment/dress/weapon names from any API structure"""
    results = []
    def recurse(o, depth=0):
        if depth > 12: return
        if isinstance(o, dict):
            # Look for common equipment keys
            for k, v in o.items():
                kl = k.lower()
                # Direct name fields that are likely equipment
                if kl in ["name","itemname","displayname","item_name","clothes_name","outfitname","weaponname","petname","charactername"]:
                    if isinstance(v, str) and 2 < len(v) < 60:
                        vl = v.lower()
                        # Filter out non-equipment meta values
                        if vl not in ["ind","sg","bd","pk","br","no guild","unknown","none","null","default","player","user"]:
                            if not v.isdigit() and len(v) > 2:
                                results.append(v.strip())
                # Check if value is a list of equipment
                if kl in ["outfits","clothes","items","weapons","equipments","costumes","bundles","skins"]:
                    if isinstance(v, list):
                        for item in v:
                            recurse(item, depth+1)
                # Recurse all values
                recurse(v, depth+1)
        elif isinstance(o, list):
            for item in o:
                recurse(item, depth+1)
    recurse(obj)
    # Deduplicate and clean
    seen = set()
    uniq = []
    for it in results:
        # Clean item name
        clean = it.strip()
        if clean.lower() not in seen and len(clean) > 2:
            # Skip if it's just numbers or region codes
            if not (clean.isdigit() or clean.lower() in ["ind","sg","br","bd","pk","us"]):
                seen.add(clean.lower())
                uniq.append(clean)
    return uniq

FF_CHARS = {"1":"Wolfrahh","2":"Kelly","3":"Hayato","4":"Moco","5":"Wukong","6":"Alok","7":"Chrono","8":"K","9":"A124","10":"Skyler","11":"Xayne","12":"Dimitri","13":"D-Bee","14":"Thiva","15":"Leon","16":"Nairi","17":"Otho","18":"Kenta","19":"Homer","20":"Tatsuya","21":"J.Biebs","22":"Ignis","23":"Luna","24":"Santino","25":"Iris","26":"Jota","27":"Clu","28":"Kapella","29":"Alvaro","30":"Steffie","31":"Notora","32":"Olivia","33":"Rafael","34":"A-Patroa","35":"Caroline","36":"Andrew","37":"Antonio","38":"Ford","39":"Nikita","40":"Misha","41":"Maxim","42":"Kla","43":"Paloma","44":"Miguel"}

def detect_char(raw, outfit):
    cid = deep_find(raw, ["characterId","CharacterId","equippedCharacterId","mainCharacterId"])
    cname = deep_find(raw, ["characterName","CharacterName","equippedCharacter","mainCharacter"])
    if not cid and outfit:
        cid = deep_find(outfit, ["characterId","CharacterId","equippedCharacterId"])
        if not cname: cname = deep_find(outfit, ["characterName","CharacterName"])
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
    return "K", "?"  # Default to K as in your screenshot

def get_player(uid):
    for url in [
        f"https://wzapi.vercel.app/get_all?uid={uid}&region=IND",
        f"https://wzapi.vercel.app/get?uid={uid}&region=IND",
        f"https://wzapi.vercel.app/get?uid={uid}&region=SG",
    ]:
        d = safe_json(url, 13)
        if d:
            s = json.dumps(d).lower()
            if "player not found" in s and len(s) < 800: continue
            if any(k in s for k in ["nickname","basicinfo","accountinfo"]):
                return d
        time.sleep(0.3)
    return None

def get_outfit(uid):
    for url in [
        f"https://wzapi.vercel.app/outfit?uid={uid}&region=IND",
        f"https://wzapi.vercel.app/outfit?uid={uid}&region=SG",
        f"https://wzapiinfo.vercel.app/outfit?uid={uid}&region=IND",
    ]:
        d = safe_json(url, 12)
        if d and len(str(d))>30: return d
        time.sleep(0.25)
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
                            expire_str="-"
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
                                    expire_str=exp.strftime("%d %b %Y")
                                    hours=p*24
                                    if p>=30:
                                        m=p//30; rd=p%30
                                        status_text=f"TEMP - {m}M {rd}D" if rd else f"TEMP - {m}M"
                                        timer_text=f"{p} Days | {hours} Hours | Exp: {expire_str}"
                                    else:
                                        status_text=f"TEMP - {p} DAYS"
                                        timer_text=f"{p} Days | {hours}H | Exp: {expire_str}"
                            except:
                                ps=str(period).lower()
                                if "permanent" in ps or "perm" in ps:
                                    status_text="PERMANENT BANNED"
                                    timer_text="Permanent"
                                    expire_str="Never"
                                elif ps and ps!="0":
                                    status_text=f"TEMP - {period}"
                                    timer_text=f"{period}"
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
                            res=(banned,period,f"TEMP - {p} DAYS",f"{p} Days | Exp: {exp_str}",exp_str)
                    except:
                        res=(banned,period,"BANNED","Unknown","Unknown")
                set_cache(uid,res)
                return res
    except: pass
    return (0,0,"SAFE - NOT BANNED","No Ban","-")

def generate_character_image(player, items, char):
    """Generate real character + equipment showcase - FIXED, always visible"""
    if not HAS_PIL:
        return None
    
    W, H = 900, 1200
    img = Image.new('RGB', (W, H), (18, 8, 45))
    draw = ImageDraw.Draw(img, 'RGBA')
    
    # Deep purple gradient background with bokeh
    for y in range(H):
        ratio = y / H
        r = int(18 + ratio*25)
        g = int(8 + ratio*15)
        b = int(45 + ratio*65)
        glow = int(25 * (1 - abs((y - H*0.5)/H*2)))
        draw.line([(0,y), (W,y)], fill=(min(r+glow//4, 90), min(g+glow//5, 70), min(b+glow//2, 160)))
    
    # Bokeh lights
    import random
    random.seed(42)
    for _ in range(12):
        x = random.randint(50, W-50)
        y = random.randint(100, H-300)
        size = random.randint(15, 40)
        draw.ellipse([x-size, y-size, x+size, y+size], fill=(120, 40, 200, 25))
    
    cx, cy = W//2, H//2 + 60
    
    # Platform - like in your screenshot
    platform_y = H - 200
    platform = [(cx-210, platform_y), (cx+210, platform_y), (cx+190, platform_y+35), (cx-190, platform_y+35)]
    draw.polygon(platform, fill=(190,200,220), outline=(100,220,255), width=2)
    
    # Character - improved realistic silhouette (not blank)
    # Legs with blue flame
    left_leg = [(cx-65, cy+80), (cx-85, cy+260), (cx-35, cy+275), (cx-15, cy+80)]
    draw.polygon(left_leg, fill=(8,70,180), outline=(0,180,255), width=2)
    flame_l = [(cx-75, cy+150), (cx-95, cy+210), (cx-50, cy+230), (cx-35, cy+170)]
    draw.polygon(flame_l, fill=(0,160,255), outline=(80,220,255), width=1)
    
    right_leg = [(cx+15, cy+80), (cx+25, cy+275), (cx+75, cy+260), (cx+55, cy+80)]
    draw.polygon(right_leg, fill=(8,60,170), outline=(0,180,255), width=2)
    flame_r = [(cx+25, cy+150), (cx+55, cy+220), (cx+75, cy+200), (cx+45, cy+150)]
    draw.polygon(flame_r, fill=(0,150,255), outline=(80,200,255), width=1)
    
    # Boots
    draw.rectangle([cx-85, cy+260, cx-30, cy+290], fill=(15,15,15), outline=(0,200,255), width=2)
    draw.rectangle([cx+25, cy+260, cx+80, cy+290], fill=(15,15,15), outline=(0,200,255), width=2)
    
    # Pants
    draw.polygon([(cx-65, cy+20), (cx+55, cy+20), (cx+65, cy+260), (cx-75, cy+260)], fill=(12,12,12), outline=(60,60,70), width=1)
    # Belt
    draw.rectangle([cx-65, cy+20, cx+55, cy+38], fill=(0,70,170), outline=(0,200,255), width=2)
    draw.ellipse([cx-12, cy+15, cx+12, cy+42], fill=(0,200,255), outline=(120,255,255), width=2)
    
    # Torso
    draw.polygon([(cx-75, cy-110), (cx+70, cy-110), (cx+60, cy+20), (cx-60, cy+20)], fill=(210,180,145), outline=(0,0,0), width=1)
    # Abs lines
    draw.line([(cx-18, cy-70), (cx-18, cy+0)], fill=(180,150,110), width=1)
    draw.line([(cx+18, cy-70), (cx+18, cy+0)], fill=(180,150,110), width=1)
    
    # Jacket
    draw.polygon([(cx-75, cy-120), (cx-28, cy-120), (cx-35, cy+20), (cx-85, cy+20)], fill=(8,8,8), outline=(70,70,70), width=1)
    draw.polygon([(cx+28, cy-120), (cx+75, cy-120), (cx+85, cy+20), (cx+35, cy+20)], fill=(8,8,8), outline=(70,70,70), width=1)
    # Shoulder pads
    draw.ellipse([cx-105, cy-130, cx-45, cy-70], fill=(8,8,8), outline=(0,180,255), width=3)
    draw.ellipse([cx+45, cy-130, cx+105, cy-70], fill=(5,50,140), outline=(0,200,255), width=3)
    
    # Arms
    draw.polygon([(cx-75, cy-110), (cx-105, cy-50), (cx-95, cy-10), (cx-55, cy-30)], fill=(8,8,8), outline=(0,0,0), width=1)
    draw.ellipse([cx-110, cy-60, cx-80, cy-30], fill=(0,90,190), outline=(0,200,255), width=2)
    draw.polygon([(cx+70, cy-110), (cx+115, cy-70), (cx+95, cy-20), (cx+55, cy-40)], fill=(210,180,145), outline=(0,0,0), width=1)
    draw.ellipse([cx+95, cy-80, cx+125, cy-50], fill=(0,70,170), outline=(0,200,255), width=2)
    
    # Head
    draw.ellipse([cx-40, cy-200, cx+40, cy-125], fill=(215,185,145), outline=(0,0,0), width=1)
    # Hair ponytail
    draw.ellipse([cx-15, cy-220, cx+55, cy-155], fill=(18,18,18), outline=(0,0,0), width=1)
    draw.ellipse([cx+25, cy-230, cx+65, cy-165], fill=(12,12,12), outline=(0,0,0), width=1)
    # Eyes
    draw.ellipse([cx-18, cy-175, cx-5, cy-165], fill=(0,0,0))
    draw.ellipse([cx+5, cy-175, cx+18, cy-165], fill=(0,0,0))
    # Necklace
    draw.ellipse([cx-8, cy-118, cx+8, cy-100], fill=(90,90,90), outline=(200,200,200), width=1)
    
    # Hexagon equipment slots
    def draw_hex(center, size, fill=(25,10,50), outline=(140,50,255)):
        x, y = center
        pts = []
        for i in range(6):
            ang = math.radians(60*i - 30)
            pts.append((x + size*math.cos(ang), y + size*math.sin(ang)))
        draw.polygon(pts, fill=fill, outline=outline, width=2)
        # Inner
        inner = []
        for i in range(6):
            ang = math.radians(60*i - 30)
            inner.append((x + size*0.65*math.cos(ang), y + size*0.65*math.sin(ang)))
        draw.polygon(inner, fill=(60,25,90,120))
        return pts
    
    hex_size = 40
    hex_positions = [
        (cx-260, cy-130), (cx-310, cy-30), (cx-260, cy+90), (cx-200, cy+200),
        (cx+260, cy-130), (cx+310, cy-30), (cx+260, cy+90), (cx+200, cy+200),
    ]
    
    # Load fonts
    try:
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        font_tiny = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
        font_tiny_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
    except:
        font_small = ImageFont.load_default()
        font_tiny = ImageFont.load_default()
        font_tiny_bold = ImageFont.load_default()
    
    for idx, (hx, hy) in enumerate(hex_positions):
        draw_hex((hx, hy), hex_size)
        # Connection line
        draw.line([(hx, hy), (cx, cy-20)], fill=(100,50,180,60), width=1)
        # Item name inside hexagon if available
        if idx < len(items):
            item_name = items[idx][:14]
            # Draw text background
            tw = len(item_name) * 6
            draw.rectangle([hx-tw//2-3, hy+38, hx+tw//2+3, hy+52], fill=(0,0,0,200))
            draw.text((hx-tw//2, hy+39), item_name, fill=(255,255,255), font=font_tiny)
    
    # Top info bar
    draw.rectangle([0,0,W,95], fill=(0,0,0,215))
    draw.text((15,8), f"UID: {player['uid']} | {player['name'][:18]} | Lv:{player['level']} | {player['likes']} Likes", fill=(0,255,255), font=font_small)
    draw.text((15,30), f"{player['region']} | {player['guild'][:18]} | Char:{char[0]} | Pet:{player['pet'][:10]}", fill=(255,255,0), font=font_tiny)
    # Ban status
    ban_color = (255,80,80) if "BANNED" in player['ban_status'] and "SAFE" not in player['ban_status'] else (80,255,80)
    draw.rectangle([0,52,W,75], fill=(80,0,180,180))
    draw.text((15,56), f"{player['ban_status']} | Timer: {player['timer'][:30]}", fill=ban_color, font=font_tiny_bold)
    
    # Bottom
    draw.rectangle([0,H-38,W,H], fill=(0,0,0,220))
    draw.text((W//2-90,H-26), f"@just_zevric | zevricxplay", fill=(0,255,255), font=font_small)
    
    return img

def menu():
    # SINGLE set of colored inline buttons - NO double
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
    # Remove any reply keyboard (fix double issue)
    await update.message.reply_text("Removing old keyboard...", reply_markup=ReplyKeyboardRemove())
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
            await status.edit_text(f"UID <code>{uid}</code> busy, retry after 5 sec", parse_mode=ParseMode.HTML, reply_markup=menu())
            continue
        
        outfit = get_outfit(uid)
        ban_data = get_ban_timer(uid)
        
        cname,cid = detect_char(raw, outfit)
        name = deep_find(raw, ["nickname","AccountName","playerName"]) or "Unknown"
        level = deep_find(raw, ["level","AccountLevel","AccountLevel"]) or "?"
        likes = deep_find(raw, ["liked","likes","AccountLikes"]) or "?"
        region = deep_find(raw, ["region","AccountRegion"]) or "IND"
        guild = deep_find(raw, ["clanName","guildName","GuildName"]) or "No Guild"
        pet = deep_find(raw, ["petName","PetName","equippedPet","pet"]) or (deep_find(outfit, ["petName","PetName"]) if outfit else None) or "?"
        
        # FIXED: Deep research equipment from BOTH raw and outfit
        all_items = []
        if outfit:
            all_items.extend(deep_find_all_equipment(outfit))
        if raw:
            all_items.extend(deep_find_all_equipment(raw))
        
        # Deduplicate, remove character name itself
        seen = set()
        uniq = []
        for it in all_items:
            if it.lower() not in seen and it.lower() != cname.lower() and len(it) > 2:
                # Skip if it's the player name
                if it.lower() != str(name).lower():
                    seen.add(it.lower())
                    uniq.append(it)
        
        items = uniq[:8]
        
        # Ban data
        ban_status = "SAFE - NOT BANNED"
        timer_text = "No Ban"
        expire_str = "-"
        is_banned = 0
        period = 0
        if ban_data:
            is_banned, period, ban_status, timer_text, expire_str = ban_data
        
        player = {
            "uid": uid,
            "name": str(name),
            "level": str(level),
            "likes": str(likes),
            "region": str(region),
            "guild": str(guild),
            "pet": str(pet) if pet else "?",
            "ban_status": ban_status,
            "timer": timer_text,
            "expire": expire_str
        }
        
        # Generate image - FIXED to always show character + equipment
        img = generate_character_image(player, items, (cname, cid))
        
        if mode == "ban":
            if is_banned == 0:
                cap = f"<b>🔴 1. Ban Check</b>\n\n<code>{uid}</code>\n{name} | {cname}\n\n🟢 {ban_status}\nTimer: {timer_text}\nExpire: {expire_str}"
            else:
                if "PERMANENT" in ban_status:
                    cap = f"<b>🔴 1. Ban Check</b>\n\n<code>{uid}</code>\n{name}\n\n🔴 {ban_status}\nTimer: {timer_text}\nExpire: Never"
                else:
                    cap = f"<b>🔴 1. Ban Check</b>\n\n<code>{uid}</code>\n{name}\n\n🔴 {ban_status}\nTimer: {timer_text}\nExpire: {expire_str}\n\n{period} Days Ban"
        else:
            cap = f"<b>🟢 2. Player Info</b>\n<code>{uid}</code> | {name}\nLv:{level} | {likes} Likes | {region}\n{guild[:20]} | Char:{cname} | Pet:{pet}\n"
            if items:
                cap += f"\n<b>Equipment ({len(items)}):</b>\n"
                for it in items[:7]:
                    cap += f"├ {it}\n"
            else:
                cap += f"\n<b>Equipment:</b> Loading...\n"
            cap += f"\n<b>Ban:</b> {ban_status}\nTimer: {timer_text}"
            if expire_str != "-":
                cap += f"\nExpire: {expire_str}"
        
        try:
            if img:
                path = f"/tmp/ff_{uid}_{cname}.jpg"
                img.save(path, "JPEG", quality=92)
                with open(path, 'rb') as f:
                    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=f, caption=cap, parse_mode=ParseMode.HTML, reply_markup=again())
                await status.delete()
            else:
                await status.edit_text(cap, parse_mode=ParseMode.HTML, reply_markup=again())
        except Exception as e:
            await status.edit_text(f"{cap}\n\nErr: {str(e)[:80]}", parse_mode=ParseMode.HTML, reply_markup=again())

async def check_cmd(update, context):
    uids = [p for a in context.args for p in a.replace(","," ").split() if p.isdigit() and 6 <= len(p) <= 15]
    if not uids:
        await update.message.reply_text("Example: <code>12345678</code>", parse_mode=ParseMode.HTML, reply_markup=menu())
        return
    await handle_uid(update, context, uids, mode="info")

async def text_handler(update, context):
    found = re.findall(r'\d{6,15}', update.message.text.strip())
    valid = [u for u in found if 6 <= len(u) <= 15]
    if valid:
        await handle_uid(update, context, valid, mode="info")
    else:
        await update.message.reply_text("Example: <code>12345678</code>", parse_mode=ParseMode.HTML, reply_markup=menu())

async def cb(update, context):
    q = update.callback_query
    await q.answer()
    d = q.data
    if d == "ban":
        await q.message.reply_text("Ban Check - UID Bhejo:\n<code>12345678</code>", parse_mode=ParseMode.HTML, reply_markup=menu())
    elif d == "info":
        await q.message.reply_text("Player Info - UID Bhejo:\n<code>12345678</code>", parse_mode=ParseMode.HTML, reply_markup=menu())
    elif d == "owner":
        await owner_info(q, context)
    elif d == "main":
        await start(q, context)

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
    print(f"FIXED DOUBLE + EQUIPMENT + CHARACTER - PIL:{HAS_PIL}")
    app.run_polling(close_loop=False)

if __name__ == "__main__": main()
