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
# DATABASE & LOGGING SETUP
# ***********************************
try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, OperationFailure
except ImportError:
    logger.error("pymongo library not found.")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Environment Variables ---
TOKEN = os.environ.get('TOKEN') 
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
PORT = int(os.environ.get('PORT', 8443))
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
MONGO_URI = os.environ.get('MONGO_URI') 

# ✅ ADMIN CONFIG
ADMIN_TELEGRAM_ID = 7567364364 
ADMIN_CHANNEL_ID = os.environ.get('ADMIN_CHANNEL_ID', '-1002992093797') 

# ✅ API KEYS & PAYMENT
ELEVEN_API_KEY = "sk_2b615fe071528fb5696ff8a1d407ab367611caa5543482bd"
KIE_API_TOKEN = "9fd5e7779094f8ca2d8da1da95e79443"
UPI_ID = "Abhiixz@ybl"

# ✅ PRICING (Credits)
PRICE = {
    "txt2vid": 30,
    "kling_pro": 50,
    "faceswap": 20,
    "upscale": 10,
    "imagine": 5,
    "bg_remove": 5
}

# -------------------- DB CONNECTION --------------------
db_client = None
db_collection_users = None
db_collection_media = None
db_collection_sent = None
db_collection_cooldown = None
DB_NAME = "Taekook_bot" 

def establish_db_connection():
    global db_client, db_collection_users, db_collection_media, db_collection_sent, db_collection_cooldown
    if db_client is not None: return True
    try:
        db_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = db_client[DB_NAME]
        db_collection_users = db['users']
        db_collection_media = db['channel_media']
        db_collection_sent = db['sent_media']
        db_collection_cooldown = db['cooldown']
        return True
    except: return False

# -------------------- DATA LISTS (RETAINED) --------------------
VOICE_MAP = {"jungkook": "GwAdAVChnhsZg6JKQQUy", "jk": "GwAdAVChnhsZg6JKQQUy", "taekook": "GwAdAVChnhsZg6JKQQUy", "taehyung": "M3gJBS8OofDJfycyA2Ip", "v": "M3gJBS8OofDJfycyA2Ip", "tae": "M3gJBS8OofDJfycyA2Ip"}
VOICE_TRIGGERS = ["voice", "speak", "audio", "say something", "ശബ്ദം", "സംസാരിക്ക്", "വോയിസ്", "sound"]
TRUTH_QUESTIONS = ["What is the first thing you noticed about me? 🙈", "Have you ever dreamt about us? 💭", "What's your favorite song of mine? 🎶", "If we went on a date right now, where would you take me? 🍷"]
DARE_CHALLENGES = ["Send a voice note saying 'I Love You'! 🎤", "Send the 3rd photo from your gallery! 📸", "Send 10 purple hearts 💜 right now!"]

COMMON_RULES = (
    "Roleplay as a BTS member. 1. BE HUMAN. 2. FOLLOW USER LEAD. 3. CHAI MODE. 4. ALL MEMBERS ARE MALE."
)
BTS_PERSONAS = {
    "RM": COMMON_RULES + " Namjoon. Intellectual, Leader.",
    "Jin": COMMON_RULES + " Jin. Funny, Dramatic.",
    "Suga": COMMON_RULES + " Suga. Cold, Savage.",
    "J-Hope": COMMON_RULES + " J-Hope. Sunshine.",
    "Jimin": COMMON_RULES + " Jimin. Flirty, Clingy.",
    "V": COMMON_RULES + " V. Deep voice, Kinky.",
    "Jungkook": COMMON_RULES + " Jungkook. Gamer boy.",
    "TaeKook": COMMON_RULES + " TaeKook. Toxic, Possessive."
}

# -------------------- HELPER FUNCTIONS --------------------
def add_emojis_balanced(text):
    if any(char in text for char in ["💜", "❤️", "🥰", "🔥"]): return text 
    if len(text.split()) < 4: return text
    return text + " 💜"

def generate_eleven_audio(text, char_name):
    clean_name = char_name.lower()
    voice_id = VOICE_MAP.get(clean_name)
    if not voice_id: return None
    try:
        res = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}", json={"text": text, "model_id": "eleven_multilingual_v2"}, headers={"xi-api-key": ELEVEN_API_KEY})
        return res.content if res.status_code == 200 else None
    except: return None

# -------------------- CORE BOT COMMANDS --------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if establish_db_connection():
        db_collection_users.update_one(
            {'user_id': user.id},
            {
                '$set': {'first_name': user.first_name, 'last_seen': datetime.now(timezone.utc)},
                '$setOnInsert': {'joined_at': datetime.now(timezone.utc), 'credits': 10, 'allow_media': True, 'character': 'TaeKook', 'user_persona': 'A girl'}
            }, upsert=True
        )
    
    keyboard = [
        [InlineKeyboardButton("🛠️ AI Studio", callback_data="open_tools"), InlineKeyboardButton("💰 My Wallet", callback_data="check_wallet")],
        [InlineKeyboardButton("💜 Change Bias", callback_data="switch_char"), InlineKeyboardButton("🎮 Games", callback_data="start_game")]
    ]
    await update.message.reply_text(f"Annyeong **{user.first_name}**! 👋💜\nWelcome to your Ultimate AI Studio. Ready?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# -------------------- NEW AI STUDIO (/tool) LOGIC --------------------

async def tool_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
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
        text = "🎥 **Video Studio**\nCreate high-quality AI videos."
        btns = [
            [InlineKeyboardButton(f"📝 Text to Video ({PRICE['txt2vid']}c)", callback_data="tool_txt2vid")],
            [InlineKeyboardButton(f"🔥 Kling AI Pro ({PRICE['kling_pro']}c)", callback_data="tool_kling")],
            [InlineKeyboardButton("🔙 Back", callback_data="open_tools")]
        ]
    elif data == "cat_motion":
        text = "⚙️ **Kling AI Motion Control**\nCamera movement settings."
        btns = [
            [InlineKeyboardButton("🔍 Zoom In/Out", callback_data="m_zoom"), InlineKeyboardButton("↔️ Pan L/R", callback_data="m_pan")],
            [InlineKeyboardButton("↕️ Tilt Up/Down", callback_data="m_tilt"), InlineKeyboardButton("🔄 Roll", callback_data="m_roll")],
            [InlineKeyboardButton("🔙 Back", callback_data="open_tools")]
        ]
    elif data == "cat_face":
        text = "🎭 **Identity Lab**"
        btns = [
            [InlineKeyboardButton(f"🔄 Face Swap ({PRICE['faceswap']}c)", callback_data="tool_faceswap")],
            [InlineKeyboardButton("🔙 Back", callback_data="open_tools")]
        ]
    elif data == "cat_image":
        text = "🖼️ **Image Studio**"
        btns = [
            [InlineKeyboardButton(f"✨ Imagine ({PRICE['imagine']}c)", callback_data="tool_imagine")],
            [InlineKeyboardButton(f"💎 4K Upscale ({PRICE['upscale']}c)", callback_data="tool_upscale")],
            [InlineKeyboardButton("🔙 Back", callback_data="open_tools")]
        ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btns), parse_mode='Markdown')

# -------------------- WALLET & PAYMENT LOGIC --------------------

async def wallet_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    user_doc = db_collection_users.find_one({'user_id': user_id})
    bal = user_doc.get('credits', 0) if user_doc else 0
    
    text = (
        f"💰 **Your Wallet**\nBalance: `{bal} Credits`\n\n"
        f"💳 **Recharge Info:**\nPay to UPI: `{UPI_ID}`\n"
        f"Send the **Screenshot** here. Admin will add credits! ✨"
    )
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_home")]]), parse_mode='Markdown')

async def admin_add_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_TELEGRAM_ID: return
    try:
        uid, amt = int(context.args[0]), int(context.args[1])
        db_collection_users.update_one({'user_id': uid}, {'$inc': {'credits': amt}}, upsert=True)
        await update.message.reply_text(f"✅ Added {amt} credits to {uid}")
        await context.bot.send_message(uid, f"🎉 **Wallet Updated!**\n`{amt}` credits added to your account.")
    except: await update.message.reply_text("Usage: `/add [UserID] [Amount]`")

# -------------------- MAIN BUTTON HANDLER --------------------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    if data == "open_tools": await tool_menu(update, context)
    elif data.startswith("cat_"): await sub_menu_handler(update, context)
    elif data == "check_wallet": await wallet_info(update, context)
    elif data == "back_home": await start(update, context)
    elif data.startswith("checkvideo_"):
        task_id = data.split("_")[1]
        await query.answer("Checking... 🔄")
        res = requests.get(f"https://api.kie.ai/api/v1/jobs/{task_id}", headers={'Authorization': f'Bearer {KIE_API_TOKEN}'}).json()
        if res.get("status") == "succeeded":
            url = res.get("video_url") or res.get("result")
            await context.bot.send_video(query.message.chat_id, url, caption="✨ Your Video is ready! 🎥")
        else: await query.answer("Still processing... ⏳", show_alert=True)

    # RETAINED CALLBACKS
    elif data.startswith("set_"): await set_character_handler(update, context)
    elif data.startswith("plot_"): await set_plot_handler(update, context)
    elif data == "switch_char": await switch_character(update, context)
    elif data.startswith("game_"): await game_handler(update, context)
    elif data == "regen_msg": await regenerate_message(update, context)

# -------------------- MESSAGE HANDLER (CHAT & SCREENSHOTS) --------------------

async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # 📸 PAYMENT SCREENSHOT FORWARDING
    if update.message.photo and user_id != ADMIN_TELEGRAM_ID:
        await context.bot.forward_message(ADMIN_TELEGRAM_ID, update.message.chat_id, update.message.message_id)
        await context.bot.send_message(ADMIN_TELEGRAM_ID, f"📩 **New Payment!**\n👤 User: {update.effective_user.first_name}\n🆔 ID: `{user_id}`\n\nUse `/add {user_id} [Amt]`")
        await update.message.reply_text("📸 **Screenshot Received!** Admin will add credits soon! 💜")
        return

    # 💬 CHAT LOGIC (RETAINED)
    if update.message.text and not update.message.text.startswith('/'):
        if context.user_data.get('waiting_for_feedback'):
            await context.bot.send_message(ADMIN_TELEGRAM_ID, f"📩 **FEEDBACK:** {update.message.text}\nFrom: `{user_id}`")
            await update.message.reply_text("✅ Feedback Sent!")
            context.user_data['waiting_for_feedback'] = False
            return
        await handle_chat(update, context)

# -------------------- AI CHAT LOGIC (RETAINED) --------------------

async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_text = update.message.text
    if establish_db_connection():
         db_collection_users.update_one({'user_id': user_id}, {'$set': {'last_seen': datetime.now(timezone.utc), 'notified_24h': False}}, upsert=True)
    
    if user_id in current_scenario and current_scenario[user_id] == "WAITING_FOR_PLOT":
        current_scenario[user_id] = user_text
        await start_roleplay_with_plot(update, context, user_id)
        return
    
    last_user_message[user_id] = user_text
    await generate_ai_response(update, context, user_text)

async def generate_ai_response(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text, is_regenerate=False):
    user_id = update.effective_user.id
    if not is_regenerate: await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    selected_char, nsfw_enabled = "TaeKook", False
    if establish_db_connection():
        user_doc = db_collection_users.find_one({'user_id': user_id})
        if user_doc:
            selected_char = user_doc.get('character', 'TaeKook')
            nsfw_enabled = user_doc.get('nsfw_enabled', False)

    system_prompt = BTS_PERSONAS.get(selected_char, BTS_PERSONAS["TaeKook"])
    if nsfw_enabled: system_prompt += " [MODE: NSFW ENABLED. Be explicit.]"

    try:
        if user_id not in chat_history: chat_history[user_id] = [{"role": "system", "content": system_prompt}]
        chat_history[user_id].append({"role": "user", "content": user_text})
        
        completion = groq_client.chat.completions.create(messages=chat_history[user_id], model="llama-3.3-70b-versatile")
        final_reply = add_emojis_balanced(completion.choices[0].message.content.strip())
        chat_history[user_id].append({"role": "assistant", "content": final_reply})
        
        await update.effective_message.reply_text(final_reply, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Change Reply", callback_data="regen_msg")]]), parse_mode='Markdown')
        
        # Voice Check
        if any(w in user_text.lower() for w in VOICE_TRIGGERS):
            audio = generate_eleven_audio(final_reply, selected_char)
            if audio: await update.effective_message.reply_voice(voice=audio)
    except: pass

# -------------------- ADMIN & JOBS (RETAINED) --------------------
# (Broadcast, User Count, Status Updates, wishes...)
# Note: സ്ഥലപരിമിതി കാരണം പ്രധാന ലോജിക് മാത്രം.

async def post_init(application: Application):
    await application.bot.send_message(ADMIN_TELEGRAM_ID, text="✅ **Bot Updated Thalaiva!** 🚀\nAI Studio & Wallet Ready.")
    commands = [BotCommand("start", "🔄 Restart"), BotCommand("tool", "🛠️ AI Studio"), BotCommand("character", "💜 Change Bias"), BotCommand("settings", "⚙️ Settings")]
    await application.bot.set_my_commands(commands)

def main():
    application = Application.builder().token(TOKEN).post_init(post_init).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("tool", tool_main_menu))
    application.add_handler(CommandHandler("add", admin_add_credits))
    application.add_handler(CommandHandler("character", switch_character))
    
    # RETAINED HANDLERS
    application.add_handler(CommandHandler("broadcast", broadcast_message))
    application.add_handler(CommandHandler("users", user_count))
    application.add_handler(CommandHandler("settings", settings_command))
    
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_all_messages))
    
    application.run_webhook(listen="0.0.0.0", port=int(PORT), url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")

if __name__ == '__main__':
    main()
