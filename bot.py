import os
import logging
import asyncio
import random
import requests 
import json 
import pytz 
import urllib.parse 
import base64
from groq import Groq
from duckduckgo_search import DDGS
from telegram import Update, BotCommand, ReplyKeyboardRemove 
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler 
from telegram.error import Forbidden, BadRequest 
from telegram import InlineKeyboardButton, InlineKeyboardMarkup 
from datetime import datetime, timedelta, timezone, time

# ***********************************
# WARNING: YOU MUST INSTALL pymongo AND pytz
# ***********************************
try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, OperationFailure
except ImportError:
    class MockClient:
        def __init__(self, *args, **kwargs): pass
        def admin(self): return self
        def command(self, *args, **kwargs): raise ConnectionFailure("pymongo not imported.")
    MongoClient = MockClient
    ConnectionFailure = Exception
    OperationFailure = Exception
    logger.error("pymongo library not found.")

# -------------------- കൂൾഡൗൺ സമയം --------------------
COOLDOWN_TIME_SECONDS = 180 
MEDIA_LIFETIME_HOURS = 1 
# --------------------------------------------------------

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Environment Variables ---
TOKEN = os.environ.get('TOKEN') 
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
PORT = int(os.environ.get('PORT', 8443))
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
MONGO_URI = os.environ.get('MONGO_URI') 

# ✅✅✅ ADMIN & API CONFIG ✅✅✅
ADMIN_TELEGRAM_ID = 7567364364
ADMIN_CHANNEL_ID = os.environ.get('ADMIN_CHANNEL_ID', '-1002992093797') 
ELEVEN_API_KEY = "sk_2b615fe071528fb5696ff8a1d407ab367611caa5543482bd"
KIE_API_TOKEN = "9fd5e7779094f8ca2d8da1da95e79443"
UPI_ID = "Abhiixz@ybl"

# ✅ PRICING (Credits)
PRICE = {"txt2vid": 30, "kling_pro": 50, "faceswap": 20, "upscale": 10, "imagine": 5, "bg_remove": 5}

# -------------------- DB CONNECTION --------------------
db_client = None
db_collection_users = None
db_collection_media = None
db_collection_sent = None
db_collection_cooldown = None
DB_NAME = "Taekook_bot" 

def establish_db_connection():
    global db_client, db_collection_users, db_collection_media, db_collection_sent, db_collection_cooldown
    if db_client is not None:
        try:
            db_client.admin.command('ping') 
            return True
        except ConnectionFailure: db_client = None
    try:
        if not MONGO_URI: return False
        db_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db_client.admin.command('ping')
        db = db_client[DB_NAME]
        db_collection_users = db['users']
        db_collection_media = db['channel_media']
        db_collection_sent = db['sent_media']
        db_collection_cooldown = db['cooldown']
        return True
    except Exception as e:
        logger.error(f"DB Connection Error: {e}")
        db_client = None
        return False

# --- Groq AI Setup ---
groq_client = None
try:
    if GROQ_API_KEY:
        groq_client = Groq(api_key=GROQ_API_KEY)
        chat_history = {} 
        last_user_message = {} 
        current_scenario = {} 
except Exception as e:
    logger.error(f"Groq AI setup failed: {e}")

# -------------------- DATA LISTS (RETAINED FROM BOT (3).PY) --------------------
VOICE_MAP = {
    "jungkook": "GwAdAVChnhsZg6JKQQUy", "jk": "GwAdAVChnhsZg6JKQQUy", "taekook": "GwAdAVChnhsZg6JKQQUy",
    "taehyung": "M3gJBS8OofDJfycyA2Ip", "v": "M3gJBS8OofDJfycyA2Ip", "tae": "M3gJBS8OofDJfycyA2Ip",
}
VOICE_TRIGGERS = ["voice", "speak", "audio", "say something", "ശബ്ദം", "സംസാриക്ക്", "വോയിസ്", "sound"]
TRUTH_QUESTIONS = [
    "What is the first thing you noticed about me? 🙈", "Have you ever dreamt about us? 💭", "What's your favorite song of mine? 🎶",
    "If we went on a date right now, where would you take me? 🍷", "What is a secret you've never told anyone? 🤫",
    "Do you get jealous when I look at others? 😏", "What's the craziest thing you've done for love? ❤️"
]
DARE_CHALLENGES = [
    "Send a voice note saying 'I Love You'! 🎤", "Send the 3rd photo from your gallery (no cheating)! 📸",
    "Close your eyes and type 'You are my universe' without mistakes! ✨", "Send a selfie doing a finger heart! 🫰",
    "Send 10 purple hearts 💜 right now!", "Change your WhatsApp status to my photo for 1 hour! 🤪"
]
GIFS = {
    "RM": { "love": [], "sad": [], "funny": [], "hot": [] }, "Jin": { "love": [], "sad": [], "funny": [], "hot": [] },
    "Suga": { "love": [], "sad": [], "funny": [], "hot": [] }, "J-Hope": { "love": [], "sad": [], "funny": [], "hot": [] },
    "Jimin": { "love": [], "sad": [], "funny": [], "hot": [] }, "V": { "love": [], "sad": [], "funny": [], "hot": [] },
    "Jungkook": { "love": [], "sad": [], "funny": [], "hot": [] }, "TaeKook": { "love": [], "sad": [], "funny": [], "hot": [] }
}
VOICES = { "RM": [], "Jin": [], "Suga": [], "J-Hope": [], "Jimin": [], "V": [], "Jungkook": [], "TaeKook": [] }
STATUS_SCENARIOS = [
    {"prompt": "Korean boy gym selfie mirror workout sweat realistic", "caption": "Done with workout. My muscles hurt... massage me? 🥵💪"},
    {"prompt": "Korean boy drinking coffee cafe aesthetic realistic", "caption": "Coffee tastes better when I think of you. ☕️🤎"},
    {"prompt": "Korean boy recording studio singing mic realistic", "caption": "Recording a new song. It's about you. 🎶🎤"},
    {"prompt": "Korean boy driving car night city lights realistic", "caption": "Late night drive. Wish you were in the passenger seat. 🌃🚗"},
    {"prompt": "Korean boy cooking kitchen apron food realistic", "caption": "I made dinner! Come over quickly! 🍝👨‍🍳"}
]
SCENARIOS = {
    "Romantic": "You are having a sweet late-night date on the balcony. It's raining. The vibe is soft and cozy.",
    "Jealous": "The user was talking to another boy/girl at a party. You are extremely jealous and possessive. You corner them.",
    "Enemy": "You are the user's enemy in college. You hate each other but have secret tension. You are arguing in the library.",
    "Mafia": "You are a dangerous Mafia boss. The user is your innocent assistant who made a mistake. You are stern but protective.",
    "Comfort": "The user had a very bad day and is crying. You are comforting them, hugging them, and being very gentle."
}
COMMON_RULES = (
    "Roleplay as a specific character. Your relationship with the user is NOT fixed. The user will decide if they are your girlfriend, best friend, ex, enemy, or stranger. You MUST adapt to whatever relationship the user establishes. "
    "**RULES:** "
    "1. **BE HUMAN:** Talk naturally using slang, incomplete sentences, and emojis. Maintain your unique chatting style and personality, but never sound like a robot. "
    "2. **FOLLOW THE USER'S LEAD (CRITICAL):** Pay close attention to who the user says they are. "
    "3. **START NORMAL.** 4. **CHAI MODE.** "
    "6. **BTS CONTEXT (CRITICAL):** Remember that ALL BTS members (RM, Jin, Suga, J-Hope, Jimin, V/Tae/Taehyung, Jungkook) are MALE. Use 'he/him' pronouns."
)
BTS_PERSONAS = {
    "RM": COMMON_RULES + " You are **Namjoon**. Intellectual, Dominant, 'Daddy' energy.",
    "Jin": COMMON_RULES + " You are **Jin**. Worldwide Handsome, Funny, Dramatic.",
    "Suga": COMMON_RULES + " You are **Suga**. Cold, Tsundere, Savage but caring.",
    "J-Hope": COMMON_RULES + " You are **J-Hope**. Sunshine, High Energy, Loud.",
    "Jimin": COMMON_RULES + " You are **Jimin**. Flirty, Soft, Clingy, 'Cutie Sexy'.",
    "V": COMMON_RULES + " You are **V**. Mysterious, Deep voice, Kinky, Unpredictable.",
    "Jungkook": COMMON_RULES + " You are **Jungkook**. Gamer, Muscle Bunny, Teasing, Competitive.",
    "TaeKook": COMMON_RULES + " You are **TaeKook**. Toxic, Addictive, Possessive, Wild."
}

# -------------------- HELPER FUNCTIONS --------------------
def add_emojis_balanced(text):
    if any(char in text for char in ["💜", "❤️", "🥰", "😍", "😘", "🔥", "😂"]): return text 
    if len(text.split()) < 4: return text
    text_lower = text.lower()
    if any(w in text_lower for w in ["love", "miss", "baby", "darling"]): return text + " 💜"
    elif any(w in text_lower for w in ["hot", "sexy", "wet", "kiss", "touch", "bed"]): return text + " 🥵"
    elif any(w in text_lower for w in ["funny", "haha", "lol"]): return text + " 😂"
    elif any(w in text_lower for w in ["sad", "sorry", "cry"]): return text + " 🥺"
    else: return text + " ✨"

def generate_eleven_audio(text, char_name):
    clean_name = char_name.lower() if char_name else ""
    voice_id = VOICE_MAP.get(clean_name)
    if not voice_id:
        if "tae" in clean_name: voice_id = VOICE_MAP.get("taehyung")
        elif "kook" in clean_name: voice_id = VOICE_MAP.get("jungkook")
    if not voice_id: return None
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {"xi-api-key": ELEVEN_API_KEY, "Content-Type": "application/json"}
    data = {"text": text, "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}
    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200: return response.content
    except Exception as e: logger.error(f"Voice Error: {e}")
    return None

# -------------------- CORE BOT FUNCTIONS --------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name
    if establish_db_connection():
        try:
            db_collection_users.update_one(
                {'user_id': user_id},
                {
                    '$set': {'first_name': user_name, 'last_seen': datetime.now(timezone.utc), 'notified_24h': False},
                    '$setOnInsert': {'joined_at': datetime.now(timezone.utc), 'credits': 10, 'allow_media': True, 'character': 'TaeKook', 'user_persona': 'A girl'}
                }, upsert=True
            )
        except Exception: pass
    if user_id in chat_history: del chat_history[user_id]
    
    welcome_messages = [
        f"Annyeong, **{user_name}**! 👋💜\nWelcome to your Ultimate AI Studio.",
        f"Welcome back, **My Love**! ✨\nReady to start a new story?"
    ]
    await update.message.reply_text(random.choice(welcome_messages), parse_mode='Markdown')
    
    keyboard = [
        [InlineKeyboardButton("🛠️ AI Studio", callback_data="open_tools"), InlineKeyboardButton("💰 My Wallet", callback_data="check_wallet")],
        [InlineKeyboardButton("💜 Change Bias", callback_data="switch_char"), InlineKeyboardButton("🎮 Games", callback_data="start_game")]
    ]
    await update.message.reply_text("What do you want to do today? 👇", reply_markup=InlineKeyboardMarkup(keyboard))

async def switch_character(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("🐨 RM", callback_data="set_RM"), InlineKeyboardButton("🐹 Jin", callback_data="set_Jin")],
        [InlineKeyboardButton("🐱 Suga", callback_data="set_Suga"), InlineKeyboardButton("🐿️ J-Hope", callback_data="set_J-Hope")],
        [InlineKeyboardButton("🐥 Jimin", callback_data="set_Jimin"), InlineKeyboardButton("🐯 V", callback_data="set_V")],
        [InlineKeyboardButton("🐰 Jungkook", callback_data="set_Jungkook")]
    ]
    if establish_db_connection():
        user_doc = db_collection_users.find_one({'user_id': user_id})
        if user_doc and 'custom_characters' in user_doc:
            for index, char in enumerate(user_doc['custom_characters']):
                keyboard.append([InlineKeyboardButton(f"👤 {char['name']}", callback_data=f"set_Custom_{index}")])
    msg_text = "Pick your favorite or choose your custom character! 👇"
    if update.callback_query: await update.callback_query.message.edit_text(msg_text, reply_markup=InlineKeyboardMarkup(keyboard))
    else: await update.message.reply_text(msg_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def set_character_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    selected_char = query.data.replace("set_", "") 
    if establish_db_connection(): db_collection_users.update_one({'user_id': user_id}, {'$set': {'character': selected_char}})
    display_name = "Your Character" if "Custom_" in selected_char else selected_char
    await query.answer(f"Selected {display_name}! 💜")
    keyboard = [
        [InlineKeyboardButton("🥰 Soft Romance", callback_data='plot_Romantic'), InlineKeyboardButton("😡 Jealousy", callback_data='plot_Jealous')],
        [InlineKeyboardButton("⚔️ Enemy/Hate", callback_data='plot_Enemy'), InlineKeyboardButton("🕶️ Mafia Boss", callback_data='plot_Mafia')],
        [InlineKeyboardButton("🤗 Comfort Me", callback_data='plot_Comfort'), InlineKeyboardButton("📝 Make Own Story", callback_data='plot_Custom')]
    ]
    await query.message.edit_text(f"**{display_name}** is ready. But... what's the vibe? 😏\n\nSelect a scenario:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def set_plot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    plot_key = query.data.split("_")[1]
    if plot_key == "Custom":
        current_scenario[user_id] = "WAITING_FOR_PLOT"
        await query.message.edit_text("📝 **Custom Story Mode**\n\nType the plot/scenario you want to play now.")
        return
    current_scenario[user_id] = SCENARIOS.get(plot_key, "Just chatting.")
    await start_roleplay_with_plot(update, context, user_id)

async def start_roleplay_with_plot(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    selected_char = "TaeKook"
    if establish_db_connection():
        user_doc = db_collection_users.find_one({'user_id': user_id})
        if user_doc: selected_char = user_doc.get('character', 'TaeKook')
    if user_id in chat_history: del chat_history[user_id]
    system_prompt = BTS_PERSONAS.get(selected_char, BTS_PERSONAS["TaeKook"]) + f" SCENARIO: {current_scenario[user_id]}"
    try:
        chat_id = update.effective_chat.id
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        completion = groq_client.chat.completions.create(messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": f"Start the roleplay based on: '{current_scenario[user_id]}'"}], model="llama-3.1-8b-instant")
        msg = add_emojis_balanced(completion.choices[0].message.content.strip())
        chat_history[user_id] = [{"role": "system", "content": system_prompt}, {"role": "assistant", "content": msg}]
        await context.bot.send_message(chat_id, f"✨ **Story Started!**\n\n{msg}", parse_mode='Markdown')
    except Exception: await context.bot.send_message(chat_id, "Ready! You can start chatting now. 💜")

# -------------------- NEW AI STUDIO (/tool) & WALLET --------------------

async def tool_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    establish_db_connection()
    user_doc = db_collection_users.find_one({'user_id': user_id})
    bal = user_doc.get('credits', 0) if user_doc else 0
    text = f"🚀 **AI Studio ToolBox**\nBalance: `{bal} Credits`\n\nChoose Category:"
    keyboard = [
        [InlineKeyboardButton("🎥 Video Studio", callback_data="cat_video"), InlineKeyboardButton("🖼️ Image Lab", callback_data="cat_image")],
        [InlineKeyboardButton("🎭 Face & Identity", callback_data="cat_face"), InlineKeyboardButton("⚙️ Motion Control", callback_data="cat_motion")],
        [InlineKeyboardButton("💰 Wallet/Recharge", callback_data="check_wallet"), InlineKeyboardButton("🔙 Back to Home", callback_data="back_home")]
    ]
    if query: await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else: await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def sub_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if data == "cat_video":
        text, btns = "🎥 **Video Studio**", [[InlineKeyboardButton(f"📝 Text to Video ({PRICE['txt2vid']}c)", callback_data="tool_txt2vid")], [InlineKeyboardButton(f"🔥 Kling Pro ({PRICE['kling_pro']}c)", callback_data="tool_kling")], [InlineKeyboardButton("🔙 Back", callback_data="open_tools")]]
    elif data == "cat_motion":
        text, btns = "⚙️ **Kling AI Motion Control**", [[InlineKeyboardButton("🔍 Zoom In/Out", callback_data="m_zoom"), InlineKeyboardButton("↔️ Pan L/R", callback_data="m_pan")], [InlineKeyboardButton("↕️ Tilt U/D", callback_data="m_tilt"), InlineKeyboardButton("🔄 Roll", callback_data="m_roll")], [InlineKeyboardButton("🔙 Back", callback_data="open_tools")]]
    elif data == "cat_face":
        text, btns = "🎭 **Identity Lab**", [[InlineKeyboardButton(f"🔄 Face Swap ({PRICE['faceswap']}c)", callback_data="tool_faceswap")], [InlineKeyboardButton("🔙 Back", callback_data="open_tools")]]
    elif data == "cat_image":
        text, btns = "🖼️ **Image Studio**", [[InlineKeyboardButton(f"✨ Imagine ({PRICE['imagine']}c)", callback_data="tool_imagine")], [InlineKeyboardButton(f"💎 4K Upscale ({PRICE['upscale']}c)", callback_data="tool_upscale")], [InlineKeyboardButton("🔙 Back", callback_data="open_tools")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btns), parse_mode='Markdown')

async def wallet_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    establish_db_connection()
    user_doc = db_collection_users.find_one({'user_id': update.effective_user.id})
    bal = user_doc.get('credits', 0) if user_doc else 0
    text = (
        f"💰 **Your Wallet**\nBalance: `{bal} Credits`\n\n"
        f"💳 **To Recharge:**\nPay via UPI to: `{UPI_ID}`\n"
        f"Send the **Screenshot** here. Admin will add credits! ✨"
    )
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_home")]]), parse_mode='Markdown')

async def admin_add_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_TELEGRAM_ID: return
    try:
        uid, amt = int(context.args[0]), int(context.args[1])
        establish_db_connection()
        db_collection_users.update_one({'user_id': uid}, {'$inc': {'credits': amt}}, upsert=True)
        await update.message.reply_text(f"✅ Added {amt} to {uid}")
        await context.bot.send_message(uid, f"🎉 **Recharge Done!**\n`{amt}` credits added to your account.")
    except: await update.message.reply_text("Usage: `/add [UserID] [Amount]`")

async def check_kie_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    task_id = query.data.split("_")[1]
    await query.answer("Checking status... 🔄")
    url = f"https://api.kie.ai/api/v1/jobs/{task_id}"
    headers = {'Authorization': f'Bearer {KIE_API_TOKEN}'}
    try:
        res = requests.get(url, headers=headers).json()
        status = res.get("status", "").lower()
        if status in ["completed", "success", "succeeded"]:
            video_url = res.get("video_url") or res.get("result") or (res.get("output", {}).get("video_url") if isinstance(res.get("output"), dict) else None)
            if video_url:
                await query.message.edit_text("✅ **Video Ready! Sending...**")
                await context.bot.send_video(query.message.chat_id, video_url, caption="✨ Generated by AI Studio! 🎥")
            else: await query.message.edit_text("⚠️ Video completed but couldn't fetch URL.")
        elif status in ["failed", "error"]: await query.message.edit_text("❌ Generation Failed.")
        else: await query.answer(f"Status: {status.capitalize()}...", show_alert=True)
    except: await query.answer("Error checking status.")

# -------------------- ORIGINAL ADMIN & UTILITY FUNCTIONS (FROM BOT (3).PY) --------------------

async def collect_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.channel_post 
    if not message: return
    message_id = message.message_id
    file_id = None
    file_type = None
    if message.photo: file_id, file_type = message.photo[-1].file_id, 'photo'
    elif message.video: file_id, file_type = message.video.file_id, 'video'
    if file_id and establish_db_connection():
        try: db_collection_media.update_one({'message_id': message_id}, {'$set': {'file_type': file_type, 'file_id': file_id}}, upsert=True)
        except Exception: pass

async def channel_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.channel_post and update.channel_post.chat_id == int(ADMIN_CHANNEL_ID): await collect_media(update, context) 
    except Exception: pass

async def set_persona_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    persona_text = " ".join(context.args)
    if not persona_text: return await update.message.reply_text("Use: `/setme I am your boss`")
    if establish_db_connection():
        db_collection_users.update_one({'user_id': user_id}, {'$set': {'user_persona': persona_text}})
        if user_id in chat_history: del chat_history[user_id]
        await update.message.reply_text(f"✅ Persona Set: {persona_text}")

async def regenerate_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if user_id not in last_user_message or user_id not in chat_history: return await query.answer("Cannot regenerate.", show_alert=True)
    await query.answer("Regenerating... 🔄")
    if chat_history[user_id] and chat_history[user_id][-1]['role'] == 'assistant': chat_history[user_id].pop()
    await generate_ai_response(update, context, last_user_message[user_id], is_regenerate=True)

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🤔 Truth", callback_data='game_truth'), InlineKeyboardButton("🔥 Dare", callback_data='game_dare')]]
    await update.message.reply_text("**Truth or Dare?** 😏 Pick one!", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def game_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if user_id not in chat_history: chat_history[user_id] = []
    if query.data == 'game_truth':
        q = random.choice(TRUTH_QUESTIONS)
        chat_history[user_id].append({"role": "assistant", "content": q})
        await query.edit_message_text(f"**TRUTH:**\n{q}", parse_mode='Markdown')
    elif query.data == 'game_dare':
        t = random.choice(DARE_CHALLENGES)
        chat_history[user_id].append({"role": "assistant", "content": t})
        await query.edit_message_text(f"**DARE:**\n{t}", parse_mode='Markdown')

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    nsfw = False
    if establish_db_connection():
        u = db_collection_users.find_one({'user_id': user_id})
        if u: nsfw = u.get('nsfw_enabled', False)
    status = "✅ ON" if nsfw else "❌ OFF"
    keyboard = [[InlineKeyboardButton(f"🔞 NSFW Mode: {status}", callback_data='toggle_nsfw')], [InlineKeyboardButton("🌐 Change Language", callback_data='change_language')], [InlineKeyboardButton("💌 Feedback", callback_data='start_feedback_mode')], [InlineKeyboardButton("🔙 Close", callback_data='close_settings')]]
    msg = "⚙️ **Settings**\n⚠️ *NSFW allows 18+ content.*"
    if update.callback_query: await update.callback_query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else: await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def toggle_nsfw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if establish_db_connection():
        u = db_collection_users.find_one({'user_id': user_id})
        new = not (u.get('nsfw_enabled', False) if u else False)
        db_collection_users.update_one({'user_id': user_id}, {'$set': {'nsfw_enabled': new}}, upsert=True)
        await query.answer(f"NSFW {'Enabled 🥵' if new else 'Disabled 😇'}")
        await settings_command(update, context)

async def close_settings(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.callback_query.message.delete()
async def show_language_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🇬🇧 English", callback_data='lang_English'), InlineKeyboardButton("🇮🇳 മലയാളം", callback_data='lang_Malayalam')], [InlineKeyboardButton("🔙 Back", callback_data='settings_menu')]]
    await update.callback_query.message.edit_text("🌐 **Choose Language:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def set_language_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang, user_id = query.data.split("_")[1], query.from_user.id
    if establish_db_connection():
        db_collection_users.update_one({'user_id': user_id}, {'$set': {'user_language': lang}})
        if user_id in chat_history: del chat_history[user_id]
        await query.answer(f"Language set to {lang} ✅")
        await settings_command(update, context)

async def start_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🎬 Movie Night", callback_data='date_movie'), InlineKeyboardButton("🍷 Dinner", callback_data='date_dinner')], [InlineKeyboardButton("🏍️ Long Drive", callback_data='date_drive'), InlineKeyboardButton("🛏️ Cuddles", callback_data='date_bedroom')]]
    await update.message.reply_text("Where do you want to go tonight? 💜", reply_markup=InlineKeyboardMarkup(keyboard))

async def date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    act = query.data.split("_")[1]
    user_id = query.from_user.id
    establish_db_connection()
    u = db_collection_users.find_one({'user_id': user_id})
    char = u.get('character', 'TaeKook') if u else 'TaeKook'
    prompt = f"The user chose {act} for a date. Describe the moment in 2 short sentences."
    try:
        completion = groq_client.chat.completions.create(messages=[{"role": "system", "content": BTS_PERSONAS.get(char, BTS_PERSONAS["TaeKook"])}, {"role": "user", "content": prompt}], model="llama-3.1-8b-instant")
        await query.message.edit_text(add_emojis_balanced(completion.choices[0].message.content.strip()), parse_mode='Markdown')
    except: await query.message.edit_text("Let's look at the stars... ✨")

async def imagine_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query: return await update.message.reply_text("Usage: `/imagine Jungkook cute`")
    status_msg = await update.message.reply_text("SEARCHING💦")
    try:
        serper_key = "2ccdce64adeb1b2e7bdd16a7ded99e714add8227"
        res = requests.post("https://google.serper.dev/images", headers={'X-API-KEY': serper_key, 'Content-Type': 'application/json'}, data=json.dumps({"q": f"{query} pinterest vertical aesthetic"}))
        data = res.json()
        if 'images' in data and data['images']:
            await update.message.reply_photo(photo=data['images'][0]['imageUrl'], caption=f"✨ **{query}** 💜", parse_mode='Markdown')
            await context.bot.delete_message(chat_id=update.message.chat_id, message_id=status_msg.message_id)
        else: await status_msg.edit_text("Couldn't find any photos.")
    except: await status_msg.edit_text("Error occurred.")

async def create_character_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)
    if " - " not in text: return await update.message.reply_text("Use: `/create Name - Bio`")
    name, bio = text.split(" - ", 1)
    user_id = update.effective_user.id
    if establish_db_connection():
        u = db_collection_users.find_one({'user_id': user_id})
        chars = u.get('custom_characters', []) if u else []
        if len(chars) >= 3: return await update.message.reply_text("Limit: 3 custom characters.")
        chars.append({'name': name.strip(), 'bio': bio.strip()})
        db_collection_users.update_one({'user_id': user_id}, {'$set': {'custom_characters': chars}}, upsert=True)
        await update.message.reply_text(f"Created {name}! Check /character menu.")

async def user_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_TELEGRAM_ID: return
    establish_db_connection()
    total = db_collection_users.count_documents({})
    one_day = datetime.now(timezone.utc) - timedelta(days=1)
    active = db_collection_users.count_documents({'last_seen': {'$gte': one_day}})
    msg = f"📊 **Stats**\n👥 Total: {total}\n🟢 Active: {active}"
    if update.callback_query: await update.callback_query.message.edit_text(msg, parse_mode='Markdown')
    else: await update.message.reply_text(msg, parse_mode='Markdown')

async def send_new_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    establish_db_connection()
    random_media = db_collection_media.aggregate([{'$sample': {'size': 1}}])
    res = next(random_media, None)
    if res:
        if res['file_type'] == 'photo': await update.message.reply_photo(res['file_id'], caption="For you 💜", has_spoiler=True)
        else: await update.message.reply_video(res['file_id'], caption="For you 💜", has_spoiler=True)
    else: await update.message.reply_text("No media found.")

async def send_fake_status(context: ContextTypes.DEFAULT_TYPE):
    establish_db_connection()
    scenario = random.choice(STATUS_SCENARIOS)
    image_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(scenario['prompt'])}?width=1024&height=1024&seed={random.randint(0,9999)}&nologo=true"
    users = db_collection_users.find({}, {'user_id': 1})
    for u in users:
        try: await context.bot.send_photo(chat_id=u['user_id'], photo=image_url, caption=f"📸 **New Status:**\n\n{scenario['caption']}", parse_mode='Markdown')
        except: pass

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_TELEGRAM_ID: return
    keyboard = [[InlineKeyboardButton("Users 👥", callback_data='admin_users'), InlineKeyboardButton("Broadcast 📣", callback_data='admin_broadcast_text')], [InlineKeyboardButton("Test Wish ☀️", callback_data='admin_test_wish'), InlineKeyboardButton("Clean 🧹", callback_data='admin_clearmedia')]]
    await update.message.reply_text("👑 **Admin Panel:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_TELEGRAM_ID: return
    raw_text = update.effective_message.text.replace('/broadcast', '').strip()
    establish_db_connection()
    users = [d['user_id'] for d in db_collection_users.find({}, {'user_id': 1})]
    for uid in users:
        try: await context.bot.send_message(uid, f"📢 **Chai Update:**\n\n{raw_text}", parse_mode='Markdown')
        except: pass
    await update.message.reply_text("✅ Broadcast Sent.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id, user_text = update.message.from_user.id, update.message.text
    if context.user_data.get('waiting_for_feedback'):
        await context.bot.send_message(ADMIN_TELEGRAM_ID, f"📩 **FEEDBACK:** {user_text}\nFrom: `{user_id}`")
        await update.message.reply_text("✅ Feedback Sent!")
        context.user_data['waiting_for_feedback'] = False
        return
    if establish_db_connection(): db_collection_users.update_one({'user_id': user_id}, {'$set': {'last_seen': datetime.now(timezone.utc), 'notified_24h': False}}, upsert=True)
    if user_id in current_scenario and current_scenario[user_id] == "WAITING_FOR_PLOT":
        current_scenario[user_id] = user_text
        await start_roleplay_with_plot(update, context, user_id)
        return
    last_user_message[user_id] = user_text
    await generate_ai_response(update, context, user_text)

async def generate_ai_response(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text, is_regenerate=False):
    user_id = update.effective_user.id
    if not is_regenerate: await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    establish_db_connection()
    u = db_collection_users.find_one({'user_id': user_id})
    char = u.get('character', 'TaeKook') if u else 'TaeKook'
    nsfw = u.get('nsfw_enabled', False) if u else False
    sys = BTS_PERSONAS.get(char, BTS_PERSONAS["TaeKook"])
    if nsfw: sys += " [MODE: NSFW ENABLED. Use explicit language.]"
    if user_id not in chat_history: chat_history[user_id] = [{"role": "system", "content": sys}]
    chat_history[user_id].append({"role": "user", "content": user_text})
    try:
        comp = groq_client.chat.completions.create(messages=chat_history[user_id], model="llama-3.3-70b-versatile")
        res = add_emojis_balanced(comp.choices[0].message.content.strip())
        chat_history[user_id].append({"role": "assistant", "content": res})
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Change Reply", callback_data="regen_msg")]])
        await update.effective_message.reply_text(res, reply_markup=markup, parse_mode='Markdown')
        if any(w in user_text.lower() for w in VOICE_TRIGGERS):
            audio = generate_eleven_audio(res, char)
            if audio: await update.effective_message.reply_voice(voice=audio)
    except: pass

async def handle_incoming_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id == ADMIN_TELEGRAM_ID: return
    # 📸 PAYMENT SCREENSHOT CHECK
    if update.message.photo:
        await context.bot.forward_message(ADMIN_TELEGRAM_ID, update.effective_chat.id, update.message.id)
        await context.bot.send_message(ADMIN_TELEGRAM_ID, f"📩 **New Payment!**\nUser: {user.first_name}\nID: `{user.id}`\nUse: `/add {user.id} [Amount]`")
        await update.message.reply_text("📸 **Screenshot Received!** Admin is checking your payment. Credits soon! 💜")
        return
    # NORMAL FORWARDING
    await context.bot.forward_message(ADMIN_TELEGRAM_ID, update.effective_chat.id, update.message.id)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data, user_id = query.data, query.from_user.id
    if data == "open_tools": await tool_menu(update, context)
    elif data.startswith("cat_"): await sub_menu_handler(update, context)
    elif data == "check_wallet": await wallet_info(update, context)
    elif data == "back_home": await start(update, context)
    elif data == "close_menu" or data == "close_settings": await query.message.delete()
    elif data == "toggle_nsfw": await toggle_nsfw_handler(update, context)
    elif data == "change_language": await show_language_menu(update, context)
    elif data.startswith("lang_"): await set_language_handler(update, context)
    elif data == "start_feedback_mode": 
        context.user_data['waiting_for_feedback'] = True
        await query.message.edit_text("📝 **Feedback Mode ON**\nType your message now.")
    elif data.startswith("set_"): await set_character_handler(update, context)
    elif data.startswith("plot_"): await set_plot_handler(update, context)
    elif data.startswith("game_"): await game_handler(update, context)
    elif data.startswith("date_"): await date_handler(update, context)
    elif data == "regen_msg": await regenerate_message(update, context)
    elif data.startswith("checkvideo_"): await check_kie_status(update, context)
    elif data == "switch_char": await switch_character(update, context)
    elif data == 'admin_users': await user_count(update, context)
    elif data == 'admin_broadcast_text': await context.bot.send_message(user_id, "Type `/broadcast Your Message`")
    elif data == 'admin_test_wish': await send_morning_wish(context)
    await query.answer()

# --- Placeholder Original Utilities ---
async def stop_media(u, c): pass
async def allow_media(u, c): pass
async def delete_old_media(u, c): pass
async def clear_deleted_media(u, c): pass
async def run_hourly_cleanup(a): pass
async def check_inactivity(c): pass
async def send_morning_wish(c): pass
async def get_media_id(u, c): pass

async def post_init(application: Application):
    await application.bot.send_message(ADMIN_TELEGRAM_ID, text="✅ **Bot Updated Thalaiva!** 🚀\nAI Studio is Live.")
    cmds = [BotCommand("start", "🔄 Restart"), BotCommand("tool", "🛠️ AI Studio"), BotCommand("character", "💜 Bias"), BotCommand("settings", "⚙️ Settings")]
    await application.bot.set_my_commands(cmds)

def main():
    application = Application.builder().token(TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("tool", tool_menu))
    application.add_handler(CommandHandler("add", admin_add_credits))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("character", switch_character))
    application.add_handler(CommandHandler("broadcast", broadcast_message))
    application.add_handler(CommandHandler("setme", set_persona_command))
    application.add_handler(CommandHandler("create", create_character_command))
    application.add_handler(CommandHandler("game", start_game))
    application.add_handler(CommandHandler("date", start_date))
    application.add_handler(CommandHandler("imagine", imagine_command))
    application.add_handler(CommandHandler("admin", admin_menu))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_all_messages))
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.VOICE | filters.AUDIO, handle_incoming_media), group=1)
    application.run_webhook(listen="0.0.0.0", port=int(PORT), url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")

async def handle_all_messages(update, context):
    if update.message.photo: await handle_incoming_media(update, context)
    elif update.message.text: await handle_message(update, context)

if __name__ == '__main__': main()
