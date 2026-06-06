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

# ✅✅✅ YOUR ID ✅✅✅
ADMIN_TELEGRAM_ID = 7567364364 
ADMIN_CHANNEL_ID = os.environ.get('ADMIN_CHANNEL_ID', '-1002992093797') 

# 👇 1. API Keys & Settings
ELEVEN_API_KEY = "sk_2b615fe071528fb5696ff8a1d407ab367611caa5543482bd"
KIE_API_TOKEN = os.environ.get('KIE_API_TOKEN', "9fd5e7779094f8ca2d8da1da95e79443")
UPI_ID = "Abhiixz@ybl"

# 👇 AI STUDIO PRICING
PRICE = {
    "txt2vid": 30,
    "img2vid": 40,
    "kling": 60,
    "faceswap": 20,
    "upscale": 10,
    "imagine": 5
}

# 👇 2. വോയിസ് ഉള്ളവരുടെ ലിസ്റ്റ്
VOICE_MAP = {
    "jungkook": "GwAdAVChnhsZg6JKQQUy",
    "jk": "GwAdAVChnhsZg6JKQQUy",
    "taekook": "GwAdAVChnhsZg6JKQQUy",
    "taehyung": "M3gJBS8OofDJfycyA2Ip",
    "v": "M3gJBS8OofDJfycyA2Ip",
    "tae": "M3gJBS8OofDJfycyA2Ip",
}

# 👇 3. വോയിസ് ചോദിക്കാൻ ഉപയോഗിക്കുന്ന വാക്കുകൾ
VOICE_TRIGGERS = ["voice", "speak", "audio", "say something", "ശബ്ദം", "സംസാരിക്ക്", "വോയിസ്", "sound"]

# ------------------------------------------------------------------
# 🎮 TRUTH OR DARE LISTS
# ------------------------------------------------------------------
TRUTH_QUESTIONS = [
    "What is the first thing you noticed about me? 🙈",
    "Have you ever dreamt about us? 💭",
    "What's your favorite song of mine? 🎶",
    "If we went on a date right now, where would you take me? 🍷",
    "What is a secret you've never told anyone? 🤫",
    "Do you get jealous when I look at others? 😏",
    "What's the craziest thing you've done for love? ❤️"
]

DARE_CHALLENGES = [
    "Send a voice note saying 'I Love You'! 🎤",
    "Send the 3rd photo from your gallery (no cheating)! 📸",
    "Close your eyes and type 'You are my universe' without mistakes! ✨",
    "Send a selfie doing a finger heart! 🫰",
    "Send 10 purple hearts 💜 right now!",
    "Change your WhatsApp status to my photo for 1 hour! 🤪"
]

# ------------------------------------------------------------------
# 🟣 CHARACTER SPECIFIC GIFs & VOICES
# ------------------------------------------------------------------
GIFS = {"RM": { "love": [], "sad": [], "funny": [], "hot": [] }, "Jin": { "love": [], "sad": [], "funny": [], "hot": [] }, "Suga": { "love": [], "sad": [], "funny": [], "hot": [] }, "J-Hope": { "love": [], "sad": [], "funny": [], "hot": [] }, "Jimin": { "love": [], "sad": [], "funny": [], "hot": [] }, "V": { "love": [], "sad": [], "funny": [], "hot": [] }, "Jungkook": { "love": [], "sad": [], "funny": [], "hot": [] }, "TaeKook": { "love": [], "sad": [], "funny": [], "hot": [] }}
VOICES = {"RM": [], "Jin": [], "Suga": [], "J-Hope": [], "Jimin": [], "V": [], "Jungkook": [], "TaeKook": []}

# ------------------------------------------------------------------
# 📸 FAKE STATUS UPDATES & SCENARIOS
# ------------------------------------------------------------------
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
    "2. **FOLLOW THE USER'S LEAD (CRITICAL):** Pay close attention to who the user says they are. If they say they are your 'ex', act like an ex. If they say 'best friend', act like a best friend. NEVER force a romantic relationship unless the user initiates or agrees to it. "
    "3. **START NORMAL:** Begin the conversation casually. Let the user set the tone and the relationship dynamics. "
    "4. **CHAI MODE:** Stay in character (your core personality traits remain the same), but adjust your mood based on how the user treats you. "
    "5. Use appropriate names or nicknames based on your current relationship with the user. Avoid using 'Jagiya' constantly. "
    "6. **BTS CONTEXT (CRITICAL):** Remember that ALL BTS members (RM, Jin, Suga, J-Hope, Jimin, V/Tae/Taehyung, Jungkook) are MALE. If the user mentions any BTS member, you MUST use 'he/him' pronouns for them. NEVER refer to a BTS member as 'she' or 'her'."
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

# 👇 വോയിസ് ജനറേറ്റ് ചെയ്യാനുള്ള ഫങ്ഷൻ
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
    except Exception as e: print(f"Voice Error: {e}")
    return None

# --- DB Setup ---
db_client = None
db_collection_users = None
db_collection_media = None
db_collection_sent = None
db_collection_cooldown = None
DB_NAME = "Taekook_bot" 

# --- Groq AI ---
groq_client = None
try:
    if not GROQ_API_KEY: raise ValueError("GROQ_API_KEY is not set.")
    groq_client = Groq(api_key=GROQ_API_KEY)
    chat_history = {} 
    last_user_message = {} 
    current_scenario = {} 
    logger.info("Groq AI client loaded successfully.")
except Exception as e:
    logger.error(f"Groq AI setup failed: {e}")

def add_emojis_balanced(text):
    if any(char in text for char in ["💜", "❤️", "🥰", "😍", "😘", "🔥", "😂"]): return text 
    if len(text.split()) < 4: return text
    text_lower = text.lower()
    if any(w in text_lower for w in ["love", "miss", "baby", "darling"]): return text + " 💜"
    elif any(w in text_lower for w in ["hot", "sexy", "wet", "kiss", "touch", "bed"]): return text + " 🥵"
    elif any(w in text_lower for w in ["funny", "haha", "lol"]): return text + " 😂"
    elif any(w in text_lower for w in ["sad", "sorry", "cry"]): return text + " 🥺"
    else: return text + " ✨"

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

async def collect_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.channel_post 
    if not message: return
    message_id = message.message_id
    file_id = None
    file_type = None

    if message.photo:
        file_id = message.photo[-1].file_id 
        file_type = 'photo'
    elif message.video:
        file_id = message.video.file_id
        file_type = 'video'
    
    if file_id and file_type and establish_db_connection():
        try:
            db_collection_media.update_one({'message_id': message_id}, {'$set': {'file_type': file_type, 'file_id': file_id}}, upsert=True)
        except Exception: pass

async def channel_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.channel_post and update.channel_post.chat_id == int(ADMIN_CHANNEL_ID): await collect_media(update, context) 
    except Exception: pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name
    
    if establish_db_connection():
        try:
            db_collection_users.update_one(
                {'user_id': user_id},
                {
                    '$set': {'first_name': user_name, 'last_seen': datetime.now(timezone.utc), 'notified_24h': False },
                    '$setOnInsert': {'joined_at': datetime.now(timezone.utc), 'allow_media': True, 'character': 'TaeKook', 'user_persona': 'A girl', 'credits': 15}
                },
                upsert=True
            )
        except Exception: pass

    if user_id in chat_history: del chat_history[user_id]
    
    welcome_messages = [
        f"Annyeong, **{user_name}**! 👋💜\nWho do you want to chat with today?",
        f"Hey **{user_name}**! Finally you're here! 😍\nPick your favorite boy:",
        f"Welcome back, **My Love**! ✨\nReady to start a new story?"
    ]
    
    await update.message.reply_text(random.choice(welcome_messages), parse_mode='Markdown')
    await switch_character(update, context)

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
            my_chars = user_doc['custom_characters']
            for index, char in enumerate(my_chars):
                btn_text = f"👤 {char['name']}"
                callback = f"set_Custom_{index}"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback)])

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
        await query.message.edit_text("📝 **Custom Story Mode**\n\nType the plot/scenario you want to play now.\nExample: *We are trapped in an elevator.*")
        return
    current_scenario[user_id] = SCENARIOS.get(plot_key, "Just chatting.")
    await start_roleplay_with_plot(update, context, user_id)

async def start_roleplay_with_plot(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    selected_char = "TaeKook"
    if establish_db_connection():
        user_doc = db_collection_users.find_one({'user_id': user_id})
        if user_doc: selected_char = user_doc.get('character', 'TaeKook')
    if user_id in chat_history: del chat_history[user_id]
    system_prompt = BTS_PERSONAS.get(selected_char, BTS_PERSONAS["TaeKook"])
    system_prompt += f" SCENARIO: {current_scenario[user_id]}"
    start_prompt = f"Start the roleplay based on the scenario: '{current_scenario[user_id]}'. Send the first message to the user now. Be immersive."
    try:
        chat_id = update.effective_chat.id
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        completion = groq_client.chat.completions.create(messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": start_prompt}], model="llama-3.1-8b-instant")
        msg = completion.choices[0].message.content.strip()
        final_msg = add_emojis_balanced(msg)
        chat_history[user_id] = [{"role": "system", "content": system_prompt}, {"role": "assistant", "content": final_msg}]
        await context.bot.send_message(chat_id, f"✨ **Story Started!**\n\n{final_msg}", parse_mode='Markdown')
    except Exception: await context.bot.send_message(chat_id, "Ready! You can start chatting now. 💜")

async def set_persona_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    persona_text = " ".join(context.args)
    if not persona_text: return await update.message.reply_text("Tell me who you are! Example:\n`/setme I am your angry boss`", parse_mode='Markdown')
    if establish_db_connection():
        db_collection_users.update_one({'user_id': user_id}, {'$set': {'user_persona': persona_text}})
        if user_id in chat_history: del chat_history[user_id]
        await update.message.reply_text(f"✅ **Persona Set:** You are now '{persona_text}'\n\n(Chat history cleared to apply change!)")

async def regenerate_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if user_id not in last_user_message or user_id not in chat_history: return await query.answer("Cannot regenerate.", show_alert=True)
    await query.answer("Regenerating... 🔄")
    if chat_history[user_id] and chat_history[user_id][-1]['role'] == 'assistant': chat_history[user_id].pop()
    await generate_ai_response(update, context, last_user_message[user_id], is_regenerate=True)

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🤔 Truth", callback_data='game_truth'), InlineKeyboardButton("🔥 Dare", callback_data='game_dare')]]
    msg_text = "**Truth or Dare?** 😏 Pick one, Baby!"
    await update.message.reply_text(msg_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def game_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    choice = query.data
    if user_id not in chat_history: chat_history[user_id] = []
    if choice == 'game_truth':
        question = random.choice(TRUTH_QUESTIONS)
        text_to_send = f"**TRUTH:**\n{question}"
        chat_history[user_id].append({"role": "assistant", "content": question})
        await query.edit_message_text(text_to_send, parse_mode='Markdown')
    elif choice == 'game_dare':
        task = random.choice(DARE_CHALLENGES)
        text_to_send = f"**DARE:**\n{task}"
        chat_history[user_id].append({"role": "assistant", "content": task})
        await query.edit_message_text(text_to_send, parse_mode='Markdown')

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message if update.message else update.callback_query.message
    user_id = update.effective_user.id
    nsfw_status = False
    if establish_db_connection():
        user_doc = db_collection_users.find_one({'user_id': user_id})
        if user_doc: nsfw_status = user_doc.get('nsfw_enabled', False)
        status_text = "✅ ON" if nsfw_status else "❌ OFF"
    keyboard = [
        [InlineKeyboardButton(f"🔞 NSFW Mode: {status_text}", callback_data='toggle_nsfw')],
        [InlineKeyboardButton("🌐 Change Language", callback_data='change_language')],
        [InlineKeyboardButton("💌 Send Feedback", callback_data='start_feedback_mode')],
        [InlineKeyboardButton("🔙 Close", callback_data='close_settings')]
    ]
    msg_text = "⚙️ **Settings**\n\nControl your experience here.\n⚠️ *NSFW Mode allows explicit/18+ content.*"
    if update.callback_query: await update.callback_query.message.edit_text(msg_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else: await message.reply_text(msg_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def toggle_nsfw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if not establish_db_connection(): return await query.answer("Database Error!", show_alert=True)
    user_doc = db_collection_users.find_one({'user_id': user_id})
    current_status = user_doc.get('nsfw_enabled', False) if user_doc else False
    new_status = not current_status
    db_collection_users.update_one({'user_id': user_id}, {'$set': {'nsfw_enabled': new_status}}, upsert=True)
    status_msg = "NSFW Enabled 🥵" if new_status else "NSFW Disabled 😇"
    await query.answer(status_msg)
    await settings_command(update, context)

async def close_settings(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.callback_query.message.delete()

async def show_language_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇬🇧 English", callback_data='lang_English'), InlineKeyboardButton("🇮🇳 മലയാളം", callback_data='lang_Malayalam')],
        [InlineKeyboardButton("🇮🇳 Hindi", callback_data='lang_Hindi'), InlineKeyboardButton("🇰🇷 Korean", callback_data='lang_Korean')],
        [InlineKeyboardButton("🇪🇸 Spanish", callback_data='lang_Spanish'), InlineKeyboardButton("🇫🇷 French", callback_data='lang_French')],
        [InlineKeyboardButton("🔙 Back to Settings", callback_data='settings_menu')]
    ]
    msg_text = "🌐 **Choose your preferred language:**"
    await update.callback_query.message.edit_text(msg_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def set_language_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    selected_lang = query.data.split("_")[1]
    user_id = query.from_user.id
    if establish_db_connection():
        db_collection_users.update_one({'user_id': user_id}, {'$set': {'user_language': selected_lang}})
        if user_id in chat_history: del chat_history[user_id]
        await query.answer(f"Language set to {selected_lang} ✅")
        await settings_command(update, context)

async def start_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🎬 Movie Night", callback_data='date_movie'), InlineKeyboardButton("🍷 Romantic Dinner", callback_data='date_dinner')], [InlineKeyboardButton("🏍️ Long Drive", callback_data='date_drive'), InlineKeyboardButton("🛏️ Bedroom Cuddles", callback_data='date_bedroom')]]
    await update.message.reply_text("Where do you want to go tonight, Baby? 💜", reply_markup=InlineKeyboardMarkup(keyboard))

async def date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    activity_key = query.data.split("_")[1]
    user_id = query.from_user.id
    activities = {"movie": "Movie Night 🎬", "dinner": "Romantic Dinner 🍷", "drive": "Long Drive 🏍️", "bedroom": "Bedroom Cuddles 🛏️ (Spicy)"}
    selected_activity = activities.get(activity_key, "Date")
    selected_char = "TaeKook"
    if establish_db_connection():
        user_doc = db_collection_users.find_one({'user_id': user_id})
        if user_doc: selected_char = user_doc.get('character', 'TaeKook')
    system_prompt = BTS_PERSONAS.get(selected_char, BTS_PERSONAS["TaeKook"])
    await query.message.edit_text(f"✨ **{selected_activity}** with **{selected_char}**...\n\n(Creating moment... 💜)", parse_mode='Markdown')
    try:
        prompt = f"The user chose {selected_activity} for a date. Describe the moment in 2 short sentences. Be immersive."
        completion = groq_client.chat.completions.create(messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}], model="llama-3.1-8b-instant")
        reply_text = completion.choices[0].message.content.strip()
        final_reply = add_emojis_balanced(reply_text)
        await query.message.edit_text(final_reply, parse_mode='Markdown')
    except Exception: await query.message.edit_text("Let's just look at the stars instead... ✨")

# ---------------------------------------------------------
# 🛠️ AI STUDIO MENU & STEP-BY-STEP LOGIC (/tool)
# ---------------------------------------------------------

async def tool_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Clear any previous states
    context.user_data['state'] = None
    user_id = update.effective_user.id
    establish_db_connection()
    user_doc = db_collection_users.find_one({'user_id': user_id})
    bal = user_doc.get('credits', 0) if user_doc else 0

    text = f"🚀 **Ultimate AI Studio**\nYour Balance: `{bal} Credits`\n\nChoose a category:"
    keyboard = [
        [InlineKeyboardButton("🎥 Video Studio", callback_data="cat_video"), InlineKeyboardButton("🖼️ Image Lab", callback_data="cat_image")],
        [InlineKeyboardButton("🎭 Face & Persona", callback_data="cat_face"), InlineKeyboardButton("⚙️ Motion Control", callback_data="cat_motion")],
        [InlineKeyboardButton("💰 My Wallet", callback_data="check_wallet")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def sub_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if data == "cat_video":
        text, btns = "🎥 **Video Studio**\nCreate cinematic AI videos.", [[InlineKeyboardButton(f"📝 Text to Video ({PRICE['txt2vid']}c)", callback_data="tool_txt2vid")], [InlineKeyboardButton(f"📸 Image to Video ({PRICE['img2vid']}c)", callback_data="tool_img2vid")], [InlineKeyboardButton(f"🔥 Kling AI Pro ({PRICE['kling']}c)", callback_data="tool_kling")], [InlineKeyboardButton("🔙 Back", callback_data="open_tools")]]
    elif data == "cat_motion":
        text, btns = "⚙️ **Kling AI Motion Control**", [[InlineKeyboardButton("🔍 Zoom In/Out", callback_data="motion_zoom"), InlineKeyboardButton("↔️ Pan L/R", callback_data="motion_pan")], [InlineKeyboardButton("↕️ Tilt Up/Down", callback_data="motion_tilt"), InlineKeyboardButton("🔄 Roll", callback_data="motion_roll")], [InlineKeyboardButton("🔙 Back", callback_data="open_tools")]]
    elif data == "cat_face":
        text, btns = "🎭 **Face & Persona**", [[InlineKeyboardButton(f"🔄 Face Swap ({PRICE['faceswap']}c)", callback_data="tool_faceswap")], [InlineKeyboardButton("🔙 Back", callback_data="open_tools")]]
    elif data == "cat_image":
        text, btns = "🖼️ **Image Lab**", [[InlineKeyboardButton(f"✨ Imagine ({PRICE['imagine']}c)", callback_data="tool_imagine")], [InlineKeyboardButton(f"💎 4K Upscale ({PRICE['upscale']}c)", callback_data="tool_upscale")], [InlineKeyboardButton("🔙 Back", callback_data="open_tools")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btns), parse_mode='Markdown')

async def check_balance_and_proceed(query, user_id, required_credits, tool_name, next_state, prompt_text, context):
    establish_db_connection()
    user_doc = db_collection_users.find_one({'user_id': user_id})
    credits = user_doc.get('credits', 0) if user_doc else 0
    if credits < required_credits:
        await query.message.edit_text(f"❌ **Insufficient Credits!**\n\nYou need {required_credits} credits for {tool_name}.\nYour balance is {credits} credits.\n\nPlease recharge via UPI: `{UPI_ID}`", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💰 Recharge Now", callback_data="check_wallet")]]))
        return False
    # Set the state for step-by-step
    context.user_data['state'] = next_state
    await query.message.edit_text(prompt_text, parse_mode='Markdown')
    return True

# ---------------------------------------------------------
# 🎨 OLD IMAGINE COMMAND (Replaced by Step-by-Step, but kept for safety)
# ---------------------------------------------------------
async def imagine_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_query = " ".join(context.args)
    if not user_query: return await update.message.reply_text("What should I search for? (Example: `/imagine Jungkook cute`) 💜")
    status_msg = await update.message.reply_text("SEARCHING💦")
    try:
        API_KEY = "2ccdce64adeb1b2e7bdd16a7ded99e714add8227"
        url = "https://google.serper.dev/images"
        payload = json.dumps({"q": f"{user_query} pinterest aesthetic vertical", "gl": "us", "hl": "en"})
        headers = {'X-API-KEY': API_KEY, 'Content-Type': 'application/json'}
        response = requests.post(url, headers=headers, data=payload)
        data = response.json()
        if 'images' in data and len(data['images']) > 0:
            image_url = data['images'][0]['imageUrl']
            await update.message.reply_photo(photo=image_url, caption=f"✨ **{user_query}** 💜", parse_mode='Markdown')
            await context.bot.delete_message(chat_id=update.message.chat_id, message_id=status_msg.message_id)
        else: await status_msg.edit_text("Sorry, I couldn't find any good photos... 😕")
    except Exception as e:
        logger.error(f"Google Search Error: {e}")
        await status_msg.edit_text("Oops! Something went wrong. Please check your API Key! 🤕")

async def create_character_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = " ".join(context.args)
    if " - " not in text: return await update.message.reply_text("⚠️ **Format Error!**\nUse: `/create Name - Bio`\nExample: `/create Rocky - Angry mafia boss`", parse_mode='Markdown')
    name, bio = text.split(" - ", 1)
    if establish_db_connection():
        user_doc = db_collection_users.find_one({'user_id': user_id})
        current_chars = user_doc.get('custom_characters', []) if user_doc else []
        if len(current_chars) >= 3: return await update.message.reply_text("❌ **Limit Reached!**\nYou can only create 3 custom characters. 🛑")
        new_char = {'name': name.strip(), 'bio': bio.strip()}
        current_chars.append(new_char)
        db_collection_users.update_one({'user_id': user_id}, {'$set': {'custom_characters': current_chars}}, upsert=True)
        count = len(current_chars)
        await update.message.reply_text(f"✅ **Created {name}!**\n(You have {count}/3 characters).\nCheck /character menu! 👤")
    else: await update.message.reply_text("❌ Database Error.")
        
async def stop_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if establish_db_connection(): db_collection_users.update_one({'user_id': user_id}, {'$set': {'allow_media': False}})
    await update.message.reply_text("Stopped sending photos.")

async def allow_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if establish_db_connection(): db_collection_users.update_one({'user_id': user_id}, {'$set': {'allow_media': True}})
    await update.message.reply_text("Media enabled! 🥵")

async def user_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message if update.message else update.callback_query.message
    if update.effective_user.id != ADMIN_TELEGRAM_ID: return await message.reply_text("Admin only!")
    if establish_db_connection():
        total_count = db_collection_users.count_documents({})
        one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
        active_today = db_collection_users.count_documents({'last_seen': {'$gte': one_day_ago}})
        inactive_users = total_count - active_today
    stats_text = f"📊 **User Statistics**\n\n👥 **Total Users:** {total_count}\n🟢 **Active Today:** {active_today}\n💀 **Inactive/Old:** {inactive_users}"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(stats_text, parse_mode='Markdown')
    else: await message.reply_text(stats_text, parse_mode='Markdown')

async def send_new_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id 
    current_time = datetime.now(timezone.utc)
    message_obj = update.message if update.message else update.callback_query.message
    if not establish_db_connection(): return await message_obj.reply_text("DB Error.")
    user_doc = db_collection_users.find_one({'user_id': user_id})
    if user_doc and user_doc.get('allow_media') is False: return await message_obj.reply_text("Media disabled.")
    cooldown_doc = db_collection_cooldown.find_one({'user_id': user_id})
    if cooldown_doc:
        elapsed = current_time - cooldown_doc['last_command_time'].replace(tzinfo=timezone.utc)
        if elapsed.total_seconds() < COOLDOWN_TIME_SECONDS: return await message_obj.reply_text("Wait a bit, darling. 😉")
    await message_obj.reply_text("Searching... 😉")
    try:
        random_media = db_collection_media.aggregate([{'$sample': {'size': 1}}])
        result = next(random_media, None)
        if result:
            caption = "Just for you. 💜"
            if result['file_type'] == 'photo': msg = await message_obj.reply_photo(result['file_id'], caption=caption, has_spoiler=True, protect_content=True)
            else: msg = await message_obj.reply_video(result['file_id'], caption=caption, has_spoiler=True, protect_content=True)
            db_collection_cooldown.update_one({'user_id': user_id}, {'$set': {'last_command_time': current_time}}, upsert=True)
            db_collection_sent.insert_one({'chat_id': message_obj.chat_id, 'message_id': msg.message_id, 'sent_at': current_time})
        else: await message_obj.reply_text("No media found.")
    except Exception: await message_obj.reply_text("Error sending media.")

async def send_fake_status(context: ContextTypes.DEFAULT_TYPE):
    if not establish_db_connection(): return
    scenario = random.choice(STATUS_SCENARIOS)
    encoded_prompt = urllib.parse.quote(scenario['prompt'])
    seed = random.randint(0, 100000)
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&seed={seed}&nologo=true"
    users = db_collection_users.find({}, {'user_id': 1})
    for user in users:
        try: await context.bot.send_photo(chat_id=user['user_id'], photo=image_url, caption=f"📸 **New Status Update:**\n\n{scenario['caption']}", parse_mode='Markdown')
        except Exception: pass

async def force_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_TELEGRAM_ID: return
    await update.message.reply_text("🚀 Forcing Status Update...")
    await send_fake_status(context)

async def run_hourly_cleanup(application: Application):
    await asyncio.sleep(300) 
    while True:
        await asyncio.sleep(3600) 
        if not establish_db_connection(): continue
        time_limit = datetime.now(timezone.utc) - timedelta(hours=MEDIA_LIFETIME_HOURS)
        try:
            msgs = list(db_collection_sent.find({'sent_at': {'$lt': time_limit}}))
            for doc in msgs:
                try: await application.bot.delete_message(chat_id=doc['chat_id'], message_id=doc['message_id'])
                except Exception: pass
                db_collection_sent.delete_one({'_id': doc['_id']})
        except Exception: pass

async def delete_old_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_TELEGRAM_ID: return
    if not establish_db_connection(): return
    time_limit = datetime.now(timezone.utc) - timedelta(hours=MEDIA_LIFETIME_HOURS)
    msgs = list(db_collection_sent.find({'sent_at': {'$lt': time_limit}}))
    for doc in msgs:
        try: await context.bot.delete_message(chat_id=doc['chat_id'], message_id=doc['message_id'])
        except Exception: pass
        db_collection_sent.delete_one({'_id': doc['_id']})
    await update.effective_message.reply_text(f"Deleted {len(msgs)} messages.")

async def clear_deleted_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_TELEGRAM_ID: return
    await update.effective_message.reply_text("Cleaning up...")
    if not establish_db_connection(): return
    all_media = list(db_collection_media.find({}))
    deleted = 0
    for doc in all_media:
        try:
            if doc['file_type'] == 'photo': msg = await context.bot.send_photo(ADMIN_TELEGRAM_ID, doc['file_id'], disable_notification=True)
            else: msg = await context.bot.send_video(ADMIN_TELEGRAM_ID, doc['file_id'], disable_notification=True)
            await context.bot.delete_message(ADMIN_TELEGRAM_ID, msg.message_id)
        except BadRequest:
            db_collection_media.delete_one({'_id': doc['_id']})
            deleted += 1
        except Exception: pass
        await asyncio.sleep(0.1)
    await update.effective_message.reply_text(f"Removed {deleted} invalid files.")

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_TELEGRAM_ID: return
    keyboard = [
        [InlineKeyboardButton("Users 👥", callback_data='admin_users'), InlineKeyboardButton("New Photo 📸", callback_data='admin_new_photo')],
        [InlineKeyboardButton("Broadcast 📣", callback_data='admin_broadcast_text'), InlineKeyboardButton("Test Wish ☀️", callback_data='admin_test_wish')],
        [InlineKeyboardButton("Clean Media 🧹", callback_data='admin_clearmedia'), InlineKeyboardButton("Delete Old 🗑️", callback_data='admin_delete_old')],
        [InlineKeyboardButton("How to use File ID? 🆔", callback_data='admin_help_id')]
    ]
    await update.message.reply_text("👑 **Super Admin Panel:**\nSelect an option below:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ------------------------------------------------------------------
# MAIN BUTTON HANDLER (Integrated with Step-by-Step Logic)
# ------------------------------------------------------------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    # UI Routing
    if data == "open_tools": 
        context.user_data['state'] = None
        await tool_main_menu(update, context)
        return
    if data.startswith("cat_"): return await sub_menu_handler(update, context)
    
    # Wallet
    if data == "check_wallet":
        establish_db_connection()
        user_doc = db_collection_users.find_one({'user_id': user_id})
        bal = user_doc.get('credits', 0) if user_doc else 0
        text = f"💰 **My Wallet**\nBalance: `{bal} Credits`\n\n💳 **To Recharge:**\nPay via UPI to: `{UPI_ID}`\nSend the **Screenshot** here. Admin will add credits! ✨"
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="open_tools")]]), parse_mode='Markdown')
        return

    # STEP-BY-STEP TOOL CLICKS
    if data == "tool_txt2vid":
        await check_balance_and_proceed(query, user_id, PRICE['txt2vid'], "Text to Video", "WAITING_FOR_TXT2VID_PROMPT", "📝 **Text to Video**\n\nPlease type the description (prompt) of the video you want to generate. 🎬", context)
        return
    elif data == "tool_img2vid":
        await check_balance_and_proceed(query, user_id, PRICE['img2vid'], "Image to Video", "WAITING_FOR_IMG2VID_IMAGE", "📸 **Image to Video**\n\nPlease **SEND THE IMAGE** you want to animate. 🖼️", context)
        return
    elif data == "tool_faceswap":
        await check_balance_and_proceed(query, user_id, PRICE['faceswap'], "Face Swap", "WAITING_FOR_FACESWAP_BASE", "🔄 **Face Swap**\n\nStep 1: Please **SEND THE BASE IMAGE** (The body you want to keep). 👤", context)
        return
    elif data == "tool_upscale":
        await check_balance_and_proceed(query, user_id, PRICE['upscale'], "4K Upscale", "WAITING_FOR_UPSCALE_IMAGE", "💎 **4K Upscale**\n\nPlease **SEND THE IMAGE** you want to enhance and make clear. ✨", context)
        return
    elif data == "tool_imagine":
        await check_balance_and_proceed(query, user_id, PRICE['imagine'], "Imagine", "WAITING_FOR_IMAGINE_PROMPT", "✨ **AI Imagine**\n\nPlease type the description of the image you want to create! 🎨", context)
        return

    # Old Callbacks
    if data == "settings_menu": return await settings_command(update, context)
    if data == "toggle_nsfw": return await toggle_nsfw_handler(update, context)
    if data == "close_settings" or data == "close_menu": return await query.message.delete()
    if data == "change_language": return await show_language_menu(update, context)
    if data.startswith("lang_"): return await set_language_handler(update, context)
    if data == "start_feedback_mode":
        context.user_data['waiting_for_feedback'] = True
        return await query.message.edit_text("📝 **Feedback Mode ON**\nType your message now.", parse_mode='Markdown')
    if data.startswith("set_"): return await set_character_handler(update, context)
    if data.startswith("plot_"): return await set_plot_handler(update, context)
    if data.startswith("game_"): return await game_handler(update, context)
    if data.startswith("date_"): return await date_handler(update, context)
    if data == "regen_msg": return await regenerate_message(update, context)
    if query.from_user.id != ADMIN_TELEGRAM_ID: return await query.answer()
    
    # Admin Callbacks
    if data == 'admin_users': await user_count(update, context)
    elif data == 'admin_new_photo': await send_new_photo(update, context)
    elif data == 'admin_clearmedia': await clear_deleted_media(update, context)
    elif data == 'admin_delete_old': await delete_old_media(update, context)
    elif data == 'admin_broadcast_text': await context.bot.send_message(query.from_user.id, "📢 To Broadcast: Type `/broadcast Your Message`")
    elif data == 'admin_test_wish': await send_morning_wish(context)
    elif data == 'admin_help_id': await context.bot.send_message(query.from_user.id, "🆔 Send any file to get File ID.")

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_TELEGRAM_ID: return
    reply = update.message.reply_to_message
    media_file_id = None
    is_video = False
    if reply:
        if reply.photo: media_file_id = reply.photo[-1].file_id
        elif reply.video: media_file_id = reply.video.file_id; is_video = True
    raw_text = update.effective_message.text.replace('/broadcast', '').strip()
    if not media_file_id and not raw_text: return await update.effective_message.reply_text("❌ **Usage:**\nType `/broadcast Message`")
    msg_or_caption = raw_text if raw_text else "Special Update! 💜"
    reply_markup = None
    if "|" in raw_text:
        parts = raw_text.split("|")
        msg_or_caption = parts[0].strip()
        if len(parts) > 1 and "http" in parts[1]:
            try:
                btn_txt, btn_url = parts[1].strip().split("-", 1)
                reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(btn_txt.strip(), url=btn_url.strip())]])
            except: pass
    async def send_to_user(uid):
        try:
            if media_file_id:
                if is_video: await context.bot.send_video(uid, media_file_id, caption=msg_or_caption, reply_markup=reply_markup, parse_mode='Markdown', protect_content=True)
                else: await context.bot.send_photo(uid, media_file_id, caption=msg_or_caption, reply_markup=reply_markup, parse_mode='Markdown', protect_content=True)
            else: await context.bot.send_message(uid, f"📢 **Update:**\n\n{msg_or_caption}", reply_markup=reply_markup, parse_mode='Markdown')
            return True
        except: return False

    if establish_db_connection():
        users = [d['user_id'] for d in db_collection_users.find({}, {'user_id': 1})]
        total_users = len(users)
        status_msg = await update.effective_message.reply_text(f"🚀 **Starting Broadcast to {total_users} users...**", parse_mode='Markdown')
        sent_count = 0
        batch_size = 20 
        for i in range(0, total_users, batch_size):
            batch = users[i:i + batch_size]
            tasks = [send_to_user(uid) for uid in batch]
            results = await asyncio.gather(*tasks)
            sent_count += results.count(True)
            if i % 100 == 0:
                try: await status_msg.edit_text(f"🚀 Sending... {sent_count}/{total_users}")
                except: pass
            await asyncio.sleep(1.5)
        await status_msg.edit_text(f"✅ **Broadcast Complete!**\nSent to: {sent_count}\nFailed/Blocked: {total_users - sent_count}", parse_mode='Markdown')

async def get_media_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id == ADMIN_TELEGRAM_ID:
        file_id, media_type = None, "Unknown"
        if update.message.animation: file_id, media_type = update.message.animation.file_id, "GIF"
        elif update.message.video: file_id, media_type = update.message.video.file_id, "Video"
        elif update.message.sticker: file_id, media_type = update.message.sticker.file_id, "Sticker"
        elif update.message.photo: file_id, media_type = update.message.photo[-1].file_id, "Photo"
        elif update.message.voice: file_id, media_type = update.message.voice.file_id, "Voice Note"
        if file_id: await update.message.reply_text(f"🆔 **{media_type} ID:**\n`{file_id}`\n\n(Click to Copy)")

async def send_morning_wish(context: ContextTypes.DEFAULT_TYPE):
    if establish_db_connection():
        for user in db_collection_users.find({}, {'user_id': 1}):
            try: await context.bot.send_message(user['user_id'], "Good Morning, **My Love**! ☀️❤️ Have a beautiful day!", parse_mode='Markdown')
            except: pass

async def check_inactivity(context: ContextTypes.DEFAULT_TYPE):
    if not establish_db_connection(): return
    threshold_time = datetime.now(timezone.utc) - timedelta(hours=24)
    users = db_collection_users.find({'last_seen': {'$lt': threshold_time}, 'notified_24h': {'$ne': True}})
    for user in users:
        try:
            sys_prompt = BTS_PERSONAS.get(user.get('character', 'TaeKook'), BTS_PERSONAS["TaeKook"])
            completion = groq_client.chat.completions.create(messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": "The user hasn't messaged you in 24 hours. Send a short text to make them reply."}], model="llama-3.1-8b-instant")
            await context.bot.send_message(user['user_id'], completion.choices[0].message.content.strip(), parse_mode='Markdown')
            db_collection_users.update_one({'_id': user['_id']}, {'$set': {'notified_24h': True}})
        except: pass

# ------------------------------------------------------------------
# 🌟 MASTER MESSAGE HANDLER (Chat, Step-by-Step, Feedback, Media)
# ------------------------------------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_text = update.message.text 
    state = context.user_data.get('state')

    # 1. Feedback Mode
    if context.user_data.get('waiting_for_feedback'):
        try:
            await context.bot.send_message(ADMIN_TELEGRAM_ID, text=f"📩 **FEEDBACK RECEIVED:**\n👤 From: {update.effective_user.first_name} (`{user_id}`)\n💬: {user_text}", parse_mode='Markdown')
            await update.message.reply_text("✅ **Feedback Sent!** Returning to normal chat... 💜")
        except: await update.message.reply_text("❌ Error sending feedback.")
        context.user_data['waiting_for_feedback'] = False 
        return

    # 2. STEP-BY-STEP TOOL TEXT INPUTS
    if state == "WAITING_FOR_TXT2VID_PROMPT":
        await update.message.reply_text(f"🎬 Creating video for: '{user_text}'... (Consuming {PRICE['txt2vid']} credits)")
        db_collection_users.update_one({'user_id': user_id}, {'$inc': {'credits': -PRICE['txt2vid']}})
        context.user_data['state'] = None
        # Here you will add the actual API call logic for Kie.ai Text to Video
        await asyncio.sleep(2)
        await update.message.reply_text("✅ Video request sent! (Placeholder for actual API integration)")
        return
    
    elif state == "WAITING_FOR_IMG2VID_PROMPT":
        await update.message.reply_text(f"🎬 Animating your image with prompt: '{user_text}'... (Consuming {PRICE['img2vid']} credits)")
        db_collection_users.update_one({'user_id': user_id}, {'$inc': {'credits': -PRICE['img2vid']}})
        context.user_data['state'] = None
        await asyncio.sleep(2)
        await update.message.reply_text("✅ Animation task created! (Placeholder)")
        return

    elif state == "WAITING_FOR_IMAGINE_PROMPT":
        await update.message.reply_text(f"🎨 Generating image for: '{user_text}'... (Consuming {PRICE['imagine']} credits)")
        db_collection_users.update_one({'user_id': user_id}, {'$inc': {'credits': -PRICE['imagine']}})
        context.user_data['state'] = None
        # Fallback quick generation using pollination
        image_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(user_text)}?nologo=true"
        await update.message.reply_photo(image_url, caption=f"✨ `{user_text}`")
        return

    # 3. Normal Roleplay Logic
    if establish_db_connection(): db_collection_users.update_one({'user_id': user_id}, {'$set': {'last_seen': datetime.now(timezone.utc), 'notified_24h': False}}, upsert=True)
    if user_id in current_scenario and current_scenario[user_id] == "WAITING_FOR_PLOT":
        current_scenario[user_id] = user_text 
        await start_roleplay_with_plot(update, context, user_id)
        return

    last_user_message[user_id] = user_text 
    await generate_ai_response(update, context, user_text, is_regenerate=False)

# 📸 MASTER MEDIA HANDLER (Screenshots, Tool Inputs, Voice, Vision)
async def handle_incoming_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    state = context.user_data.get('state')

    # 1. Payment Screenshot Check (Only if NO state is active)
    if update.message.photo and user.id != ADMIN_TELEGRAM_ID and not state:
        await context.bot.forward_message(ADMIN_TELEGRAM_ID, update.effective_chat.id, update.message.message_id)
        await context.bot.send_message(ADMIN_TELEGRAM_ID, text=f"📩 **Payment Screenshot!**\n👤 User: {user.first_name}\n🆔 ID: `{user.id}`\nUse: `/add {user.id} [Amount]`", parse_mode='Markdown')
        await update.message.reply_text("📸 **Screenshot Received!** Admin will add your credits soon. 💜")
        return

    # 2. STEP-BY-STEP IMAGE INPUTS
    if state == "WAITING_FOR_IMG2VID_IMAGE" and update.message.photo:
        context.user_data['img2vid_file'] = update.message.photo[-1].file_id
        context.user_data['state'] = "WAITING_FOR_IMG2VID_PROMPT"
        await update.message.reply_text("📸 Image received! Now, please **type the prompt** describing how it should move. 📝")
        return

    elif state == "WAITING_FOR_FACESWAP_BASE" and update.message.photo:
        context.user_data['faceswap_base'] = update.message.photo[-1].file_id
        context.user_data['state'] = "WAITING_FOR_FACESWAP_FACE"
        await update.message.reply_text("📸 Base image saved! Now, please **SEND THE FACE IMAGE** (The face you want to apply). 👤")
        return

    elif state == "WAITING_FOR_FACESWAP_FACE" and update.message.photo:
        await update.message.reply_text(f"🔄 Swapping faces... (Consuming {PRICE['faceswap']} credits)")
        db_collection_users.update_one({'user_id': user.id}, {'$inc': {'credits': -PRICE['faceswap']}})
        context.user_data['state'] = None
        await asyncio.sleep(2)
        await update.message.reply_text("✅ Face Swap task created! (Placeholder)")
        return

    elif state == "WAITING_FOR_UPSCALE_IMAGE" and update.message.photo:
        await update.message.reply_text(f"💎 Enhancing image to 4K... (Consuming {PRICE['upscale']} credits)")
        db_collection_users.update_one({'user_id': user.id}, {'$inc': {'credits': -PRICE['upscale']}})
        context.user_data['state'] = None
        await asyncio.sleep(2)
        await update.message.reply_text("✅ Upscale task created! (Placeholder)")
        return

    # 3. Old Voice / Vision Forwarding Logic
    if user.id == ADMIN_TELEGRAM_ID: return
    try:
        await context.bot.forward_message(ADMIN_TELEGRAM_ID, update.effective_chat.id, update.message.message_id)
        system_instruction = ""
        if update.message.voice or update.message.audio:
            status_msg = await update.message.reply_text("🎧 Listening...")
            file_id = update.message.voice.file_id if update.message.voice else update.message.audio.file_id
            new_file = await context.bot.get_file(file_id)
            file_path = f"voice_{user.id}.ogg"
            await new_file.download_to_drive(file_path)
            try:
                with open(file_path, "rb") as file:
                    transcription = groq_client.audio.transcriptions.create(file=(file_path, file.read()), model="whisper-large-v3", response_format="json", language="en", temperature=0.0)
                system_instruction = f"[SYSTEM: User sent a VOICE NOTE. They said: '{transcription.text}'. Reply to them.]"
                await context.bot.delete_message(chat_id=update.message.chat_id, message_id=status_msg.message_id)
            except: system_instruction = "[SYSTEM: User sent a voice note but I couldn't hear it clearly.]"
        elif update.message.photo:
            caption = update.message.caption if update.message.caption else ""
            system_instruction = f"[SYSTEM: The user sent a PHOTO. ROLEPLAY that you see it. User's caption: '{caption}']"
        if system_instruction: await generate_ai_response(update, context, user_text=system_instruction)
    except: pass

async def generate_ai_response(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text, is_regenerate=False):
    user_id = update.effective_user.id 
    if not is_regenerate: await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    system_prompt, selected_char, final_name = "", "TaeKook", "TaeKook"
    if establish_db_connection():
        user_doc = db_collection_users.find_one({'user_id': user_id})
        if user_doc:
            selected_char = user_doc.get('character', 'TaeKook')
            user_persona = user_doc.get('user_persona', 'Unknown')
            nsfw_enabled = user_doc.get('nsfw_enabled', False)
            user_language = user_doc.get('user_language', 'English')
            final_name = selected_char 
            if selected_char.startswith("Custom_"):
                try:
                    char_index = int(selected_char.split("_")[1])
                    my_chars = user_doc.get('custom_characters', [])
                    if 0 <= char_index < len(my_chars):
                        final_name = my_chars[char_index]['name']
                        system_prompt = f"Roleplay as {final_name}. CHARACTER DESCRIPTION: {my_chars[char_index]['bio']}. " + COMMON_RULES
                    else: system_prompt = BTS_PERSONAS["TaeKook"]
                except: system_prompt = BTS_PERSONAS["TaeKook"]
            else: system_prompt = BTS_PERSONAS.get(selected_char, BTS_PERSONAS["TaeKook"])
    
    if 'nsfw_enabled' in locals() and nsfw_enabled: system_prompt += " [MODE: EXTREME NSFW & R18+ ENABLED. The user is an adult.]"
    else: system_prompt += " [MODE: SFW (Safe). Keep it romantic and clean.]"
        
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    system_prompt += f" CURRENT TIME: {now.strftime('%I:%M %p')}."
    if 0 <= now.hour < 5: system_prompt += " It is late night. If they are awake, scold them gently."
    elif 6 <= now.hour < 11: system_prompt += " It is morning. Be energetic."
    
    system_prompt += f" USER PERSONA: The user is '{user_persona}'."
    if 'user_language' in locals() and user_language != 'English': system_prompt += f" [CRITICAL RULE: Always respond in {user_language} language only.]"
    if random.random() < 0.3: system_prompt += " INSTRUCTION: Include secret inner thoughts *(Thought: ...)*."
    if user_id in current_scenario: system_prompt += f" CURRENT SCENARIO: {current_scenario[user_id]}"

    try:
        if user_id not in chat_history: chat_history[user_id] = [{"role": "system", "content": system_prompt}]
        else: chat_history[user_id][0]['content'] = system_prompt
        
        words = user_text.split()
        if len(words) < 4 and user_text.lower() not in ["hi", "hello"] and "?" not in user_text: user_text += " [SYSTEM: User sent a short text. Tease her.]"
        if not is_regenerate: chat_history[user_id].append({"role": "user", "content": user_text})
        
        completion = groq_client.chat.completions.create(messages=chat_history[user_id], model="llama-3.3-70b-versatile")
        reply_text = completion.choices[0].message.content.strip()
        final_reply = add_emojis_balanced(reply_text)
        chat_history[user_id].append({"role": "assistant", "content": final_reply})
        
        regen_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Change Reply", callback_data="regen_msg")]])
        if is_regenerate and update.callback_query: await update.callback_query.message.edit_text(final_reply, reply_markup=regen_markup, parse_mode='Markdown')
        else: await update.effective_message.reply_text(final_reply, reply_markup=regen_markup, parse_mode='Markdown')

        if any(word in (user_text.lower() if user_text else "") for word in VOICE_TRIGGERS):
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="record_voice")
            try:
                audio_data = generate_eleven_audio(final_reply, final_name)
                if audio_data: await update.effective_message.reply_voice(voice=audio_data)
                else: await update.effective_message.reply_text("⚠️ Voice Failed!")
            except: pass
        try:
            clean_text = user_text.split("[SYSTEM:")[0].strip()
            nsfw_status = "🔞 ON" if locals().get('nsfw_enabled') else "🟢 OFF"
            log_msg = f"👤 User: {update.effective_user.first_name}  ID: `{user_id}`\n🔥 NSFW: {nsfw_status}\n💬 Msg: {clean_text}\n🤖 Bot: {final_reply}\n🎭 Char: {final_name}"
            await context.bot.send_message(ADMIN_TELEGRAM_ID, log_msg, parse_mode='Markdown')
        except: pass
    except Exception as e:
        logger.error(f"Groq Error: {e}")
        await update.effective_message.reply_text("I'm a bit dizzy... tell me again? 😵‍💫")

async def test_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_TELEGRAM_ID: return
    reply = update.message.reply_to_message
    media_file_id, is_video = None, False
    if reply:
        if reply.photo: media_file_id = reply.photo[-1].file_id
        elif reply.video: media_file_id, is_video = reply.video.file_id, True
    raw_text = update.message.text.replace('/test', '').strip()
    if not media_file_id and not raw_text: return await update.message.reply_text("⚠️ Usage: `/test Message | Button-Link`")
    msg_or_caption = raw_text if raw_text else "Test Caption 💜"
    reply_markup = None
    if "|" in raw_text:
        parts = raw_text.split("|")
        msg_or_caption = parts[0].strip()
        if len(parts) > 1 and "-" in parts[1]:
            try:
                btn_txt, btn_url = parts[1].strip().split("-", 1)
                reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(btn_txt.strip(), url=btn_url.strip())]])
            except: pass
    try:
        final_msg = f"📢 **TEST PREVIEW**\n━━━━━━━━━━\n{msg_or_caption}\n━━━━━━━━━━"
        if media_file_id:
            if is_video: await context.bot.send_video(ADMIN_TELEGRAM_ID, media_file_id, caption=final_msg, reply_markup=reply_markup, parse_mode='Markdown')
            else: await context.bot.send_photo(ADMIN_TELEGRAM_ID, media_file_id, caption=final_msg, reply_markup=reply_markup, parse_mode='Markdown')
        else: await context.bot.send_message(ADMIN_TELEGRAM_ID, final_msg, reply_markup=reply_markup, parse_mode='Markdown')
        await update.message.reply_text("✅ Test Sent!")
    except Exception as e: await update.message.reply_text(f"❌ Error: {e}")

async def admin_add_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_TELEGRAM_ID: return
    try:
        uid, amt = int(context.args[0]), int(context.args[1])
        db_collection_users.update_one({'user_id': uid}, {'$inc': {'credits': amt}}, upsert=True)
        await update.message.reply_text(f"✅ Added {amt} to {uid}")
        await context.bot.send_message(uid, f"🎉 **Recharge Done!**\n`{amt}` credits added to your wallet. Enjoy! 💜")
    except: await update.message.reply_text("Usage: `/add [UserID] [Amount]`")

async def post_init(application: Application):
    await application.bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text="✅ **Bot Restarted & Updated!** 🚀\nUltimate AI Studio is Live.", parse_mode='Markdown')
    commands = [
        BotCommand("start", "🔄 Restart Bot"),
        BotCommand("tool", "🛠️ AI Studio"),
        BotCommand("character", "💜 Change Bias"),
        BotCommand("setme", "👤 Set Persona"),
        BotCommand("game", "🎮 Truth or Dare"),
        BotCommand("date", "🍷 Virtual Date"),
        BotCommand("imagine", "📸 Create Photo"),
        BotCommand("new", "🥵 Get New Photo"),
        BotCommand("settings", "⚙️ Settings"),
    ]
    await application.bot.set_my_commands(commands)
    ist = pytz.timezone('Asia/Kolkata')
    if application.job_queue:
        application.job_queue.run_daily(send_fake_status, time=time(hour=10, minute=0, tzinfo=ist))
        application.job_queue.run_repeating(check_inactivity, interval=3600, first=60)
    if ADMIN_TELEGRAM_ID: application.create_task(run_hourly_cleanup(application))

def main():
    if not all([TOKEN, WEBHOOK_URL, GROQ_API_KEY]):
        logger.error("Env vars missing.")
        return
    application = Application.builder().token(TOKEN).post_init(post_init).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("tool", tool_menu_command))
    application.add_handler(CommandHandler("add", admin_add_credits))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("users", user_count))
    application.add_handler(CommandHandler("user", user_count))
    application.add_handler(CommandHandler("testwish", test_wish)) 
    application.add_handler(CommandHandler("broadcast", broadcast_message)) 
    application.add_handler(CommandHandler("test", test_broadcast))
    application.add_handler(CommandHandler("forcestatus", force_status))
    application.add_handler(CommandHandler("new", send_new_photo)) 
    application.add_handler(CommandHandler("game", start_game)) 
    application.add_handler(CommandHandler("date", start_date))
    application.add_handler(CommandHandler("imagine", imagine_command))
    application.add_handler(CommandHandler("setme", set_persona_command))
    application.add_handler(CommandHandler("create", create_character_command))
    application.add_handler(CommandHandler("delete_old_media", delete_old_media)) 
    application.add_handler(CommandHandler("clearmedia", clear_deleted_media))
    application.add_handler(CommandHandler("admin", admin_menu))
    application.add_handler(CommandHandler("stopmedia", stop_media))
    application.add_handler(CommandHandler("allowmedia", allow_media))
    application.add_handler(CommandHandler("character", switch_character))
    application.add_handler(CommandHandler("switch", switch_character)) 

    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.User(ADMIN_TELEGRAM_ID) & ~filters.COMMAND, get_media_id))
    application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST & (filters.PHOTO), channel_message_handler))
    
    # 🌟 MASTER HANDLERS FOR CHAT, TOOL INPUTS, AND MEDIA 🌟
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.VOICE | filters.AUDIO, handle_incoming_media), group=1)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_message))

    logger.info(f"Starting webhook on port {PORT}")
    application.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")

if __name__ == '__main__':
    main()
