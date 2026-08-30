import os
import re
import random
import asyncio
import traceback
import io
import html
import pickle
import base64
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

# 🌐 RENDER FAKE PORT (WEB SERVER)
from aiohttp import web

# 🚨 PYDROID / RENDER DNS SAFE SPOT 🚨
import dns.resolver
try:
    dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
    dns.resolver.default_resolver.nameservers = ['8.8.8.8', '8.8.4.4']
except Exception: pass

from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand, InputMediaPhoto, ReplyKeyboardMarkup, KeyboardButton

# 🗄️ MongoDB Async Driver
from motor.motor_asyncio import AsyncIOMotorClient

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ==========================================
# 1. SETUP & CONFIGURATION
# ==========================================
load_dotenv()
BOT_TOKEN = "8647892164:AAGffYrIO0qrjPzFIqRt40N1rsVpvLlJ6aQ"

bot = AsyncTeleBot(BOT_TOKEN, parse_mode='HTML') 
bot_username = ""

ROOT_ADMIN_ID = 7691071175
DYNAMIC_ADMINS = set() 

# 📢 CHANNELS SETUP
LOG_CHANNEL_ID = -1004357149492   
SCORE_CHANNEL_ID = -1004444723491 

# 🗄️ MONGODB SETUP
DB_USER = urllib.parse.quote_plus("Cricket_231")
DB_PASS = urllib.parse.quote_plus("Rohit1616@")
MONGO_URI = f"mongodb+srv://{DB_USER}:{DB_PASS}@zolmdho.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

mongo_client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = mongo_client.premium_cricket_db

# ⚡ CACHE
MEDIA_PATH_CACHE = {}
FILE_ID_CACHE = {}
KNOWN_CHATS_CACHE = set()

def get_media_path(filename: str) -> Optional[str]:
    if filename in MEDIA_PATH_CACHE: return MEDIA_PATH_CACHE[filename]
    paths_to_check = [
        os.path.join(os.getcwd(), filename),
        os.path.join(os.getcwd(), 'media', filename),
        f"/storage/emulated/0/{filename}",
        f"/storage/emulated/0/media/{filename}",
        f"/storage/emulated/0/Download/{filename}"
    ]
    for p in paths_to_check:
        if os.path.exists(p):
            MEDIA_PATH_CACHE[filename] = p
            return p
    return None

# 🎨 100% REAL PREMIUM EMOJIS MAPPING 🔥
PREMIUM_EMOJIS = {
    "🚫": "5039671744172917707", "🔁": "6030657343744644592", "🔄": "6030657343744644592",
    "⏳": "6194961953308283021", "⏱": "5382194935057372936", "⏱️": "5382194935057372936",
    "☠️": "5042167377869932162", "🔓": "6138966635014263327", "🔒": "6138875036246742091",
    "🤖": "6030400221232501136", "🤝": "4976940882071651344", "🛑": "5404756935134159738",
    "🏀": "5935847413859225147", "0️⃣": "5305749482170758709", "🎁": "5460860009862668155",
    "🛒": "5143290574673019778", "💼": "5967389567781703494", "📢": "6138918432596301845",
    "📭": "5352896944496728039", "🖋": "5839380580080293813", "📝": "5839380580080293813",
    "💸": "6278057926829542921", "👑": "5805553606635559688", "🔵": "5915622077854913640",
    "😔": "6255726523546868863", "⚠️": "5039665997506675838", "👎": "5121063440311386962",
    "🌎": "5224450179368767019", "👤": "5902335789798265487", "😎": "5235684778727974441",
    "🧬": "5438365861679213990", "📈": "5884366771913233289", "📊": "5028746137645876535",
    "🎮": "5042290883949495533", "🏆": "5938413566624272793", "🎖️": "5893376775781617954",
    "🏏": "5134492845268272173", "🏃": "5377589458805741988", "⚡️": "5085022089103016925",
    "💥": "5465250797879057135", "⭐️": "5053473385355412667", "🎯": "6032949275732742941",
    "🪙": "5145750530076706012", "✅": "4976940882071651344", "🧸": "5206502842478638898", 
    "❤️": "5406926593698312391"
}
THUMBS_UP_EMOJIS = ['<tg-emoji emoji-id="5073456536743838369">👍</tg-emoji>']

def pe(emoji_char: str) -> str:
    eid = PREMIUM_EMOJIS.get(emoji_char)
    if eid: return f'<tg-emoji emoji-id="{eid}">{emoji_char}</tg-emoji>'
    return emoji_char

async def _send_log_task(text: str):
    if not str(LOG_CHANNEL_ID).startswith("-100"): return
    try: await bot.send_message(LOG_CHANNEL_ID, f"📝 <b>BOT LOG:</b>\n{text}", parse_mode='HTML')
    except Exception as e: print(f"Log Error: {e}")

def send_log(text: str): 
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_send_log_task(text))
    except Exception: pass

# ==========================================
# 2. PERMISSIONS & MONGODB FUNCTIONS
# ==========================================
def is_owner(user_id: int) -> bool: return user_id == ROOT_ADMIN_ID
def is_bot_admin(user_id: int) -> bool: return user_id == ROOT_ADMIN_ID or user_id in DYNAMIC_ADMINS

async def is_group_admin(chat_id: int, user_id: int) -> bool:
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status in ['administrator', 'creator']
    except Exception: return False

async def check_owner_access(message) -> bool:
    if is_owner(message.from_user.id): return True
    try: await bot.reply_to(message, f"{pe('❌')} <b>Only Owner can use this command.</b>")
    except Exception: pass
    return False

async def check_bot_admin_access(message) -> bool:
    if is_bot_admin(message.from_user.id): return True
    try: await bot.reply_to(message, f"{pe('❌')} <b>You have no access.</b>")
    except Exception: pass
    return False

async def get_group_link(chat_id: int) -> Optional[str]:
    try:
        chat = await bot.get_chat(chat_id)
        if chat.username: return f"https://t.me/{chat.username}"
        return await bot.export_chat_invite_link(chat_id)
    except Exception: return None

async def init_db():
    try:
        admins = await db.bot_admins.find().to_list(length=None)
        for adm in admins: DYNAMIC_ADMINS.add(adm["user_id"])
    except Exception as e: print(f"MongoDB Init Error: {e}")

async def track_chat(chat_id: int, chat_type: str):
    try: await db.known_chats.update_one({"chat_id": chat_id}, {"$set": {"chat_id": chat_id, "chat_type": chat_type}}, upsert=True)
    except Exception: pass

def run_safe_track(message):
    async def _track():
        try:
            if message.from_user and message.from_user.username:
                await db.user_map.update_one(
                    {"id": message.from_user.id}, 
                    {"$set": {"firstName": message.from_user.first_name, "username": message.from_user.username}}, 
                    upsert=True
                )
            chat_id = message.chat.id
            if chat_id not in KNOWN_CHATS_CACHE:
                KNOWN_CHATS_CACHE.add(chat_id)
                await track_chat(chat_id, message.chat.type)
            if message.text and message.text.startswith('/'):
                send_log(f"Command <code>{html.escape(message.text)}</code> used by <a href='tg://user?id={message.from_user.id}'>{html.escape(message.from_user.first_name)}</a> in Chat <code>{chat_id}</code>")
        except Exception: pass
    asyncio.create_task(_track())

async def add_bot_admin(user_id: int) -> bool:
    if await db.bot_admins.find_one({"user_id": user_id}): return False
    await db.bot_admins.insert_one({"user_id": user_id})
    DYNAMIC_ADMINS.add(user_id)
    return True

async def remove_bot_admin(user_id: int) -> bool:
    res = await db.bot_admins.delete_one({"user_id": user_id})
    if res.deleted_count > 0:
        if user_id in DYNAMIC_ADMINS: DYNAMIC_ADMINS.remove(user_id)
        return True
    return False

# 🔥 SEPARATED STATS LOGIC 🔥
async def get_stats(user_id: int, view_type: str) -> Optional[dict]:
    u = await db.player_stats.find_one({"user_id": user_id})
    if not u: return None
    
    if "matches" in u and "solo" not in u:
        u["solo"] = {k: v for k, v in u.items() if k not in ["_id", "user_id", "coins", "teddy_count", "heart_count", "username", "first_name", "booster_expiry", "active_theme", "unlocked_themes"]}
    
    if view_type in ['solo', 'tour']:
        stats = u.get(view_type, {})
    else:
        stats = {}
        solo = u.get('solo', {})
        tour = u.get('tour', {})
        for key in ["matches", "motms", "wins", "losses", "total_runs", "total_balls", "total_fours", "total_sixes", "ducks", "fifties", "hundreds", "total_wickets", "total_bowling_balls", "total_runs_conceded"]:
            stats[key] = solo.get(key, 0) + tour.get(key, 0)
        stats["highest_score"] = max(solo.get("highest_score", 0), tour.get("highest_score", 0))
        stats["form"] = solo.get("form", [])
        
    stats['user_id'] = u.get('user_id')
    stats['username'] = u.get('username')
    stats['first_name'] = u.get('first_name')
    stats['active_theme'] = u.get('active_theme', 'default')
    return stats

async def update_stats_mongo(summary: dict, game_type: str):
    try:
        for p in summary['players']:
            u_doc = await db.player_stats.find_one({"user_id": p['id']})
            if not u_doc: u_doc = {"user_id": p['id'], "coins": 0, "teddy_count": 0, "heart_count": 0, "username": "", "first_name": "", "active_theme": "default", "unlocked_themes": ["default"]}
            
            if "matches" in u_doc and "solo" not in u_doc:
                u_doc["solo"] = {k: v for k, v in u_doc.items() if k not in ["_id", "user_id", "coins", "teddy_count", "heart_count", "username", "first_name", "booster_expiry", "active_theme", "unlocked_themes"]}
            
            u_doc['username'] = p['username'] or u_doc.get('username', '')
            u_doc['first_name'] = p['first_name'] or u_doc.get('first_name', '')
            
            mode_stats = u_doc.get(game_type, {
                "matches": 0, "motms": 0, "wins": 0, "losses": 0, "form": [],
                "highest_score": 0, "total_runs": 0, "total_balls": 0, "total_fours": 0, "total_sixes": 0,
                "ducks": 0, "fifties": 0, "hundreds": 0, "total_wickets": 0, "total_bowling_balls": 0,
                "total_runs_conceded": 0
            })
            
            mode_stats["matches"] += 1
            won = (p['id'] == summary['winnerId'])
            if won: 
                mode_stats["wins"] += 1
                mode_stats["form"] = (['W'] + mode_stats.get("form", []))[:5]
            else: 
                mode_stats["losses"] += 1
                mode_stats["form"] = (['L'] + mode_stats.get("form", []))[:5]
                
            if p['id'] == summary['motmId']: mode_stats["motms"] += 1
            mode_stats["highest_score"] = max(mode_stats.get("highest_score", 0), p['runs'])
            mode_stats["total_runs"] += p['runs']
            mode_stats["total_balls"] += p['balls']
            mode_stats["total_fours"] += p['fours']
            mode_stats["total_sixes"] += p['sixes']
            if p['runs'] == 0 and p['balls'] > 0: mode_stats["ducks"] += 1
            if 50 <= p['runs'] < 100: mode_stats["fifties"] += 1
            if p['runs'] >= 100: mode_stats["hundreds"] += 1
            mode_stats["total_wickets"] += p['wickets']
            mode_stats["total_bowling_balls"] += p.get('bowling_balls', 0)
            mode_stats["total_runs_conceded"] += p.get('bowling_runs', 0)
            
            u_doc[game_type] = mode_stats
            
            earned = p.get('coins_earned', 0)
            if earned > 0:
                expiry = u_doc.get("booster_expiry")
                if expiry and expiry.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
                    earned *= 2
                u_doc["coins"] = u_doc.get("coins", 0) + earned
                await db.coin_history.insert_one({"user_id": p['id'], "amount": earned, "reason": f"Match Earnings ({game_type})", "created_at": datetime.now(timezone.utc)})
            
            await db.player_stats.update_one({"user_id": p['id']}, {"$set": u_doc}, upsert=True)
    except Exception as e:
        print(f"Stats Error: {e}")

async def get_user_balance(user_id: int):
    u = await db.player_stats.find_one({"user_id": user_id})
    if not u: return 0, 0, 0
    return u.get("coins", 0), u.get("teddy_count", 0), u.get("heart_count", 0)

async def add_coins(user_id: int, amount: int, reason: str):
    await db.player_stats.update_one({"user_id": user_id}, {"$inc": {"coins": amount}}, upsert=True)
    await db.coin_history.insert_one({"user_id": user_id, "amount": amount, "reason": reason, "created_at": datetime.now(timezone.utc)})

async def deduct_coins(user_id: int, amount: int) -> bool:
    u = await db.player_stats.find_one({"user_id": user_id})
    if not u or u.get("coins", 0) < amount: return False
    await db.player_stats.update_one({"user_id": user_id}, {"$inc": {"coins": -amount}})
    await db.coin_history.insert_one({"user_id": user_id, "amount": -amount, "reason": "Shop Purchase", "created_at": datetime.now(timezone.utc)})
    return True

async def process_admin_buy(user_id: int, item: str, action: str) -> bool:
    if action == 'app':
        if item == 'booster':
            await db.player_stats.update_one({"user_id": user_id}, {"$set": {"booster_expiry": datetime.now(timezone.utc) + timedelta(days=1)}})
            await db.coin_history.insert_one({"user_id": user_id, "amount": 0, "reason": "Purchase Approved: 2x Coin Booster", "created_at": datetime.now(timezone.utc)})
        elif item.endswith('_theme'):
            theme_name = item.replace('_theme', '')
            await db.player_stats.update_one({"user_id": user_id}, {"$addToSet": {"unlocked_themes": theme_name}})
            await db.player_stats.update_one({"user_id": user_id}, {"$set": {"active_theme": theme_name}})
            await db.coin_history.insert_one({"user_id": user_id, "amount": 0, "reason": f"Purchase Approved: {theme_name.capitalize()} Theme", "created_at": datetime.now(timezone.utc)})
        else:
            field = "teddy_count" if item == 'teddy' else "heart_count"
            await db.player_stats.update_one({"user_id": user_id}, {"$inc": {field: 1}})
            await db.coin_history.insert_one({"user_id": user_id, "amount": 0, "reason": f"Purchase Approved: {item}", "created_at": datetime.now(timezone.utc)})
    elif action == 'rej':
        refund = 3000 if item == 'booster' else (10000 if item.endswith('_theme') else GIFT_CONFIG['amount'])
        await db.player_stats.update_one({"user_id": user_id}, {"$inc": {"coins": refund}})
        await db.coin_history.insert_one({"user_id": user_id, "amount": refund, "reason": f"Refund: {item} Rejected", "created_at": datetime.now(timezone.utc)})
    return True

async def pause_and_save(chat_id: int, obj, is_tour=False) -> str:
    code = ("TR-" if is_tour else "GM-") + "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=6))
    if not is_tour:
        t1, t2, t3 = obj.lobby_timer_task, obj.bowler_timer_task, obj.batter_timer_task
        obj.lobby_timer_task = obj.bowler_timer_task = obj.batter_timer_task = None
    pickled = base64.b64encode(pickle.dumps(obj)).decode('utf-8')
    if not is_tour:
        obj.lobby_timer_task, obj.bowler_timer_task, obj.batter_timer_task = t1, t2, t3

    await db.saved_sessions.delete_many({"chat_id": chat_id})
    await db.saved_sessions.insert_one({
        "chat_id": chat_id, "session_type": 'tour' if is_tour else 'game',
        "state_data": pickled, "resume_code": code, "created_at": datetime.now(timezone.utc)
    })
    return code

async def load_and_resume(code: str, session_type: str):
    row = await db.saved_sessions.find_one({"resume_code": code, "session_type": session_type})
    if not row: return None
    obj = pickle.loads(base64.b64decode(row["state_data"]))
    await db.saved_sessions.delete_one({"_id": row["_id"]})
    return obj

# ==========================================
# 3. GAME TYPES & STATE MANAGEMENT
# ==========================================
@dataclass
class Player:
    id: int; username: str; first_name: str; runs: int = 0; balls: int = 0
    fours: int = 0; sixes: int = 0; is_out: bool = False; is_eliminated: bool = False
    history: List[str] = field(default_factory=list) 

@dataclass
class Game:
    chat_id: int; status: str; host_id: int; is_special: bool; created_at: datetime
    players: List[Player] = field(default_factory=list); batting_order: List[int] = field(default_factory=list)
    current_batter_idx: int = 0; pending_bat: Optional[int] = None; pending_bowl: Optional[int] = None
    awaiting_bat: bool = False; lobby_message_id: Optional[int] = None; group_link: Optional[str] = None
    over_balls: Optional[int] = None; current_over_zeros: int = 0; commentary_enabled: bool = True; commentary_lang: str = 'en'
    bowler_list: List[int] = field(default_factory=list); bowler_idx: int = 0; current_over_balls: int = 0
    wickets_by_bowler: Dict[int, int] = field(default_factory=dict); bowling_balls: Dict[int, int] = field(default_factory=dict)
    bowling_runs: Dict[int, int] = field(default_factory=dict); milestones_sent: Dict[str, bool] = field(default_factory=dict)
    
    bowler_timeout_count: Dict[int, int] = field(default_factory=dict)
    batter_timeout_count: Dict[int, int] = field(default_factory=dict)
    bowler_history: Dict[int, List[int]] = field(default_factory=dict)
    pending_bowl_msg_id: Optional[int] = None
    
    is_tour_match: bool = False; tour_group_name: str = ""
    lobby_timer_task: Optional[asyncio.Task] = None; bowler_timer_task: Optional[asyncio.Task] = None; batter_timer_task: Optional[asyncio.Task] = None

@dataclass
class Tour:
    chat_id: int; status: str = 'open'; name: str = "Stars Special Tour"
    groups: Dict[str, List[Player]] = field(default_factory=dict); points: Dict[int, int] = field(default_factory=dict)
    runs: Dict[int, int] = field(default_factory=dict); wickets: Dict[int, int] = field(default_factory=dict)

# 🤖 NEW AI GAME STATE
@dataclass
class AIGame:
    user_id: int; diff: str = 'normal'; state: str = 'diff'; msg_id: int = 0
    user_toss: str = ''; innings: int = 1; user_batting: bool = True
    u_runs: int = 0; u_balls: int = 0; ai_runs: int = 0; ai_balls: int = 0
    target: int = -1; history: List[str] = field(default_factory=list)
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

games: Dict[int, Game] = {}; tours: Dict[int, Tour] = {}; ban_map: Dict[int, datetime] = {}; ai_games: Dict[int, AIGame] = {}
BAN_DURATION = timedelta(minutes=5) 

def is_user_in_any_group(tour: Tour, user_id: int) -> Optional[str]:
    for g_name, players in tour.groups.items():
        for p in players:
            if p.id == user_id: return g_name
    return None

# 🎁 GLOBAL STATE FOR SHOP & ADS
GIFT_CONFIG = {"status": "on", "amount": 10000}
WAITING_FOR_GIFT_AMOUNT = set()
WAITING_FOR_ADS = set()
TOUR_SETUP_STATE = {}

def get_game(chat_id: int) -> Optional[Game]: return games.get(chat_id)
def set_game(chat_id: int, game: Game): games[chat_id] = game
def delete_game(chat_id: int):
    game = games.get(chat_id)
    if game:
        if game.lobby_message_id:
            try: asyncio.create_task(bot.unpin_chat_message(chat_id, game.lobby_message_id))
            except Exception: pass
        if game.lobby_timer_task: game.lobby_timer_task.cancel()
        if game.bowler_timer_task: game.bowler_timer_task.cancel()
        if game.batter_timer_task: game.batter_timer_task.cancel()
    games.pop(chat_id, None)

def has_game(chat_id: int) -> bool: return chat_id in games
def is_banned(user_id: int) -> bool:
    until = ban_map.get(user_id)
    if not until: return False
    if datetime.now(timezone.utc) >= until: del ban_map[user_id]; return False
    return True
def ban_user(user_id: int) -> datetime:
    until = datetime.now(timezone.utc) + BAN_DURATION; ban_map[user_id] = until; return until

# ==========================================
# 4. MEDIA STRINGS & HINDI COMMENTARY 🔥
# ==========================================
RUN_FILES = {
    0: ['zero.mp4', 'zero2.mp4', 'zero3.mp4'], 1: ['one.mp4', 'one2.mp4', 'one3.mp4'], 
    2: ['two.mp4', 'two2.mp4', 'two3.mp4'], 3: ['three.mp4', 'three2.mp4', 'three3.mp4'], 
    4: ['four.mp4', 'four2.mp4', 'four3.mp4'], 5: ['five.mp4', 'five2.mp4', 'five3.mp4'], 
    6: ['six.mp4', 'six2.mp4', 'six3.mp4']
}
OUT_FILES = ['out.mp4', 'out2.mp4', 'out3.mp4']

def random_run_file(runs: int) -> str: return random.choice(RUN_FILES.get(runs, ['one.mp4']))
def random_out_file() -> str: return random.choice(OUT_FILES)

RUN_CAPTIONS = {
    0: ['Solid defense! A well-respected dot ball.', 'No run! Pressure building up on the batter.'],
    1: ['Quick single! Excellent strike rotation.', 'Pushed into the gap for a single.'],
    2: ['Pushed for two! Great running between the wickets.', 'Excellent fielding, but they comfortably get two!'],
    3: ['Brilliant placement! Three runs added to the total.', 'Running hard! They convert ones into threes!'],
    4: ['FOUR! Smashed away to the boundary line!', 'What a shot! Finds the gap flawlessly for a boundary.'],
    5: ['Five runs! The fielding side is in absolute chaos!', 'Incredible running and overthrows! 5 runs total!'],
    6: ['SIX! Massive strike, into the stands!', 'Out of the park! Pure power and timing for a maximum!'],
}
OUT_CAPTIONS = ['OUT! The bowler strikes, absolute beauty of a delivery!', 'WICKET! The stumps are rattled, batter has to walk back!']

COMMENTARY = {
    'en': {
        0: ['Batter shows patience, perfectly defends.', 'A dot ball! The batter looked clueless.', 'No run! Bowler is dominating.'],
        1: ['Finds the gap and takes a quick single.', 'Good rotation of strike.', 'Tapped and run. 1 run.'],
        2: ['Excellent call, they scramble for a double.', 'Good placement allows two easily.', 'Fielders chasing shadows! 2 runs.'],
        3: ['Splendid shot, chased down for three.', 'Great athleticism shown for those three runs.'],
        4: ['Pierces the field! A magnificent boundary.', 'Smacked! That went like a tracer bullet for four!', 'Bowler punished for bad line! FOUR!'],
        5: ['Absolute disaster in the field, five runs.', 'Pressure tactic works, 5 runs added!'],
        6: ['Stand and deliver! Miles up in the air.', 'Out of the galaxy! That ball needs a passport!', 'BOMBASTIC SIX! Bowler is in tears.']
    },
    'hi': {
        0: ['गोटे मुँह में आ गए थे! बच गया... शानदार डिफेंस।', 'डॉट बॉल! बॉलर ने पूरी तरह चकमा दे दिया।', 'खाता नहीं खुल रहा, बॉलर भारी पड़ रहा है!'],
        1: ['हल्के हाथ से खेला और चतुराई से सिंगल निकाला।', 'स्ट्राइक रोटेट कर रहे हैं, स्मार्ट प्ले।', 'एक रन चुरा लिया!'],
        2: ['तेज़ दौड़! फील्डर देखते रह गए और दो रन निकाल लिए।', 'क्या रनिंग है भाई, चीता फेल!', 'गैप में धकेला और आसानी से दो रन पूरे किए।'],
        3: ['बेहतरीन प्लेसमेंट, तीन रन भाग कर पूरे किए!', 'फिटनेस का बेहतरीन प्रदर्शन, 3 रन मिले।'],
        4: ['FOUR! फील्डर के पास कोई मौका नहीं, शानदार चौका!', 'बाप रे बाप! क्या चाबुक शॉट था, चार रन।', 'बॉलर की गलती और सीधा बाउंड्री के पार!'],
        5: ['पाँच रन! फील्डिंग साइड पूरी तरह घबरा गई है।', 'ओवरथ्रो का पूरा फायदा, फ्री के 5 रन मिले!'],
        6: ['SIX! गेंद सीधा चाँद पर! बॉलर रो रहा है।', 'आसमान को चूमता हुआ लाजवाब छक्का!', 'स्टेडियम के बाहर! क्या ताक़त है इस शॉट में!']
    }
}

def run_caption(r: int) -> str: return random.choice(RUN_CAPTIONS.get(r, [f"{r} Runs!"]))
def out_caption() -> str: return random.choice(OUT_CAPTIONS)

def ball_commentary(runs: int, lang: str) -> str: 
    return random.choice(COMMENTARY.get(lang, COMMENTARY['en']).get(runs, [f"{runs} runs!"]))
def out_commentary(lang: str) -> str: 
    if lang == 'hi': return "गिल्ली उड़ गई! बॉलर ने पूरी तरह चकमा दे दिया। OUT!"
    return "The bowler completely bamboozled the batter! WICKET!"

# ==========================================
# 5. DATA FORMATTERS & VIP SCORECARD 🔥
# ==========================================
def display_name(p: Player) -> str: return f"@{p.username}" if p.username else p.first_name
def mention_user(p: Player) -> str: return f'<a href="tg://user?id={p.id}">{html.escape(display_name(p))}</a>'

def get_player(game: Game, user_id: int) -> Optional[Player]: return next((p for p in game.players if p.id == user_id), None)
def get_batter(game: Game) -> Optional[Player]:
    if game.current_batter_idx < len(game.batting_order): return get_player(game, game.batting_order[game.current_batter_idx])
    return None
def get_bowler(game: Game) -> Optional[Player]:
    if not game.bowler_list: return None
    return get_player(game, game.bowler_list[game.bowler_idx % len(game.bowler_list)])
def build_bowler_list(game: Game) -> List[int]:
    if game.current_batter_idx >= len(game.batting_order): return []
    batter_id = game.batting_order[game.current_batter_idx]
    others = [p.id for p in game.players if p.id != batter_id and not p.is_eliminated]
    if not game.is_special: random.shuffle(others)
    return others

# 🔥 NEW VIP SCORECARD GENERATOR 🔥
def live_score_text(game: Game) -> str:
    mode_name = "TOUR SCORECARD" if game.is_special else "SOLO SCORECARD"
    overs_txt = f"{game.over_balls} Balls/Over" if game.over_balls else "6 Balls/Over"
    header = f"{pe('🏏')} <b>{mode_name}</b>\n━━━━━━━━━━━━━━\n{pe('🎯')} {overs_txt}  •  Players: {len(game.players)}\n━━━━━━━━━━━━━━\n\n"
    
    body = ""
    for idx, p in enumerate(game.players):
        marker = ""
        if get_batter(game) and p.id == get_batter(game).id: marker = f"{pe('🏏')} "
        elif get_bowler(game) and p.id == get_bowler(game).id: marker = f"{pe('🎯')} "
        
        host_mark = " †" if p.id == game.host_id else ""
        elim_mark = " (Eliminated)" if p.is_eliminated else ""
        sr = f"{(p.runs / p.balls) * 100:.1f}" if p.balls > 0 else '0.0'
        wkts = game.wickets_by_bowler.get(p.id, 0)
        history_str = " • ".join(p.history) if p.history else "No balls played"
        name_display = f"{marker}{html.escape(p.first_name)}{host_mark}{elim_mark}"
        
        body += f"{idx+1}.  {name_display}\n"
        body += f"┣ {p.runs}({p.balls})  SR:{sr}  {wkts}W\n"
        body += f"┗ {history_str}\n\n"
        
    footer = "━━━━━━━━━━━━━━\n"
    curr_bat = get_batter(game)
    curr_bowl = get_bowler(game)
    bat_name = (html.escape(curr_bat.first_name) + (" †" if curr_bat.id == game.host_id else "")) if curr_bat else "—"
    bowl_name = (html.escape(curr_bowl.first_name) + (" †" if curr_bowl.id == game.host_id else "")) if curr_bowl else "—"
    footer += f"{pe('🏏')} Bat: {bat_name}\n{pe('🎯')} Bowl: {bowl_name}"
    
    return header + body + footer

# 🎴 IMPROVED VISUAL PLAYER CARD GENERATOR (NEW 8-BOX GRID)
def generate_stats_card_image(s: dict, game_type: str, theme: str = "default") -> Optional[io.BytesIO]:
    if not HAS_PIL: return None
    try:
        width, height = 950, 550
        
        # Color Themes Setup 🔥
        if theme == 'spider':
            bg_color = (25, 10, 10); accent1 = (255, 40, 40); accent2 = (40, 60, 255); text_main = (255, 255, 255); box_bg = (40, 15, 15); box_out = (255, 80, 80)
        elif theme == 'dark':
            bg_color = (15, 15, 15); accent1 = (255, 215, 0); accent2 = (150, 150, 150); text_main = (255, 255, 255); box_bg = (30, 30, 30); box_out = (255, 215, 0)
        elif theme == 'neon':
            bg_color = (15, 5, 25); accent1 = (0, 255, 255); accent2 = (255, 0, 255); text_main = (255, 255, 255); box_bg = (30, 10, 45); box_out = (0, 255, 255)
        elif theme == 'ocean':
            bg_color = (5, 25, 35); accent1 = (0, 200, 255); accent2 = (0, 100, 200); text_main = (255, 255, 255); box_bg = (10, 40, 60); box_out = (0, 200, 255)
        elif theme == 'forest':
            bg_color = (10, 25, 10); accent1 = (50, 205, 50); accent2 = (34, 139, 34); text_main = (255, 255, 255); box_bg = (15, 45, 15); box_out = (50, 205, 50)
        else: # Default (White/Blue Tech style)
            bg_color = (240, 245, 250); accent1 = (60, 130, 255); accent2 = (180, 200, 255); text_main = (30, 40, 60); box_bg = (255, 255, 255); box_out = (180, 210, 255)

        img = Image.new('RGB', (width, height), color=bg_color)
        draw = ImageDraw.Draw(img)
        try:
            f_xl = ImageFont.truetype("DejaVuSansMono-Bold.ttf", 45)
            f_l = ImageFont.truetype("DejaVuSansMono-Bold.ttf", 36)
            f_m = ImageFont.truetype("DejaVuSansMono-Bold.ttf", 26)
            f_s = ImageFont.truetype("DejaVuSansMono-Bold.ttf", 16)
        except:
            f_xl = f_l = f_m = f_s = ImageFont.load_default()

        # Tech Lines Background
        draw.line([(0, height-60), (width, height-60)], fill=accent2, width=2)
        draw.line([(0, 60), (350, 60)], fill=accent1, width=3)
        draw.line([(width-250, 60), (width, 60)], fill=accent2, width=2)

        # Avatar Circle & User Info
        draw.ellipse([(60, 40), (220, 200)], outline=accent1, width=6)
        name = s.get('username') or s.get('first_name', 'Player')
        draw.text((250, 80), f"@{name}".upper()[:15], font=f_xl, fill=text_main)
        draw.text((250, 150), f"{game_type.upper()} CAREER STATS", font=f_l, fill=accent1)
        draw.text((width-60, 120), f"ID: {s.get('user_id', 'N/A')}", font=f_m, fill=text_main, anchor="rm")

        # Stats Processing
        matches = s.get('matches', 0)
        runs = s.get('total_runs', 0)
        balls = s.get('total_balls', 0)
        sr = f"{(runs / balls) * 100:.1f}" if balls > 0 else '0.0'
        wkts = s.get('total_wickets', 0)
        b_balls = s.get('total_bowling_balls', 0)
        b_runs = s.get('total_runs_conceded', 0)
        eco = f"{(b_runs / max(1,b_balls)) * 6:.2f}" if b_balls > 0 else '0.00'
        high = s.get('highest_score', 0)
        perf = runs + (wkts * 20) + (s.get('motms', 0) * 30)

        # 8 Boxes Config
        box_w = 200; box_h = 80
        x_start = 45; padding = 20
        y1 = 280; y2 = 380

        def draw_box(col, row_y, title, val):
            x = x_start + (col * (box_w + padding))
            try: draw.rounded_rectangle([(x, row_y), (x+box_w, row_y+box_h)], radius=12, fill=box_bg, outline=box_out, width=2)
            except AttributeError: draw.rectangle([(x, row_y), (x+box_w, row_y+box_h)], fill=box_bg, outline=box_out, width=2)
            draw.text((x + box_w//2, row_y + 25), title, font=f_s, fill=text_main, anchor="mm")
            draw.text((x + box_w//2, row_y + 55), str(val), font=f_m, fill=accent1, anchor="mm")

        # Row 1
        draw_box(0, y1, "TOTAL MATCHES", matches)
        draw_box(1, y1, "TOTAL RUNS", runs)
        draw_box(2, y1, "STRIKE RATE", sr)
        draw_box(3, y1, "TOTAL WICKETS", wkts)
        
        # Row 2
        draw_box(0, y2, "ECONOMY", eco)
        draw_box(1, y2, "HIGHEST SCORE", high)
        draw_box(2, y2, "MOTM AWARDS", s.get('motms', 0))
        draw_box(3, y2, "RATING", perf)

        # Footer Name Updated 🔥
        draw.text((width-50, height-30), "Stars Solo ✨", font=f_m, fill=accent1, anchor="rm")
        
        buf = io.BytesIO(); img.save(buf, format='PNG'); buf.seek(0)
        return buf
    except Exception as e:
        print("Stats card err:", e)
        return None

def format_stats_profile_html(s: dict, game_type: str) -> str:
    form_arr = s.get('form', [])
    form_str = " ".join(["🟢" if r == 'W' else "🔴" for r in form_arr]) if form_arr else '—'
    perf = s.get('total_runs', 0) + (s.get('total_wickets', 0) * 20) + (s.get('motms', 0) * 30)
    tag = '#TourLegacy' if game_type == 'tour' else ('#SoloLegacy' if game_type == 'solo' else '#OverallLegacy')
    return f"🌟 <b>PERFORMANCE RATING: {perf}</b>\n{pe('📈')} <b>Form:</b> {form_str}\n\n<i>{tag} | {datetime.now(timezone.utc).strftime('%Y-%m-%d')}</i>"

def generate_scoreboard_image(game: Game) -> Optional[io.BytesIO]:
    if not HAS_PIL: return None
    try:
        width = 800
        height = 360 + (len(game.players) * 140)
        img = Image.new('RGB', (width, height), color=(8, 13, 17))
        draw = ImageDraw.Draw(img)
        try:
            f_xl = ImageFont.truetype("DejaVuSansMono-Bold.ttf", 36)
            f_l = ImageFont.truetype("DejaVuSansMono-Bold.ttf", 28)
            f_m = ImageFont.truetype("DejaVuSansMono.ttf", 22)
            f_s = ImageFont.truetype("DejaVuSansMono.ttf", 18)
        except:
            f_xl = f_l = f_m = f_s = ImageFont.load_default()

        title = f"🏆 {game.tour_group_name.upper()} FINAL SCORE 🏆" if game.is_special else "🎖️ SOLO FINAL SCORE 🎖️"
        draw.text((width//2, 50), title, font=f_xl, fill=(88, 255, 33), anchor="mm") 
        draw.line([(50, 90), (width-50, 90)], fill=(255, 33, 170), width=3) 
        
        y = 120
        for p in game.players:
            sr = f"{(p.runs / p.balls) * 100:.1f}" if p.balls > 0 else '0.0'
            b_balls = game.bowling_balls.get(p.id, 0); b_wkts = game.wickets_by_bowler.get(p.id, 0); b_runs = game.bowling_runs.get(p.id, 0)
            eco = f"{(b_runs / b_balls) * 6:.1f}" if b_balls > 0 else '0.0'
            name_str = f"@{p.username}" if p.username else p.first_name
            if p.is_eliminated: name_str += " (OUT)"
            if p.id == game.host_id: name_str += " †"
            
            draw.text((50, y), name_str, font=f_l, fill=(255, 255, 255) if not p.is_eliminated else (150,150,150))
            draw.text((width-50, y), f"{p.runs} ({p.balls})", font=f_l, fill=(255, 170, 0), anchor="rm") 
            draw.text((70, y+35), f"Bat: 4s: {p.fours} | 6s: {p.sixes} | SR: {sr}", font=f_s, fill=(200, 200, 200))
            draw.text((70, y+65), f"Bowl: {b_balls}b | {b_wkts}W | {b_runs}R | Eco: {eco}", font=f_s, fill=(200, 200, 200))
            y += 130

        draw.line([(50, y), (width-50, y)], fill=(255, 33, 170), width=3)
        y += 30
        total_runs = sum(p.runs for p in game.players); total_balls = sum(p.balls for p in game.players)
        overs_str = f"{total_balls // 6}.{total_balls % 6}"
        
        orange_cap = sorted(game.players, key=lambda x: x.runs, reverse=True)[0] if game.players else None
        wkts_list = sorted([(get_player(game, k), v) for k, v in game.wickets_by_bowler.items() if get_player(game, k)], key=lambda x: x[1], reverse=True)
        purple_cap = wkts_list[0] if wkts_list else None
        
        best_score = -1; motm = None
        for p in game.players:
            score = p.runs + (game.wickets_by_bowler.get(p.id, 0) * 30)
            if score > best_score: best_score = score; motm = p
            
        mn = f"@{motm.username}" if motm and motm.username else (motm.first_name if motm else "—")
        ocn = f"@{orange_cap.username}" if orange_cap and orange_cap.username else (orange_cap.first_name if orange_cap else "—")
        pcn = f"@{purple_cap[0].username}" if purple_cap and purple_cap[0].username else (purple_cap[0].first_name if purple_cap else "—")
        
        draw.text((50, y), f"Man of the Match: {mn}", font=f_m, fill=(255, 215, 0))
        draw.text((50, y+35), f"Orange Cap: {ocn} ({orange_cap.runs if orange_cap else 0}R)", font=f_s, fill=(255, 170, 0))
        draw.text((50, y+65), f"Purple Cap: {pcn} ({purple_cap[1] if purple_cap else 0}W)", font=f_s, fill=(255, 33, 170))
        draw.text((50, y+100), f"Match Total: {total_runs} Runs in {overs_str} Overs", font=f_m, fill=(88, 255, 33))
        
        buf = io.BytesIO(); img.save(buf, format='PNG'); buf.seek(0)
        return buf
    except Exception as e: 
        print(f"Scoreboard Image Error: {e}")
        return None

def generate_leaderboard_image(title_text: str, records: list) -> Optional[io.BytesIO]:
    if not HAS_PIL: return None
    try:
        width = 850
        height = 250 + (len(records) * 60)
        if height < 350: height = 350
        img = Image.new('RGB', (width, height), color=(8, 13, 17)) 
        draw = ImageDraw.Draw(img)
        try:
            f_title = ImageFont.truetype("DejaVuSansMono-Bold.ttf", 50)
            f_hdr = ImageFont.truetype("DejaVuSansMono-Bold.ttf", 22)
            f_l = ImageFont.truetype("DejaVuSansMono.ttf", 26)
            f_s = ImageFont.truetype("DejaVuSansMono.ttf", 20)
        except:
            f_title = f_hdr = f_l = f_s = ImageFont.load_default()

        draw.text((50, 20), "* HIGH SCORES *", fill=(255, 33, 170), font=f_hdr) 
        draw.text((50, 50), title_text, fill=(88, 255, 33), font=f_title) 
        
        draw.text((50, 130), "RANK", fill=(88, 255, 33), font=f_hdr)
        draw.text((160, 130), "PLAYER", fill=(88, 255, 33), font=f_hdr)
        draw.text((500, 130), "PTS", fill=(88, 255, 33), font=f_hdr)
        draw.text((630, 130), "RUNS", fill=(88, 255, 33), font=f_hdr)
        draw.text((750, 130), "WKTS", fill=(88, 255, 33), font=f_hdr)
        
        draw.line([(50, 160), (width-50, 160)], fill=(50, 70, 80), width=2)
        
        y = 180
        for i, r in enumerate(records):
            color = (255, 170, 0) if i < 3 else (220, 220, 220) 
            draw.text((50, y), f"{i+1:02d}", fill=color, font=f_l)
            name = str(r['name'])[:18] + ".." if len(str(r['name'])) > 18 else str(r['name'])
            draw.text((160, y), name, fill=color, font=f_l)
            draw.text((500, y), str(r['pts']), fill=color, font=f_l)
            draw.text((630, y), str(r['runs']), fill=(88, 255, 33) if i < 3 else (150, 200, 150), font=f_l)
            draw.text((750, y), str(r['wkts']), fill=(88, 255, 33) if i < 3 else (150, 200, 150), font=f_l)
            y += 60
            
        draw.text((width//2, y+30), "> INSERT COIN TO CONTINUE <", fill=(255, 33, 170), anchor="mm", font=f_hdr)
        
        buf = io.BytesIO(); img.save(buf, format='PNG'); buf.seek(0)
        return buf
    except Exception as e: 
        print(f"LBC Image Error: {e}")
        return None

def over_length(game: Game) -> int: return game.over_balls if game.over_balls else 6
def zero_limit(game: Game) -> int: return 1 if over_length(game) == 3 else 2
def can_play_zero(game: Game) -> bool: return game.current_over_zeros < zero_limit(game)
def zero_limit_message() -> str: return f"{pe('❌')} <b>Your limit has been reached for Zero. Play 1 to 6.</b>"

# ==========================================
# 6. JSON KEYBOARDS & LOBBY
# ==========================================
def lobby_text(game: Game) -> str:
    names = "\n".join([f"  • {html.escape(p.first_name)}" for p in game.players]) or "  (none yet)"
    if game.is_special: return f"{pe('👑')} <b>Stars Special Match Lobby</b>\n\n👥 <b>Players added ({len(game.players)}):</b>\n{names}\n\nAdmin: Use /addplayer to add players.\nUse /startsolo when ready."
    zl = 1 if game.over_balls == 3 else 2
    return f"{pe('🏏')} <b>Hand Cricket — Solo Lobby</b>\n\n👥 <b>Players joined ({len(game.players)}):</b>\n{names}\n\n🎯 Over: <b>{game.over_balls} balls</b> | Zero limit: <b>{zl}</b>\n{pe('⏳')} Game auto-starts 60s after 1st player joins."

def lobby_keyboard(chat_id: int, is_special=False, over_balls=None):
    if is_special:
        rows = [[{"text": 'Force Start', "callback_data": f"force:{chat_id}", "style": "success"}], [{"text": 'Cancel Match', "callback_data": f"cancel_req:{chat_id}", "style": "danger"}]]
    elif not over_balls:
        rows = [[{"text": '3 Balls Over', "callback_data": f"over:{chat_id}:3", "style": "primary"}, {"text": '6 Balls Over', "callback_data": f"over:{chat_id}:6", "style": "success"}], [{"text": 'Cancel Game', "callback_data": f"cancel_req:{chat_id}", "style": "danger"}]]
    else:
        rows = [[{"text": 'Join Match', "callback_data": f"join:{chat_id}", "style": "primary"}, {"text": 'Leave', "callback_data": f"leave:{chat_id}", "style": "danger"}], [{"text": 'Force Start', "callback_data": f"force:{chat_id}", "style": "success"}], [{"text": 'Cancel Game', "callback_data": f"cancel_req:{chat_id}", "style": "danger"}]]
    return InlineKeyboardMarkup.de_json({"inline_keyboard": rows})

async def edit_lobby(msg_or_call_msg, game: Game, chat_id: int):
    opts = {"parse_mode": 'HTML', "reply_markup": lobby_keyboard(chat_id, game.is_special, game.over_balls)}
    text = lobby_text(game)
    try: await bot.edit_message_caption(caption=text, chat_id=msg_or_call_msg.chat.id, message_id=msg_or_call_msg.message_id, **opts)
    except Exception:
        try: await bot.edit_message_text(text=text, chat_id=msg_or_call_msg.chat.id, message_id=msg_or_call_msg.message_id, **opts)
        except Exception: pass

def get_lbc_keyboard():
    rows = [
        [{"text": "Daily", "callback_data": "lbc:daily", "style": "primary"}, {"text": "Weekly", "callback_data": "lbc:weekly", "style": "primary"}],
        [{"text": "30 Days", "callback_data": "lbc:30", "style": "primary"}, {"text": "60 Days", "callback_data": "lbc:60", "style": "primary"}, {"text": "90 Days", "callback_data": "lbc:90", "style": "primary"}],
        [{"text": "All Time", "callback_data": "lbc:all", "style": "success"}]
    ]
    return InlineKeyboardMarkup.de_json({"inline_keyboard": rows})

async def get_leaderboard_data(chat_id: int, tf: str):
    delta = None
    title_text = "ALL-TIME LEADERBOARD"
    if tf == 'daily': delta = timedelta(days=1); title_text = "DAILY LEADERBOARD"
    elif tf == 'weekly': delta = timedelta(weeks=1); title_text = "WEEKLY LEADERBOARD"
    elif tf == '30': delta = timedelta(days=30); title_text = "30 DAYS LEADERBOARD"
    elif tf == '60': delta = timedelta(days=60); title_text = "60 DAYS LEADERBOARD"
    elif tf == '90': delta = timedelta(days=90); title_text = "90 DAYS LEADERBOARD"
    
    match_stage = {"chat_id": chat_id}
    if delta: match_stage["created_at"] = {"$gte": datetime.now(timezone.utc) - delta}
    
    try:
        pipeline = [
            {"$match": match_stage},
            {"$group": {"_id": "$user_id", "runs": {"$sum": "$runs"}, "wkts": {"$sum": "$wickets"}, "pts": {"$sum": "$points"}}},
            {"$sort": {"pts": -1}},
            {"$limit": 10}
        ]
        cursor = db.match_records.aggregate(pipeline)
        rows = await cursor.to_list(length=10)
        if not rows: return None, f"{pe('📭')} No matches played in this group for selected timeframe."
        
        records = []
        for r in rows:
            u_id = r["_id"]
            u = await db.user_map.find_one({"id": u_id})
            name = u["firstName"] if u else f"User {u_id}"
            records.append({'name': name, 'runs': r['runs'], 'wkts': r['wkts'], 'pts': r['pts']})
            
        img_buf = await asyncio.to_thread(generate_leaderboard_image, title_text, records)
        text = f"{pe('📊')} <b>{title_text}</b>"
        return img_buf, text
    except Exception as e:
        print(f"LBC Error: {e}")
        return None, f"{pe('❌')} Error loading leaderboard."

# ==========================================
# 7. ULTRA FAST SENDERS ⚡
# ==========================================
async def send_media_with_fallback(chat_id: int, filename: str, caption: str, reply_markup=None):
    try:
        media_doc = await db.media.find_one({"filename": filename})
        if media_doc and "file_id" in media_doc:
            fid = media_doc["file_id"]
            try:
                if filename.endswith(('.png', '.jpg', '.jpeg')):
                    await bot.send_photo(chat_id, fid, caption=caption, parse_mode='HTML', reply_markup=reply_markup)
                else:
                    await bot.send_video(chat_id, fid, caption=caption, parse_mode='HTML', reply_markup=reply_markup)
                return
            except Exception as e:
                await db.media.delete_one({"filename": filename})
    except Exception: pass
    
    path = get_media_path(filename)
    if path:
        try:
            with open(path, 'rb') as f:
                if filename.endswith(('.png', '.jpg', '.jpeg')):
                    msg = await bot.send_photo(chat_id, f, caption=caption, parse_mode='HTML', reply_markup=reply_markup)
                    await db.media.update_one({"filename": filename}, {"$set": {"file_id": msg.photo[-1].file_id}}, upsert=True)
                else:
                    msg = await bot.send_video(chat_id, f, caption=caption, parse_mode='HTML', reply_markup=reply_markup)
                    await db.media.update_one({"filename": filename}, {"$set": {"file_id": msg.video.file_id}}, upsert=True)
            return
        except Exception: pass
        
    try: await bot.send_message(chat_id, caption, parse_mode='HTML', reply_markup=reply_markup)
    except Exception: pass

# ==========================================
# 8. AFK & TIMERS (Elimination & Penalty 70s) 🔥
# ==========================================
async def kill_pending_buttons(chat_id: int, user_id: int, msg_id: int):
    try: await bot.edit_message_text(text=f"{pe('☠️')} <b>Timeout! Button Dead.</b>", chat_id=user_id, message_id=msg_id, parse_mode='HTML')
    except Exception: pass

async def _lobby_timer_task(chat_id: int):
    try:
        await asyncio.sleep(30)
        g = get_game(chat_id)
        if not g or g.status != 'waiting': return
        try: await bot.send_message(chat_id, f"{pe('⏳')} <b>30 seconds left</b> to join the game! Hurry up.", parse_mode='HTML')
        except Exception: pass
        await asyncio.sleep(20)
        g = get_game(chat_id)
        if not g or g.status != 'waiting': return
        try: await bot.send_message(chat_id, f"{pe('⏳')} <b>10 seconds left</b> to join! Game starting soon.", parse_mode='HTML')
        except Exception: pass
        await asyncio.sleep(10)
        g = get_game(chat_id)
        if not g or g.status != 'waiting': return

        if len(g.players) < 2:
            delete_game(chat_id)
            try: await bot.send_message(chat_id, f"{pe('❌')} <b>Game Cancelled</b> — Only 1 player joined. Auto-cancelling.", parse_mode='HTML')
            except Exception: pass
        else:
            asyncio.create_task(begin_game(chat_id))
    except asyncio.CancelledError: pass
    except Exception as e: print(f"Lobby Timer Error: {e}")

async def _bowler_timer_task(chat_id: int):
    try:
        await asyncio.sleep(40) 
        g = get_game(chat_id)
        if not g or g.status != 'playing' or g.pending_bowl is not None: return
        bl = get_bowler(g)
        if bl: 
            try: await bot.send_message(chat_id, f"{pe('⚠️')} {mention_user(bl)} — <b>30s left!</b> Bowl NOW or face penalty (-6 runs & Free hit).", parse_mode='HTML')
            except Exception: pass
        
        await asyncio.sleep(20)
        g = get_game(chat_id)
        if not g or g.status != 'playing' or g.pending_bowl is not None: return
        bl = get_bowler(g)
        if bl: 
            try: await bot.send_message(chat_id, f"{pe('⚠️')} {mention_user(bl)} — <b>10s left!</b> Hurry up!", parse_mode='HTML')
            except Exception: pass
        
        await asyncio.sleep(10)
        await eliminate_bowler(chat_id)
    except asyncio.CancelledError: pass
    except Exception as e: print(f"Bowler Timer Error: {e}")

async def _batter_timer_task(chat_id: int):
    try:
        await asyncio.sleep(40)
        g = get_game(chat_id)
        if not g or g.status != 'playing' or g.pending_bat is not None: return
        bt = get_batter(g)
        if bt: 
            try: await bot.send_message(chat_id, f"{pe('⚠️')} {mention_user(bt)} — <b>30s left!</b> Type your shot NOW or face penalty (-6 runs & Ball skipped).", parse_mode='HTML')
            except Exception: pass
        
        await asyncio.sleep(20)
        g = get_game(chat_id)
        if not g or g.status != 'playing' or g.pending_bat is not None: return
        bt = get_batter(g)
        if bt: 
            try: await bot.send_message(chat_id, f"{pe('⚠️')} {mention_user(bt)} — <b>10s left!</b> Hurry up!", parse_mode='HTML')
            except Exception: pass
        
        await asyncio.sleep(10)
        await eliminate_batter(chat_id)
    except asyncio.CancelledError: pass
    except Exception as e: print(f"Batter Timer Error: {e}")

def clear_all_round_timers(game: Game):
    try: curr = asyncio.current_task()
    except RuntimeError: curr = None
    if game.bowler_timer_task and game.bowler_timer_task != curr: game.bowler_timer_task.cancel()
    if game.batter_timer_task and game.batter_timer_task != curr: game.batter_timer_task.cancel()

def start_bowler_timer(chat_id: int):
    game = get_game(chat_id)
    if not game: return
    clear_all_round_timers(game)
    game.bowler_timer_task = asyncio.create_task(_bowler_timer_task(chat_id))

def start_batter_timer(chat_id: int):
    game = get_game(chat_id)
    if not game: return
    clear_all_round_timers(game)
    game.batter_timer_task = asyncio.create_task(_batter_timer_task(chat_id))

async def eliminate_bowler(chat_id: int):
    try:
        game = get_game(chat_id)
        if not game or game.status != 'playing' or game.pending_bowl is not None: return
        bowler, batter = get_bowler(game), get_batter(game)
        if not bowler or not batter: return
        
        count = game.bowler_timeout_count.get(bowler.id, 0) + 1
        game.bowler_timeout_count[bowler.id] = count

        if game.pending_bowl_msg_id: await kill_pending_buttons(chat_id, bowler.id, game.pending_bowl_msg_id)
        clear_all_round_timers(game)

        if count == 1:
            bowler.runs -= 6
            batter.runs += 6
            game.pending_bowl = None; game.pending_bat = None; game.awaiting_bat = False
            
            try: await bot.send_message(chat_id, f"{pe('⚠️')} <b>WARNING!</b> {mention_user(bowler)} you took too long to bowl!\n\n📉 Penalty: <b>-6 Runs</b> from your score!\n{pe('🎁')} {mention_user(batter)} gets a <b>FREE HIT (+6 Runs)</b>!\n\n<i>Next timeout = Elimination!</i>", parse_mode='HTML')
            except Exception: pass
            await start_round(chat_id)
        else:
            until = ban_user(bowler.id)
            mins = int((until - datetime.now(timezone.utc)).total_seconds() // 60)
            bowler.runs -= 6
            bowler.is_out = True
            bowler.is_eliminated = True
            game.pending_bowl = None; game.pending_bat = None; game.awaiting_bat = False
            
            try: await bot.send_message(chat_id, f"{pe('🚫')} <b>ELIMINATED!</b>\n\n{mention_user(bowler)} failed to bowl AGAIN and is kicked out of the match!\n📉 Penalty: <b>-6 Runs</b>.\n{pe('🚫')} Banned for <b>{mins} min</b>.", parse_mode='HTML')
            except Exception: pass
            
            game.bowler_list = build_bowler_list(game)
            if not game.bowler_list:
                await end_game(chat_id)
                return
            game.current_over_balls = 0; game.current_over_zeros = 0
            nb, nbl = get_batter(game), get_bowler(game)
            if not nb or not nbl:
                await end_game(chat_id)
                return
            try: await bot.send_message(chat_id, f"{pe('🔄')} <b>Bowler Eliminated! New Matchup:</b>\n\n{pe('🏏')} Batting: {mention_user(nb)}\n{pe('🎯')} Bowling: {mention_user(nbl)}", parse_mode='HTML')
            except Exception: pass
            await start_round(chat_id)
    except Exception as e: print(f"Elim Bowler Error: {e}")

async def eliminate_batter(chat_id: int):
    try:
        game = get_game(chat_id)
        if not game or game.status != 'playing' or game.pending_bat is not None: return
        batter = get_batter(game)
        bowler = get_bowler(game)
        if not batter: return
        
        count = game.batter_timeout_count.get(batter.id, 0) + 1
        game.batter_timeout_count[batter.id] = count
        clear_all_round_timers(game)

        if count == 1:
            batter.runs -= 6
            batter.balls += 1
            batter.history.append('0')
            if bowler: game.bowling_balls[bowler.id] = game.bowling_balls.get(bowler.id, 0) + 1
            game.pending_bat = None; game.pending_bowl = None; game.awaiting_bat = False
            game.current_over_balls += 1
            
            try: await bot.send_message(chat_id, f"{pe('⚠️')} <b>WARNING!</b> {mention_user(batter)} you took too long to bat!\n\n📉 Penalty: <b>-6 Runs</b>!\n⏩ Ball skipped (0 runs scored).\n\n<i>Next timeout = Elimination!</i>", parse_mode='HTML')
            except Exception: pass
            
            over_changed = False
            if game.current_over_balls >= over_length(game):
                over_changed = True
                game.current_over_balls = 0; game.current_over_zeros = 0; game.bowler_idx += 1
                nb = get_bowler(game)
                if nb:
                    try: await bot.send_message(chat_id, f"{pe('🔄')} <b>Over complete ({over_length(game)} balls)!</b> New bowler: {mention_user(nb)}", parse_mode='HTML')
                    except Exception: pass
            await start_round(chat_id)
        else:
            until = ban_user(batter.id)
            mins = int((until - datetime.now(timezone.utc)).total_seconds() // 60)
            batter.runs -= 6 
            batter.is_out = True
            batter.is_eliminated = True
            batter.balls += 1
            batter.history.append('W') 
            
            if bowler:
                game.wickets_by_bowler[bowler.id] = game.wickets_by_bowler.get(bowler.id, 0) + 1
                game.bowling_balls[bowler.id] = game.bowling_balls.get(bowler.id, 0) + 1
            
            game.pending_bat = None; game.pending_bowl = None; game.awaiting_bat = False
            try: await bot.send_message(chat_id, f"{pe('🚫')} <b>ELIMINATED!</b>\n\n{mention_user(batter)} failed to bat AGAIN and is kicked out of the match!\n📉 Penalty: <b>-6 Runs</b>.\n{pe('🚫')} Banned for <b>{mins} min</b>.", parse_mode='HTML')
            except Exception: pass
            await advance_batter(chat_id)
    except Exception as e: print(f"Elim Batter Error: {e}")

# ==========================================
# 9. THE GAME LOOP 🏏
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("runup:"))
async def cb_runup(call):
    chat_id = int(call.data.split(":")[1])
    game = get_game(chat_id)
    if not game or game.status != 'playing': return
    bowler, batter = get_bowler(game), get_batter(game)
    if not bowler or bowler.id != call.from_user.id: return
    
    try: await bot.edit_message_text(f"{pe('🏏')} <b>Bowling Started!</b>", call.message.chat.id, call.message.message_id, parse_mode='HTML')
    except Exception: pass
    
    rows = [[{"text": "1", "callback_data": f"bowl:{chat_id}:1", "style": "primary"}, {"text": "2", "callback_data": f"bowl:{chat_id}:2", "style": "primary"}, {"text": "3", "callback_data": f"bowl:{chat_id}:3", "style": "primary"}],
            [{"text": "4", "callback_data": f"bowl:{chat_id}:4", "style": "primary"}, {"text": "5", "callback_data": f"bowl:{chat_id}:5", "style": "primary"}, {"text": "6", "callback_data": f"bowl:{chat_id}:6", "style": "primary"}]]
    kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
    msg = await bot.send_message(call.message.chat.id, f"{pe('🎯')} Choose your delivery (1–6):", parse_mode='HTML', reply_markup=kbd)
    game.pending_bowl_msg_id = msg.message_id

async def send_bowling_dm(user_id: int, chat_id: int, batter_mention: str) -> bool:
    rows = [[{"text": "🚀 Start Run-up", "callback_data": f"runup:{chat_id}", "style": "success"}]]
    kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
    try:
        await bot.send_message(user_id, f"{pe('🎯')} <b>You're bowling!</b>\n\n{batter_mention} is at the crease.\nClick below to start:", parse_mode='HTML', reply_markup=kbd)
        return True
    except Exception: return False

async def start_round(chat_id: int):
    game = get_game(chat_id)
    if not game or game.status != 'playing': return
    batter, bowler = get_batter(game), get_bowler(game)
    if not batter or not bowler: return
    game.pending_bat = None; game.pending_bowl = None; game.awaiting_bat = False
    clear_all_round_timers(game)

    dm_ok = await send_bowling_dm(bowler.id, chat_id, mention_user(batter))
    if not dm_ok:
        btn = InlineKeyboardMarkup.de_json({"inline_keyboard": [[{"text": '🚀 Start Bot to Bowl', "url": f"https://t.me/{bot_username}?start=bowl_{chat_id}", "style": "success"}]]})
        await bot.send_message(chat_id, f"{pe('⚠️')} {mention_user(bowler)}, you haven't started me in DM!\nClick the button below to start, then you will get your bowling panel.", parse_mode='HTML', reply_markup=btn)
    else:
        dm_btn = InlineKeyboardMarkup.de_json({"inline_keyboard": [[{"text": 'Open Bot DM', "url": f"https://t.me/{bot_username}", "style": "primary"}]]})
        cap = f"{pe('🎯')} {mention_user(bowler)} is ready to bowl!\nCheck your DM to pick delivery secretly 👇"
        await send_media_with_fallback(chat_id, 'ball.mp4', cap, reply_markup=dm_btn)
        
    start_bowler_timer(chat_id)

@bot.callback_query_handler(func=lambda call: re.match(r"^bowl:(-?\d+):([1-6])$", call.data))
async def cb_bowl(call):
    match = re.match(r"^bowl:(-?\d+):([1-6])$", call.data)
    chat_id, num = int(match.group(1)), int(match.group(2))
    game = get_game(chat_id)
    if not game or game.status != 'playing': return
    bowler = get_bowler(game)
    if not bowler or bowler.id != call.from_user.id: return
    if game.pending_bowl is not None: return

    if getattr(game, 'is_special', False) or getattr(game, 'is_tour_match', False):
        history = game.bowler_history.get(bowler.id, [])
        if len(history) >= 2 and history[-1] == num and history[-2] == num:
            game.bowler_history[bowler.id] = history + [-1] 
            batter = get_batter(game)
            if batter: 
                batter.runs += 1 
                batter.history.append('1') 
            try: await bot.answer_callback_query(call.id, '🚨 WIDE! Spamming not allowed.', show_alert=True)
            except Exception: pass
            clear_all_round_timers(game)
            
            dm_btn = InlineKeyboardMarkup.de_json({"inline_keyboard": [[{"text": 'Open Bot DM', "url": f"https://t.me/{bot_username}", "style": "primary"}]]})
            await send_media_with_fallback(chat_id, 'wide.mp4', f"🚨 <b>WIDE BALL!</b>\n\n{mention_user(bowler)} tried to spam the same delivery 3 times!\n{pe('🎁')} 1 Free run to {mention_user(batter)}.\n\nBowl again!", reply_markup=dm_btn)
            
            await kill_pending_buttons(chat_id, bowler.id, call.message.message_id)
            await send_bowling_dm(bowler.id, chat_id, mention_user(batter))
            start_bowler_timer(chat_id)
            return
        else:
            history.append(num)
            game.bowler_history[bowler.id] = history

    game.bowler_timeout_count[bowler.id] = 0
    if game.bowler_timer_task: game.bowler_timer_task.cancel()
    game.pending_bowl = num; game.awaiting_bat = True
    try: await bot.answer_callback_query(call.id, f"{pe('🔒')} Locked!")
    except Exception: pass

    await kill_pending_buttons(chat_id, bowler.id, call.message.message_id)

    back_kbd = None
    if game.group_link:
        back_kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": [[{"text": '🔙 Back to Game', "url": game.group_link, "style": "primary"}]]})
    
    try: await bot.send_message(call.message.chat.id, f"{pe('🔒')} <b>Delivery locked!</b>\n\nYou chose <b>{num}</b>. Head back to the group.", parse_mode='HTML', reply_markup=back_kbd)
    except Exception: pass

    batter = get_batter(game)
    if batter: 
        cap = f"{pe('⚡️')} {mention_user(batter)} — your turn!\n_Bowler has locked in…_\n\nType your shot <b>(0–6)</b> in this group."
        await send_media_with_fallback(chat_id, 'bat.mp4', cap)
        
    start_batter_timer(chat_id)
    if game.pending_bat is not None: await process_shot(chat_id)

async def process_shot(chat_id: int):
    game = get_game(chat_id)
    if not game or game.pending_bat is None or game.pending_bowl is None: return
    bat, bowl = game.pending_bat, game.pending_bowl
    batter, bowler = get_batter(game), get_bowler(game)
    if not batter: return

    game.pending_bat = None; game.pending_bowl = None; game.awaiting_bat = False
    if game.batter_timer_task: game.batter_timer_task.cancel()
    
    game.batter_timeout_count[batter.id] = 0
    game.current_over_balls += 1
    if bat == 0 or bowl == 0: game.current_over_zeros += 1
    
    over_changed = False
    if game.current_over_balls >= over_length(game): over_changed = True

    if bat == bowl:
        prev_runs = batter.runs
        batter.is_out = True; batter.balls += 1
        batter.history.append('W') 
        
        if bowler:
            game.wickets_by_bowler[bowler.id] = game.wickets_by_bowler.get(bowler.id, 0) + 1
            game.bowling_balls[bowler.id] = game.bowling_balls.get(bowler.id, 0) + 1
            
        out_file = 'duck.mp4' if prev_runs == 0 else random_out_file()
        caption = f"{out_caption()}\n\n{mention_user(batter)} is dismissed!\n{pe('📊')} <b>{batter.runs}</b> runs off <b>{batter.balls}</b> balls"
        if game.commentary_enabled: caption += f"\n\n<i>{out_commentary(game.commentary_lang)}</i>"
        
        await send_media_with_fallback(chat_id, out_file, caption)
        
        if over_changed:
            game.current_over_balls = 0; game.current_over_zeros = 0; game.bowler_idx += 1
            
        await advance_batter(chat_id)
    else:
        prev_runs = batter.runs
        batter.runs += bat; batter.balls += 1
        batter.history.append(str(bat)) 
        
        if bat == 4: batter.fours += 1
        if bat == 6: batter.sixes += 1
        if bowler:
            game.bowling_balls[bowler.id] = game.bowling_balls.get(bowler.id, 0) + 1
            game.bowling_runs[bowler.id] = game.bowling_runs.get(bowler.id, 0) + bat

        run_file = random_run_file(bat)
        caption = f"{run_caption(bat)}\n\n{mention_user(batter)}: <b>{batter.runs}</b> runs off <b>{batter.balls}</b> balls"
        if game.commentary_enabled: caption += f"\n\n<i>{ball_commentary(bat, game.commentary_lang)}</i>"
        
        await send_media_with_fallback(chat_id, run_file, caption)

        for target in [50, 100]:
            if prev_runs < target and batter.runs >= target:
                key = f"{batter.id}_{target}"
                if not game.milestones_sent.get(key):
                    game.milestones_sent[key] = True
                    file = 'fifty.mp4' if target == 50 else 'hundred.mp4'
                    label = '🏅 FIFTY! Half-Century!' if target == 50 else '💯 CENTURY! Magnificent Hundred!'
                    asyncio.create_task(send_media_with_fallback(chat_id, file, f"{label}\n\n🎉 {mention_user(batter)} has smashed <b>{target} RUNS!</b> 🚀"))

        if over_changed:
            game.current_over_balls = 0; game.current_over_zeros = 0; game.bowler_idx += 1
            nb = get_bowler(game)
            if nb:
                try: await bot.send_message(chat_id, f"{pe('🔄')} <b>Over complete ({over_length(game)} balls)!</b> New bowler: {mention_user(nb)}", parse_mode='HTML')
                except Exception: pass
        await start_round(chat_id)

async def advance_batter(chat_id: int):
    game = get_game(chat_id)
    if not game: return
    designated_bowler = get_bowler(game) 
    
    game.current_batter_idx += 1
    while game.current_batter_idx < len(game.batting_order):
        next_b = get_player(game, game.batting_order[game.current_batter_idx])
        if next_b and not next_b.is_eliminated:
            break
        game.current_batter_idx += 1

    if game.current_batter_idx >= len(game.batting_order):
        await end_game(chat_id); return
        
    game.bowler_list = build_bowler_list(game)
    
    if designated_bowler and designated_bowler.id in game.bowler_list:
        game.bowler_idx = game.bowler_list.index(designated_bowler.id)
    else:
        game.bowler_idx = 0; game.current_over_balls = 0; game.current_over_zeros = 0
        
    nb, nbl = get_batter(game), get_bowler(game)
    if not nb or not nbl:
        await end_game(chat_id); return
        
    try: await bot.send_message(chat_id, f"{pe('🔄')} <b>Next Innings!</b>\n\n{pe('🏏')} Batting: {mention_user(nb)}\n{pe('🎯')} Bowling: {mention_user(nbl)}", parse_mode='HTML')
    except Exception: pass
    await start_round(chat_id)

async def end_game(chat_id: int):
    game = get_game(chat_id)
    if not game: return
    
    winner = sorted(game.players, key=lambda p: p.runs, reverse=True)[0]
    best_score = -1; motm = winner
    
    for p in game.players:
        score = p.runs + (game.wickets_by_bowler.get(p.id, 0) * 30)
        if score > best_score:
            best_score = score
            motm = p

    orange_cap = sorted(game.players, key=lambda x: x.runs, reverse=True)[0] if game.players else None
    wkts_list = sorted([(get_player(game, k), v) for k, v in game.wickets_by_bowler.items() if get_player(game, k)], key=lambda x: x[1], reverse=True)
    purple_cap = wkts_list[0] if wkts_list else None

    coin_rewards = {}
    
    async def save_match_data():
        records = []
        for p in game.players:
            is_winner = (p.id == winner.id)
            earned = (p.runs * 2) + (game.wickets_by_bowler.get(p.id, 0) * 20) + (100 if is_winner else 0)
            coin_rewards[p.id] = earned
            
            pts = p.runs * 1 + game.wickets_by_bowler.get(p.id, 0) * 2
            if is_winner: pts += 12
            if motm and p.id == motm.id: pts += 5
            if orange_cap and p.id == orange_cap.id: pts += 5
            if purple_cap and purple_cap[0] and p.id == purple_cap[0].id: pts += 5
            
            records.append({
                "chat_id": chat_id, "user_id": p.id, "runs": p.runs, 
                "wickets": game.wickets_by_bowler.get(p.id, 0), "points": pts,
                "created_at": datetime.now(timezone.utc)
            })
            
            if getattr(game, 'is_tour_match', False) and chat_id in tours:
                tour = tours[chat_id]
                tour.runs[p.id] = tour.runs.get(p.id, 0) + p.runs
                tour.wickets[p.id] = tour.wickets.get(p.id, 0) + game.wickets_by_bowler.get(p.id, 0)
                tour.points[p.id] = tour.points.get(p.id, 0) + pts
                
        if records:
            try: await db.match_records.insert_many(records)
            except Exception: pass
    await save_match_data()

    img_buf = await asyncio.to_thread(generate_scoreboard_image, game)
    coin_msg = f"\n💰 <b>Coins Earned:</b>\n"
    for p in game.players: coin_msg += f"• {mention_user(p)} : {pe('🪙')} +{coin_rewards[p.id]}\n"

    txt_score = live_score_text(game)
    delete_game(chat_id)

    db_summary = {
        'players': [{
            'id': p.id, 'username': p.username, 'first_name': p.first_name,
            'runs': p.runs, 'balls': p.balls, 'fours': p.fours, 'sixes': p.sixes,
            'bowling_balls': game.bowling_balls.get(p.id, 0),
            'bowling_runs': game.bowling_runs.get(p.id, 0),
            'wickets': game.wickets_by_bowler.get(p.id, 0),
            'coins_earned': coin_rewards[p.id]
        } for p in game.players],
        'motmId': motm.id if motm else 0, 'winnerId': winner.id
    }
    asyncio.create_task(update_stats_mongo(db_summary, 'tour' if getattr(game, 'is_special', False) else 'solo'))

    if img_buf:
        try: await bot.send_photo(chat_id, img_buf.getvalue(), caption=coin_msg, parse_mode='HTML')
        except Exception as e: await bot.send_message(chat_id, txt_score + coin_msg, parse_mode='HTML')
    else:
        await bot.send_message(chat_id, txt_score + coin_msg, parse_mode='HTML')

    send_log(f"Match Ended in Chat {chat_id}. Winner: {winner.first_name}")
    
    try:
        channel_caption = f"{pe('🏆')} <b>Match Result</b>\nGroup ID: <code>{chat_id}</code>\nWinner: <b>{winner.first_name}</b>\n\n{txt_score}"
        if img_buf: await bot.send_photo(SCORE_CHANNEL_ID, img_buf.getvalue(), caption=channel_caption, parse_mode='HTML')
        else: await bot.send_message(SCORE_CHANNEL_ID, channel_caption, parse_mode='HTML')
    except Exception as e: pass

async def begin_game(chat_id: int):
    game = get_game(chat_id)
    if not game or game.status != 'waiting': return
    if len(game.players) < 2:
        try: await bot.send_message(chat_id, f"{pe('❌')} Need at least 2 players to start!")
        except Exception: pass
        return
    
    if game.lobby_timer_task: game.lobby_timer_task.cancel()
    if game.lobby_message_id:
        try: await bot.unpin_chat_message(chat_id, game.lobby_message_id)
        except Exception: pass

    p_ids = [p.id for p in game.players]
    random.shuffle(p_ids)
    game.batting_order = p_ids; game.status = 'playing'; game.awaiting_bat = False
    game.group_link = await get_group_link(chat_id)
    game.current_over_balls = 0; game.current_over_zeros = 0; game.bowler_idx = 0
    game.bowler_list = build_bowler_list(game)

    order_lines = "\n".join([f"  {i+1}. {mention_user(get_player(game, id))}" for i, id in enumerate(game.batting_order)])
    mode_note = f"<i>6-ball overs · Bowler rotates every over · Everyone bats & bowls</i> 🏟️" if getattr(game, 'is_special', False) else f"<i>{game.over_balls}-ball overs · Zero max {zero_limit(game)} per over · Batter types 0–6 in the chat!</i> 🤫"

    text = f"{pe('🏏')} <b>{'Stars Special Match' if getattr(game, 'is_special', False) else 'Solo Hand Cricket'} — Game On!</b>\n\n<b>Batting Order:</b>\n{order_lines}\n\n{mode_note}"
    
    await send_media_with_fallback(chat_id, 'start.mp4', text)
    await start_round(chat_id)


# ==========================================
# 10. AI GAME MODE (1v1 in DM) 🤖🔥
# ==========================================
@bot.message_handler(commands=['playai'])
async def playai_cmd(m):
    run_safe_track(m)
    if m.chat.type != 'private': return await bot.reply_to(m, f"{pe('⚠️')} <b>Please use /playai in my DM!</b>", parse_mode='HTML')
    
    if m.from_user.id in ai_games:
        game = ai_games[m.from_user.id]
        now = datetime.now(timezone.utc)
        if (now - game.last_update).total_seconds() < 60:
            return await bot.reply_to(m, f"{pe('⚠️')} <b>You already have an active AI match running.</b> Finish it or wait 60s for it to timeout.", parse_mode='HTML')
        else:
            del ai_games[m.from_user.id]

    ai_games[m.from_user.id] = AIGame(user_id=m.from_user.id)
    
    txt = (f"{pe('🤖')} <b>WELCOME TO AI MODE!</b>\n\n"
           f"Here you will play a 1v1 Hand Cricket match against the Bot.\n\n"
           f"📖 <b>Instructions:</b>\n"
           f"1. Select a difficulty level.\n"
           f"2. Win the Toss to choose Bat/Bowl.\n"
           f"3. Score runs by selecting numbers (1-6).\n"
           f"4. Unlimited overs! You play until WICKET.\n\n"
           f"Select Difficulty Level to begin:")
           
    rows = [
        [{"text": "🟢 Easy", "callback_data": "aip:diff:easy", "style": "success"}],
        [{"text": "🟡 Normal", "callback_data": "aip:diff:normal", "style": "primary"}],
        [{"text": "🔴 Hard", "callback_data": "aip:diff:hard", "style": "danger"}]
    ]
    kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
    msg = await bot.send_message(m.chat.id, txt, parse_mode='HTML', reply_markup=kbd)
    ai_games[m.from_user.id].msg_id = msg.message_id

@bot.callback_query_handler(func=lambda call: call.data.startswith("aip:"))
async def ai_cb_handler(call):
    uid = call.from_user.id
    if uid not in ai_games: return await bot.answer_callback_query(call.id, "Game not found.")
    
    game = ai_games[uid]
    now = datetime.now(timezone.utc)
    
    if (now - game.last_update).total_seconds() > 60:
        del ai_games[uid]
        try: await bot.edit_message_text(f"{pe('❌')} <b>Match Cancelled!</b> (60 seconds timeout)", uid, game.msg_id, parse_mode='HTML')
        except: pass
        return await bot.answer_callback_query(call.id, "Match Cancelled due to inactivity!", show_alert=True)
        
    game.last_update = now 
    parts = call.data.split(':')
    cmd = parts[1]
    
    if cmd == 'diff':
        game.diff = parts[2]
        game.state = 'toss'
        rows = [[{"text": "Odd", "callback_data": "aip:toss:odd", "style": "primary"}, {"text": "Even", "callback_data": "aip:toss:even", "style": "primary"}]]
        kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
        await bot.edit_message_text(f"{pe('🪙')} <b>TOSS TIME</b>\n\nCall Odd or Even:", uid, game.msg_id, parse_mode='HTML', reply_markup=kbd)
        
    elif cmd == 'toss':
        game.user_toss = parts[2]
        game.state = 'toss_num'
        rows = [
            [{"text": "1", "callback_data": "aip:num:1", "style": "primary"}, {"text": "2", "callback_data": "aip:num:2", "style": "primary"}, {"text": "3", "callback_data": "aip:num:3", "style": "primary"}],
            [{"text": "4", "callback_data": "aip:num:4", "style": "primary"}, {"text": "5", "callback_data": "aip:num:5", "style": "primary"}, {"text": "6", "callback_data": "aip:num:6", "style": "primary"}]
        ]
        kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
        await bot.edit_message_text(f"{pe('🪙')} <b>TOSS TIME</b>\n\nChoose a number (1-6):", uid, game.msg_id, parse_mode='HTML', reply_markup=kbd)
        
    elif cmd == 'num':
        user_num = int(parts[2])
        bot_num = random.randint(1,6)
        total = user_num + bot_num
        is_even = (total % 2 == 0)
        user_won = (is_even and game.user_toss == 'even') or (not is_even and game.user_toss == 'odd')
        
        text = f"You chose: {user_num}\nBot chose: {bot_num}\nTotal: {total} ({'Even' if is_even else 'Odd'})\n\n"
        if user_won:
            text += f"🎉 <b>You won the toss!</b> Choose to Bat or Bowl:"
            rows = [[{"text": f"🏏 Bat", "callback_data": "aip:opt:bat", "style": "success"}, {"text": f"🎯 Bowl", "callback_data": "aip:opt:bowl", "style": "danger"}]]
            kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
        else:
            bot_choice = random.choice(['bat', 'bowl'])
            text += f"{pe('🤖')} <b>Bot won the toss</b> and chose to {bot_choice} first.\n\nClick below to start."
            game.user_batting = (bot_choice == 'bowl')
            rows = [[{"text": "Start Match", "callback_data": "aip:start", "style": "success"}]]
            kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
        await bot.edit_message_text(text, uid, game.msg_id, parse_mode='HTML', reply_markup=kbd)
        
    elif cmd == 'opt':
        game.user_batting = (parts[2] == 'bat')
        rows = [[{"text": "Start Match", "callback_data": "aip:start", "style": "success"}]]
        kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
        await bot.edit_message_text(f"{pe('✅')} Choice locked. Ready?", uid, game.msg_id, parse_mode='HTML', reply_markup=kbd)
        
    elif cmd == 'start' or cmd == 'next':
        if game.innings == 1: txt = f"{pe('🏏')} <b>Innings 1</b>\n\n{'You are BATTING' if game.user_batting else 'You are BOWLING'}\n\nChoose your number:"
        else: txt = f"{pe('🏏')} <b>Innings 2</b>\n\nTarget: {game.target}\n{'You are BATTING' if game.user_batting else 'You are BOWLING'}\n\nChoose your number:"
        rows = [
            [{"text": "1", "callback_data": "aip:ball:1", "style": "primary"}, {"text": "2", "callback_data": "aip:ball:2", "style": "primary"}, {"text": "3", "callback_data": "aip:ball:3", "style": "primary"}],
            [{"text": "4", "callback_data": "aip:ball:4", "style": "primary"}, {"text": "5", "callback_data": "aip:ball:5", "style": "primary"}, {"text": "6", "callback_data": "aip:ball:6", "style": "primary"}]
        ]
        kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
        await bot.edit_message_text(txt, uid, game.msg_id, parse_mode='HTML', reply_markup=kbd)
        
    elif cmd == 'ball':
        user_num = int(parts[2])
        bot_num = random.randint(1,6)
        if game.diff == 'hard' and game.history:
            most_freq = max(set(game.history), key=game.history.count)
            if random.random() < 0.3: bot_num = int(most_freq)
        game.history.append(str(user_num))
        
        bat_num = user_num if game.user_batting else bot_num
        bowl_num = bot_num if game.user_batting else user_num
        
        out = (bat_num == bowl_num) 
        if not out:
            if game.user_batting: game.u_runs += bat_num
            else: game.ai_runs += bat_num
            
        if game.user_batting: game.u_balls += 1
        else: game.ai_balls += 1
        
        end_innings = out 
        if game.innings == 2 and ((game.user_batting and game.u_runs >= game.target) or (not game.user_batting and game.ai_runs >= game.target)):
            end_innings = True

        txt = f"You played: {user_num}\nBot played: {bot_num}\n\n"
        if out: txt += f"💥 <b>WICKET!</b>\n"
        else: txt += f"🏃 <b>{bat_num} Runs scored!</b>\n"
        txt += f"\n📊 Score: {game.u_runs if game.user_batting else game.ai_runs} / {game.u_balls if game.user_batting else game.ai_balls} balls"
        
        if end_innings:
            if game.innings == 1:
                game.target = (game.u_runs if game.user_batting else game.ai_runs) + 1
                game.innings = 2
                game.user_batting = not game.user_batting
                game.history = []
                txt += f"\n\n{pe('🛑')} <b>Innings Over!</b>\nTarget: {game.target}"
                rows = [[{"text": "Start Innings 2", "callback_data": "aip:next", "style": "success"}]]
                kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
            else:
                u_won = (game.u_runs >= game.target) if game.innings==2 and game.user_batting else (game.u_runs > game.ai_runs)
                is_tie = (game.u_runs == game.ai_runs)
                
                if is_tie: 
                    txt += f"\n\n{pe('🤝')} <b>Match Tied!</b> (+10 Coins)"
                    await add_coins(uid, 10, "AI Match Tie")
                elif u_won: 
                    try:
                        earned = 75
                        u_data = await get_user(uid)
                        expiry = u_data.get("booster_expiry")
                        if expiry and expiry.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc): earned *= 2
                        txt += f"\n\n🏆 <b>YOU WON!</b> (+{earned} Coins)"
                        await add_coins(uid, earned, "AI Match Win")
                    except Exception: pass
                else: 
                    txt += f"\n\n{pe('😔')} <b>BOT WON!</b> (+30 Coins)"
                    await add_coins(uid, 30, "AI Match Loss")
                    
                txt += f"\n\nFinal Score:\nYou: {game.u_runs}\nBot: {game.ai_runs}"
                del ai_games[uid]
                return await bot.edit_message_text(txt, uid, game.msg_id, parse_mode='HTML')
        else:
            rows = [[{"text": "Next Ball", "callback_data": "aip:next", "style": "primary"}]]
            kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
        await bot.edit_message_text(txt, uid, game.msg_id, parse_mode='HTML', reply_markup=kbd)

# ==========================================
# 11. GENERAL COMMANDS & HANDLERS 
# ==========================================
@bot.message_handler(commands=['themes'])
async def themes_cmd(message):
    run_safe_track(message)
    u = await get_stats(message.from_user.id, 'overall') or {}
    unlocked = u.get("unlocked_themes", ["default"])
    current = u.get("active_theme", "default")
    
    rows = []
    for t in unlocked:
        prefix = "✅ " if t == current else ""
        rows.append([{"text": f"{prefix}{t.capitalize()} Theme", "callback_data": f"equip_theme:{t}", "style": "primary"}])
    
    kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
    await bot.reply_to(message, f"🎨 <b>Select your Stats Profile Theme:</b>\n<i>(Buy more themes from /buy)</i>", parse_mode='HTML', reply_markup=kbd)

@bot.callback_query_handler(func=lambda call: call.data.startswith("equip_theme:"))
async def cb_equip_theme(call):
    theme = call.data.split(":")[1]
    await db.player_stats.update_one({"user_id": call.from_user.id}, {"$set": {"active_theme": theme}})
    await bot.answer_callback_query(call.id, f"Equipped {theme.capitalize()} Theme successfully!", show_alert=True)

@bot.message_handler(commands=['gift'])
async def gift_cmd(message):
    run_safe_track(message)
    if not is_owner(message.from_user.id): return await bot.reply_to(message, f"{pe('❌')} Only Owner can edit gift.", parse_mode='HTML')
    text = f"{pe('🎁')} <b>Shop/Gift Control Panel</b>\n\nStatus: <b>{GIFT_CONFIG['status'].upper()}</b>\nPrice/Amount: <b>{GIFT_CONFIG['amount']} Coins</b>\n\nChoose an action:"
    rows = [
        [{"text": "Turn ON", "callback_data": "gift:on", "style": "success"}, {"text": "Turn OFF", "callback_data": "gift:off", "style": "danger"}],
        [{"text": "Change Amount", "callback_data": "gift:amt", "style": "primary"}]
    ]
    kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
    await bot.reply_to(message, text, parse_mode='HTML', reply_markup=kbd)

@bot.message_handler(commands=['lbc', 'leaderboard'])
async def lbc_cmd(message):
    run_safe_track(message)
    if message.chat.type == 'private': return await bot.reply_to(message, f"{pe('⚠️')} Leaderboard is only for Groups.")
    try:
        img_buf, text = await get_leaderboard_data(message.chat.id, 'all')
        if img_buf: await bot.send_photo(message.chat.id, img_buf.getvalue(), caption=text, parse_mode='HTML', reply_markup=get_lbc_keyboard())
        else: await bot.reply_to(message, text, parse_mode='HTML', reply_markup=get_lbc_keyboard())
    except Exception as e:
        await bot.reply_to(message, f"{pe('❌')} Error loading Leaderboard: {e}")

@bot.message_handler(commands=['daily'])
async def daily_cmd(message):
    run_safe_track(message)
    if message.chat.type == 'private': return await bot.reply_to(message, f"{pe('⚠️')} Leaderboard is only for Groups.")
    try:
        img_buf, text = await get_leaderboard_data(message.chat.id, 'daily')
        if img_buf: await bot.send_photo(message.chat.id, img_buf.getvalue(), caption=text, parse_mode='HTML', reply_markup=get_lbc_keyboard())
        else: await bot.reply_to(message, text, parse_mode='HTML', reply_markup=get_lbc_keyboard())
    except Exception as e: pass

@bot.message_handler(commands=['weekly'])
async def weekly_cmd(message):
    run_safe_track(message)
    if message.chat.type == 'private': return await bot.reply_to(message, f"{pe('⚠️')} Leaderboard is only for Groups.")
    try:
        img_buf, text = await get_leaderboard_data(message.chat.id, 'weekly')
        if img_buf: await bot.send_photo(message.chat.id, img_buf.getvalue(), caption=text, parse_mode='HTML', reply_markup=get_lbc_keyboard())
        else: await bot.reply_to(message, text, parse_mode='HTML', reply_markup=get_lbc_keyboard())
    except Exception as e: pass

@bot.message_handler(commands=['monthly'])
async def monthly_cmd(message):
    run_safe_track(message)
    if message.chat.type == 'private': return await bot.reply_to(message, f"{pe('⚠️')} Leaderboard is only for Groups.")
    try:
        img_buf, text = await get_leaderboard_data(message.chat.id, '30')
        if img_buf: await bot.send_photo(message.chat.id, img_buf.getvalue(), caption=text, parse_mode='HTML', reply_markup=get_lbc_keyboard())
        else: await bot.reply_to(message, text, parse_mode='HTML', reply_markup=get_lbc_keyboard())
    except Exception as e: pass

@bot.message_handler(commands=['ping'])
async def ping_cmd(message):
    run_safe_track(message)
    await bot.reply_to(message, "🏓 Pong! Bot is running perfectly.")

@bot.message_handler(commands=['bug'])
async def bug_cmd(message):
    run_safe_track(message)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2: return await bot.reply_to(message, f"{pe('⚠️')} Usage: <code>/bug &lt;message&gt;</code>", parse_mode='HTML')
    p = Player(id=message.from_user.id, username=message.from_user.username, first_name=message.from_user.first_name)
    log_text = f"🐛 <b>Bug / User Request:</b>\nUser: {mention_user(p)}\nChat ID: <code>{message.chat.id}</code>\nMessage: {html.escape(parts[1])}"
    for adm in list(DYNAMIC_ADMINS) + [ROOT_ADMIN_ID]:
        try: await bot.send_message(adm, log_text, parse_mode='HTML')
        except Exception: pass
    await bot.reply_to(message, f"{pe('✅')} Thanks for it. Okay.", parse_mode='HTML')

@bot.message_handler(commands=['broadcast'])
async def broadcast_cmd(message):
    run_safe_track(message)
    if not is_bot_admin(message.from_user.id): return
    text = message.text.replace('/broadcast', '').strip()
    if not text: return await bot.reply_to(message, f"{pe('⚠️')} Usage: <code>/broadcast &lt;your message&gt;</code>", parse_mode='HTML')
    await bot.reply_to(message, f"{pe('📢')} Broadcast initiated. This may take some time...")
    chats = await db.known_chats.find().to_list(length=None)
    success = 0
    for c in chats:
        try:
            await bot.send_message(c["chat_id"], f"{pe('📢')} <b>BROADCAST MESSAGE</b>\n\n{text}", parse_mode='HTML')
            success += 1; await asyncio.sleep(0.05)
        except Exception: pass
    await bot.reply_to(message, f"{pe('✅')} Broadcast finished. Sent successfully to {success} out of {len(chats)} chats.", parse_mode='HTML')

@bot.message_handler(commands=['ads'])
async def ads_cmd(message):
    run_safe_track(message)
    if not await check_owner_access(message): return
    WAITING_FOR_ADS.add(message.from_user.id)
    await bot.reply_to(message, f"{pe('📢')} <b>Ads Mode ON!</b>\n\nPlease send the message/post you want to forward to all groups and users.", parse_mode='HTML')

@bot.message_handler(commands=['qpromo'])
async def qpromo_cmd(message):
    run_safe_track(message)
    if not await check_owner_access(message): return
    parts = message.text.split()
    if len(parts) != 5: return await bot.reply_to(message, f"{pe('⚠️')} Usage: `/qpromo <CODE> <COINS> <USES> <HOURS>`", parse_mode='HTML')
    code, coins, uses, hours = parts[1], int(parts[2]), int(parts[3]), int(parts[4])
    exp_time = datetime.now(timezone.utc) + timedelta(hours=hours)
    try:
        await db.promo_codes.insert_one({"code": code, "coins": coins, "max_uses": uses, "used_count": 0, "expires_at": exp_time})
        await bot.reply_to(message, f"{pe('✅')} <b>Promo Code Created!</b>\nCode: <code>{code}</code>\nValue: {coins} Coins\nMax Uses: {uses}\nExpires in: {hours} hours.", parse_mode='HTML')
    except Exception as e:
        await bot.reply_to(message, f"{pe('❌')} Error: {e}")

@bot.message_handler(commands=['promo'])
async def promo_cmd(message):
    run_safe_track(message)
    parts = message.text.split()
    if len(parts) < 2: return await bot.reply_to(message, f"{pe('⚠️')} Send a valid promo code. Ex: `/promo VIP100`", parse_mode='HTML')
    code = parts[1].strip()
    user_id = message.from_user.id
    try:
        res_redeem = await db.promo_redeems.find_one({"code": code, "user_id": user_id})
        if res_redeem: return await bot.reply_to(message, f"{pe('⚠️')} You have already redeemed this promo code.")
        promo = await db.promo_codes.find_one({"code": code})
        if not promo: return await bot.reply_to(message, f"{pe('❌')} Invalid Promo Code.")
        if datetime.now(timezone.utc) > promo["expires_at"].replace(tzinfo=timezone.utc): return await bot.reply_to(message, f"{pe('❌')} This promo code has expired.")
        if promo["used_count"] >= promo["max_uses"]: return await bot.reply_to(message, f"{pe('❌')} This promo code is fully used up.")
        await db.promo_codes.update_one({"code": code}, {"$inc": {"used_count": 1}})
        await db.promo_redeems.insert_one({"code": code, "user_id": user_id})
        await add_coins(user_id, promo["coins"], "Promo Code")
        await bot.reply_to(message, f"🎉 <b>PROMO REDEEMED!</b>\n\nYou received <b>{promo['coins']} Coins!</b> {pe('🪙')}", parse_mode='HTML')
    except Exception as e:
        await bot.reply_to(message, f"{pe('❌')} DB Error: {e}")

@bot.message_handler(commands=['addadmin'])
async def addadmin_cmd(message):
    run_safe_track(message)
    if not await check_owner_access(message): return
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit(): return await bot.reply_to(message, f"{pe('⚠️')} Usage: <code>/addadmin &lt;User_ID&gt;</code>", parse_mode='HTML')
    u_id = int(parts[1])
    success = await add_bot_admin(u_id)
    if success: await bot.reply_to(message, f"{pe('✅')} User <code>{u_id}</code> added as Bot Admin.", parse_mode='HTML')
    else: await bot.reply_to(message, f"{pe('⚠️')} User is already an Admin.", parse_mode='HTML')

@bot.message_handler(commands=['removeadmin'])
async def removeadmin_cmd(message):
    run_safe_track(message)
    if not await check_owner_access(message): return
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit(): return await bot.reply_to(message, f"{pe('⚠️')} Usage: `/removeadmin <User_ID>`", parse_mode='HTML')
    u_id = int(parts[1])
    success = await remove_bot_admin(u_id)
    if success: await bot.reply_to(message, f"{pe('✅')} User <code>{u_id}</code> removed from Admins.", parse_mode='HTML')
    else: await bot.reply_to(message, f"{pe('⚠️')} User is not an admin.", parse_mode='HTML')

@bot.message_handler(commands=['coinhistory'])
async def coinhistory_cmd(message):
    run_safe_track(message)
    if not is_bot_admin(message.from_user.id): return
    if not message.reply_to_message: return await bot.reply_to(message, f"{pe('⚠️')} Please reply to a user's message to view their coin history.", parse_mode='HTML')
    target_id = message.reply_to_message.from_user.id
    target_name = html.escape(message.reply_to_message.from_user.first_name)
    try:
        history = await db.coin_history.find({"user_id": target_id}).sort("created_at", -1).limit(10).to_list(length=10)
        if not history: return await bot.reply_to(message, f"{pe('📭')} No coin history found for <b>{target_name}</b>.", parse_mode='HTML')
        text = f"{pe('🪙')} <b>Coin History for {target_name}</b>\n\n"
        for h in history:
            sign = "+" if h["amount"] > 0 else ""
            text += f"• {sign}{h['amount']} Coins | <i>{h['reason']}</i>\n"
        await bot.reply_to(message, text, parse_mode='HTML')
    except Exception: pass

@bot.message_handler(commands=['send'])
async def send_coins_cmd(message):
    run_safe_track(message)
    if not message.reply_to_message:
        return await bot.reply_to(message, f"{pe('⚠️')} Reply to a user's message to send coins.")
    
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return await bot.reply_to(message, f"{pe('⚠️')} Usage: `/send <amount>`", parse_mode='HTML')
        
    amount = int(parts[1])
    if amount < 10:
        return await bot.reply_to(message, f"{pe('⚠️')} Minimum transfer amount is 10 coins.")
        
    sender_id = message.from_user.id
    receiver = message.reply_to_message.from_user
    
    if sender_id == receiver.id:
        return await bot.reply_to(message, f"{pe('⚠️')} You cannot send coins to yourself.")
        
    sender_bal, _, _ = await get_user_balance(sender_id)
    if sender_bal < amount:
        return await bot.reply_to(message, f"{pe('❌')} Insufficient balance! You have {sender_bal} coins.")
        
    tax = int(amount * 0.05)
    final_amount = amount - tax
    
    success = await deduct_coins(sender_id, amount)
    if success:
        await add_coins(receiver.id, final_amount, f"Received from {message.from_user.first_name}")
        await bot.reply_to(message, f"{pe('✅')} <b>Transfer Successful!</b>\n\n{pe('💸')} Sent: {amount}\n📉 Tax (5%): {tax}\n{pe('🎁')} Received by {html.escape(receiver.first_name)}: {final_amount} Coins", parse_mode='HTML')
        send_log(f"{pe('💸')} {message.from_user.first_name} sent {amount} coins to {receiver.first_name}. (Tax: {tax})")

@bot.message_handler(commands=['host'])
async def host_cmd(message):
    run_safe_track(message)
    game = get_game(message.chat.id)
    if not game: return await bot.reply_to(message, f"{pe('⚠️')} No active game in this chat.")
    host_p = get_player(game, game.host_id)
    if host_p:
        await bot.reply_to(message, f"{pe('👑')} <b>Current Game Host:</b> {mention_user(host_p)}", parse_mode='HTML')
    else:
        await bot.reply_to(message, f"{pe('👑')} <b>Current Game Host ID:</b> <code>{game.host_id}</code>", parse_mode='HTML')

@bot.message_handler(commands=['start'])
async def start_cmd(message):
    run_safe_track(message)
    
    if message.text.startswith('/start bowl_'):
        try:
            chat_id = int(message.text.split('_')[1])
            game = get_game(chat_id)
            if game and game.status == 'playing':
                bl = get_bowler(game)
                if bl and bl.id == message.from_user.id:
                    bt = get_batter(game)
                    await send_bowling_dm(bl.id, chat_id, bt.first_name if bt else "Batter")
                    return await bot.reply_to(message, f"{pe('✅')} Click 'Start Run-up' to bowl!")
        except Exception: pass

    if message.chat.type == 'private':
        if is_banned(message.from_user.id): return await bot.reply_to(message, f"{pe('🚫')} You are banned.", parse_mode='HTML')
        add_url = f"https://t.me/{bot_username}?startgroup=true"
        rows = [
            [{"text": 'Add Bot to Group', "url": add_url, "style": "success"}],
            [{"text": 'Stars Cricket Playzone', "url": 'https://t.me/starscricketplayzone', "style": "primary"}],
            [{"text": 'Help & Guide', "callback_data": 'help_menu', "style": "primary"}]
        ]
        kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
        text = (f"{pe('🏏')} <b>Welcome to Stars League Cricket Bot!</b>\n\n"
                f"I am an advanced hand-cricket bot featuring Solo modes, Custom Over Limits, Shop System, and huge Special Tours.\n\n"
                f"Tap the buttons below to begin or learn how to play!")
        await send_media_with_fallback(message.chat.id, 'welcome.png', text, kbd)
        return

    if message.chat.id in tours:
        return await bot.reply_to(message, f"{pe('⚠️')} <b>A Tour is already running in this group!</b>\nEnd or pause it first to play normal matches.", parse_mode='HTML')
    if has_game(message.chat.id): 
        return await bot.reply_to(message, f"{pe('⚠️')} A game is already running! Use /cancel to end it first.")
    
    rows = [
        [{"text": 'Start Solo Game', "callback_data": f"solo:{message.chat.id}", "style": "primary"}],
        [{"text": 'Cancel', "callback_data": f"cancel_req:{message.chat.id}", "style": "danger"}]
    ]
    kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
    text = f"{pe('🏏')} <b>Stars League Cricket Bot</b>\n\n• Bowler picks secretly in <b>DM</b>\n• Batter types <b>(0–6)</b> here\n• Select a <b>3-ball</b> or <b>6-ball</b> over after starting\n• <b>Timeout</b>: 70s max to bowl/bat."
    await send_media_with_fallback(message.chat.id, 'welcome.png', text, kbd)

@bot.message_handler(commands=['help'])
async def help_cmd(message):
    run_safe_track(message)
    rows = [
        [{"text": "Normal Match Guide", "callback_data": "help_guide:normal", "style": "primary"}],
        [{"text": "Special Match Guide", "callback_data": "help_guide:special", "style": "primary"}],
        [{"text": "Tour Match Guide", "callback_data": "help_guide:tour", "style": "primary"}]
    ]
    kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
    await bot.reply_to(message, "🛠 <b>Welcome to the Help Center!</b>\n\nChoose a guide to learn more about the commands and features:", parse_mode='HTML', reply_markup=kbd)

@bot.message_handler(commands=['balance', 'bal'])
async def balance_cmd(message):
    run_safe_track(message)
    target_user = message.from_user
    if message.reply_to_message: target_user = message.reply_to_message.from_user
    coins, teddy, heart = await get_user_balance(target_user.id)
    text = (f"{pe('💼')} <b>Bank of Stars League</b>\n\n"
            f"{pe('👤')} <b>Player:</b> <code>{html.escape(target_user.first_name)}</code>\n"
            f"{pe('🪙')} <b>Coins:</b> <b>{coins}</b>\n\n"
            f"🎒 <b>Inventory:</b>\n"
            f"{pe('🧸')} Teddy: <b>{teddy}</b>\n"
            f"{pe('❤️')} Heart: <b>{heart}</b>\n\n"
            f"<i>(Use /buy to shop)</i>")
    await bot.reply_to(message, text, parse_mode='HTML')

@bot.message_handler(commands=['buy'])
async def buy_cmd(message):
    run_safe_track(message)
    rows = [
        [{"text": 'Buy Teddy', "callback_data": "buy_item:teddy", "style": "primary"}],
        [{"text": 'Buy Heart', "callback_data": "buy_item:heart", "style": "primary"}],
        [{"text": '2x Coin Booster', "callback_data": "buy_item:booster", "style": "success"}],
        [{"text": '🕸️ Spider Theme', "callback_data": "buy_item:spider_theme", "style": "primary"}],
        [{"text": '🖤 Dark Theme', "callback_data": "buy_item:dark_theme", "style": "primary"}],
        [{"text": '🩵 Neon Theme', "callback_data": "buy_item:neon_theme", "style": "primary"}],
        [{"text": '🌊 Ocean Theme', "callback_data": "buy_item:ocean_theme", "style": "primary"}],
        [{"text": '🌲 Forest Theme', "callback_data": "buy_item:forest_theme", "style": "primary"}]
    ]
    kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
    text = f"{pe('🛒')} <b>Welcome to Stars Shop</b>\n\nSelect an item to buy. Admin will verify your request!"
    await bot.reply_to(message, text, parse_mode='HTML', reply_markup=kbd)

@bot.message_handler(commands=['cancel'])
async def cancel_cmd(message):
    run_safe_track(message)
    if message.chat.type == 'private': return
    if not has_game(message.chat.id): return
    game = get_game(message.chat.id)
    is_normal_admin = (message.from_user.id == game.host_id) or await is_group_admin(message.chat.id, message.from_user.id)
    is_bot_adm = is_bot_admin(message.from_user.id)
    if game.is_special and not is_bot_adm: return await bot.reply_to(message, f"{pe('❌')} Only Bot Admins can cancel Special Matches.")
    if not game.is_special and not is_normal_admin and not is_bot_adm: return await bot.reply_to(message, f"{pe('❌')} Only Host or Group Admin can cancel Normal Matches.")

    rows = [[{"text": 'Yes, Cancel', "callback_data": f"cancel:{message.chat.id}", "style": "danger"}], [{"text": 'Keep playing', "callback_data": "ignore_cancel", "style": "success"}]]
    kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
    await bot.reply_to(message, f"{pe('⚠️')} <b>Are you sure you want to permanently cancel and delete the active match?</b>", parse_mode='HTML', reply_markup=kbd)

@bot.message_handler(commands=['score'])
async def score_cmd(message):
    run_safe_track(message)
    if message.chat.type == 'private': return
    game = get_game(message.chat.id)
    if not game or game.status != 'playing': return
    await bot.reply_to(message, live_score_text(game), parse_mode='HTML')

@bot.message_handler(commands=['stats'])
async def stats_cmd(message):
    run_safe_track(message)
    s = await get_stats(message.from_user.id, 'solo')
    if not s or s.get('matches', 0) == 0: return await bot.reply_to(message, f"{pe('📭')} No Solo stats yet! Play a game first.", parse_mode='HTML')
    rows = [
        [{"text": "Overall Stats", "callback_data": f"statsview:{message.from_user.id}:overall", "style": "primary"}],
        [{"text": "Solo Match Stats", "callback_data": f"statsview:{message.from_user.id}:solo", "style": "primary"}],
        [{"text": "Tour Match Stats", "callback_data": f"statsview:{message.from_user.id}:tour", "style": "primary"}]
    ]
    kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
    img_buf = await asyncio.to_thread(generate_stats_card_image, s, 'solo', s.get('active_theme', 'default'))
    caption = format_stats_profile_html(s, 'solo')
    if img_buf: await bot.send_photo(message.chat.id, img_buf.getvalue(), caption=caption, parse_mode='HTML', reply_markup=kbd)
    else: await bot.reply_to(message, caption, parse_mode='HTML', reply_markup=kbd)

@bot.message_handler(commands=['tourstats'])
async def tourstats_cmd(message):
    run_safe_track(message)
    s = await get_stats(message.from_user.id, 'tour')
    if not s or s.get('matches', 0) == 0: return await bot.reply_to(message, f"{pe('📭')} No tour stats yet! Play a game first.", parse_mode='HTML')
    
    img_buf = await asyncio.to_thread(generate_stats_card_image, s, 'tour', s.get('active_theme', 'default'))
    caption = format_stats_profile_html(s, 'tour')
    if img_buf: await bot.send_photo(message.chat.id, img_buf.getvalue(), caption=caption, parse_mode='HTML')
    else: await bot.reply_to(message, caption, parse_mode='HTML')

@bot.message_handler(commands=['adminpanel'])
async def adminpanel_cmd(message):
    run_safe_track(message)
    if not await check_bot_admin_access(message): return
    await bot.reply_to(message, f"{pe('👑')} <b>Admin Panel — Stars League</b>\n\n/specialmatch — Create special match\n/addplayer @u1 @u2 — Add players\n/startmatch — Force start match\n/cancel — Cancel active game\n/newtour — Setup new tour\n/endtour [name] — End specific tour\n/tourend — End active live tour in group\n/removeadmin [id] — Remove bot admin\n/listtour [name] — View registrations\n/broadcast &lt;msg&gt; — Message all users\n/gift — Open Shop config panel\n/cachemedia — Fast Video Upload (Owner)\n\n<b>Your ID:</b> <code>{message.from_user.id}</code>", parse_mode='HTML')

@bot.message_handler(commands=['specialmatch'])
async def specialmatch_cmd(message):
    run_safe_track(message)
    if message.chat.type == 'private': return
    if not await check_bot_admin_access(message): return
    if message.chat.id in tours: return await bot.reply_to(message, f"{pe('⚠️')} A Tour is active in this group.")
    if has_game(message.chat.id): return await bot.reply_to(message, f"{pe('⚠️')} Game already running! Use /cancel first.")
    game = Game(chat_id=message.chat.id, status='waiting', host_id=message.from_user.id, is_special=True, over_balls=6, created_at=datetime.now(timezone.utc))
    set_game(message.chat.id, game)
    msg = await bot.reply_to(message, lobby_text(game), parse_mode='HTML', reply_markup=lobby_keyboard(message.chat.id, True))
    game.lobby_message_id = msg.message_id
    try: await bot.pin_chat_message(message.chat.id, msg.message_id, disable_notification=True)
    except Exception: pass

@bot.message_handler(commands=['addplayer'])
async def addplayer_cmd(message):
    run_safe_track(message)
    if message.chat.type == 'private' or not await check_bot_admin_access(message): return
    game = get_game(message.chat.id)
    if not game or not game.is_special or game.status != 'waiting': return
    added, not_found, already_in = [], [], []
    if message.entities:
        for ent in message.entities:
            if ent.type == 'text_mention' and ent.user:
                u = ent.user
                if get_player(game, u.id): already_in.append(html.escape(u.first_name)); continue
                game.players.append(Player(id=u.id, username=u.username or "", first_name=u.first_name))
                added.append(html.escape(u.first_name))
            elif ent.type == 'mention':
                raw_name = message.text[ent.offset + 1: ent.offset + ent.length]
                info = await db.user_map.find_one({"username": re.compile(f"^{raw_name}$", re.I)})
                if not info: not_found.append(html.escape(f"@{raw_name}")); continue
                if get_player(game, info['id']): already_in.append(html.escape(f"@{raw_name}")); continue
                game.players.append(Player(id=info['id'], username=info['username'], first_name=info['firstName']))
                added.append(html.escape(f"@{raw_name}"))
    reply = ""
    if added: reply += f"{pe('✅')} Added: {', '.join(added)}\n"
    if already_in: reply += f"ℹ️ Already in: {', '.join(already_in)}\n"
    if not_found: reply += f"{pe('❌')} Not found: {', '.join(not_found)}\n"
    if game.lobby_message_id:
        try: await bot.edit_message_text(text=lobby_text(game), chat_id=message.chat.id, message_id=game.lobby_message_id, parse_mode='HTML', reply_markup=lobby_keyboard(message.chat.id, True))
        except Exception: pass
    await bot.reply_to(message, reply.strip(), parse_mode='HTML')

@bot.message_handler(commands=['startmatch'])
async def startmatch_cmd(message):
    run_safe_track(message)
    if message.chat.type == 'private' or not await check_bot_admin_access(message): return
    game = get_game(message.chat.id)
    if not game or not game.is_special: return
    await begin_game(message.chat.id)

@bot.message_handler(commands=['cm'])
async def cm_cmd(message):
    run_safe_track(message)
    if message.chat.type == 'private': return
    game = get_game(message.chat.id)
    if not game: return await bot.reply_to(message, f"{pe('⚠️')} No active game.")
    
    is_normal_admin = (message.from_user.id == game.host_id) or await is_group_admin(message.chat.id, message.from_user.id)
    if not is_normal_admin and not is_bot_admin(message.from_user.id): return await bot.reply_to(message, f"{pe('❌')} Only Host or Admin can edit settings.")
    
    def comm_kbd(c_id, en, lang):
        rows = [[{"text": "ON ✅" if en else "OFF ❌", "callback_data": f"cm:{c_id}:toggle", "style": "success" if en else "danger"}],
                [{"text": "English ✅" if lang=='en' else "English", "callback_data": f"cm:{c_id}:en", "style": "primary"}, 
                 {"text": "Hindi ✅" if lang=='hi' else "Hindi", "callback_data": f"cm:{c_id}:hi", "style": "primary"}]]
        return InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
        
    await bot.reply_to(message, f"💬 <b>Commentary Settings</b>\n\nSelect Language & Toggle ON/OFF:", parse_mode='HTML', reply_markup=comm_kbd(message.chat.id, game.commentary_enabled, game.commentary_lang))

# ==========================================
# 12. SPECIAL TOUR / REGISTRATION
# ==========================================
@bot.message_handler(commands=['newtour'])
async def newtour_cmd(message):
    run_safe_track(message)
    if not is_bot_admin(message.from_user.id): return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2: return await bot.reply_to(message, f"{pe('⚠️')} Usage: `/newtour <Tournament Name>`", parse_mode='HTML')
    tour_name = parts[1].strip()
    res = await db.open_tournaments.find_one({"name": tour_name})
    if res: return await bot.reply_to(message, f"{pe('❌')} This tournament name already exists!")
    TOUR_SETUP_STATE[message.from_user.id] = {"step": 1, "name": tour_name}
    await bot.reply_to(message, f"{pe('📝')} <b>Tour Name:</b> {html.escape(tour_name)}\n\nNow, please send the <b>GC ID</b> (Group Chat ID) where this tournament will take place.", parse_mode='HTML')

@bot.message_handler(commands=['register'])
async def register_cmd(message):
    run_safe_track(message)
    if message.chat.type != 'private': return await bot.reply_to(message, f"{pe('⚠️')} Please use /register in my DM.")
    open_tours = await db.open_tournaments.find().to_list(length=None)
    rules = ("📜 <b>Tournament Registration</b>\n\n"
             "• <b>Spam Policy:</b> No continuous repeating deliveries.\n"
             "• <b>Wide Ball:</b> Repeating 3 times results in WIDE (1 Free run).\n"
             "• <b>Timeout:</b> 70s max. 1st time (-6 runs), 2nd time Elimination!\n\n")
    if not open_tours: return await bot.reply_to(message, rules + f"{pe('🚫')} <b>There is no any active tournament.</b>", parse_mode='HTML')
    rules += "👇 <b>Select a Tournament to Register:</b>"
    rows = []
    for t in open_tours: rows.append([{"text": str(t['name']), "callback_data": f"regtour:{t['_id']}", "style": "primary"}])
    kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
    await bot.send_message(message.chat.id, rules, parse_mode='HTML', reply_markup=kbd)

@bot.message_handler(commands=['listtour'])
async def listtour_cmd(message):
    run_safe_track(message)
    if not is_bot_admin(message.from_user.id): return
    parts = message.text.split(maxsplit=1)
    
    if len(parts) > 1:
        t_name = parts[1].strip()
        tour = await db.open_tournaments.find_one({"name": t_name})
        if not tour: return await bot.reply_to(message, f"{pe('❌')} Tournament not found.")
    else:
        tours_list = await db.open_tournaments.find().sort("_id", -1).limit(1).to_list(1)
        if not tours_list: return await bot.reply_to(message, f"{pe('❌')} No active tournaments found.")
        tour = tours_list[0]
        
    regs = await db.tour_registrations.find({"tour_id": tour["_id"]}).to_list(length=None)
    if not regs: return await bot.reply_to(message, f"{pe('📭')} No registrations yet for <b>{html.escape(tour['name'])}</b>.", parse_mode='HTML')
    
    chunk_size = 5
    for i in range(0, len(regs), chunk_size):
        chunk = regs[i:i+chunk_size]
        msg = f"📋 <b>{html.escape(tour['name'])} Registration List ({i+1} to {i+len(chunk)})</b>\n\n"
        for idx, r in enumerate(chunk):
            uname = f"@{r['username']}" if r.get('username') else r['first_name']
            msg += f"{i+idx+1}. {html.escape(uname)} — ID: <code>{r['user_id']}</code>\n"
        await bot.send_message(message.chat.id, msg, parse_mode='HTML')

@bot.message_handler(commands=['endtour'])
async def endtour_cmd(message):
    run_safe_track(message)
    if not is_bot_admin(message.from_user.id): return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2: return await bot.reply_to(message, f"{pe('⚠️')} Usage: `/endtour <Tournament Name>`", parse_mode='HTML')
    t_name = parts[1].strip()
    res = await db.open_tournaments.delete_one({"name": t_name})
    if res.deleted_count > 0: await bot.reply_to(message, f"{pe('✅')} Tournament <b>{html.escape(t_name)}</b> has been ended and removed from registrations.", parse_mode='HTML')
    else: await bot.reply_to(message, f"{pe('❌')} No tournament found with name <b>{html.escape(t_name)}</b>.", parse_mode='HTML')

@bot.message_handler(commands=['pt'])
async def pt_cmd(message):
    run_safe_track(message)
    if message.chat.id not in tours: return
    tour = tours[message.chat.id]
    pts = sorted(tour.points.items(), key=lambda x: x[1], reverse=True)
    text = f"{pe('🏆')} <b>TOUR POINTS TABLE (OVERALL)</b>\n\n"
    for i, (uid, pt) in enumerate(pts):
        name = f"<code>{uid}</code>" 
        try:
            u = await db.user_map.find_one({"id": uid})
            if u: name = u["firstName"]
        except Exception: pass
        text += f"{i+1}. {html.escape(name)} — <b>{pt} pts</b>\n"
    rows = [[{"text": "Overall", "callback_data": "pt:overall", "style": "primary"}, {"text": "Group Wise", "callback_data": "pt:groups", "style": "primary"}]]
    kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
    await bot.reply_to(message, text, parse_mode='HTML', reply_markup=kbd)

@bot.message_handler(commands=['specialtour'])
async def specialtour_cmd(message):
    run_safe_track(message)
    if message.chat.type == 'private': return
    if not await check_bot_admin_access(message): return
    if message.chat.id in tours: return await bot.reply_to(message, f"{pe('⚠️')} A Tour is already running in this chat. Use /tourend to end it.")
    if has_game(message.chat.id): return await bot.reply_to(message, f"{pe('⚠️')} Game already running! Use /cancel first.")
    
    parts = message.text.split(maxsplit=1)
    t_name = parts[1].strip() if len(parts) > 1 else "Stars Special Tour"
    tours[message.chat.id] = Tour(chat_id=message.chat.id, name=t_name)
    await bot.reply_to(message, f"{pe('🏆')} <b>{html.escape(t_name)} CREATED!</b>\n\nAdd players using <code>/addgroup 1 @user</code>\nWhen done, type <code>/tourlock</code>.", parse_mode='HTML')

@bot.message_handler(func=lambda m: m.text and m.text.startswith('/addgroup '))
async def addgroup_cmd(message):
    run_safe_track(message)
    if message.chat.id not in tours: return
    if not await check_bot_admin_access(message): return
    tour = tours[message.chat.id]
    if tour.status == 'locked': return await bot.reply_to(message, f"{pe('❌')} Tour is locked! Use <code>/touropen</code> to modify groups.", parse_mode='HTML')
    parts = message.text.split()
    if len(parts) < 3: return
    grp_name = parts[1]
    added, not_found, already_added = [], [], []
    for part in parts[2:]:
        if part.isdigit():
            uid = int(part)
            existing_g = is_user_in_any_group(tour, uid)
            if existing_g: already_added.append(str(uid) + f"(Grp {existing_g})"); continue
            usr_info = await db.user_map.find_one({"id": uid})
            p_name = usr_info['firstName'] if usr_info else str(uid)
            p_uname = usr_info['username'] if usr_info else ""
            if grp_name not in tour.groups: tour.groups[grp_name] = []
            tour.groups[grp_name].append(Player(id=uid, username=p_uname, first_name=p_name))
            added.append(str(uid))

    if message.entities:
        for ent in message.entities:
            if ent.type == 'text_mention' and ent.user:
                u = ent.user
                existing_g = is_user_in_any_group(tour, u.id)
                if existing_g: already_added.append(html.escape(u.first_name) + f" (Grp {existing_g})"); continue
                if grp_name not in tour.groups: tour.groups[grp_name] = []
                tour.groups[grp_name].append(Player(id=u.id, username=u.username or "", first_name=u.first_name))
                added.append(html.escape(u.first_name))
            elif ent.type == 'mention':
                raw_name = message.text[ent.offset + 1: ent.offset + ent.length]
                info = await db.user_map.find_one({"username": re.compile(f"^{raw_name}$", re.I)})
                if not info: not_found.append(html.escape(f"@{raw_name}")); continue
                existing_g = is_user_in_any_group(tour, info['id'])
                if existing_g: already_added.append(html.escape(f"@{raw_name}") + f" (Grp {existing_g})"); continue
                if grp_name not in tour.groups: tour.groups[grp_name] = []
                tour.groups[grp_name].append(Player(id=info['id'], username=info['username'], first_name=info['firstName']))
                added.append(html.escape(f"@{raw_name}"))

    resp = f"{pe('✅')} <b>Group {html.escape(grp_name)} Updated!</b>\nAdded: {', '.join(added) if added else 'None'}"
    if already_added: resp += f"\n{pe('⚠️')} Already added in group: {', '.join(already_added)}"
    if not_found: resp += f"\n{pe('❌')} Not found: {', '.join(not_found)}"
    await bot.reply_to(message, resp, parse_mode='HTML')

@bot.message_handler(commands=['tourlock', 'touropen'])
async def tour_status_cmd(message):
    run_safe_track(message)
    if message.chat.id not in tours: return
    if not await check_bot_admin_access(message): return
    tour = tours[message.chat.id]
    if message.text.startswith('/tourlock'):
        tour.status = 'locked'
        await bot.reply_to(message, f"{pe('🔒')} <b>Tour Locked!</b>\n\nGroups are finalized. Use <code>/tourplay</code> to start matches.", parse_mode='HTML')
    else:
        tour.status = 'open'
        await bot.reply_to(message, f"{pe('🔓')} <b>Tour Opened!</b>\n\nYou can modify groups again.", parse_mode='HTML')

@bot.message_handler(commands=['tourplay'])
async def tourplay_cmd(message):
    run_safe_track(message)
    if message.chat.id not in tours: return
    if not await check_bot_admin_access(message): return
    tour = tours[message.chat.id]
    if tour.status != 'locked': return await bot.reply_to(message, f"{pe('❌')} Please <code>/tourlock</code> the tour first.", parse_mode='HTML')
    rows = []
    for grp_name in tour.groups.keys():
        rows.append([{"text": f"Start Group {grp_name}", "callback_data": f"tourstart:{grp_name}", "style": "success"}])
    rows.append([{"text": "Cancel Menu", "callback_data": "ignore_cancel", "style": "danger"}])
    kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
    await bot.reply_to(message, "🏟️ <b>Tour Match Menu</b>\n\nSelect a group to start their match:", parse_mode='HTML', reply_markup=kbd)

@bot.message_handler(commands=['tourend'])
async def tourend_cmd(message):
    run_safe_track(message)
    if message.chat.id not in tours: return
    if not await check_bot_admin_access(message): return
    rows = [
        [{"text": "Delete Tour", "callback_data": "tour_end_confirm", "style": "danger"}],
        [{"text": "Save & Pause Tour", "callback_data": f"pause_tour:{message.chat.id}", "style": "primary"}],
        [{"text": "Keep Tour", "callback_data": "ignore_cancel", "style": "success"}]
    ]
    kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
    await bot.reply_to(message, f"{pe('⚠️')} <b>Are you sure you want to end or pause the ENTIRE Tour?</b>", parse_mode='HTML', reply_markup=kbd)

@bot.message_handler(commands=['tourpause'])
async def tourpause_cmd(message):
    run_safe_track(message)
    if message.chat.id not in tours: return await bot.reply_to(message, "No active tour found to pause.")
    if not await check_bot_admin_access(message): return
    tour = tours[message.chat.id]
    code = await pause_and_save(message.chat.id, tour, True)
    del tours[message.chat.id]
    await bot.reply_to(message, f"⏸ <b>Tour Paused & Saved.</b>\n\n🔑 <b>Code:</b> <code>{code}</code>\n\nUse <code>/tourcontinue {code}</code> to continue later.", parse_mode='HTML')

@bot.message_handler(commands=['tourcontinue'])
async def tourcontinue_cmd(message):
    run_safe_track(message)
    if not await check_bot_admin_access(message): return
    parts = message.text.split()
    if len(parts) < 2: return await bot.reply_to(message, f"{pe('⚠️')} Usage: `/tourcontinue <CODE>`", parse_mode='HTML')
    code = parts[1].strip()
    if message.chat.id in tours: return await bot.reply_to(message, f"{pe('⚠️')} A tour is already running here. End it first.")
    if has_game(message.chat.id): return await bot.reply_to(message, f"{pe('⚠️')} A game is currently running here. End it first.")
    
    obj = await load_and_resume(code, 'tour')
    if not obj: return await bot.reply_to(message, f"{pe('❌')} Invalid or expired Tour Resume Code.")
    obj.chat_id = message.chat.id
    tours[message.chat.id] = obj
    await bot.reply_to(message, "▶️ <b>Tour Resumed Successfully!</b>\n\nThe tour state is restored. Use <code>/tourplay</code> to continue group matches.", parse_mode='HTML')


# ==========================================
# 13. EXCLUSIVE NEW COMMANDS
# ==========================================
@bot.message_handler(commands=['ogw'])
async def ogw_cmd(message):
    run_safe_track(message)
    if message.chat.id not in tours: return await bot.reply_to(message, f"{pe('⚠️')} No active tour in this group.", parse_mode='HTML')
    tour = tours[message.chat.id]
    sorted_runs = sorted(tour.runs.items(), key=lambda x: x[1], reverse=True)[:10]
    text = f"{pe('🏆')} <b>ORANGE CAP LEADERBOARD</b> (Most Runs)\n\n"
    for i, (uid, runs) in enumerate(sorted_runs):
        name = f"<code>{uid}</code>"
        try:
            u = await db.user_map.find_one({"id": uid})
            if u: name = u["firstName"]
        except Exception: pass
        text += f"{i+1}. {html.escape(name)} — <b>{runs} Runs</b>\n"
    if not sorted_runs: text += "No runs scored yet."
    await bot.reply_to(message, text, parse_mode='HTML')

@bot.message_handler(commands=['ogp'])
async def ogp_cmd(message):
    run_safe_track(message)
    if message.chat.id not in tours: return await bot.reply_to(message, f"{pe('⚠️')} No active tour in this group.", parse_mode='HTML')
    tour = tours[message.chat.id]
    sorted_wkts = sorted(tour.wickets.items(), key=lambda x: x[1], reverse=True)[:10]
    text = f"{pe('🏆')} <b>PURPLE CAP LEADERBOARD</b> (Most Wickets)\n\n"
    for i, (uid, wkts) in enumerate(sorted_wkts):
        name = f"<code>{uid}</code>"
        try:
            u = await db.user_map.find_one({"id": uid})
            if u: name = u["firstName"]
        except Exception: pass
        text += f"{i+1}. {html.escape(name)} — <b>{wkts} Wickets</b>\n"
    if not sorted_wkts: text += "No wickets taken yet."
    await bot.reply_to(message, text, parse_mode='HTML')

@bot.message_handler(commands=['startsolo'])
async def startsolo_cmd(message):
    run_safe_track(message)
    chat_id = message.chat.id
    game = get_game(chat_id)
    if not game or game.status != 'waiting': return
    is_normal_admin = (message.from_user.id == game.host_id) or await is_group_admin(chat_id, message.from_user.id)
    if not is_normal_admin and not is_bot_admin(message.from_user.id): return
    if not game.is_special and not game.over_balls: return await bot.reply_to(message, f"{pe('⚠️')} Select over length first!")
    if len(game.players) < 2: return await bot.reply_to(message, f"{pe('⚠️')} Need at least 2 players.")
    asyncio.create_task(begin_game(chat_id))

@bot.message_handler(commands=['addsolo'])
async def addsolo_cmd(message):
    run_safe_track(message)
    chat_id = message.chat.id
    game = get_game(chat_id)
    if not game: return await bot.reply_to(message, f"{pe('⚠️')} No game running.")
    
    if game.is_special or getattr(game, 'is_tour_match', False):
        return await bot.reply_to(message, f"{pe('⚠️')} <b>/addsolo</b> is only available in Normal Matches.", parse_mode='HTML')
        
    if message.from_user.id != game.host_id:
        return await bot.reply_to(message, f"{pe('❌')} Only the Match Host can use /addsolo.", parse_mode='HTML')
    
    if not message.reply_to_message: return await bot.reply_to(message, f"{pe('⚠️')} Reply to a user's message to add them.")
    target = message.reply_to_message.from_user
    
    if is_banned(target.id):
        return await bot.reply_to(message, f"{pe('⚠️')} This user is currently banned from playing for 5 minutes.", parse_mode='HTML')
        
    if get_player(game, target.id): return await bot.reply_to(message, f"{pe('⚠️')} Player is already in the game.")
    
    rows = [
        [{"text": "✅ Confirm", "callback_data": f"addsolo:yes:{target.id}", "style": "success"},
         {"text": "❌ Cancel", "callback_data": f"addsolo:no:{target.id}", "style": "danger"}]
    ]
    kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
    msg = await bot.reply_to(message, f"{pe('⚡️')} <b>{html.escape(target.first_name)}</b>, do you want to join the current match? (60s left)", parse_mode='HTML', reply_markup=kbd)
    
    async def delete_if_ignored(msg_id):
        await asyncio.sleep(60)
        try: await bot.delete_message(chat_id, msg_id)
        except Exception: pass
    asyncio.create_task(delete_if_ignored(msg.message_id))

@bot.message_handler(commands=['removegroup'])
async def removegroup_cmd(message):
    run_safe_track(message)
    if message.chat.id not in tours: return
    if not await check_bot_admin_access(message): return
    tour = tours[message.chat.id]
    if tour.status == 'locked': return await bot.reply_to(message, f"{pe('❌')} Tour is locked! Use <code>/touropen</code> first.", parse_mode='HTML')
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2: return await bot.reply_to(message, f"{pe('⚠️')} Usage: `/removegroup <Group Name>`", parse_mode='HTML')
    g_name = parts[1].strip()
    if g_name in tour.groups:
        del tour.groups[g_name]
        await bot.reply_to(message, f"{pe('✅')} Group <b>{html.escape(g_name)}</b> removed from the tour.", parse_mode='HTML')
    else:
        await bot.reply_to(message, f"{pe('❌')} Group <b>{html.escape(g_name)}</b> not found.", parse_mode='HTML')

@bot.message_handler(commands=['removeplayer'])
async def removeplayer_cmd(message):
    run_safe_track(message)
    if message.chat.id not in tours: return
    if not await check_bot_admin_access(message): return
    tour = tours[message.chat.id]
    if tour.status == 'locked': return await bot.reply_to(message, f"{pe('❌')} Tour is locked! Use <code>/touropen</code> first.", parse_mode='HTML')
    parts = message.text.split()
    if len(parts) < 2: return await bot.reply_to(message, f"{pe('⚠️')} Usage: `/removeplayer <ID/@username>`", parse_mode='HTML')
    target = parts[1].replace('@', '').strip()
    target_id = None
    if target.isdigit(): target_id = int(target)
    else:
        try:
            u = await db.user_map.find_one({"username": re.compile(f"^{target}$", re.I)})
            if u: target_id = u['id']
        except Exception: pass
    
    if not target_id: return await bot.reply_to(message, f"{pe('❌')} User not found.")
    removed = False
    for g_name, players in tour.groups.items():
        for p in players:
            if p.id == target_id:
                players.remove(p)
                removed = True
                break
        if removed: break
        
    if removed: await bot.reply_to(message, f"{pe('✅')} Player removed from the tour.", parse_mode='HTML')
    else: await bot.reply_to(message, f"{pe('❌')} Player is not in any group.", parse_mode='HTML')

# ==========================================
# 14. CALLBACK HANDLERS
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("cm:"))
async def cb_cm(call):
    parts = call.data.split(":")
    chat_id = int(parts[1])
    action = parts[2]
    game = get_game(chat_id)
    if not game:
        return await bot.answer_callback_query(call.id, "Game not found or has ended.", show_alert=True)
    
    if not is_owner(call.from_user.id) and not is_bot_admin(call.from_user.id):
        is_group_adm = await is_group_admin(chat_id, call.from_user.id)
        if not is_group_adm and call.from_user.id != game.host_id:
            return await bot.answer_callback_query(call.id, "Only the Game Host or Admin can toggle this.", show_alert=True)
            
    if action == "toggle": game.commentary_enabled = not game.commentary_enabled
    elif action in ["en", "hi"]: game.commentary_lang = action
    
    def comm_kbd(c_id, en, lang):
        rows = [[{"text": "ON ✅" if en else "OFF ❌", "callback_data": f"cm:{c_id}:toggle", "style": "success" if en else "danger"}],
                [{"text": "English ✅" if lang=='en' else "English", "callback_data": f"cm:{c_id}:en", "style": "primary"}, 
                 {"text": "Hindi ✅" if lang=='hi' else "Hindi", "callback_data": f"cm:{c_id}:hi", "style": "primary"}]]
        return InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
        
    try: await bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=comm_kbd(chat_id, game.commentary_enabled, game.commentary_lang))
    except: pass
    await bot.answer_callback_query(call.id, "Commentary Settings Updated!")

@bot.callback_query_handler(func=lambda call: call.data.startswith("addsolo:"))
async def cb_addsolo(call):
    parts = call.data.split(":")
    action = parts[1]
    target_id = int(parts[2])
    if call.from_user.id != target_id: return await bot.answer_callback_query(call.id, "❌ This is not for you!", show_alert=True)
    
    if is_banned(target_id):
        return await bot.answer_callback_query(call.id, "❌ You are banned for 5 minutes!", show_alert=True)
        
    chat_id = call.message.chat.id
    game = get_game(chat_id)
    if action == "no":
        try: await bot.edit_message_text(f"{pe('❌')} Request Cancelled.", chat_id, call.message.message_id)
        except Exception: pass
        return await bot.answer_callback_query(call.id, "Cancelled.")
    
    if not game:
        try: await bot.edit_message_text(f"{pe('⚠️')} Game has already ended.", chat_id, call.message.message_id)
        except Exception: pass
        return
        
    if game.is_special or getattr(game, 'is_tour_match', False):
        return await bot.answer_callback_query(call.id, "Only available in Normal Matches.", show_alert=True)
        
    if get_player(game, target_id):
        try: await bot.edit_message_text(f"{pe('⚠️')} You are already in the game.", chat_id, call.message.message_id)
        except Exception: pass
        return
        
    new_p = Player(id=target_id, username=call.from_user.username or "", first_name=call.from_user.first_name)
    game.players.append(new_p)
    if game.status == 'waiting':
        await edit_lobby(call.message, game, chat_id)
        try: await bot.delete_message(chat_id, call.message.message_id)
        except Exception: pass
    elif game.status == 'playing':
        game.batting_order.append(target_id)
        batter = get_batter(game)
        if batter and batter.id != target_id: game.bowler_list.append(target_id)
        try: await bot.edit_message_text(f"{pe('✅')} <b>{html.escape(call.from_user.first_name)}</b> joined the live match successfully!", chat_id, call.message.message_id, parse_mode='HTML')
        except Exception: pass
    await bot.answer_callback_query(call.id, "Joined!")

@bot.callback_query_handler(func=lambda call: call.data.startswith("gift:"))
async def cb_giftsetup(call):
    if not is_owner(call.from_user.id): return await bot.answer_callback_query(call.id, "❌ Only Owner can edit gift.", show_alert=True)
    action = call.data.split(":")[1]
    if action == "on": GIFT_CONFIG["status"] = "on"
    elif action == "off": GIFT_CONFIG["status"] = "off"
    elif action == "amt":
        WAITING_FOR_GIFT_AMOUNT.add(call.from_user.id)
        await bot.send_message(call.message.chat.id, f"Current amount is {GIFT_CONFIG['amount']}.\nSend new amount or type 'skip'.")
        return await bot.answer_callback_query(call.id)
    text = f"{pe('🎁')} <b>Shop/Gift Control Panel</b>\n\nStatus: <b>{GIFT_CONFIG['status'].upper()}</b>\nPrice/Amount: <b>{GIFT_CONFIG['amount']} Coins</b>\n\nChoose an action:"
    rows = [
        [{"text": "Turn ON", "callback_data": "gift:on", "style": "success"}, {"text": "Turn OFF", "callback_data": "gift:off", "style": "danger"}],
        [{"text": "Change Amount", "callback_data": "gift:amt", "style": "primary"}]
    ]
    kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
    try: await bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='HTML', reply_markup=kbd)
    except Exception: pass
    await bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("lbc:"))
async def cb_lbc(call):
    tf = call.data.split(":")[1]
    await bot.answer_callback_query(call.id, "Generating Leaderboard...")
    try:
        img_buf, text = await get_leaderboard_data(call.message.chat.id, tf)
        if img_buf:
            media = InputMediaPhoto(img_buf.getvalue(), caption=text, parse_mode='HTML')
            try: await bot.edit_message_media(media=media, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_lbc_keyboard())
            except Exception: pass
        else:
            try: await bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML', reply_markup=get_lbc_keyboard())
            except Exception: pass
    except Exception: pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("pt:"))
async def cb_pt(call):
    chat_id = call.message.chat.id
    if chat_id not in tours: return await bot.answer_callback_query(call.id, "No active tour here.", show_alert=True)
    tour = tours[chat_id]
    action = call.data.split(":")[1]
    if action == "overall":
        pts = sorted(tour.points.items(), key=lambda x: x[1], reverse=True)
        text = f"{pe('🏆')} <b>TOUR POINTS TABLE (OVERALL)</b>\n\n"
        for i, (uid, pt) in enumerate(pts):
            name = f"<code>{uid}</code>" 
            try:
                u = await db.user_map.find_one({"id": uid})
                if u: name = u["firstName"]
            except Exception: pass
            text += f"{i+1}. {html.escape(name)} — <b>{pt} pts</b>\n"
        if not pts: text += "No points yet."
        rows = [[{"text": "Overall", "callback_data": "pt:overall", "style": "primary"}, {"text": "Group Wise", "callback_data": "pt:groups", "style": "primary"}]]
        kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
        try: await bot.edit_message_text(text, chat_id, call.message.message_id, parse_mode='HTML', reply_markup=kbd)
        except Exception: pass
    elif action == "groups":
        text = f"{pe('🏆')} <b>Select Group for Points Table:</b>"
        rows = []
        for g_name in tour.groups.keys(): rows.append([{"text": f"Group {g_name}", "callback_data": f"pt:grp:{g_name}", "style": "success"}])
        rows.append([{"text": "🔙 Back", "callback_data": "pt:overall", "style": "danger"}])
        kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
        try: await bot.edit_message_text(text, chat_id, call.message.message_id, parse_mode='HTML', reply_markup=kbd)
        except Exception: pass
    elif action == "grp":
        g_name = call.data.split(":")[2]
        group_players = tour.groups.get(g_name, [])
        group_pids = [p.id for p in group_players]
        group_pts = {uid: pt for uid, pt in tour.points.items() if uid in group_pids}
        pts = sorted(group_pts.items(), key=lambda x: x[1], reverse=True)
        text = f"{pe('🏆')} <b>TOUR POINTS TABLE (GROUP {g_name})</b>\n\n"
        for i, (uid, pt) in enumerate(pts):
            name = f"<code>{uid}</code>" 
            try:
                u = await db.user_map.find_one({"id": uid})
                if u: name = u["firstName"]
            except Exception: pass
            text += f"{i+1}. {html.escape(name)} — <b>{pt} pts</b>\n"
        if not pts: text += "No points yet."
        rows = [[{"text": "🔙 Back to Groups", "callback_data": "pt:groups", "style": "danger"}]]
        kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
        try: await bot.edit_message_text(text, chat_id, call.message.message_id, parse_mode='HTML', reply_markup=kbd)
        except Exception: pass
    await bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("regtour:"))
async def cb_regtour(call):
    tour_id_str = call.data.split(":")[1]
    from bson.objectid import ObjectId
    try:
        tour = await db.open_tournaments.find_one({"_id": ObjectId(tour_id_str)})
        if not tour: return await bot.answer_callback_query(call.id, "❌ Tournament not found or closed.", show_alert=True)
        chk = await db.tour_registrations.find_one({"tour_id": ObjectId(tour_id_str), "user_id": call.from_user.id})
        if chk: return await bot.answer_callback_query(call.id, "⚠️ You are already registered for this tournament!", show_alert=True)
        await db.tour_registrations.insert_one({"tour_id": ObjectId(tour_id_str), "user_id": call.from_user.id, "username": call.from_user.username, "first_name": call.from_user.first_name})
        await bot.answer_callback_query(call.id, "✅ Registration Successful!", show_alert=True)
        await bot.send_message(call.message.chat.id, f"🎉 <b>Successfully registered for tournament:</b> {html.escape(tour['name'])}\n\n<i>Get ready for the battlefield, champion! Keep an eye on the group for matches.</i>", parse_mode='HTML')
    except Exception: pass

@bot.callback_query_handler(func=lambda call: call.data == "help_menu")
async def cb_help_menu(call):
    rows = [[{"text": "Normal Match Guide", "callback_data": "help_guide:normal", "style": "primary"}],
            [{"text": "Special Match Guide", "callback_data": "help_guide:special", "style": "primary"}],
            [{"text": "Tour Match Guide", "callback_data": "help_guide:tour", "style": "primary"}]]
    kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
    text = "🛠 <b>Welcome to the Help Center!</b>\n\nChoose a guide to learn more about the commands and features:"
    try:
        if call.message.content_type == 'photo': await bot.edit_message_caption(caption=text, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML', reply_markup=kbd)
        else: await bot.edit_message_text(text=text, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML', reply_markup=kbd)
    except Exception: pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("help_guide:"))
async def cb_help_guide(call):
    guide_type = call.data.split(":")[1]
    if guide_type == 'normal':
        txt = ("📖 <b>Normal Match Guide</b>\n\n"
               "• <code>/start</code> : Initialize the bot.\n"
               "• <code>Join</code> : Anyone can join the open lobby.\n"
               "• <code>3 Balls / 6 Balls</code> : Choose the over length.\n"
               "• <code>Zeros</code> : Only 1 Zero allowed per 3 balls, 2 per 6 balls.\n"
               "• <code>Batting</code> : Type 0 to 6 in the main group.\n"
               "• <code>Bowling</code> : Select 1 to 6 on the secret DM button.\n"
               "• <code>Timeout</code> : 70s max to bowl/bat.\n"
               "• <code>/cancel</code> : Requests to cancel active game.")
    elif guide_type == 'special':
        txt = ("🏆 <b>Special Match Guide (Admin Only)</b>\n\n"
               "• <code>/specialmatch</code> : Opens a special 6-ball match lobby.\n"
               "• <code>/addplayer @user</code> : Admin adds players manually.\n"
               "• <code>/startmatch</code> / <code>/startsolo</code> : Forces the match to begin.\n"
               "• Everyone bats against everyone in a rotating bowler format.")
    else:
        txt = ("🌍 <b>Tour Match Guide (Admin Only)</b>\n\n"
               "• <code>/specialtour [Name]</code> : Creates a master tour.\n"
               "• <code>/addgroup 1 @user1</code> : Adds players to Group 1.\n"
               "• <code>/tourlock</code> : Locks groups to prevent changes.\n"
               "• <code>/tourplay</code> : Gives buttons to start matches per group.\n"
               "• <code>/pt</code> : View Points Table.\n"
               "• <code>/tourpause</code> : Save & Pause the tour.\n"
               "• <code>/tourcontinue</code> : Resume a saved tour.")
        
    rows = [[{"text": "Back to Menu", "callback_data": "help_menu", "style": "danger"}]]
    kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
    try:
        if call.message.content_type == 'photo': await bot.edit_message_caption(caption=txt, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML', reply_markup=kbd)
        else: await bot.edit_message_text(text=txt, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML', reply_markup=kbd)
    except Exception: pass

@bot.callback_query_handler(func=lambda call: call.data == "tour_end_confirm")
async def cb_tour_end(call):
    if call.message.chat.id in tours:
        del tours[call.message.chat.id]
        await bot.edit_message_text(f"{pe('✅')} <b>Tour ended and deleted successfully.</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith("pause:"))
async def cb_pause(call):
    chat_id = int(call.data.split(":")[1])
    game = get_game(chat_id)
    if not game: return await bot.answer_callback_query(call.id, "No active game found to pause.", show_alert=True)
    code = await pause_and_save(chat_id, game, False)
    delete_game(chat_id)
    await bot.edit_message_text(f"⏸ <b>Game Paused & Saved.</b>\n\n🔑 <b>Code:</b> <code>{code}</code>\n\nUse <code>/resumematch {code}</code> to continue later.", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith("pause_tour:"))
async def cb_pause_tour(call):
    chat_id = int(call.data.split(":")[1])
    if chat_id not in tours: return await bot.answer_callback_query(call.id, "No active tour found to pause.", show_alert=True)
    tour = tours[chat_id]
    code = await pause_and_save(chat_id, tour, True)
    del tours[chat_id]
    await bot.edit_message_text(f"⏸ <b>Tour Paused & Saved.</b>\n\n🔑 <b>Code:</b> <code>{code}</code>\n\nUse <code>/tourcontinue {code}</code> to continue later.", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith("tourstart:"))
async def cb_tourstart(call):
    if not is_bot_admin(call.from_user.id): return
    grp_name = call.data.split(":")[1]
    chat_id = call.message.chat.id
    if chat_id not in tours: return
    tour = tours[chat_id]
    if has_game(chat_id): return await bot.answer_callback_query(call.id, "⚠️ A game is already running in this group!", show_alert=True)
    players = tour.groups.get(grp_name, [])
    if len(players) < 2: return await bot.answer_callback_query(call.id, f"Group {grp_name} doesn't have enough players (Min 2).", show_alert=True)
    game = Game(chat_id=chat_id, status='playing', host_id=call.from_user.id, is_special=True, over_balls=6, created_at=datetime.now(timezone.utc))
    game.players = [Player(id=p.id, username=p.username, first_name=p.first_name) for p in players]
    p_ids = [p.id for p in game.players]
    random.shuffle(p_ids)
    game.batting_order = p_ids; game.awaiting_bat = False
    game.group_link = await get_group_link(chat_id)
    game.current_over_balls = 0; game.current_over_zeros = 0; game.bowler_idx = 0
    game.bowler_list = build_bowler_list(game)
    game.is_tour_match = True; game.tour_group_name = grp_name
    set_game(chat_id, game)
    await bot.answer_callback_query(call.id)
    try: await bot.edit_message_text(f"{pe('✅')} <b>Group {html.escape(grp_name)} match initialized!</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML')
    except Exception: pass
    order_lines = "\n".join([f"  {i+1}. {mention_user(get_player(game, id))}" for i, id in enumerate(game.batting_order)])
    await bot.send_message(chat_id, f"{pe('🏏')} <b>Tour Match: Group {html.escape(grp_name)}!</b>\n\n<b>Batting Order:</b>\n{order_lines}\n\n<i>6-ball overs · Auto-rotating bowlers</i> 🏟️", parse_mode='HTML')
    await start_round(chat_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("statsview:"))
async def cb_statsview(call):
    parts = call.data.split(":")
    if str(call.from_user.id) != parts[1]: return await bot.answer_callback_query(call.id, "You can only view your own stats here.", show_alert=True)
    view_type = parts[2]
    user_id = int(parts[1])
    s = await get_stats(user_id, view_type)
    if not s or s.get('matches', 0) == 0: return await bot.answer_callback_query(call.id, f"No stats available for this mode.", show_alert=True)
    rows = [
        [{"text": "Overall Stats", "callback_data": f"statsview:{user_id}:overall", "style": "primary"}],
        [{"text": "Solo Match Stats", "callback_data": f"statsview:{user_id}:solo", "style": "primary"}],
        [{"text": "Tour Match Stats", "callback_data": f"statsview:{user_id}:tour", "style": "primary"}]
    ]
    kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
    await bot.answer_callback_query(call.id)
    try: 
        img_buf = await asyncio.to_thread(generate_stats_card_image, s, view_type, s.get('active_theme', 'default'))
        caption = format_stats_profile_html(s, view_type)
        if img_buf:
            media = InputMediaPhoto(img_buf.getvalue(), caption=caption, parse_mode='HTML')
            await bot.edit_message_media(media, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=kbd)
        else:
            await bot.edit_message_text(caption, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML', reply_markup=kbd)
    except Exception as e: print(e)

@bot.callback_query_handler(func=lambda call: call.data == "ignore_cancel")
async def cb_ignore(call):
    try: await bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception: pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("cancel:"))
async def cb_cancel_req(call):
    chat_id = int(call.data.split(":")[1])
    game = get_game(chat_id)
    if not game: return
    is_normal_admin = (call.from_user.id == game.host_id) or await is_group_admin(chat_id, call.from_user.id)
    is_bot_adm = is_bot_admin(call.from_user.id)
    if game.is_special and not is_bot_adm: return
    if not game.is_special and not is_normal_admin and not is_bot_adm: return
    delete_game(chat_id)
    try: await bot.edit_message_text(text=f"{pe('❌')} <b>Game deleted forever.</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML')
    except Exception: pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("cancel_req:"))
async def cb_cancel_lobby(call):
    chat_id = int(call.data.split(":")[1])
    game = get_game(chat_id)
    if not game: return
    is_normal_admin = (call.from_user.id == game.host_id) or await is_group_admin(chat_id, call.from_user.id)
    is_bot_adm = is_bot_admin(call.from_user.id)
    if game.is_special and not is_bot_adm: return
    if not game.is_special and not is_normal_admin and not is_bot_adm: return
    delete_game(chat_id)
    try:
        if call.message.content_type == 'photo': await bot.edit_message_caption(caption=f"{pe('❌')} <b>Lobby cancelled.</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML')
        else: await bot.edit_message_text(text=f"{pe('❌')} <b>Lobby cancelled.</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML')
    except Exception: pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_item:"))
async def cb_buy_item(call):
    if GIFT_CONFIG["status"] != "on": return await bot.answer_callback_query(call.id, "🚫 Out of stock!", show_alert=True)
    item = call.data.split(":")[1]
    cost = 3000 if item == 'booster' else (10000 if item.endswith('_theme') else GIFT_CONFIG["amount"])
    user_id = call.from_user.id
    success = await deduct_coins(user_id, cost)
    if not success: return await bot.answer_callback_query(call.id, f"❌ Not enough coins! You need {cost} coins.", show_alert=True)
    await bot.answer_callback_query(call.id, "✅ Request sent to Admin! Coins deducted.", show_alert=True)
    rows = [[{"text": "Confirm", "callback_data": f"admin_buy:app:{user_id}:{item}", "style": "success"}, {"text": "Reject", "callback_data": f"admin_buy:rej:{user_id}:{item}", "style": "danger"}]]
    admin_kbd = InlineKeyboardMarkup.de_json({"inline_keyboard": rows})
    req_text = f"{pe('🛍️')} <b>New Buy Request!</b>\n\nUser: <a href='tg://user?id={user_id}'>{html.escape(call.from_user.first_name)}</a>\nItem: <b>{item.replace('_theme', ' Theme').capitalize()}</b>\nCost: <b>{cost} Coins</b>\n\nPlease Confirm or Reject."
    for adm in list(DYNAMIC_ADMINS) + [ROOT_ADMIN_ID]:
        try: await bot.send_message(adm, req_text, parse_mode='HTML', reply_markup=admin_kbd)
        except Exception: pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_buy:"))
async def cb_admin_buy(call):
    if not is_bot_admin(call.from_user.id): return
    parts = call.data.split(":")
    if len(parts) != 4: return
    _, action, user_id_str, item = parts
    user_id = int(user_id_str)
    success = await process_admin_buy(user_id, item, action)
    if not success: return
    new_text = call.message.text + f"\n\n<i>(Status: {'✅ Approved' if action == 'app' else '❌ Rejected'} by Admin)</i>"
    try: await bot.edit_message_text(new_text, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='HTML')
    except Exception: return
    try:
        if action == 'app': await bot.send_message(user_id, f"🎉 <b>Congratulations!</b>\n\nYour request for <b>{item.replace('_theme', ' Theme').capitalize()}</b> has been {pe('✅')} <b>Approved</b>!", parse_mode='HTML')
        else: await bot.send_message(user_id, f"{pe('😔')} <b>Request Rejected!</b>\n\nYour Coins have been refunded.", parse_mode='HTML')
    except Exception: pass

@bot.callback_query_handler(func=lambda call: re.match(r"^solo:(-?\d+)$", call.data))
async def cb_solo(call):
    chat_id = int(re.match(r"^solo:(-?\d+)$", call.data).group(1))
    if chat_id in tours: return await bot.answer_callback_query(call.id, "Tour Active! Match cannot be started.", show_alert=True)
    if has_game(chat_id): return
    await bot.answer_callback_query(call.id)
    game = Game(chat_id=chat_id, status='waiting', host_id=call.from_user.id, is_special=False, created_at=datetime.now(timezone.utc))
    set_game(chat_id, game)
    opts = {"parse_mode": 'HTML', "reply_markup": lobby_keyboard(chat_id, False, game.over_balls)}
    msg = None
    try: 
        if call.message.content_type == 'photo': msg = await bot.edit_message_caption(caption=lobby_text(game), chat_id=call.message.chat.id, message_id=call.message.message_id, **opts)
        else: msg = await bot.edit_message_text(text=lobby_text(game), chat_id=call.message.chat.id, message_id=call.message.message_id, **opts)
    except Exception: pass
    if msg:
        game.lobby_message_id = msg.message_id
        try: await bot.pin_chat_message(chat_id, msg.message_id, disable_notification=True)
        except Exception: pass

@bot.callback_query_handler(func=lambda call: re.match(r"^over:(-?\d+):(3|6)$", call.data))
async def cb_over(call):
    match = re.match(r"^over:(-?\d+):(3|6)$", call.data)
    chat_id, selected = int(match.group(1)), int(match.group(2))
    game = get_game(chat_id)
    if not game or game.status != 'waiting' or game.is_special: return
    is_normal_admin = (call.from_user.id == game.host_id) or await is_group_admin(chat_id, call.from_user.id)
    if not is_normal_admin and not is_bot_admin(call.from_user.id): return
    game.over_balls = selected; game.current_over_zeros = 0
    await edit_lobby(call.message, game, chat_id)

@bot.callback_query_handler(func=lambda call: re.match(r"^join:(-?\d+)$", call.data))
async def cb_join(call):
    chat_id = int(re.match(r"^join:(-?\d+)$", call.data).group(1))
    u = call.from_user
    if is_banned(u.id): return
    game = get_game(chat_id)
    if not game or game.status != 'waiting': return
    if game.is_special: return
    if not game.over_balls: return
    if get_player(game, u.id): return
    
    game.players.append(Player(id=u.id, username=u.username or "", first_name=u.first_name))
    if len(game.players) == 1:
        game.lobby_timer_task = asyncio.create_task(_lobby_timer_task(chat_id))
    await bot.answer_callback_query(call.id, f"✅ Joined!")
    await edit_lobby(call.message, game, chat_id)

@bot.callback_query_handler(func=lambda call: re.match(r"^leave:(-?\d+)$", call.data))
async def cb_leave(call):
    chat_id = int(re.match(r"^leave:(-?\d+)$", call.data).group(1))
    game = get_game(chat_id)
    if not game or game.status != 'waiting': return
    p = get_player(game, call.from_user.id)
    if not p: return
    game.players.remove(p)
    await edit_lobby(call.message, game, chat_id)

@bot.callback_query_handler(func=lambda call: re.match(r"^force:(-?\d+)$", call.data))
async def cb_force(call):
    chat_id = int(re.match(r"^force:(-?\d+)$", call.data).group(1))
    if chat_id in tours and not get_game(chat_id).is_tour_match: 
        return await bot.answer_callback_query(call.id, "Tour Active! Cannot force start normal match.", show_alert=True)
    game = get_game(chat_id)
    if not game or game.status != 'waiting': return
    is_normal_admin = (call.from_user.id == game.host_id) or await is_group_admin(chat_id, call.from_user.id)
    is_bot_adm = is_bot_admin(call.from_user.id)
    if game.is_special and not is_bot_adm: return
    if not game.is_special and not is_normal_admin and not is_bot_adm: return
    if not game.is_special and not game.over_balls: return
    if len(game.players) < 2: return
    asyncio.create_task(begin_game(chat_id))

# ==========================================
# 15. GLOBAL MESSAGE HANDLER
# ==========================================
@bot.message_handler(content_types=['photo', 'text'])
async def handle_all_messages(message):
    run_safe_track(message)
    
    if message.chat.type == 'private' and message.from_user.id in WAITING_FOR_GIFT_AMOUNT:
        WAITING_FOR_GIFT_AMOUNT.remove(message.from_user.id)
        if message.text and message.text.strip().lower() == 'skip':
            return await bot.reply_to(message, f"{pe('✅')} Skipped. Amount not changed.", parse_mode='HTML')
        elif message.text and message.text.strip().isdigit():
            GIFT_CONFIG['amount'] = int(message.text.strip())
            return await bot.reply_to(message, f"{pe('✅')} Shop amount updated to {GIFT_CONFIG['amount']} Coins.", parse_mode='HTML')
        else:
            return await bot.reply_to(message, f"{pe('❌')} Invalid amount. Skipped.", parse_mode='HTML')
    
    if message.from_user.id in TOUR_SETUP_STATE and message.chat.type == 'private':
        state = TOUR_SETUP_STATE[message.from_user.id]
        if state["step"] == 1:
            if not message.text: return await bot.reply_to(message, f"{pe('⚠️')} Send GC ID (e.g., -100123456).", parse_mode='HTML')
            try:
                gc_id = int(message.text.strip())
                state["gc_id"] = gc_id
                state["step"] = 2
                await bot.reply_to(message, f"{pe('✅')} GC ID Saved.\nNow send a <b>Banner Photo</b> for the Tournament, or send <code>skip</code> to proceed without banner.", parse_mode='HTML')
            except ValueError:
                await bot.reply_to(message, f"{pe('❌')} Invalid ID. Send only numbers.", parse_mode='HTML')
            return

        elif state["step"] == 2:
            banner_id = None
            if message.content_type == 'photo': banner_id = message.photo[-1].file_id
            elif message.text and message.text.lower() == "skip": pass
            else: return await bot.reply_to(message, f"{pe('⚠️')} Send a photo or send <code>skip</code>.", parse_mode='HTML')
            
            try:
                await db.open_tournaments.insert_one({"name": state["name"], "chat_id": state["gc_id"], "banner_file_id": banner_id, "created_by": message.from_user.id, "created_at": datetime.now(timezone.utc)})
            except Exception: pass
            
            del TOUR_SETUP_STATE[message.from_user.id]
            await bot.send_message(message.chat.id, f"🎉 <b>Tournament Setup Complete!</b>\n\nName: {html.escape(state['name'])}\nGroup: <code>{state['gc_id']}</code>\n\nUsers can now use /register in my DM.", parse_mode='HTML')
            return
            
    if message.chat.type == 'private' and message.from_user.id in WAITING_FOR_ADS:
        WAITING_FOR_ADS.remove(message.from_user.id)
        await bot.reply_to(message, f"{pe('📢')} Broadcasting your message everywhere. This will take some time...", parse_mode='HTML')
        try:
            chats = await db.known_chats.find().to_list(length=None)
            success = 0
            for c in chats:
                try:
                    await bot.copy_message(c["chat_id"], from_chat_id=message.chat.id, message_id=message.message_id)
                    success += 1; await asyncio.sleep(0.01)
                except Exception: pass
            return await bot.reply_to(message, f"{pe('✅')} Ads Broadcast finished. Sent successfully to {success} groups/users.", parse_mode='HTML')
        except Exception: pass

    if message.chat.type != 'private':
        chat_id = message.chat.id
        game = get_game(chat_id)
        if not game or game.status != 'playing' or not game.awaiting_bat: return
        batter = get_batter(game)
        if not batter or batter.id != message.from_user.id: return
        
        try: num = int(message.text.strip())
        except ValueError: return
        
        if num < 0 or num > 6: return
        if num == 0 and not can_play_zero(game):
            await bot.reply_to(message, zero_limit_message(), parse_mode='HTML')
            return
        
        game.batter_timeout_count[batter.id] = 0
        clear_all_round_timers(game)
        game.awaiting_bat = False; game.pending_bat = num

        thumb = random.choice(THUMBS_UP_EMOJIS)
        try: await bot.send_message(chat_id, thumb, reply_to_message_id=message.message_id, parse_mode='HTML')
        except Exception: pass
        
        await process_shot(chat_id)

# ==========================================
# 16. MAIN LAUNCHER & FAKE PORT & MENU
# ==========================================
async def handle_web(request):
    return web.Response(text="Bot is running smoothly on Render!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_web)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"✅ Fake Port bound on {port} for Render")

async def set_bot_commands():
    cmds = [
        BotCommand("start", "Start the Bot"),
        BotCommand("help", "Guides & How to Play"),
        BotCommand("startsolo", "Force start a Solo Match"),
        BotCommand("addsolo", "Add user to live match (Reply)"),
        BotCommand("balance", "Check your Coins"),
        BotCommand("send", "Transfer coins to someone"),
        BotCommand("buy", "Buy Premium Items"),
        BotCommand("gift", "Open Shop Settings (Owner)"),
        BotCommand("themes", "Equip your Stats Theme"),
        BotCommand("score", "Check Live Match Score"),
        BotCommand("host", "Check current match host"),
        BotCommand("stats", "Check your Career Stats"),
        BotCommand("tourstats", "Check your Tour Stats"),
        BotCommand("lbc", "View All-Time Leaderboard"),
        BotCommand("daily", "View Daily Leaderboard"),
        BotCommand("weekly", "View Weekly Leaderboard"),
        BotCommand("monthly", "View Monthly Leaderboard"),
        BotCommand("register", "Register for Tournaments"),
        BotCommand("pt", "View Tour Points Table"),
        BotCommand("ogw", "Tour Orange Cap List"),
        BotCommand("ogp", "Tour Purple Cap List"),
        BotCommand("playai", "Play 1v1 match vs Bot"),
        BotCommand("promo", "Redeem Promo Code"),
        BotCommand("cancel", "Cancel/Pause Game"),
        BotCommand("adminpanel", "Open Admin Control Panel"),
        BotCommand("bug", "Report a Bug / Request Feature")
    ]
    try: await bot.set_my_commands(cmds)
    except Exception: pass

async def main():
    global bot_username
    try:
        me = await bot.get_me()
        bot_username = me.username
        print(f"✅ Stars League Cricket Bot launching as @{bot_username}")
    except Exception as e:
        print(f"Failed to get bot info: {e}")
    
    await init_db()
    await set_bot_commands()
    await start_web_server()
    
    while True:
        try:
            await bot.polling(non_stop=True, request_timeout=90)
        except Exception as e:
            print(f"Polling error: {e}")
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())