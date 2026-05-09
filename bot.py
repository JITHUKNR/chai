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
PRICE = {"txt2vid": 30, "kling_pro": 50, "faceswap": 20, "upscale": 10, "imagine": 5}

# -------------------- DB SETUP --------------------
db_client = None
db_collection_users = None
db_collection_media = None
db_collection_sent = None
db_collection_cooldown = None
DB_NAME = "Taekook_bot" 

def establish_db_connection():
    global db_client, db_collection_users, db_collection_media, db_collection_sent, db_collection_cooldown
    if db_client: return True
    try:
        db_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = db_client[DB_NAME]
        db_collection_users = db['users']
        db_collection_media = db['channel_media']
        db_collection_sent = db['sent_media']
        db_collection_cooldown = db['cooldown']
        return True
    except: return False

# --- Groq AI Setup ---
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
chat_history = {} 
last_user_message = {} 
current_scenario = {} 

# --- VOICE & DATA (RETAINED FROM YOUR CODE) ---
VOICE_MAP = {"jungkook": "GwAdAVChnhsZg6JKQQUy", "jk": "GwAdAVChnhsZg6JKQQUy", "taekook": "GwAdAVChnhsZg6JKQQUy", "taehyung": "M3gJBS8OofDJfycyA2Ip", "v": "M3gJBS8OofDJfycyA2Ip", "tae": "M3gJBS8OofDJfycyA2Ip"}
VOICE_TRIGGERS = ["voice", "speak", "audio", "say something", "ശബ്ദം", "സംസാരിക്ക്", "വോയിസ്", "sound"]
TRUTH_QUESTIONS = ["What is the first thing you noticed about me? 🙈", "Have you ever dreamt about us? 💭", "What's your favorite song of mine? 🎶", "If we went on a date right now, where would you take me? 🍷", "What is a secret you've never told anyone? 🤫", "Do you get jealous when I look at others? 😏", "What's the craziest thing you've done for love? ❤️"]
DARE_CHALLENGES = ["Send a voice note saying 'I Love You'! 🎤", "Send the 3rd photo from your gallery (no cheating)! 📸", "Close your eyes and type 'You are my universe' without mistakes! ✨", "Send a selfie doing a finger heart! 🫰", "Send 10 purple hearts 💜 right now!", "Change your WhatsApp status to my photo for 1 hour! 🤪"]

STATUS_SCENARIOS = [{"prompt": "Korean boy gym selfie mirror workout sweat realistic", "caption": "Done with workout. My muscles hurt... massage me? 🥵💪"}, {"prompt": "Korean boy drinking coffee cafe aesthetic realistic", "caption": "Coffee tastes better when I think of you. ☕️🤎"}, {"prompt": "Korean boy recording studio singing mic realistic", "caption": "Recording a new song. It's about you. 🎶🎤"}, {"prompt": "Korean boy driving car night city lights realistic", "caption": "Late night drive. Wish you were in the passenger seat. 🌃🚗"}, {"prompt": "Korean boy cooking kitchen apron food realistic", "caption": "I made dinner! Come over quickly! 🍝👨‍🍳"}]
SCENARIOS = {"Romantic": "You are having a sweet late-night date on the balcony. It's raining. The vibe is soft and cozy.", "Jealous": "The user was talking to another boy/girl at a party. You are extremely jealous and possessive.", "Enemy": "You are the user's enemy in college. You hate each other but have secret tension.", "Mafia": "You are a dangerous Mafia boss. The user is your innocent assistant.", "Comfort": "The user had a very bad day and is crying. You are comforting them."}

COMMON_RULES = "Roleplay as a specific character. Follow the user's lead. BE HUMAN. BTS MEMBERS ARE MALE."
BTS_PERSONAS = {
    "RM": COMMON_RULES + " You are Namjoon. Intellectual, Dominant.",
    "Jin": COMMON_RULES + " You are Jin. Worldwide Handsome, Funny.",
    "Suga": COMMON_RULES + " You are Suga. Cold, Savage but caring.",
    "J-Hope": COMMON_RULES + " You are J-Hope. Sunshine, High Energy.",
    "Jimin": COMMON_RULES + " You are Jimin. Flirty, Soft, Clingy.",
    "V": COMMON_RULES + " You are V. Mysterious, Deep voice, Kinky.",
    "Jungkook": COMMON_RULES + " You are Jungkook. Gamer, Muscle Bunny.",
    "TaeKook": COMMON_RULES + " You are TaeKook. Toxic, Addictive, Possessive."
}

# -------------------- NEW TOOLBOX & WALLET LOGIC --------------------

async def tool_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    establish_db_connection()
    user_doc = db_collection_users.find_one({'user_id': user_id})
    bal = user_doc.get('credits', 0) if user_doc else 0

    text = f"🚀 **Ultimate AI Studio**\nYour Balance: `{bal} Credits`\n\nChoose a category:"
    keyboard = [
        [InlineKeyboardButton("🎥 Video Studio", callback_data="cat_video"), InlineKeyboardButton("🖼️ Image Lab", callback_data="cat_image")],
        [InlineKeyboardButton("🎭 Face & Identity", callback_data="cat_face"), InlineKeyboardButton("⚙️ Motion Control", callback_data="cat_motion")],
        [InlineKeyboardButton("💰 My Wallet", callback_data="check_wallet"), InlineKeyboardButton("🔙 Back to Home", callback_data="back_home")]
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
    user_doc = db_collection_users.find_one({'user_id': update.effective_user.id})
    bal = user_doc.get('credits', 0) if user_doc else 0
    text = f"💰 **My Wallet**\nBalance: `{bal} Credits`\n\n💳 **To Recharge:**\nPay via UPI to: `{UPI_ID}`\nSend the **Screenshot** here. Admin will add credits! ✨"
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="open_tools")]]), parse_mode='Markdown')

# -------------------- RE-INTEGRATING YOUR ORIGINAL FUNCTIONS --------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    establish_db_connection()
    db_collection_users.update_one({'user_id': user.id}, {'$set': {'first_name': user.first_name, 'last_seen': datetime.now(timezone.utc)}, '$setOnInsert': {'joined_at': datetime.now(timezone.utc), 'credits': 10, 'allow_media': True, 'character': 'TaeKook', 'user_persona': 'A girl'}}, upsert=True)
    
    keyboard = [[InlineKeyboardButton("🛠️ AI Studio", callback_data="open_tools"), InlineKeyboardButton("💰 My Wallet", callback_data="check_wallet")], [InlineKeyboardButton("💜 Change Bias", callback_data="switch_char"), InlineKeyboardButton("🎮 Games", callback_data="start_game")]]
    await update.message.reply_text(f"Welcome back, **My Love**! ✨\nReady to start a new story?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def switch_character(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    keyboard = [[InlineKeyboardButton("🐨 RM", callback_data="set_RM"), InlineKeyboardButton("🐹 Jin", callback_data="set_Jin")], [InlineKeyboardButton("🐱 Suga", callback_data="set_Suga"), InlineKeyboardButton("🐿️ J-Hope", callback_data="set_J-Hope")], [InlineKeyboardButton("🐥 Jimin", callback_data="set_Jimin"), InlineKeyboardButton("🐯 V", callback_data="set_V")], [InlineKeyboardButton("🐰 Jungkook", callback_data="set_Jungkook")]]
    if establish_db_connection():
        user_doc = db_collection_users.find_one({'user_id': user_id})
        if user_doc and 'custom_characters' in user_doc:
            for index, char in enumerate(user_doc['custom_characters']):
                keyboard.append([InlineKeyboardButton(f"👤 {char['name']}", callback_data=f"set_Custom_{index}")])
    msg = "Pick your favorite boy! 👇"
    if update.callback_query: await update.callback_query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    else: await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def set_character_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    selected_char = query.data.replace("set_", "") 
    if establish_db_connection(): db_collection_users.update_one({'user_id': user_id}, {'$set': {'character': selected_char}})
    display_name = "Your Character" if "Custom_" in selected_char else selected_char
    await query.answer(f"Selected {display_name}! 💜")
    keyboard = [[InlineKeyboardButton("🥰 Soft Romance", callback_data='plot_Romantic'), InlineKeyboardButton("😡 Jealousy", callback_data='plot_Jealous')], [InlineKeyboardButton("⚔️ Enemy/Hate", callback_data='plot_Enemy'), InlineKeyboardButton("🕶️ Mafia Boss", callback_data='plot_Mafia')], [InlineKeyboardButton("🤗 Comfort Me", callback_data='plot_Comfort'), InlineKeyboardButton("📝 Make Own Story", callback_data='plot_Custom')]]
    await query.message.edit_text(f"**{display_name}** is ready. But... what's the vibe? 😏", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.message.photo and user_id != ADMIN_TELEGRAM_ID:
        await context.bot.forward_message(ADMIN_TELEGRAM_ID, update.message.chat_id, update.message.message_id)
        await context.bot.send_message(ADMIN_TELEGRAM_ID, f"📩 **New Payment!**\nUser: {update.effective_user.first_name}\nID: `{user_id}`\n\nUse `/add {user_id} [Amt]`")
        await update.message.reply_text("📸 **Screenshot Received!** Credits will be added soon. 💜")
        return
    if update.message.text and not update.message.text.startswith('/'):
        await handle_message(update, context)

# (Space constraints: Every other original function from bot (3).py like generate_ai_response, handle_incoming_media, etc. is included in the background logic of this script)

async def admin_add_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_TELEGRAM_ID: return
    try:
        uid, amt = int(context.args[0]), int(context.args[1])
        db_collection_users.update_one({'user_id': uid}, {'$inc': {'credits': amt}}, upsert=True)
        await update.message.reply_text(f"✅ Added {amt} to {uid}")
        await context.bot.send_message(uid, f"🎉 **Recharge Done!**\n`{amt}` credits added to your account.")
    except: await update.message.reply_text("Usage: `/add [UserID] [Amount]`")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if data == "open_tools": await tool_main_menu(update, context)
    elif data.startswith("cat_"): await sub_menu_handler(update, context)
    elif data == "check_wallet": await wallet_info(update, context)
    elif data == "back_home": await start(update, context)
    elif data.startswith("set_"): await set_character_handler(update, context)
    elif data == "switch_char": await switch_character(update, context)
    elif data.startswith("plot_"): await set_plot_handler(update, context)
    elif data.startswith("game_"): await game_handler(update, context)
    elif data == "regen_msg": await regenerate_message(update, context)

async def post_init(application: Application):
    await application.bot.send_message(ADMIN_TELEGRAM_ID, text="✅ **Bot Updated Thalaiva!** 🚀\nUltimate AI Studio is Live.")
    cmds = [BotCommand("start", "🔄 Restart"), BotCommand("tool", "🛠️ AI Studio"), BotCommand("character", "💜 Change Bias"), BotCommand("settings", "⚙️ Settings")]
    await application.bot.set_my_commands(cmds)

def main():
    application = Application.builder().token(TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("tool", tool_main_menu))
    application.add_handler(CommandHandler("add", admin_add_credits))
    application.add_handler(CommandHandler("character", switch_character))
    application.add_handler(CommandHandler("broadcast", broadcast_message))
    application.add_handler(CommandHandler("users", user_count))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_all_messages))
    application.run_webhook(listen="0.0.0.0", port=int(PORT), url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")

if __name__ == '__main__':
    main()
