import os, time, asyncio, requests, threading, re, json, math
from collections import OrderedDict
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
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
    results = []
    def recurse(o, depth=0):
        if depth > 12: return
        if isinstance(o, dict):
            for k, v in o.items():
                kl = k.lower()
                if kl in ["name","itemname","displayname","item_name"]:
                    if isinstance(v, str) and 2 < len(v) < 60:
                        vl = v.lower()
                        if vl not in ["ind","sg","bd","pk","br","no guild","unknown","none","null","default","player","user"]:
                            if not v.isdigit() and len(v) > 2:
                                results.append(v.strip())
                if kl in ["outfits","clothes","items","weapons","equipments","costumes","bundles","skins","costume"]:
                    if isinstance(v, list):
                        for item in v:
                            recurse(item, depth+1)
                recurse(v, depth+1)
        elif isinstance(o, list):
            for item in o:
                recurse(item, depth+1)
    recurse(obj)
    seen = set()
    uniq = []
    for it in results:
        clean = it.strip()
        if clean.lower() not in seen and len(clean) > 2:
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
    return "K", "?"

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
                                    status_text=f"TEMP - {p} DAYS"
                                    timer_text=f"{p} Days | {hours}H | Exp: {expire_str}"
                            except:
                                status_text="BANNED"
                                timer_text=str(period)
                                expire_str="Unknown"
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

def get_real_outfit_image(uid, region="IND"):
    apis = [
        f"https://discordbot.freefirecommunity.com/outfit_image_api?uid={uid}&region={region.lower()}",
        f"https://api.freefirecommunity.com/outfit/{uid}?region={region}",
    ]
    for api_url in apis:
        try:
            r = requests.get(api_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and 'image' in r.headers.get('content-type',''):
                if len(r.content) > 5000:
                    path = f"/tmp/real_outfit_{uid}.png"
                    with open(path, 'wb') as f:
                        f.write(r.content)
                    return path
            if r.status_code == 200:
                try:
                    data = r.json()
                    img_url = data.get('outfitImageUrl') or data.get('imageUrl') or data.get('url')
                    if img_url:
                        r2 = requests.get(img_url, timeout=10)
                        if r2.status_code == 200 and len(r2.content) > 5000:
                            path = f"/tmp/real_outfit_{uid}.png"
                            with open(path, 'wb') as f:
                                f.write(r2.content)
                            return path
                except:
                    pass
        except:
            continue
    return None

def generate_premium_image(player, items, char):
    """REAL Free Fire style - NOT cartoon stickman, premium rendered"""
    if not HAS_PIL:
        return None
    
    # Try real image first
    real_path = get_real_outfit_image(player['uid'], player['region'])
    if real_path and os.path.exists(real_path):
        try:
            base_img = Image.open(real_path).convert('RGB')
            W, H = base_img.size
            if W < 800:
                new_h = int(H * 900 / W)
                base_img = base_img.resize((900, new_h), Image.Resampling.LANCZOS)
                W, H = base_img.size
            final_H = H + 130
            final_img = Image.new('RGB', (W, final_H), (18,8,45))
            final_img.paste(base_img, (0, 65))
            draw = ImageDraw.Draw(final_img, 'RGBA')
            try:
                font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
                font_tiny = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
                font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
            except:
                font_small = font_tiny = font_bold = ImageFont.load_default()
            draw.rectangle([0,0,W,65], fill=(0,0,0,220))
            draw.text((12,6), f"UID: {player['uid']} | {player['name'][:20]} | Lv:{player['level']} | {player['likes']} | {char[0]}", fill=(0,255,255), font=font_small)
            draw.text((12,30), f"{player['region']} | {player['guild'][:22]} | {player['ban_status']}", fill=(255,255,0), font=font_tiny)
            draw.rectangle([0,final_H-35,W,final_H], fill=(0,0,0,220))
            draw.text((W//2-90,final_H-24), f"@just_zevric | zevricxplay", fill=(0,255,255), font=font_small)
            if items:
                draw.rectangle([W-210, 75, W-10, 75+len(items[:8])*22+10], fill=(0,0,0,180))
                for i, it in enumerate(items[:8]):
                    draw.text((W-200, 80+i*22), f"• {it[:18]}", fill=(255,255,255), font=font_tiny)
            return final_img
        except:
            pass
    
    # Premium realistic render - NOT cartoon
    W, H = 1080, 1350
    img = Image.new('RGB', (W, H), (12, 8, 35))
    draw = ImageDraw.Draw(img, 'RGBA')
    
    # Deep space gradient
    for y in range(H):
        ratio = y / H
        r = int(12 + ratio*28)
        g = int(8 + ratio*18)
        b = int(35 + ratio*70)
        glow = int(28 * math.sin(ratio * math.pi))
        draw.line([(0,y), (W,y)], fill=(r+glow//4, g+glow//5, b+glow//2))
    
    # Stars
    import random
    random.seed(hash(player['uid']) % 10000)
    for _ in range(25):
        x = random.randint(10, W-10)
        y = random.randint(20, H-400)
        sz = random.randint(2, 12)
        draw.ellipse([x-sz, y-sz, x+sz, y+sz], fill=(180, 120, 255, random.randint(20, 60)))
    
    cx, cy = W//2, H//2 + 70
    platform_y = H - 210
    
    # Platform glow
    draw.ellipse([cx-280, platform_y-15, cx+280, platform_y+60], fill=(0, 200, 255, 55))
    platform = [(cx-250, platform_y), (cx+250, platform_y), (cx+220, platform_y+48), (cx-220, platform_y+48)]
    draw.polygon(platform, fill=(205,215,235), outline=(0,220,255), width=3)
    draw.polygon([(cx-230, platform_y), (cx+230, platform_y), (cx+200, platform_y+18), (cx-200, platform_y+18)], fill=(255,255,255,90))
    
    # Character - detailed, muscular, Free Fire accurate - NOT stickman
    # Legs - blue flame tech pants
    draw.polygon([(cx-80, cy+85), (cx-102, cy+285), (cx-42, cy+300), (cx-22, cy+85)], fill=(4, 62, 172), outline=(0,195,255), width=2)
    draw.polygon([(cx-88, cy+165), (cx-108, cy+245), (cx-58, cy+265), (cx-42, cy+180)], fill=(0,175,255), outline=(120,235,255), width=1)
    draw.polygon([(cx+22, cy+85), (cx+32, cy+300), (cx+92, cy+285), (cx+72, cy+85)], fill=(4, 58, 162), outline=(0,195,255), width=2)
    draw.polygon([(cx+32, cy+165), (cx+62, cy+245), (cx+82, cy+225), (cx+52, cy+165)], fill=(0,165,255), outline=(90,215,255), width=1)
    
    # Tactical boots
    draw.rectangle([cx-102, cy+285, cx-38, cy+320], fill=(8,8,8), outline=(0,220,255), width=2)
    draw.rectangle([cx+38, cy+285, cx+102, cy+320], fill=(8,8,8), outline=(0,220,255), width=2)
    draw.rectangle([cx-96, cy+290, cx-62, cy+302], fill=(70,70,70,160))
    draw.rectangle([cx+42, cy+290, cx+76, cy+302], fill=(70,70,70,160))
    
    # Cargo pants
    draw.polygon([(cx-80, cy+22), (cx+70, cy+22), (cx+80, cy+290), (cx-90, cy+290)], fill=(6,6,9), outline=(35,35,45), width=1)
    
    # Belt with LED buckle
    draw.rectangle([cx-80, cy+22, cx+70, cy+48], fill=(0,72,176), outline=(0,220,255), width=2)
    draw.ellipse([cx-16, cy+17, cx+16, cy+52], fill=(0,220,255), outline=(160,255,255), width=2)
    draw.ellipse([cx-9, cy+26, cx+9, cy+43], fill=(255,255,255,110))
    
    # Torso - athletic
    draw.polygon([(cx-88, cy-135), (cx+83, cy-135), (cx+73, cy+22), (cx-73, cy+22)], fill=(220,190,154), outline=(0,0,0), width=1)
    # Muscle definition
    draw.line([(cx-22, cy-85), (cx-22, cy-8)], fill=(188,158,118), width=2)
    draw.line([(cx+22, cy-85), (cx+22, cy-8)], fill=(188,158,118), width=2)
    
    # Tactical jacket open
    draw.polygon([(cx-88, cy-152), (cx-32, cy-152), (cx-40, cy+22), (cx-98, cy+22)], fill=(5,5,7), outline=(55,55,65), width=1)
    draw.polygon([(cx+32, cy-152), (cx+88, cy-152), (cx+98, cy+22), (cx+40, cy+22)], fill=(5,5,7), outline=(55,55,65), width=1)
    draw.polygon([(cx-32, cy-147), (cx-40, cy+18), (cx-52, cy+18), (cx-44, cy-142)], fill=(0,38,115,140))
    draw.polygon([(cx+32, cy-147), (cx+44, cy-142), (cx+52, cy+18), (cx+40, cy+18)], fill=(0,38,115,140))
    
    # Shoulder armor
    draw.ellipse([cx-125, cy-162, cx-52, cy-84], fill=(7,7,9), outline=(0,195,255), width=3)
    draw.ellipse([cx-120, cy-157, cx-57, cy-89], fill=(0,0,0,0), outline=(0,255,255,70), width=1)
    draw.ellipse([cx+52, cy-162, cx+125, cy-84], fill=(3,42,130), outline=(0,215,255), width=3)
    draw.ellipse([cx+57, cy-157, cx+120, cy-89], fill=(0,75,190,90))
    
    # Arms
    draw.polygon([(cx-88, cy-142), (cx-130, cy-65), (cx-114, cy-18), (cx-68, cy-45)], fill=(5,5,7), outline=(0,0,0), width=1)
    draw.ellipse([cx-140, cy-75, cx-98, cy-33], fill=(0,92,190), outline=(0,215,255), width=2)
    draw.ellipse([cx-124, cy-28, cx-88, cy+2], fill=(7,7,9), outline=(0,185,255), width=1)
    
    draw.polygon([(cx+83, cy-142), (cx+140, cy-90), (cx+114, cy-28), (cx+68, cy-55)], fill=(220,190,154), outline=(0,0,0), width=1)
    draw.ellipse([cx+118, cy-100, cx+155, cy-63], fill=(0,72,176), outline=(0,215,255), width=2)
    draw.ellipse([cx+98, cy-38, cx+128, cy-8], fill=(220,190,154), outline=(0,0,0), width=1)
    
    # Head
    draw.ellipse([cx-50, cy-250, cx+50, cy-156], fill=(224,192,157), outline=(0,0,0), width=1)
    draw.ellipse([cx-42, cy-186, cx+37, cy-161], fill=(202,172,137,110))
    
    # Hair - styled
    draw.ellipse([cx-20, cy-275, cx+64, cy-192], fill=(14,14,14), outline=(0,0,0), width=1)
    draw.ellipse([cx+30, cy-285, cx+78, cy-202], fill=(9,9,9), outline=(0,0,0), width=1)
    draw.ellipse([cx+4, cy-260, cx+24, cy-220], fill=(55,55,55,110))
    
    # Eyes
    draw.ellipse([cx-24, cy-218, cx-8, cy-205], fill=(0,0,0))
    draw.ellipse([cx+8, cy-218, cx+24, cy-205], fill=(0,0,0))
    draw.ellipse([cx-20, cy-214, cx-14, cy-209], fill=(255,255,255,210))
    draw.ellipse([cx+14, cy-214, cx+20, cy-209], fill=(255,255,255,210))
    
    # Tag
    draw.ellipse([cx-11, cy-150, cx+11, cy-125], fill=(78,78,83), outline=(215,215,215), width=1)
    draw.rectangle([cx-2, cy-152, cx+2, cy-130], fill=(185,185,185), width=1)
    
    # Equipment hex - glowing
    def draw_hex(center, size, has_item=False):
        x, y = center
        pts = []
        for i in range(6):
            ang = math.radians(60*i - 30)
            pts.append((x + size*math.cos(ang), y + size*math.sin(ang)))
        if has_item:
            glow_pts = []
            for i in range(6):
                ang = math.radians(60*i - 30)
                glow_pts.append((x + (size+10)*math.cos(ang), y + (size+10)*math.sin(ang)))
            draw.polygon(glow_pts, fill=(100,50,255,28))
        draw.polygon(pts, fill=(28,14,56), outline=(165,85,255) if has_item else (75,38,115), width=2)
        inner = []
        for i in range(6):
            ang = math.radians(60*i - 30)
            inner.append((x + size*0.60*math.cos(ang), y + size*0.60*math.sin(ang)))
        draw.polygon(inner, fill=(68,33,106,160) if has_item else (38,18,58,80))
    
    hex_size = 54
    hex_positions = [(cx-310, cy-155), (cx-375, cy-30), (cx-310, cy+115), (cx-235, cy+250),(cx+310, cy-155), (cx+375, cy-30), (cx+310, cy+115), (cx+235, cy+250)]
    
    try:
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        font_tiny = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except:
        font_small = font_tiny = font_bold = ImageFont.load_default()
    
    for idx, (hx, hy) in enumerate(hex_positions):
        has_item = idx < len(items)
        draw_hex((hx, hy), hex_size, has_item)
        line_col = (115,75,195,95) if has_item else (55,35,85,35)
        draw.line([(hx, hy), (cx, cy)], fill=line_col, width=2 if has_item else 1)
        if has_item:
            item_name = items[idx][:16]
            tw = len(item_name) * 7
            draw.rectangle([hx-tw//2-6, hy+58, hx+tw//2+6, hy+78], fill=(0,0,0,215))
            draw.text((hx-tw//2, hy+60), item_name, fill=(255,255,255), font=font_tiny)
    
    draw.rectangle([0,0,W,110], fill=(0,0,0,228))
    draw.rectangle([0,0,W,3], fill=(0,255,255))
    draw.text((18,10), f"UID: {player['uid']} | {player['name'][:22]} | Lv:{player['level']} | {player['likes']} | {char[0]}", fill=(0,255,255), font=font_small)
    draw.text((18,36), f"{player['region']} | {player['guild'][:24]} | Pet:{player['pet'][:12]}", fill=(255,255,0), font=font_tiny)
    ban_color = (255,85,85) if "BANNED" in player['ban_status'] and "SAFE" not in player['ban_status'] else (85,255,85)
    draw.rectangle([0,62,W,90], fill=(88,0,195,190))
    draw.text((18,66), f"{player['ban_status']} | Timer: {player['timer'][:40]}", fill=ban_color, font=font_bold)
    draw.rectangle([0,H-46,W,H], fill=(0,0,0,232))
    draw.rectangle([0,H-46,W,H-43], fill=(0,255,255,150))
    draw.text((W//2-110,H-30), f"@just_zevric | zevricxplay", fill=(0,255,255), font=font_small)
    return img

# === ONLY KEYBOARD - NO UPPER INLINE DOUBLE, NO EXTRA TEXT ===
def get_main_keyboard():
    keyboard = [
        [KeyboardButton("🔴 1. Ban Check")],
        [KeyboardButton("🟢 2. Player Info")],
        [KeyboardButton("👑 3. Owner Info")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update, context):
    # ONLY keyboard, no inline double, no extra Choose/Support text
    txt = "<b>ZEVRIC PLAY</b>\n\nExample: <code>12345678</code>"
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard())

async def owner_info(update, context):
    txt = f"<b>👑 Owner</b>\n{OWNER}\n\n<b>Color Buttons:</b>"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Subscribe YouTube Channel", url=YT_LINK)],
        [InlineKeyboardButton("Add Me To Your Group", url="https://t.me/ZevricPlayBot?startgroup=true")],
    ])
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
    # Still keep only keyboard, no extra text

async def handle_uid(update, context, uid_list, mode):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    status = await update.message.reply_text(f"Checking <code>{uid_list[0]}</code>...", parse_mode=ParseMode.HTML)
    for uid in uid_list[:1]:  # Only 1 to avoid spam
        raw = get_player(uid)
        if not raw:
            await status.edit_text(f"UID <code>{uid}</code> not found", parse_mode=ParseMode.HTML)
            return
        outfit = get_outfit(uid)
        ban_data = get_ban_timer(uid)
        cname,cid = detect_char(raw, outfit)
        name = deep_find(raw, ["nickname","AccountName"]) or "Unknown"
        level = deep_find(raw, ["level","AccountLevel"]) or "?"
        likes = deep_find(raw, ["liked","likes"]) or "?"
        region = deep_find(raw, ["region"]) or "IND"
        guild = deep_find(raw, ["clanName","guildName"]) or "No Guild"
        pet = deep_find(raw, ["petName","PetName","equippedPet"]) or (deep_find(outfit, ["petName"]) if outfit else None) or "?"
        all_items = []
        if outfit: all_items.extend(deep_find_all_equipment(outfit))
        if raw: all_items.extend(deep_find_all_equipment(raw))
        seen=set(); uniq=[]
        for it in all_items:
            if it.lower() not in seen and it.lower()!=cname.lower() and len(it)>2:
                if it.lower()!=str(name).lower():
                    seen.add(it.lower()); uniq.append(it)
        items=uniq[:8]
        ban_status, timer_text, expire_str = "SAFE - NOT BANNED", "No Ban", "-"
        is_banned, period = 0, 0
        if ban_data:
            is_banned, period, ban_status, timer_text, expire_str = ban_data
        player={"uid":uid,"name":str(name),"level":str(level),"likes":str(likes),"region":str(region),"guild":str(guild),"pet":str(pet) if pet else "?","ban_status":ban_status,"timer":timer_text,"expire":expire_str}
        img = generate_premium_image(player, items, (cname,cid))
        if mode=="ban":
            if is_banned==0:
                cap=f"<b>🔴 Ban Check</b>\n<code>{uid}</code>\n{name}\n\n🟢 {ban_status}\nTimer: {timer_text}"
            else:
                cap=f"<b>🔴 Ban Check</b>\n<code>{uid}</code>\n{name}\n\n🔴 {ban_status}\nTimer: {timer_text}\nExpire: {expire_str}"
        else:
            cap=f"<b>🟢 Player Info</b>\n<code>{uid}</code> | {name}\nLv:{level} | {likes} Likes | {region}\n{guild[:22]} | {cname} | Pet:{pet}\n"
            if items:
                cap+=f"\n<b>Equipment:</b>\n"
                for it in items[:7]: cap+=f"├ {it}\n"
            cap+=f"\n<b>Ban:</b> {ban_status}\nTimer: {timer_text}"
            if expire_str!="-": cap+=f"\nExpire: {expire_str}"
        try:
            if img:
                path=f"/tmp/ff_final_{uid}.jpg"
                img.save(path,"JPEG",quality=95)
                with open(path,'rb') as f:
                    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=f, caption=cap, parse_mode=ParseMode.HTML)
                await status.delete()
            else:
                await status.edit_text(cap, parse_mode=ParseMode.HTML)
            # NO extra Choose/Support text, only keyboard stays
        except Exception as e:
            await status.edit_text(f"{cap}\nErr:{str(e)[:60]}", parse_mode=ParseMode.HTML)

async def check_cmd(update, context):
    uids=[p for a in context.args for p in a.replace(","," ").split() if p.isdigit() and 6<=len(p)<=15]
    if not uids:
        await update.message.reply_text("<code>12345678</code>", parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard())
        return
    await handle_uid(update, context, uids, mode="info")

async def text_handler(update, context):
    txt=update.message.text.strip()
    if "1. Ban Check" in txt:
        await update.message.reply_text("UID Bhejo: <code>12345678</code>", parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard())
        return
    elif "2. Player Info" in txt:
        await update.message.reply_text("UID Bhejo: <code>12345678</code>", parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard())
        return
    elif "3. Owner Info" in txt:
        await owner_info(update, context)
        return
    found=re.findall(r'\d{6,15}', txt)
    valid=[u for u in found if 6<=len(u)<=15]
    if valid: await handle_uid(update, context, valid, mode="info")
    else: await update.message.reply_text("<code>12345678</code>", parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard())

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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    print("FINAL CLEAN - Only keyboard, no double, no extra text, real image")
    app.run_polling(close_loop=False)

if __name__ == "__main__": main()
