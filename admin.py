import asyncio
import random
import urllib.parse
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.error import BadRequest
import logging

# bot.py ഫയലിലെ വേരിയബിളുകൾ ഉപയോഗിക്കാൻ വേണ്ടി ഇത് ഇമ്പോർട്ട് ചെയ്യുന്നു
import bot

logger = logging.getLogger(__name__)

async def user_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message if update.message else update.callback_query.message
    if update.effective_user.id != bot.ADMIN_TELEGRAM_ID: return await message.reply_text("Admin only!")
    if bot.establish_db_connection():
        total_count = bot.db_collection_users.count_documents({})
        one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
        active_today = bot.db_collection_users.count_documents({'last_seen': {'$gte': one_day_ago}})
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
    if not bot.establish_db_connection(): return await message_obj.reply_text("DB Error.")
    user_doc = bot.db_collection_users.find_one({'user_id': user_id})
    if user_doc and user_doc.get('allow_media') is False: return await message_obj.reply_text("Media disabled.")
    cooldown_doc = bot.db_collection_cooldown.find_one({'user_id': user_id})
    if cooldown_doc:
        elapsed = current_time - cooldown_doc['last_command_time'].replace(tzinfo=timezone.utc)
        if elapsed.total_seconds() < bot.COOLDOWN_TIME_SECONDS: return await message_obj.reply_text("Wait a bit, darling. 😉")
    await message_obj.reply_text("Searching... 😉")
    try:
        random_media = bot.db_collection_media.aggregate([{'$sample': {'size': 1}}])
        result = next(random_media, None)
        if result:
            caption = "Just for you. 💜"
            if result['file_type'] == 'photo': msg = await message_obj.reply_photo(result['file_id'], caption=caption, has_spoiler=True, protect_content=True)
            else: msg = await message_obj.reply_video(result['file_id'], caption=caption, has_spoiler=True, protect_content=True)
            bot.db_collection_cooldown.update_one({'user_id': user_id}, {'$set': {'last_command_time': current_time}}, upsert=True)
            bot.db_collection_sent.insert_one({'chat_id': message_obj.chat_id, 'message_id': msg.message_id, 'sent_at': current_time})
        else: await message_obj.reply_text("No media found.")
    except Exception: await message_obj.reply_text("Error sending media.")

async def send_fake_status(context: ContextTypes.DEFAULT_TYPE):
    if not bot.establish_db_connection(): return
    scenario = random.choice(bot.STATUS_SCENARIOS)
    encoded_prompt = urllib.parse.quote(scenario['prompt'])
    seed = random.randint(0, 100000)
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&seed={seed}&nologo=true"
    users = bot.db_collection_users.find({}, {'user_id': 1})
    for user in users:
        try: await context.bot.send_photo(chat_id=user['user_id'], photo=image_url, caption=f"📸 **New Status Update:**\n\n{scenario['caption']}", parse_mode='Markdown')
        except Exception: pass

async def force_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != bot.ADMIN_TELEGRAM_ID: return
    await update.message.reply_text("🚀 Forcing Status Update...")
    await send_fake_status(context)

async def run_hourly_cleanup(application):
    await asyncio.sleep(300) 
    while True:
        await asyncio.sleep(3600) 
        if not bot.establish_db_connection(): continue
        time_limit = datetime.now(timezone.utc) - timedelta(hours=bot.MEDIA_LIFETIME_HOURS)
        try:
            msgs = list(bot.db_collection_sent.find({'sent_at': {'$lt': time_limit}}))
            for doc in msgs:
                try: await application.bot.delete_message(chat_id=doc['chat_id'], message_id=doc['message_id'])
                except Exception: pass
                bot.db_collection_sent.delete_one({'_id': doc['_id']})
        except Exception: pass

async def delete_old_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != bot.ADMIN_TELEGRAM_ID: return
    if not bot.establish_db_connection(): return
    time_limit = datetime.now(timezone.utc) - timedelta(hours=bot.MEDIA_LIFETIME_HOURS)
    msgs = list(bot.db_collection_sent.find({'sent_at': {'$lt': time_limit}}))
    for doc in msgs:
        try: await context.bot.delete_message(chat_id=doc['chat_id'], message_id=doc['message_id'])
        except Exception: pass
        bot.db_collection_sent.delete_one({'_id': doc['_id']})
    await update.effective_message.reply_text(f"Deleted {len(msgs)} messages.")

async def clear_deleted_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != bot.ADMIN_TELEGRAM_ID: return
    await update.effective_message.reply_text("Cleaning up...")
    if not bot.establish_db_connection(): return
    all_media = list(bot.db_collection_media.find({}))
    deleted = 0
    for doc in all_media:
        try:
            if doc['file_type'] == 'photo': msg = await context.bot.send_photo(bot.ADMIN_TELEGRAM_ID, doc['file_id'], disable_notification=True)
            else: msg = await context.bot.send_video(bot.ADMIN_TELEGRAM_ID, doc['file_id'], disable_notification=True)
            await context.bot.delete_message(bot.ADMIN_TELEGRAM_ID, msg.message_id)
        except BadRequest:
            bot.db_collection_media.delete_one({'_id': doc['_id']})
            deleted += 1
        except Exception: pass
        await asyncio.sleep(0.1)
    await update.effective_message.reply_text(f"Removed {deleted} invalid files.")

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != bot.ADMIN_TELEGRAM_ID: return
    keyboard = [
        [InlineKeyboardButton("Users 👥", callback_data='admin_users'), InlineKeyboardButton("New Photo 📸", callback_data='admin_new_photo')],
        [InlineKeyboardButton("Broadcast 📣", callback_data='admin_broadcast_text'), InlineKeyboardButton("Test Wish ☀️", callback_data='admin_test_wish')],
        [InlineKeyboardButton("Clean Media 🧹", callback_data='admin_clearmedia'), InlineKeyboardButton("Delete Old 🗑️", callback_data='admin_delete_old')],
        [InlineKeyboardButton("How to use File ID? 🆔", callback_data='admin_help_id')]
    ]
    await update.message.reply_text("👑 **Super Admin Panel:**\nSelect an option below:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def admin_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data == 'admin_users': await user_count(update, context)
    elif data == 'admin_new_photo': await send_new_photo(update, context)
    elif data == 'admin_clearmedia': await clear_deleted_media(update, context)
    elif data == 'admin_delete_old': await delete_old_media(update, context)
    elif data == 'admin_broadcast_text': await context.bot.send_message(query.from_user.id, "📢 To Broadcast: Type `/broadcast Your Message`")
    elif data == 'admin_test_wish': await send_morning_wish(context)
    elif data == 'admin_help_id': await context.bot.send_message(query.from_user.id, "🆔 Send any file to get File ID.")

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != bot.ADMIN_TELEGRAM_ID: return
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

    if bot.establish_db_connection():
        users = [d['user_id'] for d in bot.db_collection_users.find({}, {'user_id': 1})]
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
    if update.message.from_user.id == bot.ADMIN_TELEGRAM_ID:
        file_id, media_type = None, "Unknown"
        if update.message.animation: file_id, media_type = update.message.animation.file_id, "GIF"
        elif update.message.video: file_id, media_type = update.message.video.file_id, "Video"
        elif update.message.sticker: file_id, media_type = update.message.sticker.file_id, "Sticker"
        elif update.message.photo: file_id, media_type = update.message.photo[-1].file_id, "Photo"
        elif update.message.voice: file_id, media_type = update.message.voice.file_id, "Voice Note"
        if file_id: await update.message.reply_text(f"🆔 **{media_type} ID:**\n`{file_id}`\n\n(Click to Copy)")

async def send_morning_wish(context: ContextTypes.DEFAULT_TYPE):
    if bot.establish_db_connection():
        for user in bot.db_collection_users.find({}, {'user_id': 1}):
            try: await context.bot.send_message(user['user_id'], "Good Morning, **My Love**! ☀️❤️ Have a beautiful day!", parse_mode='Markdown')
            except: pass

async def check_inactivity(context: ContextTypes.DEFAULT_TYPE):
    if not bot.establish_db_connection(): return
    threshold_time = datetime.now(timezone.utc) - timedelta(hours=24)
    users = bot.db_collection_users.find({'last_seen': {'$lt': threshold_time}, 'notified_24h': {'$ne': True}})
    for user in users:
        try:
            sys_prompt = bot.BTS_PERSONAS.get(user.get('character', 'TaeKook'), bot.BTS_PERSONAS["TaeKook"])
            completion = bot.groq_client.chat.completions.create(messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": "The user hasn't messaged you in 24 hours. Send a short text to make them reply."}], model="llama-3.3-70b-versatile")
            await context.bot.send_message(user['user_id'], completion.choices[0].message.content.strip(), parse_mode='Markdown')
            bot.db_collection_users.update_one({'_id': user['_id']}, {'$set': {'notified_24h': True}})
        except: pass

async def test_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != bot.ADMIN_TELEGRAM_ID: return
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
            if is_video: await context.bot.send_video(bot.ADMIN_TELEGRAM_ID, media_file_id, caption=final_msg, reply_markup=reply_markup, parse_mode='Markdown')
            else: await context.bot.send_photo(bot.ADMIN_TELEGRAM_ID, media_file_id, caption=final_msg, reply_markup=reply_markup, parse_mode='Markdown')
        else: await context.bot.send_message(bot.ADMIN_TELEGRAM_ID, final_msg, reply_markup=reply_markup, parse_mode='Markdown')
        await update.message.reply_text("✅ Test Sent!")
    except Exception as e: await update.message.reply_text(f"❌ Error: {e}")

async def admin_add_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != bot.ADMIN_TELEGRAM_ID: return
    try:
        uid, amt = int(context.args[0]), int(context.args[1])
        bot.db_collection_users.update_one({'user_id': uid}, {'$inc': {'credits': amt}}, upsert=True)
        await update.message.reply_text(f"✅ Added {amt} to {uid}")
        await context.bot.send_message(uid, f"🎉 **Recharge Done!**\n`{amt}` credits added to your wallet. Enjoy! 💜")
    except: await update.message.reply_text("Usage: `/add [UserID] [Amount]`")
