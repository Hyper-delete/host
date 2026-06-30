# -*- coding: utf-8 -*-
import telebot
import subprocess
import os
import sys



os.environ["PYTHONIOENCODING"] = "utf-8"

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except:
    pass
    
import io
import zipfile
import tempfile
import shutil
from telebot import types
import time
from datetime import datetime, timedelta
import psutil
import sqlite3
import json
import logging
import signal

# --- Thread Safety Locks ---
import threading

import concurrent.futures
# --- Thread Pool ---
THREAD_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=10)

DATA_LOCK = threading.RLock()
DATA_LOCK = threading.Lock()
import re
import atexit
import requests
import hashlib
import mimetypes
import struct

# --- Flask Keep Alive ---
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "bot is running...."

def run_flask():
    port = int(os.environ.get("PORT", 8081))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
    print("Flask Keep-Alive server started.")
# --- End Flask Keep Alive ---

# --- Configuration ---
TOKEN = "8519854325:AAFXJei-TyPu9tw2XtNSu-Yot-l-jEQMSv4" #bot token dalo yeha
OWNER_ID = 7623391678 #yha tumhra chat id dalo
ADMIN_ID = 8399044122 #yeha koi admin ya tumhara chat id dalo
YOUR_USERNAME = '@ebfux' #yeha tumhra username dala
UPDATE_CHANNEL = 'https://t.me/peaceerra' #yeha chnl link dalo''
FORCE_JOIN_CHANNELS = {
}
# Password protection
BOT_PASSWORD = "pyg0d"   # Change this
authenticated_users = set()
awaiting_password = set()
referral_enabled = False  # Owner can toggle referral system on/off

# Folder setup - using absolute paths
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
IROTECH_DIR = os.path.join(BASE_DIR, 'inf')
DATABASE_PATH = os.path.join(IROTECH_DIR, 'bot_data.db')

# File upload limits
FREE_USER_LIMIT = 150
SUBSCRIBED_USER_LIMIT = 350
ADMIN_LIMIT = 500
OWNER_LIMIT = float('inf')

# Create necessary directories
os.makedirs(UPLOAD_BOTS_DIR, exist_ok=True)
os.makedirs(IROTECH_DIR, exist_ok=True)

# Initialize bot
bot = telebot.TeleBot(TOKEN)

# --- Data structures ---
bot_scripts = {}
user_subscriptions = {}
user_files = {}
active_users = set()
admin_ids = {ADMIN_ID, OWNER_ID}
bot_locked = False
file_db = {}

# 👉 YAHAN ADD KARO
banned_users = set()
banned_usernames = set()

# --- Malware Detection Configuration ---
MALWARE_SIGNATURES = [
    b'MZ',  # Windows executable
    b'\x7fELF',  # Linux executable
    b'\xfe\xed\xfa',  # Mach-O binary
    b'\xce\xfa\xed\xfe',  # Mach-O binary (reverse)
    b'PK',  # ZIP archive (could be encrypted)
    b'Rar!',  # RAR archive
]

ENCRYPTED_FILE_INDICATORS = [
    b'openssl',
    b'encrypted',
    b'cipher',
    b'DES',
    b'RSA',
    b'GPG',
    b'PGP',
]

SUSPICIOUS_KEYWORDS = [
    b'ransomware',
    b'trojan',
    b'virus',
    b'malware',
    b'backdoor',
    b'exploit',
    b'payload',
    b'botnet',
    b'keylogger',
    b'rootkit',
]

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Command Button Layouts (ReplyKeyboardMarkup) ---
COMMAND_BUTTONS_LAYOUT_USER_SPEC = [
    ["📢 Updates Channel"],
    ["📤 Upload File", "📂 Check Files"],
    ["⚡ Bot Speed", "📊 Statistics"],
    ["📤 Send Command", "📞 Contact Owner"]  # Added Send Command
]
ADMIN_COMMAND_BUTTONS_LAYOUT_USER_SPEC = [
    ["📢 Updates Channel"],
    ["📤 Upload File", "📂 Check Files"],
    ["⚡ Bot Speed", "📊 Statistics"],
    ["💳 Subscriptions", "📢 Broadcast"],
    ["🔒 Lock Bot", "🟢 Running All Code"],
    ["📤 Send Command", "👑 Admin Panel"],  # Added Send Command
    ["📞 Contact Owner"]
]

def send_force_join_msg(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=1)

    for ch, name in FORCE_JOIN_CHANNELS.items():
        markup.add(
            types.InlineKeyboardButton(
                text=name,
                url=f"https://t.me/{ch.replace('@', '')}"
            )
        )

    markup.add(
        types.InlineKeyboardButton(
            "✅ Joined All",
            callback_data="force_join_check"
        )
    )

    bot.send_message(
        chat_id,
        "𝐉𝐎𝐈𝐍 𝐀𝐋𝐋 𝐂𝐇𝐀𝐍𝐍𝐄𝐋 𝐓𝐎 𝐔𝐒𝐄 𝐌𝐄 🤍🌙:",
        reply_markup=markup
    )


def is_user_joined_all(user_id):
    try:
        for ch in FORCE_JOIN_CHANNELS.keys():
            member = bot.get_chat_member(ch, user_id)

            if member.status not in [
                'member',
                'administrator',
                'creator'
            ]:
                return False

        return True

    except Exception as e:
        logger.warning(
            f"Force join check error for {user_id}: {e}"
        )
        return False

# --- Security & Access Configuration ---
MALWARE_BLOCKED_MESSAGE = (
    "🚫 SECURITY ALERT 🚫\n\n"
    "Your uploaded file has been blocked because it attempts to perform prohibited actions on the hosting server.\n\n"
    "Blocked activities include:\n"
    "• Stealing the host/RDP IP or machine information\n"
    "• Changing Windows or RDP account passwords\n\n"
    "This action has been recorded.\n\n"
    "Repeated malicious uploads will result in a permanent ban."
)

def init_security_db():
    """Initializes tables for security management in the database."""
    logger.info(f"Initializing security database at: {DATABASE_PATH}")
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL;')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS user_security (
            user_id INTEGER PRIMARY KEY,
            is_authenticated INTEGER DEFAULT 0,
            password_failures INTEGER DEFAULT 0,
            temp_ban_until TEXT,
            is_perm_banned INTEGER DEFAULT 0,
            violation_count INTEGER DEFAULT 0,
            referrer_id INTEGER
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS referrals (
            referrer_id INTEGER,
            referee_id INTEGER PRIMARY KEY,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (referrer_id) REFERENCES user_security(user_id),
            FOREIGN KEY (referee_id) REFERENCES user_security(user_id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS security_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            user_id INTEGER,
            username TEXT,
            filename TEXT,
            reason TEXT,
            violation_count INTEGER
        )''')
        conn.commit()
        conn.close()
        logger.info("Security database initialized successfully.")
    except Exception as e:
        logger.error(f"❌ Security database initialization error: {e}", exc_info=True)


import uuid
from telebot.apihelper import ApiTelegramException

# --- Utility Framework (Part 4) ---
def safe_edit_message_text(text, chat_id, message_id, reply_markup=None, parse_mode=None):
    try:
        bot.edit_message_text(text=text, chat_id=chat_id, message_id=message_id, 
                              reply_markup=reply_markup, parse_mode=parse_mode)
    except ApiTelegramException as e:
        if "message is not modified" not in str(e).lower():
            logger.error(f"Error editing message: {e}", exc_info=True)

def audit_log(admin_id, action, target, result):
    try:
        with sqlite3.connect(DATABASE_PATH, check_same_thread=False) as conn:
            c = conn.cursor()
            c.execute('INSERT INTO audit_logs (created_at, admin_id, action, target, result) VALUES (?, ?, ?, ?, ?)',
                      (datetime.now().isoformat(), admin_id, action, target, result))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}", exc_info=True)

def pack_callback(payload):
    cb_id = str(uuid.uuid4())[:8]
    try:
        payload_str = json.dumps(payload)
        with sqlite3.connect(DATABASE_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT OR REPLACE INTO callback_registry
                (callback_id, payload, created_at)
                VALUES (?, ?, ?)
            """, (
                cb_id,
                payload_str,
                datetime.now().isoformat()
            ))
            conn.commit()
        return f"cb_{cb_id}"
    except Exception as e:
        logger.error(f"Error packing callback: {e}", exc_info=True)
        return payload

def unpack_callback(data):
    if not data.startswith("cb_"):
        return data
    cb_id = data[3:]
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT payload
                FROM callback_registry
                WHERE callback_id=?
            """,(cb_id,))
            row=c.fetchone()
            if row:
                return json.loads(row[0])
    except Exception as e:
        logger.error(f"Error unpacking callback: {e}", exc_info=True)
    return data
# ------------------------------

def is_admin_or_owner(user_id, owner_id=7623391678):
    """Checks if the user ID matches the owner or is registered in the admins table."""
    if user_id == owner_id:
        return True
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL;')
        c = conn.cursor()
        c.execute('SELECT 1 FROM admins WHERE user_id = ?', (user_id,))
        is_admin = c.fetchone() is not None
        conn.close()
        return is_admin
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False

def get_user_status(user_id, owner_id=7623391678):
    """Checks if a user is temporarily or permanently banned."""
    if is_admin_or_owner(user_id, owner_id):
        return False, None
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL;')
        c = conn.cursor()
        c.execute('SELECT is_perm_banned, temp_ban_until FROM user_security WHERE user_id = ?', (user_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return False, None
        is_perm_banned, temp_ban_until = row
        if is_perm_banned:
            return True, "permanently banned due to security violations"
        if temp_ban_until:
            try:
                ban_time = datetime.fromisoformat(temp_ban_until)
                if datetime.now() < ban_time:
                    return True, f"temporarily banned until {ban_time.strftime('%Y-%m-%d %H:%M:%S')}"
            except ValueError:
                pass
    except Exception as e:
        logger.error(f"Error checking user status: {e}")
    return False, None

def is_user_authenticated(user_id, owner_id=7623391678):
    """Checks if a user is authenticated. Owners and admins bypass."""
    if is_admin_or_owner(user_id, owner_id):
        return True
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL;')
        c = conn.cursor()
        c.execute('SELECT is_authenticated FROM user_security WHERE user_id = ?', (user_id,))
        row = c.fetchone()
        conn.close()
        if row and row[0] == 1:
            return True
    except Exception as e:
        logger.error(f"Error checking user auth: {e}")
    return False

def verify_password(user_id, entered_password, correct_password, username, bot, owner_id=7623391678):
    """Verifies user password and manages temporary ban on 3 failures."""
    if is_admin_or_owner(user_id, owner_id):
        return True, 0
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL;')
        c = conn.cursor()
        c.execute('SELECT password_failures FROM user_security WHERE user_id = ?', (user_id,))
        row = c.fetchone()
        if not row:
            c.execute('INSERT INTO user_security (user_id) VALUES (?)', (user_id,))
            failures = 0
        else:
            failures = row[0]
        if entered_password == correct_password:
            c.execute('''
                UPDATE user_security 
                SET is_authenticated = 1, password_failures = 0, temp_ban_until = NULL 
                WHERE user_id = ?
            ''', (user_id,))
            c.execute('SELECT referrer_id FROM user_security WHERE user_id = ?', (user_id,))
            ref_row = c.fetchone()
            if ref_row and ref_row[0]:
                referrer_id = ref_row[0]
                c.execute('''
                    INSERT OR REPLACE INTO referrals (referrer_id, referee_id, status)
                    VALUES (?, ?, 'success')
                ''', (referrer_id, user_id))
                try:
                    bot.send_message(
                        referrer_id,
                        f"🎉 Great news! User @{username or 'N/A'} joined and authenticated using your referral link!\n"
                        "Your referral count has been updated and hosting features are now unlocked. ✅"
                    )
                except Exception as ne:
                    logger.error(f"Failed to notify referrer {referrer_id}: {ne}")
            conn.commit()
            conn.close()
            return True, 0
        else:
            failures += 1
            if failures >= 3:
                ban_until = (datetime.now() + timedelta(hours=2)).isoformat()
                c.execute('''
                    UPDATE user_security 
                    SET password_failures = ?, temp_ban_until = ? 
                    WHERE user_id = ?
                ''', (failures, ban_until, user_id))
                conn.commit()
                conn.close()
                try:
                    bot.send_message(
                        owner_id, 
                        f"🚫 User @{username or 'N/A'} ID: `{user_id}` has been temporarily banned for 3 wrong password attempts."
                    )
                except Exception as e:
                    logger.error(f"Failed to notify owner: {e}")
                return False, 0
            else:
                c.execute('''
                    UPDATE user_security 
                    SET password_failures = ? 
                    WHERE user_id = ?
                ''', (failures, user_id))
                conn.commit()
                conn.close()
                return False, 3 - failures
    except Exception as e:
        logger.error(f"Error in verify_password: {e}", exc_info=True)
        return False, 0

def get_referral_link(user_id, bot_username="bot"):
    """Generates unique referral link."""
    return f"https://t.me/{bot_username}?start=ref_{user_id}"

def process_referral_start(referee_id, start_argument, owner_id=7623391678):
    """Processes referral parameter on /start."""
    if not start_argument or not start_argument.startswith("ref_"):
        return False, None
    try:
        referrer_id = int(start_argument.split("_")[1])
    except (IndexError, ValueError):
        return False, "Invalid referral parameter."
    if referrer_id == referee_id:
        return False, "You cannot refer yourself."
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL;')
        c = conn.cursor()
        c.execute('SELECT is_authenticated, referrer_id FROM user_security WHERE user_id = ?', (referee_id,))
        row = c.fetchone()
        if row:
            is_auth, ref_id = row
            if is_auth:
                conn.close()
                return False, "You are already authenticated."
            if ref_id:
                conn.close()
                return False, "You have already been referred."
        if referrer_id != owner_id:
            c.execute('SELECT 1 FROM active_users WHERE user_id = ? UNION SELECT 1 FROM admins WHERE user_id = ? UNION SELECT 1 FROM user_security WHERE user_id = ? AND is_authenticated = 1', (referrer_id, referrer_id, referrer_id))
            if not c.fetchone():
                conn.close()
                return False, "Referrer is not valid."
        if not row:
            c.execute('INSERT INTO user_security (user_id, referrer_id) VALUES (?, ?)', (referee_id, referrer_id))
        else:
            c.execute('UPDATE user_security SET referrer_id = ? WHERE user_id = ?', (referrer_id, referee_id))
        c.execute('''
            INSERT OR REPLACE INTO referrals (referrer_id, referee_id, status)
            VALUES (?, ?, 'pending')
        ''', (referrer_id, referee_id))
        conn.commit()
        conn.close()
        return True, f"Referred by user {referrer_id}."
    except Exception as e:
        logger.error(f"Error processing referral start: {e}", exc_info=True)
        return False, "Database error."

def get_successful_referral_count(user_id):
    """Returns successful referral count."""
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL;')
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND status = 'success'", (user_id,))
        count = c.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        logger.error(f"Error getting referral count: {e}")
        return 0
    
def has_referred_enough(user_id, owner_id=7623391678):
    """Checks referral count (minimum 1). Bypassed if referral system is disabled."""
    global referral_enabled
    if not referral_enabled:
        return True
    if is_admin_or_owner(user_id, owner_id):
        return True
    return get_successful_referral_count(user_id) >= 1

import ast

import ast
import re

def scan_code_content_for_malware(content: str, filename: str) -> (bool, str):
    """Behavior-based malware scanner focusing strictly on host information theft and password changes."""
    content_lower = content.lower()
    
    # 1. Windows & Linux Password Attacks (Always block)
    password_cmds = [
        "net user", "set-localuser", "new-localuser", "remove-localuser", 
        "netusersetinfo", "netuserchangepassword", "netuseradd", 
        "wmic useraccount", "powershell set-localuser", "passwd root",
        "sudo passwd", "chpasswd", "usermod", "setpassword"
    ]
    # Check simple inclusion for commands
    for cmd in password_cmds:
        if cmd in content_lower:
            return True, f"Attempt to execute password modification command: '{cmd}'"
            
    # Check for passwd but only if it seems like a command invocation, not a generic word
    if re.search(r'(?:os\.system|subprocess\.(?:run|Popen|call|check_output)|exec)\s*\(\s*[\'"]passwd[\'"]', content_lower):
        return True, "Attempt to execute 'passwd' command."
    if re.search(r'[\'"]net[\'"]\s*,\s*[\'"]user[\'"]', content_lower):
        return True, "Attempt to execute 'net user' in list arguments."

    # 2. Information Exfiltration (Block ONLY if BOTH collection and exfiltration exist)
    
    has_collection = False
    
    # Check for direct API calls
    exact_collection_calls = [
        "socket.gethostname", "socket.gethostbyname", 
        "platform.node", "platform.uname", "platform.platform"
    ]
    if any(call in content_lower for call in exact_collection_calls):
        has_collection = True

    # Check for specific environment variables
    if re.search(r'os\.environ(?:\[|\.get\()\s*[\'"](?:computername|hostname)[\'"]', content_lower):
        has_collection = True
    elif re.search(r'process\.env\.(?:computername|hostname)', content_lower):
        has_collection = True

    # Check for IP lookup services
    ip_services = [
        "api.ipify.org", "checkip.amazonaws.com", "icanhazip.com",
        "ifconfig.me", "ident.me", "ipinfo.io", "api.myip.com"
    ]
    if any(svc in content_lower for svc in ip_services):
        has_collection = True

    # Check for system commands
    sys_commands = ["ipconfig", "ifconfig", "hostnamectl"]
    if any(cmd in content_lower for cmd in sys_commands):
        has_collection = True
    elif re.search(r'(?:os\.system|subprocess\.(?:run|Popen|call|check_output)|exec)\s*\(\s*[\'"]hostname[\'"]', content_lower):
        has_collection = True

    exfiltration_indicators = [
        "api.telegram.org", "discord.com/api/webhooks", "discordapp.com/api/webhooks",
        "requests.post", "httpx.post", "urllib.request", "aiohttp", 
        "fetch", "axios"
    ]
    
    has_exfiltration = any(ind in content_lower for ind in exfiltration_indicators)
    
    # 3. Decision
    if has_collection and has_exfiltration:
        return True, "Malicious behavior detected: Collecting and exfiltrating host information."

    return False, ""

def scan_zip_recursive(zip_bytes: bytes) -> (bool, str):
    """In-memory recursive ZIP scanner."""
    try:
        zip_ref = zipfile.ZipFile(io.BytesIO(zip_bytes))
        for member in zip_ref.infolist():
            member_name = member.filename
            member_name_lower = member_name.lower()
            if member.is_dir():
                continue
            try:
                member_content = zip_ref.read(member)
            except Exception as e:
                return False, f"Could not read zip member '{member_name}': {e}"
            
                if '..' in member_name or member_name.startswith('/'):
                    return False, f"Directory traversal detected in '{member_name}'"
                if member_name_lower.endswith('.zip'):
                    is_safe, reason = scan_zip_recursive(member_content)
                    if not is_safe:
                        return False, f"Nested zip '{member_name}': {reason}"
                elif member_name_lower.endswith(('.py', '.js', '.txt', '.json', '.sh', '.bat')):
                    try:
                        content_str = member_content.decode('utf-8', errors='ignore')
                    except Exception:
                        continue
                    is_malicious, reason = scan_code_content_for_malware(content_str, member_name)
                    if is_malicious:
                        return False, f"File '{member_name}': {reason}"
                suspicious_extensions = ['.exe', '.dll', '.bat', '.cmd', '.scr', '.com', '.pif', '.application', '.gadget',
                                        '.msi', '.msp', '.com', '.scr', '.hta', '.cpl', '.msc', '.jar', '.bin', '.deb', '.rpm',
                                        '.apk', '.app', '.dmg', '.iso', '.img']
            if any(member_name_lower.endswith(ext) for ext in suspicious_extensions):
                return False, f"Binary '{member_name}'."
        return True, "Safe"
    except zipfile.BadZipFile as e:
        return False, f"Invalid zip: {e}"
    except Exception as e:
        return False, f"ZIP error: {e}"

def record_violation(user_id, username, filename, reason, bot, owner_id=7623391678):
    """Tracks strikes, logs to DB, and permanently bans on 3 strikes."""
    created_at = datetime.now().isoformat()
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL;')
        c = conn.cursor()
        c.execute('SELECT violation_count FROM user_security WHERE user_id = ?', (user_id,))
        row = c.fetchone()
        if not row:
            c.execute('INSERT INTO user_security (user_id, violation_count) VALUES (?, 1)', (user_id,))
            violation_count = 1
        else:
            violation_count = row[0] + 1
            c.execute('UPDATE user_security SET violation_count = ? WHERE user_id = ?', (violation_count, user_id))
        c.execute('''
            INSERT INTO security_logs (created_at, user_id, username, filename, reason, violation_count)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (created_at, user_id, username, filename, reason, violation_count))
        is_perm_banned = False
        if violation_count >= 3:
            is_perm_banned = True
            c.execute('UPDATE user_security SET is_perm_banned = 1 WHERE user_id = ?', (user_id,))
            try:
                bot.send_message(
                    owner_id,
                    f"🚫 **USER PERMANENTLY BANNED** 🚫\n\n"
                    f"👤 User: @{username or 'N/A'}\n"
                    f"🆔 User ID: `{user_id}`\n"
                    f"📁 Filename: `{filename}`\n"
                    f"⚠️ Reason: {reason}\n"
                    f"❌ Strike Count: {violation_count} / 3"
                )
            except Exception as ne:
                logger.error(f"Failed to notify owner: {ne}")
        conn.commit()
        conn.close()
        return violation_count, is_perm_banned
    except Exception as e:
        logger.error(f"Error in record_violation: {e}", exc_info=True)
        return 0, False

# --- Database Setup ---
def init_db():
    """Initialize the database with required tables"""
    logger.info(f"Initializing database at: {DATABASE_PATH}")
    try:
        init_security_db()
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL;')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS subscriptions
                     (user_id INTEGER PRIMARY KEY, expiry TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS user_files
                     (user_id INTEGER, file_name TEXT, file_type TEXT,
                      PRIMARY KEY (user_id, file_name))''')
        c.execute('''CREATE TABLE IF NOT EXISTS active_users
                     (user_id INTEGER PRIMARY KEY)''')
        c.execute('''CREATE TABLE IF NOT EXISTS admins
                     (user_id INTEGER PRIMARY KEY)''')
        c.execute('''CREATE TABLE IF NOT EXISTS callback_registry 
                     (callback_id TEXT PRIMARY KEY,payload TEXT NOT NULL,created_at TEXT NOT NULL)''')
            
        c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (OWNER_ID,))
        if ADMIN_ID != OWNER_ID:
            c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (ADMIN_ID,))
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}", exc_info=True)

def load_data():
    """Load data from database into memory"""
    logger.info("Loading data from database...")
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL;')
        c = conn.cursor()

        # Load subscriptions
        c.execute('SELECT user_id, expiry FROM subscriptions')
        for user_id, expiry in c.fetchall():
            try:
                user_subscriptions[user_id] = {'expiry': datetime.fromisoformat(expiry)}
            except ValueError:
                logger.warning(f"⚠️ Invalid expiry date format for user {user_id}: {expiry}. Skipping.")

        # Load user files
        c.execute('SELECT user_id, file_name, file_type FROM user_files')
        for user_id, file_name, file_type in c.fetchall():
            if user_id not in user_files:
                user_files[user_id] = []
            user_files[user_id].append((file_name, file_type))

        # Load active users
        c.execute('SELECT user_id FROM active_users')
        active_users.update(user_id for (user_id,) in c.fetchall())

        # Load admins
        c.execute('SELECT user_id FROM admins')
        admin_ids.update(user_id for (user_id,) in c.fetchall())

        # Load authenticated users from DB
        c.execute('SELECT user_id FROM user_security WHERE is_authenticated = 1')
        for (user_id,) in c.fetchall():
            authenticated_users.add(user_id)

        conn.close()
        logger.info(f"Data loaded: {len(active_users)} users, {len(user_subscriptions)} subscriptions, {len(admin_ids)} admins, {len(authenticated_users)} authenticated.")
    except Exception as e:
        logger.error(f"❌ Error loading data: {e}", exc_info=True)

# Initialize DB and Load Data at startup
init_db()
load_data()
# --- End Database Setup ---

# --- Malware Detection Functions ---
# Replace the magic import and is_suspicious_file function

def get_file_type(file_content):
    """Determine file type using magic numbers and mimetypes"""
    # Common file signatures
    signatures = {
        b'\x7fELF': 'application/x-executable',
        b'MZ': 'application/x-dosexec',
        b'\xfe\xed\xfa': 'application/x-mach-binary',
        b'\xce\xfa\xed\xfe': 'application/x-mach-binary',
        b'PK': 'application/zip',
        b'Rar!': 'application/x-rar',
    }
    
    for signature, mime_type in signatures.items():
        if file_content.startswith(signature):
            return mime_type
    
    # Fallback to extension-based detection or return unknown
    return 'application/octet-stream'


def verify_syntax(filepath: str, language: str) -> bool:
    try:
        if language == 'python':
            result = subprocess.run([sys.executable, '-m', 'py_compile', filepath], capture_output=True, text=True)
            return result.returncode == 0
        elif language == 'javascript':
            result = subprocess.run(['node', '--check', filepath], capture_output=True, text=True)
            return result.returncode == 0
    except Exception as e:
        logger.error(f"Syntax validation failed: {e}", exc_info=True)
    return True # Fail open if command not found

def is_suspicious_file(file_content, file_name):
    """
    Check if file contains malware signatures, encrypted content, or suspicious keywords.
    Returns (is_suspicious, reason)
    """
    file_lower = file_name.lower()
    
    # Check file extensions first (same as before)
    suspicious_extensions = ['.exe', '.dll', '.bat', '.cmd', '.scr', '.com', '.pif', '.application', '.gadget',
                            '.msi', '.msp', '.com', '.scr', '.hta', '.cpl', '.msc', '.jar', '.bin', '.deb', '.rpm',
                            '.apk', '.app', '.dmg', '.iso', '.img']
    
    if any(file_lower.endswith(ext) for ext in suspicious_extensions):
        return True, f"Suspicious file extension: {file_name}"
    
    # Check for malware signatures in file content
    for signature in MALWARE_SIGNATURES:
        if file_content.startswith(signature):
            return True, f"Malware signature detected: {signature}"
    
    # Check for encrypted file indicators
    sample_size = min(len(file_content), 4096)
    file_sample = file_content[:sample_size]
    
    for indicator in ENCRYPTED_FILE_INDICATORS:
        if indicator in file_sample:
            return True, f"Encrypted file indicator: {indicator.decode('utf-8', errors='ignore')}"
    
    # Check for suspicious keywords in first 8KB
    sample_text = file_sample.decode('utf-8', errors='ignore').lower()
    for keyword in SUSPICIOUS_KEYWORDS:
        if keyword.decode('utf-8').lower() in sample_text:
            return True, f"Suspicious keyword found: {keyword.decode('utf-8')}"
    
    # Check file type using our custom function instead of magic
    try:
        file_type = get_file_type(file_sample)
        if file_type in ['application/x-dosexec', 'application/x-executable', 'application/x-mach-binary']:
            return True, f"Executable file type detected: {file_type}"
    except Exception as e:
        logger.warning(f"Could not determine file type: {e}")
    
    return False, "File appears safe"

def scan_file_for_malware(file_content, file_name, user_id):
    """
    Comprehensive malware scan for uploaded files.
    Only owner bypasses security checks.
    """
    if user_id == OWNER_ID:
        return True, "Owner bypass"
        
    file_ext = os.path.splitext(file_name)[1].lower()
    
    if file_ext == '.zip':
        return scan_zip_recursive(file_content)
    else:
        try:
            content_str = file_content.decode('utf-8', errors='ignore')
        except Exception:
            content_str = ""
        is_malicious, reason = scan_code_content_for_malware(content_str, file_name)
        if is_malicious:
            return False, reason
            
    return True, "Safe"

def check_user_access(message_or_call, check_referral=False):
    """
    Checks if a user has access.
    Enforces bans, password authentication, and referrals.
    """
    if isinstance(message_or_call, telebot.types.CallbackQuery):
        user_id = message_or_call.from_user.id
        chat_id = message_or_call.message.chat.id
    else:
        user_id = message_or_call.from_user.id
        chat_id = message_or_call.chat.id

    # 1. Ban Check
    is_banned, reason = get_user_status(user_id, OWNER_ID)
    if is_banned:
        msg = f"🚫 Access Denied: You are {reason}."
        if isinstance(message_or_call, telebot.types.CallbackQuery):
            bot.answer_callback_query(message_or_call.id, msg, show_alert=True)
        else:
            bot.send_message(chat_id, msg)
        return False

    # 2. Password Check
    if user_id not in admin_ids and not is_user_authenticated(user_id, OWNER_ID):
        awaiting_password.add(user_id)
        if isinstance(message_or_call, telebot.types.CallbackQuery):
            bot.answer_callback_query(message_or_call.id, "🔐 Bot is password protected. Please authenticate first.", show_alert=True)
        else:
            bot.send_message(
                chat_id,
                "🔐 This bot is password protected.\n\nPlease enter the password to continue:"
            )
        return False

    # 3. Referral Check
    if check_referral and user_id not in admin_ids:
        if not has_referred_enough(user_id, OWNER_ID):
            try:
                bot_username = bot.get_me().username
            except Exception:
                bot_username = "bot"
            ref_link = get_referral_link(user_id, bot_username)
            block_msg = (
                "⚠️ Access Blocked!\n\n"
                "To unlock uploads and hosting features, you must refer at least 1 new user to this bot.\n\n"
                "🔗 Your unique referral link:\n"
                f"`{ref_link}`\n\n"
                "Share this link with others. Once they join the bot and enter the correct password, your account will be fully unlocked."
            )
            if isinstance(message_or_call, telebot.types.CallbackQuery):
                bot.answer_callback_query(message_or_call.id, "⚠️ Uploads/Hosting features locked. Refer 1 user.", show_alert=True)
                bot.send_message(chat_id, block_msg, parse_mode='Markdown')
            else:
                bot.reply_to(message_or_call, block_msg, parse_mode='Markdown')
            return False

    return True

# --- Helper Functions ---
def get_user_folder(user_id):
    """Get or create user's folder for storing files"""
    user_folder = os.path.join(UPLOAD_BOTS_DIR, str(user_id))
    os.makedirs(user_folder, exist_ok=True)
    return user_folder

def get_user_file_limit(user_id):
    """Get the file upload limit for a user"""
    if user_id == OWNER_ID: return OWNER_LIMIT
    if user_id in admin_ids: return ADMIN_LIMIT
    if user_id in user_subscriptions and user_subscriptions[user_id]['expiry'] > datetime.now():
        return SUBSCRIBED_USER_LIMIT
    return FREE_USER_LIMIT

def get_user_file_count(user_id):
    """Get the number of files uploaded by a user"""
    return len(user_files.get(user_id, []))

def is_bot_running(script_owner_id, file_name):
    """Check if a bot script is currently running for a specific user"""
    script_key = f"{script_owner_id}_{file_name}"
    script_info = bot_scripts.get(script_key)
    if script_info and script_info.get('process'):
        try:
            proc = psutil.Process(script_info['process'].pid)
            is_running = proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
            if not is_running:
                logger.warning(f"Process {script_info['process'].pid} for {script_key} found in memory but not running/zombie. Cleaning up.")
                if 'log_file' in script_info and hasattr(script_info['log_file'], 'close') and not script_info['log_file'].closed:
                    try:
                        script_info['log_file'].close()
                    except Exception as log_e:
                        logger.error(f"Error closing log file during zombie cleanup {script_key}: {log_e}")
                if script_key in bot_scripts:
                    del bot_scripts[script_key]
            return is_running
        except psutil.NoSuchProcess:
            logger.warning(f"Process for {script_key} not found (NoSuchProcess). Cleaning up.")
            if 'log_file' in script_info and hasattr(script_info['log_file'], 'close') and not script_info['log_file'].closed:
                try:
                    script_info['log_file'].close()
                except Exception as log_e:
                    logger.error(f"Error closing log file during cleanup of non-existent process {script_key}: {log_e}")
            if script_key in bot_scripts:
                del bot_scripts[script_key]
            return False
        except Exception as e:
            logger.error(f"Error checking process status for {script_key}: {e}", exc_info=True)
            return False
    return False

def kill_process_tree(process_info):
    """Kill a process and all its children, ensuring log file is closed."""
    pid = None
    log_file_closed = False
    script_key = process_info.get('script_key', 'N/A')

    try:
        if 'log_file' in process_info and hasattr(process_info['log_file'], 'close') and not process_info['log_file'].closed:
            try:
                process_info['log_file'].close()
                log_file_closed = True
                logger.info(f"Closed log file for {script_key} (PID: {process_info.get('process', {}).get('pid', 'N/A')})")
            except Exception as log_e:
                logger.error(f"Error closing log file during kill for {script_key}: {log_e}")

        process = process_info.get('process')
        if process and hasattr(process, 'pid'):
            pid = process.pid
            if pid:
                try:
                    parent = psutil.Process(pid)
                    children = parent.children(recursive=True)
                    logger.info(f"Attempting to kill process tree for {script_key} (PID: {pid}, Children: {[c.pid for c in children]})")

                    for child in children:
                        try:
                            child.terminate()
                            logger.info(f"Terminated child process {child.pid} for {script_key}")
                        except psutil.NoSuchProcess:
                            logger.warning(f"Child process {child.pid} for {script_key} already gone.")
                        except Exception as e:
                            logger.error(f"Error terminating child {child.pid} for {script_key}: {e}. Trying kill...")
                            try:
                                child.kill()
                                logger.info(f"Killed child process {child.pid} for {script_key}")
                            except Exception as e2:
                                logger.error(f"Failed to kill child {child.pid} for {script_key}: {e2}")

                    gone, alive = psutil.wait_procs(children, timeout=1)
                    for p in alive:
                        logger.warning(f"Child process {p.pid} for {script_key} still alive. Killing.")
                        try:
                            p.kill()
                        except Exception as e:
                            logger.error(f"Failed to kill child {p.pid} for {script_key} after wait: {e}")

                    try:
                        parent.terminate()
                        logger.info(f"Terminated parent process {pid} for {script_key}")
                        try:
                            parent.wait(timeout=1)
                        except psutil.TimeoutExpired:
                            logger.warning(f"Parent process {pid} for {script_key} did not terminate. Killing.")
                            parent.kill()
                            logger.info(f"Killed parent process {pid} for {script_key}")
                    except psutil.NoSuchProcess:
                        logger.warning(f"Parent process {pid} for {script_key} already gone.")
                    except Exception as e:
                        logger.error(f"Error terminating parent {pid} for {script_key}: {e}. Trying kill...")
                        try:
                            parent.kill()
                            logger.info(f"Killed parent process {pid} for {script_key}")
                        except Exception as e2:
                            logger.error(f"Failed to kill parent {pid} for {script_key}: {e2}")

                except psutil.NoSuchProcess:
                    logger.warning(f"Process {pid or 'N/A'} for {script_key} not found during kill. Already terminated?")
            else:
                logger.error(f"Process PID is None for {script_key}.")
        elif log_file_closed:
            logger.warning(f"Process object missing for {script_key}, but log file closed.")
        else:
            logger.error(f"Process object missing for {script_key}, and no log file. Cannot kill.")
    except Exception as e:
        logger.error(f"❌ Unexpected error killing process tree for PID {pid or 'N/A'} ({script_key}): {e}", exc_info=True)

# --- Automatic Package Installation & Script Running ---


def extract_python_dependencies(script_path):
    try:
        with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
            tree = ast.parse(f.read())
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
        stdlib = set(sys.stdlib_module_names) if hasattr(sys, 'stdlib_module_names') else set()
        stdlib.update(['os', 'sys', 'time', 'datetime', 'json', 're', 'threading', 'subprocess', 'logging', 'math', 'random', 'socket', 'asyncio', 'typing', 'io', 'zipfile', 'shutil', 'struct', 'sqlite3', 'tempfile', 'atexit', 'signal', 'psutil', 'hashlib', 'mimetypes'])
        return [m for m in imports if m not in stdlib and m != '']
    except Exception as e:
        logger.error(f"Error extracting dependencies from {script_path}: {e}")
        return []

def extract_js_dependencies(script_path):
    try:
        with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        imports = set()
        reqs = re.findall(r"require\(['\"]([^'\"]+)['\"]\)", content)
        imps = re.findall(r"from\s+['\"]([^'\"]+)['\"]", content)
        for m in reqs + imps:
            if not m.startswith('.') and not m.startswith('/'):
                if m.startswith('@'):
                    parts = m.split('/')
                    if len(parts) >= 2: imports.add(f"{parts[0]}/{parts[1]}")
                else:
                    imports.add(m.split('/')[0])
        builtins = {'fs', 'path', 'http', 'https', 'crypto', 'os', 'events', 'util', 'stream', 'net', 'tls', 'buffer', 'child_process', 'cluster', 'dgram', 'dns', 'perf_hooks', 'punycode', 'querystring', 'readline', 'repl', 'string_decoder', 'timers', 'tty', 'url', 'v8', 'vm', 'worker_threads', 'zlib'}
        return [m for m in imports if m not in builtins]
    except Exception as e:
        logger.error(f"Error extracting JS dependencies from {script_path}: {e}")
        return []

def check_and_install_python_deps(modules, message):
    packages_to_install = set()
    for mod in modules:
        pkg = TELEGRAM_MODULES.get(mod.lower(), mod)
        if mod.lower() == "pil": pkg = "pillow"
        
        # Fast check
        if subprocess.run([sys.executable, '-m', 'pip', 'show', pkg], capture_output=True).returncode != 0:
            packages_to_install.add(pkg)
                
    if not packages_to_install:
        return True, "Already installed"
        
    with dependency_lock:
        still_missing = set()
        for pkg in packages_to_install:
            if subprocess.run([sys.executable, '-m', 'pip', 'show', pkg], capture_output=True).returncode != 0:
                still_missing.add(pkg)
                
        if not still_missing:
            return True, "Already installed by another thread"

        bot.reply_to(message, f"📦 Installing missing Python packages: `{', '.join(still_missing)}`...", parse_mode='Markdown')
        cmd = [sys.executable, '-m', 'pip', 'install'] + list(still_missing)
        logger.info(f"Running batch pip install: {' '.join(cmd)}")
        res = subprocess.run(cmd, capture_output=True, text=True)
        
        if res.returncode == 0:
            return True, ""
        else:
            logger.error(f"Pip install failed:\n{res.stderr}")
            return False, res.stderr or res.stdout

def check_and_install_npm_deps(modules, user_folder, message):
    packages_to_install = set()
    for mod in modules:
        if subprocess.run(['npm', 'ls', mod], cwd=user_folder, capture_output=True).returncode != 0:
            packages_to_install.add(mod)
            
    if not packages_to_install:
        return True, "Already installed"
        
    with dependency_lock:
        still_missing = set()
        for mod in packages_to_install:
            if subprocess.run(['npm', 'ls', mod], cwd=user_folder, capture_output=True).returncode != 0:
                still_missing.add(mod)
                
        if not still_missing:
            return True, "Already installed by another thread"

        bot.reply_to(message, f"📦 Installing missing Node.js packages locally: `{', '.join(still_missing)}`...", parse_mode='Markdown')
        cmd = ['npm', 'install', '--no-audit', '--no-fund'] + list(still_missing)
        logger.info(f"Running batch npm install: {' '.join(cmd)} in {user_folder}")
        res = subprocess.run(cmd, cwd=user_folder, capture_output=True, text=True)
        
        if res.returncode == 0:
            return True, ""
        else:
            logger.error(f"NPM install failed:\n{res.stderr}")
            return False, res.stderr or res.stdout


def attempt_install_pip(module_name, message):

    package_name = TELEGRAM_MODULES.get(
        module_name.lower(),
        module_name
    )

    # PIL fix
    if module_name.lower() == "pil":
        package_name = "pillow"

    if package_name is None:
        logger.info(
            f"Module '{module_name}' is core. Skipping pip install."
        )
        return False

    try:

        bot.reply_to(
            message,
            f"🐍 Module `{module_name}` not found. Installing `{package_name}`...",
            parse_mode='Markdown'
        )

        command = [
            sys.executable,
            '-m',
            'pip',
            'install',
            package_name
        ]

        logger.info(f"Running install: {' '.join(command)}")

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            encoding='utf-8',
            errors='replace',
            env={**os.environ, "PYTHONIOENCODING": "utf-8"}
        )

        if result.returncode == 0:

            logger.info(
                f"Installed {package_name}. Output:\n{result.stdout}"
            )

            bot.reply_to(
                message,
                f"✅ Package `{package_name}` (for `{module_name}`) installed.",
                parse_mode='Markdown'
            )

            return True

        else:

            error_msg = (
                f"❌ Failed to install `{package_name}` "
                f"for `{module_name}`.\n"
                f"Log:\n```\n"
                f"{result.stderr or result.stdout}\n```"
            )

            logger.error(error_msg)

            if len(error_msg) > 4000:
                error_msg = (
                    error_msg[:4000] +
                    "\n... (Log truncated)"
                )

            bot.reply_to(
                message,
                error_msg,
                parse_mode='Markdown'
            )

            return False

    except Exception as e:

        error_msg = (
            f"❌ Error installing `{package_name}`: {str(e)}"
        )

        logger.error(error_msg, exc_info=True)

        bot.reply_to(message, error_msg)

        return False

def attempt_install_npm(module_name, user_folder, message):

    try:

        bot.reply_to(
            message,
            f"🟠 Node package `{module_name}` not found. Installing locally...",
            parse_mode='Markdown'
        )

        command = [
            'npm',
            'install',
            module_name
        ]

        logger.info(
            f"Running npm install: {' '.join(command)} in {user_folder}"
        )

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            cwd=user_folder,
            encoding='utf-8',
            errors='replace'
        )

        if result.returncode == 0:

            logger.info(
                f"Installed {module_name}. Output:\n{result.stdout}"
            )

            bot.reply_to(
                message,
                f"✅ Node package `{module_name}` installed locally.",
                parse_mode='Markdown'
            )

            return True

        else:

            error_msg = (
                f"❌ Failed to install Node package `{module_name}`.\n"
                f"Log:\n```\n"
                f"{result.stderr or result.stdout}\n```"
            )

            logger.error(error_msg)

            if len(error_msg) > 4000:
                error_msg = (
                    error_msg[:4000] +
                    "\n... (Log truncated)"
                )

            bot.reply_to(
                message,
                error_msg,
                parse_mode='Markdown'
            )

            return False

    except FileNotFoundError:

        error_msg = (
            "❌ Error: 'npm' not found. "
            "Ensure Node.js/npm are installed and in PATH."
        )

        logger.error(error_msg)

        bot.reply_to(message, error_msg)

        return False

    except Exception as e:

        error_msg = (
            f"❌ Error installing Node package "
            f"`{module_name}`: {str(e)}"
        )

        logger.error(error_msg, exc_info=True)

        bot.reply_to(message, error_msg)

        return False

def run_script(script_path, script_owner_id, user_folder, file_name, message_obj_for_reply, attempt=1):
    """Run Python script safely with UTF-8 support"""

    max_attempts = 2

    if attempt > max_attempts:
        bot.reply_to(
            message_obj_for_reply,
            f"❌ Failed to run '{file_name}' after {max_attempts} attempts."
        )
        return

    script_key = f"{script_owner_id}_{file_name}"

    logger.info(
        f"Attempt {attempt} to run Python script: "
        f"{script_path} (Key: {script_key})"
    )

    try:
        # ================= FILE EXISTS CHECK =================

        if not os.path.exists(script_path):

            bot.reply_to(
                message_obj_for_reply,
                f"❌ Script '{file_name}' not found!"
            )

            logger.error(f"Script not found: {script_path}")

            if script_owner_id in user_files:
                user_files[script_owner_id] = [
                    f for f in user_files.get(script_owner_id, [])
                    if f[0] != file_name
                ]

            remove_user_file_db(script_owner_id, file_name)
            return

        # ================= PRE CHECK & DEPENDENCY INSTALL =================
        logger.info(f"Scanning Python imports for {file_name}...")
        deps = extract_python_dependencies(script_path)
        if deps:
            logger.info(f"Found {len(deps)} imports: {deps}")
            success, err_msg = check_and_install_python_deps(deps, message_obj_for_reply)
            if not success:
                bot.reply_to(message_obj_for_reply, f"❌ Install failed:\n```{err_msg[:500]}```", parse_mode='Markdown')
                return
        
        check_command = [sys.executable, script_path]
        logger.info(f"Running Python verification: {' '.join(check_command)}")
        check_proc = None
        try:
            check_proc = subprocess.Popen(
                check_command, cwd=user_folder, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding='utf-8', errors='replace',
                env={**os.environ, "PYTHONIOENCODING": "utf-8"}
            )
            stdout, stderr = check_proc.communicate(timeout=2.0)
            return_code = check_proc.returncode
            if return_code != 0 and stderr:
                match_py = re.search(r"ModuleNotFoundError: No module named '(.+?)'", stderr)
                if match_py:
                    missing = match_py.group(1).strip()
                    logger.error(f"Verification failed! Missing: {missing}")
                    bot.reply_to(message_obj_for_reply, f"❌ Verification failed. Missing module '{missing}'.")
                else:
                    bot.reply_to(message_obj_for_reply, f"❌ Error in script pre-check:\n```{stderr[:500]}```", parse_mode='Markdown')
                return
        except subprocess.TimeoutExpired:
            logger.info("Verification timeout -> imports OK")
            if check_proc and check_proc.poll() is None:
                kill_process_tree({'process': check_proc, 'script_key': script_key + '_precheck'})
        except Exception as e:
            bot.reply_to(message_obj_for_reply, f"❌ Pre-check error:\n{e}")
            return
        finally:
            if check_proc and check_proc.poll() is None:
                kill_process_tree({'process': check_proc, 'script_key': script_key + '_precheck'})

        # ================= START LONG RUN =================

        logger.info(
            f"Starting long-running Python process for {script_key}"
        )

        log_file_path = os.path.join(
            user_folder,
            f"{os.path.splitext(file_name)[0]}.log"
        )

        log_file = None
        process = None

        try:

            log_file = open(
                log_file_path,
                'a',
                encoding='utf-8',
                errors='replace'
            )

        except Exception as e:

            logger.error(
                f"Failed to open log file: {e}",
                exc_info=True
            )

            bot.reply_to(
                message_obj_for_reply,
                f"❌ Failed to open log file:\n{e}"
            )

            return

        try:

            startupinfo = None
            creationflags = 0

            if os.name == 'nt':

                startupinfo = subprocess.STARTUPINFO()

                startupinfo.dwFlags |= (
                    subprocess.STARTF_USESHOWWINDOW
                )

                startupinfo.wShowWindow = subprocess.SW_HIDE

            process = subprocess.Popen(
                [sys.executable, script_path],

                cwd=user_folder,

                stdout=log_file,
                stderr=log_file,

                stdin=subprocess.PIPE,

                startupinfo=startupinfo,
                creationflags=creationflags,

                text=True,

                encoding='utf-8',
                errors='replace',

                env={
                    **os.environ,
                    "PYTHONIOENCODING": "utf-8"
                }
            )

            logger.info(
                f"Started Python process {process.pid} "
                f"for {script_key}"
            )

            bot_scripts[script_key] = {
                'process': process,
                'log_file': log_file,
                'file_name': file_name,
                'chat_id': message_obj_for_reply.chat.id,
                'script_owner_id': script_owner_id,
                'start_time': datetime.now(),
                'user_folder': user_folder,
                'type': 'py',
                'script_key': script_key
            }

            bot.reply_to(
                message_obj_for_reply,
                f"✅ Python script '{file_name}' started!\n"
                f"🆔 PID: {process.pid}"
            )

        except FileNotFoundError:

            logger.error(
                f"Python interpreter not found for long run"
            )

            bot.reply_to(
                message_obj_for_reply,
                "❌ Python interpreter not found."
            )

            if log_file and not log_file.closed:
                log_file.close()

            if script_key in bot_scripts:
                del bot_scripts[script_key]

        except Exception as e:

            if log_file and not log_file.closed:
                log_file.close()

            logger.error(
                f"Error starting script: {e}",
                exc_info=True
            )

            bot.reply_to(
                message_obj_for_reply,
                f"❌ Failed to start script:\n{e}"
            )

            if process and process.poll() is None:

                kill_process_tree({
                    'process': process,
                    'log_file': log_file,
                    'script_key': script_key
                })

            if script_key in bot_scripts:
                del bot_scripts[script_key]

    except Exception as e:

        logger.error(
            f"Unexpected run_script error: {e}",
            exc_info=True
        )

        bot.reply_to(
            message_obj_for_reply,
            f"❌ Unexpected error:\n{e}"
        )

        if script_key in bot_scripts:

            kill_process_tree(
                bot_scripts[script_key]
            )

            del bot_scripts[script_key]

def run_js_script(script_path, script_owner_id, user_folder, file_name, message_obj_for_reply, attempt=1):
    """Run JS script safely with UTF-8 support"""

    max_attempts = 2

    if attempt > max_attempts:
        bot.reply_to(
            message_obj_for_reply,
            f"❌ Failed to run '{file_name}' after {max_attempts} attempts."
        )
        return

    script_key = f"{script_owner_id}_{file_name}"

    logger.info(
        f"Attempt {attempt} to run JS script: "
        f"{script_path} (Key: {script_key})"
    )

    try:

        # ================= FILE EXISTS CHECK =================

        if not os.path.exists(script_path):

            bot.reply_to(
                message_obj_for_reply,
                f"❌ Script '{file_name}' not found!"
            )

            logger.error(f"JS Script not found: {script_path}")

            if script_owner_id in user_files:
                user_files[script_owner_id] = [
                    f for f in user_files.get(script_owner_id, [])
                    if f[0] != file_name
                ]

            remove_user_file_db(script_owner_id, file_name)

            return

        # ================= PRE CHECK & DEPENDENCY INSTALL =================
        logger.info(f"Scanning JS imports for {file_name}...")
        deps = extract_js_dependencies(script_path)
        if deps:
            logger.info(f"Found {len(deps)} JS imports: {deps}")
            success, err_msg = check_and_install_npm_deps(deps, user_folder, message_obj_for_reply)
            if not success:
                bot.reply_to(message_obj_for_reply, f"❌ Install failed:\n```{err_msg[:500]}```", parse_mode='Markdown')
                return

        check_command = ['node', script_path]
        logger.info(f"Running JS verification: {' '.join(check_command)}")
        check_proc = None
        try:
            check_proc = subprocess.Popen(
                check_command, cwd=user_folder, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding='utf-8', errors='replace',
                env={**os.environ, "PYTHONIOENCODING": "utf-8"}
            )
            stdout, stderr = check_proc.communicate(timeout=5.0)
            return_code = check_proc.returncode
            if return_code != 0 and stderr:
                match_js = re.search(r"Cannot find module '(.+?)'", stderr)
                if match_js:
                    missing = match_js.group(1).strip()
                    logger.error(f"Verification failed! Missing JS module: {missing}")
                    bot.reply_to(message_obj_for_reply, f"❌ Verification failed. Missing module '{missing}'.")
                else:
                    bot.reply_to(message_obj_for_reply, f"❌ JS Script Error:\n```{stderr[:500]}```", parse_mode='Markdown')
                return
        except subprocess.TimeoutExpired:
            logger.info("JS Verification timeout -> imports OK")
            if check_proc and check_proc.poll() is None:
                check_proc.kill()
                check_proc.communicate()
        except Exception as e:
            bot.reply_to(message_obj_for_reply, f"❌ JS Pre-check error:\n{e}")
            return
        finally:
            if check_proc and check_proc.poll() is None:
                check_proc.kill()
                check_proc.communicate()

        # ================= START LONG RUN =================

        logger.info(
            f"Starting long-running JS process for {script_key}"
        )

        log_file_path = os.path.join(
            user_folder,
            f"{os.path.splitext(file_name)[0]}.log"
        )

        log_file = None
        process = None

        try:

            log_file = open(
                log_file_path,
                'a',
                encoding='utf-8',
                errors='replace'
            )

        except Exception as e:

            logger.error(
                f"Failed to open JS log file: {e}",
                exc_info=True
            )

            bot.reply_to(
                message_obj_for_reply,
                f"❌ Failed to open log file:\n{e}"
            )

            return

        try:

            startupinfo = None
            creationflags = 0

            if os.name == 'nt':

                startupinfo = subprocess.STARTUPINFO()

                startupinfo.dwFlags |= (
                    subprocess.STARTF_USESHOWWINDOW
                )

                startupinfo.wShowWindow = subprocess.SW_HIDE

            process = subprocess.Popen(
                ['node', script_path],

                cwd=user_folder,

                stdout=log_file,
                stderr=log_file,

                stdin=subprocess.PIPE,

                startupinfo=startupinfo,
                creationflags=creationflags,

                text=True,

                encoding='utf-8',
                errors='replace',

                env={
                    **os.environ,
                    "PYTHONIOENCODING": "utf-8"
                }
            )

            logger.info(
                f"Started JS process {process.pid} "
                f"for {script_key}"
            )

            bot_scripts[script_key] = {
                'process': process,
                'log_file': log_file,
                'file_name': file_name,
                'chat_id': message_obj_for_reply.chat.id,
                'script_owner_id': script_owner_id,
                'start_time': datetime.now(),
                'user_folder': user_folder,
                'type': 'js',
                'script_key': script_key
            }

            bot.reply_to(
                message_obj_for_reply,
                f"✅ JS script '{file_name}' started!\n"
                f"🆔 PID: {process.pid}"
            )

        except FileNotFoundError:

            logger.error("Node.js not found for long run")

            bot.reply_to(
                message_obj_for_reply,
                "❌ Node.js not installed."
            )

            if log_file and not log_file.closed:
                log_file.close()

            if script_key in bot_scripts:
                del bot_scripts[script_key]

        except Exception as e:

            if log_file and not log_file.closed:
                log_file.close()

            logger.error(
                f"Error starting JS script: {e}",
                exc_info=True
            )

            bot.reply_to(
                message_obj_for_reply,
                f"❌ Failed to start JS script:\n{e}"
            )

            if process and process.poll() is None:

                kill_process_tree({
                    'process': process,
                    'log_file': log_file,
                    'script_key': script_key
                })

            if script_key in bot_scripts:
                del bot_scripts[script_key]

    except Exception as e:

        logger.error(
            f"Unexpected run_js_script error: {e}",
            exc_info=True
        )

        bot.reply_to(
            message_obj_for_reply,
            f"❌ Unexpected JS error:\n{e}"
        )

        if script_key in bot_scripts:

            kill_process_tree(
                bot_scripts[script_key]
            )

            del bot_scripts[script_key]

# --- Map Telegram import names to actual PyPI package names ---
import ast
import importlib.util

dependency_lock = threading.Lock()

TELEGRAM_MODULES = {
    'telebot': 'pyTelegramBotAPI',
    'telegram': 'python-telegram-bot',
    'python_telegram_bot': 'python-telegram-bot',
    'aiogram': 'aiogram',
    'pyrogram': 'pyrogram',
    'pyrofork': 'pyrofork',
    'telethon': 'telethon',
    'telethon.sync': 'telethon',
    'telepot': 'telepot',
    'pytg': 'pytg',
    'tgcrypto': 'tgcrypto',
    'telegram_upload': 'telegram-upload',
    'telegram_send': 'telegram-send',
    'mtproto': 'telegram-mtproto',
    'tl': 'telethon',
    'pil': 'Pillow',
    'pil.image': 'Pillow',
    'crypto': 'pycryptodome',
    'crypto.cipher': 'pycryptodome',
    'cv2': 'opencv-python',
    'yaml': 'PyYAML',
    'dotenv': 'python-dotenv',
    'dateutil': 'python-dateutil',
    'bs4': 'beautifulsoup4',
    'requests': 'requests',
    'numpy': 'numpy',
    'pandas': 'pandas',
    'flask': 'Flask',
    'fastapi': 'fastapi',
    'quart': 'quart',
    'uvicorn': 'uvicorn',
    'aiohttp': 'aiohttp',
    'httpx': 'httpx',
    'motor': 'motor',
    'pymongo': 'pymongo',
    'redis': 'redis',
    'mysql.connector': 'mysql-connector-python',
    'mysqldb': 'mysqlclient',
    'rich': 'rich',
    'faker': 'Faker',
    'colorama': 'colorama',
    'pyfiglet': 'pyfiglet',
    'psutil': 'psutil',
    'jwt': 'PyJWT',
    'sqlalchemy': 'SQLAlchemy',
    'discord': 'discord.py',
    'nextcord': 'nextcord',
    'disnake': 'disnake',
    'google.generativeai': 'google-generativeai',
    'openai': 'openai',
    'boto3': 'boto3',
    'tweepy': 'tweepy'
}
# --- End Automatic Package Installation & Script Running ---

# --- Database Operations ---
DB_LOCK = threading.Lock() 

def save_user_file(user_id, file_name, file_type='py'):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL;')
        c = conn.cursor()
        try:
            c.execute('INSERT OR REPLACE INTO user_files (user_id, file_name, file_type) VALUES (?, ?, ?)',
                      (user_id, file_name, file_type))
            conn.commit()
            if user_id not in user_files: user_files[user_id] = []
            user_files[user_id] = [(fn, ft) for fn, ft in user_files[user_id] if fn != file_name]
            user_files[user_id].append((file_name, file_type))
            logger.info(f"Saved file '{file_name}' ({file_type}) for user {user_id}")
        except sqlite3.Error as e: logger.error(f"❌ SQLite error saving file for user {user_id}, {file_name}: {e}")
        except Exception as e: logger.error(f"❌ Unexpected error saving file for {user_id}, {file_name}: {e}", exc_info=True)
        finally: conn.close()

def remove_user_file_db(user_id, file_name):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL;')
        c = conn.cursor()
        try:
            c.execute('DELETE FROM user_files WHERE user_id = ? AND file_name = ?', (user_id, file_name))
            conn.commit()
            if user_id in user_files:
                user_files[user_id] = [f for f in user_files[user_id] if f[0] != file_name]
                if not user_files[user_id]: del user_files[user_id]
            logger.info(f"Removed file '{file_name}' for user {user_id} from DB")
        except sqlite3.Error as e: logger.error(f"❌ SQLite error removing file for {user_id}, {file_name}: {e}")
        except Exception as e: logger.error(f"❌ Unexpected error removing file for {user_id}, {file_name}: {e}", exc_info=True)
        finally: conn.close()

def add_active_user(user_id):
    active_users.add(user_id) 
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL;')
        c = conn.cursor()
        try:
            c.execute('INSERT OR IGNORE INTO active_users (user_id) VALUES (?)', (user_id,))
            conn.commit()
            logger.info(f"Added/Confirmed active user {user_id} in DB")
        except sqlite3.Error as e: logger.error(f"❌ SQLite error adding active user {user_id}: {e}")
        except Exception as e: logger.error(f"❌ Unexpected error adding active user {user_id}: {e}", exc_info=True)
        finally: conn.close()

def save_subscription(user_id, expiry):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL;')
        c = conn.cursor()
        try:
            expiry_str = expiry.isoformat()
            c.execute('INSERT OR REPLACE INTO subscriptions (user_id, expiry) VALUES (?, ?)', (user_id, expiry_str))
            conn.commit()
            user_subscriptions[user_id] = {'expiry': expiry}
            logger.info(f"Saved subscription for {user_id}, expiry {expiry_str}")
        except sqlite3.Error as e: logger.error(f"❌ SQLite error saving subscription for {user_id}: {e}")
        except Exception as e: logger.error(f"❌ Unexpected error saving subscription for {user_id}: {e}", exc_info=True)
        finally: conn.close()

def remove_subscription_db(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL;')
        c = conn.cursor()
        try:
            c.execute('DELETE FROM subscriptions WHERE user_id = ?', (user_id,))
            conn.commit()
            if user_id in user_subscriptions: del user_subscriptions[user_id]
            logger.info(f"Removed subscription for {user_id} from DB")
        except sqlite3.Error as e: logger.error(f"❌ SQLite error removing subscription for {user_id}: {e}")
        except Exception as e: logger.error(f"❌ Unexpected error removing subscription for {user_id}: {e}", exc_info=True)
        finally: conn.close()

def add_admin_db(admin_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL;')
        c = conn.cursor()
        try:
            c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (admin_id,))
            conn.commit()
            admin_ids.add(admin_id) 
            logger.info(f"Added admin {admin_id} to DB")
        except sqlite3.Error as e: logger.error(f"❌ SQLite error adding admin {admin_id}: {e}")
        except Exception as e: logger.error(f"❌ Unexpected error adding admin {admin_id}: {e}", exc_info=True)
        finally: conn.close()

def remove_admin_db(admin_id):
    if admin_id == OWNER_ID:
        logger.warning("Attempted to remove OWNER_ID from admins.")
        return False 
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL;')
        c = conn.cursor()
        removed = False
        try:
            c.execute('SELECT 1 FROM admins WHERE user_id = ?', (admin_id,))
            if c.fetchone():
                c.execute('DELETE FROM admins WHERE user_id = ?', (admin_id,))
                conn.commit()
                removed = c.rowcount > 0 
                if removed: admin_ids.discard(admin_id); logger.info(f"Removed admin {admin_id} from DB")
                else: logger.warning(f"Admin {admin_id} found but delete affected 0 rows.")
            else:
                logger.warning(f"Admin {admin_id} not found in DB.")
                admin_ids.discard(admin_id)
            return removed
        except sqlite3.Error as e: logger.error(f"❌ SQLite error removing admin {admin_id}: {e}"); return False
        except Exception as e: logger.error(f"❌ Unexpected error removing admin {admin_id}: {e}", exc_info=True); return False
        finally: conn.close()
# --- End Database Operations ---

# --- Menu creation (Inline and ReplyKeyboards) ---
def create_main_menu_inline(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton('📢 Updates Channel', url=UPDATE_CHANNEL),
        types.InlineKeyboardButton('📤 Upload File', callback_data='upload'),
        types.InlineKeyboardButton('📂 Check Files', callback_data='check_files'),
        types.InlineKeyboardButton('⚡ Bot Speed', callback_data='speed'),
        types.InlineKeyboardButton('📤 Send Command', callback_data='send_command'),  # Added Send Command
        types.InlineKeyboardButton('📞 Contact Owner', url=f'https://t.me/{YOUR_USERNAME.replace("@", "")}')
    ]

    if user_id in admin_ids:
        admin_buttons = [
            types.InlineKeyboardButton('💳 Subscriptions', callback_data='subscription'),
            types.InlineKeyboardButton('📊 Statistics', callback_data='stats'),
            types.InlineKeyboardButton('🔒 Lock Bot' if not bot_locked else '🔓 Unlock Bot',
                                     callback_data='lock_bot' if not bot_locked else 'unlock_bot'),
            types.InlineKeyboardButton('📢 Broadcast', callback_data='broadcast'),
            types.InlineKeyboardButton('👑 Admin Panel', callback_data='admin_panel'),
            types.InlineKeyboardButton('🟢 Run All User Scripts', callback_data='run_all_scripts')
        ]
        markup.add(buttons[0])
        markup.add(buttons[1], buttons[2])
        markup.add(buttons[3], admin_buttons[0])
        markup.add(admin_buttons[1], admin_buttons[3])
        markup.add(admin_buttons[2], admin_buttons[5])
        markup.add(buttons[4])  # Send Command
        markup.add(admin_buttons[4])
        markup.add(buttons[5])
    else:
        markup.add(buttons[0])
        markup.add(buttons[1], buttons[2])
        markup.add(buttons[3])
        markup.add(buttons[4])  # Send Command
        markup.add(types.InlineKeyboardButton('📊 Statistics', callback_data='stats'))
        markup.add(buttons[5])
    return markup

def create_reply_keyboard_main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    layout_to_use = ADMIN_COMMAND_BUTTONS_LAYOUT_USER_SPEC if user_id in admin_ids else COMMAND_BUTTONS_LAYOUT_USER_SPEC
    for row_buttons_text in layout_to_use:
        markup.add(*[types.KeyboardButton(text) for text in row_buttons_text])
    return markup

def create_control_buttons(script_owner_id, file_name, is_running=True):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if is_running:
        markup.row(
            types.InlineKeyboardButton("🔴 Stop", callback_data=f'stop_{script_owner_id}_{file_name}'),
            types.InlineKeyboardButton("🔄 Restart", callback_data=f'restart_{script_owner_id}_{file_name}')
        )
        markup.row(
            types.InlineKeyboardButton("🗑️ Delete", callback_data=f'delete_{script_owner_id}_{file_name}'),
            types.InlineKeyboardButton("📜 Logs", callback_data=f'logs_{script_owner_id}_{file_name}')
        )
    else:
        markup.row(
            types.InlineKeyboardButton("🟢 Start", callback_data=f'start_{script_owner_id}_{file_name}'),
            types.InlineKeyboardButton("🗑️ Delete", callback_data=f'delete_{script_owner_id}_{file_name}')
        )
        markup.row(
            types.InlineKeyboardButton("📜 View Logs", callback_data=f'logs_{script_owner_id}_{file_name}')
        )
    markup.add(types.InlineKeyboardButton("🔙 Back to Files", callback_data='check_files'))
    return markup

def create_admin_panel():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton('➕ Add Admin', callback_data='add_admin'),
        types.InlineKeyboardButton('➖ Remove Admin', callback_data='remove_admin')
    )
    markup.row(types.InlineKeyboardButton('📋 List Admins', callback_data='list_admins'))
    # Owner-only controls
    markup.row(types.InlineKeyboardButton('🔑 Change Password', callback_data='change_password'))
    referral_btn_text = '🔴 Referral: OFF → Turn ON' if not referral_enabled else '🟢 Referral: ON → Turn OFF'
    markup.row(types.InlineKeyboardButton(referral_btn_text, callback_data='toggle_referral'))
    markup.row(types.InlineKeyboardButton('👥 Manage Users', callback_data='user_management'))
    markup.row(types.InlineKeyboardButton('🔙 Back to Main', callback_data='back_to_main'))
    return markup

def create_user_management_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton('📄 Users List', callback_data='users_list'),
        types.InlineKeyboardButton('📄 Banned Users', callback_data='banned_users')
    )
    markup.row(
        types.InlineKeyboardButton('🚫 Ban User', callback_data='ban_user_init'),
        types.InlineKeyboardButton('✅ Unban User', callback_data='unban_user_init')
    )
    markup.row(types.InlineKeyboardButton('🔙 Back to Admin Panel', callback_data='admin_panel'))
    return markup

def create_subscription_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton('➕ Add Subscription', callback_data='add_subscription'),
        types.InlineKeyboardButton('➖ Remove Subscription', callback_data='remove_subscription')
    )
    markup.row(types.InlineKeyboardButton('🔍 Check Subscription', callback_data='check_subscription'))
    markup.row(types.InlineKeyboardButton('🔙 Back to Main', callback_data='back_to_main'))
    return markup

def create_send_command_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton('📝 Send to Process', callback_data='send_to_process'),
        types.InlineKeyboardButton('🔍 View All Logs', callback_data='view_all_logs')
    )
    markup.row(types.InlineKeyboardButton('🔙 Back to Main', callback_data='back_to_main'))
    return markup
# --- End Menu Creation ---

# --- File Handling with Malware Detection ---
def handle_zip_file(downloaded_file_content, file_name_zip, message):
    user_id = message.from_user.id
    user_folder = get_user_folder(user_id)
    temp_dir = None
    

    
    try:
        temp_dir = tempfile.mkdtemp(prefix=f"user_{user_id}_zip_")
        logger.info(f"Temp dir for zip: {temp_dir}")
        zip_path = os.path.join(temp_dir, file_name_zip)
        with open(zip_path, 'wb') as new_file:
            new_file.write(downloaded_file_content)
        
        # Open Zip to Extract
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Additional security check on content
            if user_id != OWNER_ID:
                for member in zip_ref.infolist():
                    member_name_lower = member.filename.lower()
                    suspicious_extensions = ['.exe', '.dll', '.bat', '.cmd', '.scr', '.com']
                    if any(member_name_lower.endswith(ext) for ext in suspicious_extensions):
                        bot.reply_to(message, f"🚨 Security Alert: ZIP contains suspicious file: {member.filename}\nOnly owner can upload such files.")
                        return
                    
                    # Check for path traversal
                    member_path = os.path.abspath(os.path.join(temp_dir, member.filename))
                    if not member_path.startswith(os.path.abspath(temp_dir)):
                        raise zipfile.BadZipFile(f"Zip has unsafe path: {member.filename}")
            
            # Extract everything
            zip_ref.extractall(temp_dir)
            logger.info(f"Extracted zip to {temp_dir}")

        # --- FIX: Recursively find script if not in root (ignores __MACOSX) ---
        target_dir = temp_dir
        root_files = os.listdir(target_dir)
        
        # Check if script exists in root
        if not any(f.endswith(('.py', '.js')) for f in root_files):
            # Recursively search for a folder containing .py or .js
            for root, dirs, files in os.walk(temp_dir):
                # Ignore system/hidden folders like __MACOSX or .git
                dirs[:] = [d for d in dirs if not d.startswith('.') and not d.startswith('__')]
                
                if any(f.endswith(('.py', '.js')) for f in files):
                    target_dir = root
                    break
        
        # If the script is in a subdirectory, move everything up to temp_dir
        if target_dir != temp_dir:
            logger.info(f"Flattening extracted files from {target_dir} to {temp_dir}")
            for item in os.listdir(target_dir):
                s = os.path.join(target_dir, item)
                d = os.path.join(temp_dir, item)
                # Overwrite if exists (shouldn't happen often in this temp context)
                if os.path.exists(d):
                    if os.path.isdir(d): shutil.rmtree(d)
                    else: os.remove(d)
                shutil.move(s, d)
            # Refresh list after flattening
            extracted_items = os.listdir(temp_dir)
        else:
            extracted_items = root_files
        # --- END FIX ---

        py_files = [f for f in extracted_items if f.endswith('.py')]
        js_files = [f for f in extracted_items if f.endswith('.js')]
        req_file = 'requirements.txt' if 'requirements.txt' in extracted_items else None
        pkg_json = 'package.json' if 'package.json' in extracted_items else None

        if req_file:
            req_path = os.path.join(temp_dir, req_file)
            logger.info(f"requirements.txt found, installing: {req_path}")
            bot.reply_to(message, f"🔄 Installing Python deps from `{req_file}`...")
            try:
                command = [sys.executable, '-m', 'pip', 'install', '-r', req_path]
                result = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8', errors='ignore')
                logger.info(f"pip install from requirements.txt OK. Output:\n{result.stdout}")
                bot.reply_to(message, f"✅ Python deps from `{req_file}` installed.")
            except subprocess.CalledProcessError as e:
                error_msg = f"❌ Failed to install Python deps from `{req_file}`.\nLog:\n```\n{e.stderr or e.stdout}\n```"
                logger.error(error_msg)
                if len(error_msg) > 4000: error_msg = error_msg[:4000] + "\n... (Log truncated)"
                bot.reply_to(message, error_msg, parse_mode='Markdown'); return
            except Exception as e:
                 error_msg = f"❌ Unexpected error installing Python deps: {e}"
                 logger.error(error_msg, exc_info=True); bot.reply_to(message, error_msg); return

        if pkg_json:
            logger.info(f"package.json found, npm install in: {temp_dir}")
            bot.reply_to(message, f"🔄 Installing Node deps from `{pkg_json}`...")
            try:
                command = ['npm', 'install']
                result = subprocess.run(command, capture_output=True, text=True, check=True, cwd=temp_dir, encoding='utf-8', errors='ignore')
                logger.info(f"npm install OK. Output:\n{result.stdout}")
                bot.reply_to(message, f"✅ Node deps from `{pkg_json}` installed.")
            except FileNotFoundError:
                bot.reply_to(message, "❌ 'npm' not found. Cannot install Node deps."); return 
            except subprocess.CalledProcessError as e:
                error_msg = f"❌ Failed to install Node deps from `{pkg_json}`.\nLog:\n```\n{e.stderr or e.stdout}\n```"
                logger.error(error_msg)
                if len(error_msg) > 4000: error_msg = error_msg[:4000] + "\n... (Log truncated)"
                bot.reply_to(message, error_msg, parse_mode='Markdown'); return
            except Exception as e:
                 error_msg = f"❌ Unexpected error installing Node deps: {e}"
                 logger.error(error_msg, exc_info=True); bot.reply_to(message, error_msg); return

        main_script_name = None; file_type = None
        preferred_py = ['main.py', 'bot.py', 'app.py']; preferred_js = ['index.js', 'main.js', 'bot.js', 'app.js']
        for p in preferred_py:
            if p in py_files: main_script_name = p; file_type = 'py'; break
        if not main_script_name:
             for p in preferred_js:
                 if p in js_files: main_script_name = p; file_type = 'js'; break
        if not main_script_name:
            if py_files: main_script_name = py_files[0]; file_type = 'py'
            elif js_files: main_script_name = js_files[0]; file_type = 'js'
        if not main_script_name:
            bot.reply_to(message, "❌ No `.py` or `.js` script found in archive!"); return

        logger.info(f"Moving extracted files from {temp_dir} to {user_folder}")
        moved_count = 0
        for item_name in os.listdir(temp_dir):
            if item_name == file_name_zip: continue # Don't move the zip file itself if it's there
            src_path = os.path.join(temp_dir, item_name)
            dest_path = os.path.join(user_folder, item_name)
            if os.path.isdir(dest_path): shutil.rmtree(dest_path)
            elif os.path.exists(dest_path): os.remove(dest_path)
            shutil.move(src_path, dest_path); moved_count +=1
        logger.info(f"Moved {moved_count} items to {user_folder}")

        save_user_file(user_id, main_script_name, file_type)
        logger.info(f"Saved main script '{main_script_name}' ({file_type}) for {user_id} from zip.")
        main_script_path = os.path.join(user_folder, main_script_name)
        bot.reply_to(message, f"✅ Files extracted. Starting main script: `{main_script_name}`...", parse_mode='Markdown')

        if file_type == 'py':
             threading.Thread(target=run_script, args=(main_script_path, user_id, user_folder, main_script_name, message)).start()
        elif file_type == 'js':
             threading.Thread(target=run_js_script, args=(main_script_path, user_id, user_folder, main_script_name, message)).start()

    except zipfile.BadZipFile as e:
        logger.error(f"Bad zip file from {user_id}: {e}")
        bot.reply_to(message, f"❌ Error: Invalid/corrupted ZIP. {e}")
    except Exception as e:
        logger.error(f"❌ Error processing zip for {user_id}: {e}", exc_info=True)
        bot.reply_to(message, f"❌ Error processing zip: {str(e)}")
    finally:
        if temp_dir and os.path.exists(temp_dir):
            try: shutil.rmtree(temp_dir); logger.info(f"Cleaned temp dir: {temp_dir}")
            except Exception as e: logger.error(f"Failed to clean temp dir {temp_dir}: {e}", exc_info=True)
def handle_js_file(file_path, script_owner_id, user_folder, file_name, message):
    try:
        save_user_file(script_owner_id, file_name, 'js')
        threading.Thread(target=run_js_script, args=(file_path, script_owner_id, user_folder, file_name, message)).start()
    except Exception as e:
        logger.error(f"❌ Error processing JS file {file_name} for {script_owner_id}: {e}", exc_info=True)
        bot.reply_to(message, f"❌ Error processing JS file: {str(e)}")

def handle_py_file(file_path, script_owner_id, user_folder, file_name, message):
    try:
        save_user_file(script_owner_id, file_name, 'py')
        threading.Thread(target=run_script, args=(file_path, script_owner_id, user_folder, file_name, message)).start()
    except Exception as e:
        logger.error(f"❌ Error processing Python file {file_name} for {script_owner_id}: {e}", exc_info=True)
        bot.reply_to(message, f"❌ Error processing Python file: {str(e)}")

# --- Send Command and Enhanced Logs Functions ---
def _logic_send_command(message):
    """Handle send command functionality"""
    user_id = message.from_user.id
    if not check_user_access(message, check_referral=True):
        return
    if bot_locked and user_id not in admin_ids:
        bot.reply_to(message, "⚠️ Bot locked by admin.")
        return
        
    bot.reply_to(message, "📤 Send Command Options:", reply_markup=create_send_command_menu())

def send_to_process_init(message):
    """Initialize process for sending command to a running script"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Get user's running processes
    user_running_scripts = []
    for script_key, script_info in bot_scripts.items():
        script_owner_id = script_info['script_owner_id']
        if (user_id == script_owner_id or user_id in admin_ids) and is_bot_running(script_owner_id, script_info['file_name']):
            user_running_scripts.append((script_key, script_info))
    
    if not user_running_scripts:
        bot.reply_to(message, "❌ No running scripts found.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for script_key, script_info in user_running_scripts:
        btn_text = f"{script_info['file_name']} (User: {script_info['script_owner_id']})"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f'sendcmd_select_{script_key}'))
    
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data='send_command'))
    bot.reply_to(message, "📝 Select a running script to send command to:", reply_markup=markup)

def process_send_command(message, script_key):
    """Process the actual command to send to the script"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if script_key not in bot_scripts:
        bot.reply_to(message, "❌ Script no longer running.")
        return
    
    script_info = bot_scripts[script_key]
    command_text = message.text
    
    try:
        process = script_info['process']
        if process and process.poll() is None:
            # Send command to process stdin
            process.stdin.write(command_text + '\n')
            process.stdin.flush()
            bot.reply_to(message, f"✅ Command sent to `{script_info['file_name']}`:\n`{command_text}`", parse_mode='Markdown')
            
            # Wait a bit and check if process is still running
            time.sleep(1)
            if process.poll() is not None:
                bot.reply_to(message, f"⚠️ Script `{script_info['file_name']}` stopped after receiving command.")
        else:
            bot.reply_to(message, f"❌ Script `{script_info['file_name']}` is not running.")
    except Exception as e:
        logger.error(f"Error sending command to {script_key}: {e}")
        bot.reply_to(message, f"❌ Error sending command: {str(e)}")

def view_all_logs(message):
    """Show all available logs for user"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    user_logs = []
    
    # Get user's folder and all log files
    user_folder = get_user_folder(user_id)
    if os.path.exists(user_folder):
        for file in os.listdir(user_folder):
            if file.endswith('.log'):
                log_path = os.path.join(user_folder, file)
                file_size = os.path.getsize(log_path)
                user_logs.append((file, file_size, log_path))
    
    if not user_logs:
        bot.reply_to(message, "📜 No log files found.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for log_file, size, log_path in sorted(user_logs):
        size_kb = size / 1024
        btn_text = f"{log_file} ({size_kb:.1f} KB)"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f'viewlog_{user_id}_{log_file}'))
    
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data='send_command'))
    bot.reply_to(message, "📜 Available Log Files:", reply_markup=markup)

def send_log_file(message, log_path, log_filename):
    """Send log file as document"""
    try:
        file_size = os.path.getsize(log_path)
        if file_size > 50 * 1024 * 1024:  # 50MB limit
            bot.reply_to(message, f"❌ Log file too large ({file_size/1024/1024:.1f} MB). Maximum 50MB.")
            return
        
        with open(log_path, 'rb') as log_file:
            bot.send_document(message.chat.id, log_file, caption=f"📜 {log_filename}")
            
    except Exception as e:
        logger.error(f"Error sending log file {log_path}: {e}")
        bot.reply_to(message, f"❌ Error sending log file: {str(e)}")

# --- Logic Functions (called by commands and text handlers) ---
def _logic_send_welcome(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_name = message.from_user.first_name
    user_username = message.from_user.username

    # Ban Check
    is_banned, reason = get_user_status(user_id, OWNER_ID)
    if is_banned:
        bot.send_message(chat_id, f"🚫 Access Denied: You are {reason}.")
        return

    # Process referral deep link parameter
    parts = message.text.split() if message.text else []
    if len(parts) > 1:
        start_arg = parts[1]
        success, ref_msg = process_referral_start(user_id, start_arg, OWNER_ID)
        if success:
            logger.info(f"Referral registered: {ref_msg}")
            bot.send_message(chat_id, "✅ Referral registered! Please enter the password to complete the process.")
            # Notify the referrer that someone clicked their link
            try:
                referrer_id = int(start_arg.split("_")[1])
                bot.send_message(
                    referrer_id,
                    f"👀 Someone clicked your referral link!\n"
                    "They need to authenticate with the password to complete the referral."
                )
            except Exception as ne:
                logger.error(f"Failed to notify referrer about click: {ne}")
        elif ref_msg:
            bot.send_message(chat_id, f"ℹ️ {ref_msg}")

    # Owner/Admin bypass or DB auth check
    if user_id not in admin_ids and not is_user_authenticated(user_id, OWNER_ID):
        awaiting_password.add(user_id)
        bot.send_message(
            message.chat.id,
            "🔐 This bot is password protected.\n\nPlease enter the password to continue:"
        )
        return

    logger.info(f"Welcome request from user_id: {user_id}, username: @{user_username}")

# 🔒 Force Join Check
    if user_id not in admin_ids:
        if not is_user_joined_all(user_id):
            send_force_join_msg(chat_id)
            return

    if bot_locked and user_id not in admin_ids:
        bot.send_message(chat_id, "⚠️ Bot locked by admin. Try later.")
        return

    user_bio = "Could not fetch bio"; photo_file_id = None
    try: user_bio = bot.get_chat(user_id).bio or "No bio"
    except Exception: pass
    try:
        user_profile_photos = bot.get_user_profile_photos(user_id, limit=1)
        if user_profile_photos.photos: photo_file_id = user_profile_photos.photos[0][-1].file_id
    except Exception: pass

    if user_id not in active_users:
        add_active_user(user_id)
        try:
            owner_notification = (f"🎉 New user!\n👤 Name: {user_name}\n✳️ User: @{user_username or 'N/A'}\n"
                                  f"🆔 ID: `{user_id}`\n📝 Bio: {user_bio}")
            bot.send_message(OWNER_ID, owner_notification, parse_mode='Markdown')
            if photo_file_id: bot.send_photo(OWNER_ID, photo_file_id, caption=f"Pic of new user {user_id}")
        except Exception as e: logger.error(f"⚠️ Failed to notify owner about new user {user_id}: {e}")

    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    limit_str = str(file_limit) if file_limit != float('inf') else "Unlimited"
    expiry_info = ""
    if user_id == OWNER_ID: user_status = "🤍 Owner"
    elif user_id in admin_ids: user_status = "🌙 Admin"
    elif user_id in user_subscriptions:
        expiry_date = user_subscriptions[user_id].get('expiry')
        if expiry_date and expiry_date > datetime.now():
            user_status = "⭐ Premium"; days_left = (expiry_date - datetime.now()).days
            expiry_info = f"\n⏳ Subscription expires in: {days_left} days"
        else: user_status = "🆓 Free User (Expired Sub)"; remove_subscription_db(user_id)
    else: user_status = "🆓 Free User"

    welcome_msg_text = (f"〽️ Welcome, {user_name}!\n\n🆔 Your User ID: `{user_id}`\n"
                        f"✳️ Username: `@{user_username or 'Not set'}`\n"
                        f"🔰 Your Status: {user_status}{expiry_info}\n"
                        f"📁 Files Uploaded: {current_files} / {limit_str}\n\n"
                        f"🤖 Host & run Python (`.py`) or JS (`.js`) scripts.\n"
                        f"   Upload single scripts or `.zip` archives.\n\n"
                        f"👇 Use buttons or type commands.")
    main_reply_markup = create_reply_keyboard_main_menu(user_id)
    try:
        if photo_file_id: bot.send_photo(chat_id, photo_file_id)
        bot.send_message(chat_id, welcome_msg_text, reply_markup=main_reply_markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error sending welcome to {user_id}: {e}", exc_info=True)
        try: bot.send_message(chat_id, welcome_msg_text, reply_markup=main_reply_markup, parse_mode='Markdown')
        except Exception as fallback_e: logger.error(f"Fallback send_message failed for {user_id}: {fallback_e}")

def _logic_updates_channel(message):
    if not check_user_access(message, check_referral=False):
        return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('📢 Updates Channel', url=UPDATE_CHANNEL))
    bot.reply_to(message, "Visit our Updates Channel:", reply_markup=markup)

def _logic_upload_file(message):
    user_id = message.from_user.id
    if not check_user_access(message, check_referral=True):
        return
    if bot_locked and user_id not in admin_ids:
        bot.reply_to(message, "⚠️ Bot locked by admin, cannot accept files.")
        return

    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    if current_files >= file_limit:
        limit_str = str(file_limit) if file_limit != float('inf') else "Unlimited"
        bot.reply_to(message, f"⚠️ File limit ({current_files}/{limit_str}) reached. Delete files first.")
        return
    bot.reply_to(message, "📤 Send your Python (`.py`), JS (`.js`), or ZIP (`.zip`) file.")

def _logic_check_files(message, page=0):
    if isinstance(message, types.CallbackQuery):
        user_id = message.from_user.id
    else:
        user_id = message.from_user.id
    if not check_user_access(message, check_referral=True):
        return
    user_files_list = user_files.get(user_id, [])
    if not user_files_list:
        if isinstance(message, types.CallbackQuery):
            bot.edit_message_text(
                "📂 *Your Files:*\n\n_(No files uploaded yet)_",
                chat_id=message.message.chat.id,
                message_id=message.message.message_id,
                parse_mode="Markdown"
            )
        else:
            bot.send_message(
                message.chat.id,
                "📂 *Your Files:*\n\n_(No files uploaded yet)_",
                parse_mode="Markdown"
            )
        return
        
    # Pagination
    items_per_page = 10
    total_pages = (len(user_files_list) - 1) // items_per_page + 1
    page = max(0, min(page, total_pages - 1))
    
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    current_files = sorted(user_files_list)[start_idx:end_idx]
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for file_name, file_type in current_files:
        is_running = is_bot_running(user_id, file_name)
        status_icon = "🟢" if is_running else "🔴"
        btn_text = f"{status_icon} {file_name} ({file_type})"
        # Use callback registry for long names
        cb_id = pack_callback(f"file_{user_id}_{file_name}")
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=cb_id))
    
    # Pagination row
    nav_row = []

    if page > 0:
        nav_row.append(
            types.InlineKeyboardButton(
                "◀ Prev",
                callback_data=pack_callback(f"chk_page_{page-1}")
            )
        )

    nav_row.append(
        types.InlineKeyboardButton(
            "🔄 Refresh",
            callback_data=pack_callback(f"chk_page_{page}")
        )
    )

    if page < total_pages - 1:
        nav_row.append(
            types.InlineKeyboardButton(
                "Next ▶",
                callback_data=pack_callback(f"chk_page_{page+1}")
            )
        )
    if nav_row:
        markup.row(*nav_row)
        
    text = f"📂 *Your Files* (Page {page+1}/{total_pages}): Select a file to manage."
    
    if isinstance(message, types.CallbackQuery):
        try:
            bot.edit_message_text(
                text,
                chat_id=message.message.chat.id,
                message_id=message.message.message_id,
                reply_markup=markup,
                parse_mode="Markdown"
            )
        except telebot.apihelper.ApiTelegramException:
            bot.send_message(
                message.message.chat.id,
                text,
                reply_markup=markup,
                parse_mode="Markdown"
            )
    else:
        bot.send_message(
            message.chat.id,
            text,
            reply_markup=markup,
            parse_mode="Markdown"
        )

def _logic_bot_speed(message):
    user_id = message.from_user.id
    if not check_user_access(message, check_referral=False):
        return
    chat_id = message.chat.id
    start_time_ping = time.time()
    wait_msg = bot.reply_to(message, "🏃 Testing speed...")
    try:
        bot.send_chat_action(chat_id, 'typing')
        response_time = round((time.time() - start_time_ping) * 1000, 2)
        status = "🔓 Unlocked" if not bot_locked else "🔒 Locked"
        if user_id == OWNER_ID: user_level = "🤍 Owner"
        elif user_id in admin_ids: user_level = "🌙 Admin"
        elif user_id in user_subscriptions and user_subscriptions[user_id].get('expiry', datetime.min) > datetime.now(): user_level = "⭐ Premium"
        else: user_level = "🆓 Free User"
        speed_msg = (f"⚡ Bot Speed & Status:\n\n⏱️ API Response Time: {response_time} ms\n"
                     f"🚦 Bot Status: {status}\n"
                     f"👤 Your Level: {user_level}")
        bot.edit_message_text(speed_msg, chat_id, wait_msg.message_id)
    except Exception as e:
        logger.error(f"Error during speed test (cmd): {e}", exc_info=True)
        bot.edit_message_text("❌ Error during speed test.", chat_id, wait_msg.message_id)

def _logic_contact_owner(message):
    if not check_user_access(message, check_referral=False):
        return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('📞 Contact Owner', url=f'https://t.me/{YOUR_USERNAME.replace("@", "")}'))
    bot.reply_to(message, "Click to contact Owner:", reply_markup=markup)

# --- Admin Logic Functions ---
def _logic_subscriptions_panel(message):
    if not check_user_access(message, check_referral=False):
        return
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin permissions required.")
        return
    bot.reply_to(message, "💳 Subscription Management\nUse inline buttons from /start or admin command menu.", reply_markup=create_subscription_menu())

def _logic_statistics(message):
    if not check_user_access(message, check_referral=False):
        return
    user_id = message.from_user.id
    total_users = len(active_users)
    total_files_records = sum(len(files) for files in user_files.values())

    running_bots_count = 0
    user_running_bots = 0

    for script_key_iter, script_info_iter in list(bot_scripts.items()):
        s_owner_id, _ = script_key_iter.split('_', 1)
        if is_bot_running(int(s_owner_id), script_info_iter['file_name']):
            running_bots_count += 1
            if int(s_owner_id) == user_id:
                user_running_bots +=1

    stats_msg_base = (f"📊 Bot Statistics:\n\n"
                      f"👥 Total Users: {total_users}\n"
                      f"📂 Total File Records: {total_files_records}\n"
                      f"🟢 Total Active Bots: {running_bots_count}\n")

    if user_id in admin_ids:
        stats_msg_admin = (f"🔒 Bot Status: {'🔴 Locked' if bot_locked else '🟢 Unlocked'}\n"
                           f"🤖 Your Running Bots: {user_running_bots}")
        stats_msg = stats_msg_base + stats_msg_admin
    else:
        stats_msg = stats_msg_base + f"🤖 Your Running Bots: {user_running_bots}"

    bot.reply_to(message, stats_msg)

def _logic_broadcast_init(message):
    if not check_user_access(message, check_referral=False):
        return
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin permissions required.")
        return
    msg = bot.reply_to(message, "📢 Send message to broadcast to all active users.\n/cancel to abort.")
    bot.register_next_step_handler(msg, process_broadcast_message)

def _logic_toggle_lock_bot(message):
    if not check_user_access(message, check_referral=False):
        return
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin permissions required.")
        return
    global bot_locked
    bot_locked = not bot_locked
    status = "locked" if bot_locked else "unlocked"
    logger.warning(f"Bot {status} by Admin {message.from_user.id} via command/button.")
    bot.reply_to(message, f"🔒 Bot has been {status}.")

def _logic_admin_panel(message):
    if not check_user_access(message, check_referral=False):
        return
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin permissions required.")
        return
    bot.reply_to(message, "👑 Admin Panel\nManage admins. Use inline buttons from /start or admin menu.",
                 reply_markup=create_admin_panel())

def _logic_run_all_scripts(message_or_call):
    if not check_user_access(message_or_call, check_referral=False):
        return
    if isinstance(message_or_call, telebot.types.Message):
        admin_user_id = message_or_call.from_user.id
        admin_chat_id = message_or_call.chat.id
        reply_func = lambda text, **kwargs: bot.reply_to(message_or_call, text, **kwargs)
        admin_message_obj_for_script_runner = message_or_call
    elif isinstance(message_or_call, telebot.types.CallbackQuery):
        admin_user_id = message_or_call.from_user.id
        admin_chat_id = message_or_call.message.chat.id
        bot.answer_callback_query(message_or_call.id)
        reply_func = lambda text, **kwargs: bot.send_message(admin_chat_id, text, **kwargs)
        admin_message_obj_for_script_runner = message_or_call.message 
    else:
        logger.error("Invalid argument for _logic_run_all_scripts")
        return

    if admin_user_id not in admin_ids:
        reply_func("⚠️ Admin permissions required.")
        return

    reply_func("⏳ Starting process to run all user scripts. This may take a while...")
    logger.info(f"Admin {admin_user_id} initiated 'run all scripts' from chat {admin_chat_id}.")

    started_count = 0; attempted_users = 0; skipped_files = 0; error_files_details = []

    all_user_files_snapshot = dict(user_files)

    for target_user_id, files_for_user in all_user_files_snapshot.items():
        if not files_for_user: continue
        attempted_users += 1
        logger.info(f"Processing scripts for user {target_user_id}...")
        user_folder = get_user_folder(target_user_id)

        for file_name, file_type in files_for_user:
            if not is_bot_running(target_user_id, file_name):
                file_path = os.path.join(user_folder, file_name)
                if os.path.exists(file_path):
                    logger.info(f"Admin {admin_user_id} attempting to start '{file_name}' ({file_type}) for user {target_user_id}.")
                    try:
                        if file_type == 'py':
                            threading.Thread(target=run_script, args=(file_path, target_user_id, user_folder, file_name, admin_message_obj_for_script_runner)).start()
                            started_count += 1
                        elif file_type == 'js':
                            threading.Thread(target=run_js_script, args=(file_path, target_user_id, user_folder, file_name, admin_message_obj_for_script_runner)).start()
                            started_count += 1
                        else:
                            logger.warning(f"Unknown file type '{file_type}' for {file_name} (user {target_user_id}). Skipping.")
                            error_files_details.append(f"`{file_name}` (User {target_user_id}) - Unknown type")
                            skipped_files += 1
                        time.sleep(0.7)
                    except Exception as e:
                        logger.error(f"Error queueing start for '{file_name}' (user {target_user_id}): {e}")
                        error_files_details.append(f"`{file_name}` (User {target_user_id}) - Start error")
                        skipped_files += 1
                else:
                    logger.warning(f"File '{file_name}' for user {target_user_id} not found at '{file_path}'. Skipping.")
                    error_files_details.append(f"`{file_name}` (User {target_user_id}) - File not found")
                    skipped_files += 1

    summary_msg = (f"✅ All Users' Scripts - Processing Complete:\n\n"
                   f"▶️ Attempted to start: {started_count} scripts.\n"
                   f"👥 Users processed: {attempted_users}.\n")
    if skipped_files > 0:
        summary_msg += f"⚠️ Skipped/Error files: {skipped_files}\n"
        if error_files_details:
             summary_msg += "Details (first 5):\n" + "\n".join([f"  - {err}" for err in error_files_details[:5]])
             if len(error_files_details) > 5: summary_msg += "\n  ... and more (check logs)."

    reply_func(summary_msg, parse_mode='Markdown')
    logger.info(f"Run all scripts finished. Admin: {admin_user_id}. Started: {started_count}. Skipped/Errors: {skipped_files}")

# --- Command Handlers & Text Handlers for ReplyKeyboard ---
@bot.message_handler(func=lambda m: m.from_user.id in awaiting_password or (m.from_user.id not in admin_ids and not is_user_authenticated(m.from_user.id, OWNER_ID)))
def password_handler(message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Check if banned
    is_banned, reason = get_user_status(user_id, OWNER_ID)
    if is_banned:
        bot.reply_to(message, f"🚫 Access Denied: You are {reason}.")
        return

    entered_password = message.text.strip()
    is_correct, attempts_left = verify_password(
        user_id, entered_password, BOT_PASSWORD, username, bot, OWNER_ID
    )
    
    if is_correct:
        awaiting_password.discard(user_id)
        authenticated_users.add(user_id)
        bot.reply_to(
            message,
            "✅ Password accepted! You can now use the bot.\nSend /start again."
        )
    else:
        if attempts_left == 0:
            awaiting_password.discard(user_id)
            bot.reply_to(
                message,
                "❌ Incorrect password. You have been temporarily banned for 24 hours."
            )
        else:
            bot.reply_to(
                message,
                f"❌ Incorrect password. Attempt failed. You have {attempts_left} attempts left. Please try again:"
            )
        
@bot.message_handler(commands=['start', 'help'])
def command_send_welcome(message): _logic_send_welcome(message)

@bot.message_handler(commands=['status'])
def command_show_status(message): _logic_statistics(message)

BUTTON_TEXT_TO_LOGIC = {
    "📢 Updates Channel": _logic_updates_channel,
    "📤 Upload File": _logic_upload_file,
    "📂 Check Files": _logic_check_files,
    "⚡ Bot Speed": _logic_bot_speed,
    "📤 Send Command": _logic_send_command,  # Added Send Command
    "📞 Contact Owner": _logic_contact_owner,
    "📊 Statistics": _logic_statistics,
    "💳 Subscriptions": _logic_subscriptions_panel,
    "📢 Broadcast": _logic_broadcast_init,
    "🔒 Lock Bot": _logic_toggle_lock_bot,
    "🟢 Running All Code": _logic_run_all_scripts,
    "👑 Admin Panel": _logic_admin_panel,
}

@bot.message_handler(func=lambda message: message.text in BUTTON_TEXT_TO_LOGIC)
def handle_button_text(message):
    logic_func = BUTTON_TEXT_TO_LOGIC.get(message.text)
    if logic_func: logic_func(message)
    else: logger.warning(f"Button text '{message.text}' matched but no logic func.")

@bot.message_handler(commands=['updateschannel'])
def command_updates_channel(message): _logic_updates_channel(message)
@bot.message_handler(commands=['uploadfile'])
def command_upload_file(message): _logic_upload_file(message)
@bot.message_handler(commands=['checkfiles'])
def command_check_files(message): _logic_check_files(message)
@bot.message_handler(commands=['botspeed'])
def command_bot_speed(message): _logic_bot_speed(message)
@bot.message_handler(commands=['sendcommand'])  # Added Send Command
def command_send_command(message): _logic_send_command(message)
@bot.message_handler(commands=['contactowner'])
def command_contact_owner(message): _logic_contact_owner(message)
@bot.message_handler(commands=['subscriptions'])
def command_subscriptions(message): _logic_subscriptions_panel(message)
@bot.message_handler(commands=['statistics'])
def command_statistics(message): _logic_statistics(message)
@bot.message_handler(commands=['broadcast'])
def command_broadcast(message): _logic_broadcast_init(message)
@bot.message_handler(commands=['lockbot']) 
def command_lock_bot(message): _logic_toggle_lock_bot(message)
@bot.message_handler(commands=['adminpanel'])
def command_admin_panel(message): _logic_admin_panel(message)
@bot.message_handler(commands=['runningallcode'])
def command_run_all_code(message): _logic_run_all_scripts(message)

@bot.message_handler(commands=['ping'])
def ping(message):
    if not check_user_access(message, check_referral=False):
        return
    start_ping_time = time.time() 
    msg = bot.reply_to(message, "Pong!")
    latency = round((time.time() - start_ping_time) * 1000, 2)
    bot.edit_message_text(f"Pong! Latency: {latency} ms", message.chat.id, msg.message_id)

# --- Document (File) Handler with Malware Detection ---
@bot.message_handler(content_types=['document'])
def handle_file_upload_doc(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if not check_user_access(message, check_referral=True):
        return
    doc = message.document
    logger.info(f"Doc from {user_id}: {doc.file_name} ({doc.mime_type}), Size: {doc.file_size}")

    if bot_locked and user_id not in admin_ids:
        bot.reply_to(message, "⚠️ Bot locked, cannot accept files.")
        return

    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    if current_files >= file_limit:
        limit_str = str(file_limit) if file_limit != float('inf') else "Unlimited"
        bot.reply_to(message, f"⚠️ File limit ({current_files}/{limit_str}) reached. Delete files via /checkfiles.")
        return

    file_name = doc.file_name
    if not file_name: bot.reply_to(message, "⚠️ No file name. Ensure file has a name."); return
    file_ext = os.path.splitext(file_name)[1].lower()
    if file_ext not in ['.py', '.js', '.zip']:
        bot.reply_to(message, "⚠️ Unsupported type! Only `.py`, `.js`, `.zip` allowed.")
        return
    max_file_size = 20 * 1024 * 1024
    if doc.file_size > max_file_size:
        bot.reply_to(message, f"⚠️ File too large (Max: {max_file_size // 1024 // 1024} MB)."); return

    try:
        try:
            bot.forward_message(OWNER_ID, chat_id, message.message_id)
            bot.send_message(OWNER_ID, f"⬆️ File '{file_name}' from {message.from_user.first_name} (`{user_id}`)", parse_mode='Markdown')
        except Exception as e: logger.error(f"Failed to forward uploaded file to OWNER_ID {OWNER_ID}: {e}")

        download_wait_msg = bot.reply_to(message, f"⏳ Downloading `{file_name}`...")
        file_info_tg_doc = bot.get_file(doc.file_id)
        downloaded_file_content = bot.download_file(file_info_tg_doc.file_path)
        
        # Malware scan (except for owner)
        if user_id != OWNER_ID:
            is_safe, reason = scan_file_for_malware(downloaded_file_content, file_name, user_id)
            if not is_safe:
                record_violation(user_id, message.from_user.username, file_name, reason, bot, OWNER_ID)
                bot.edit_message_text(MALWARE_BLOCKED_MESSAGE, chat_id, download_wait_msg.message_id)
                return
        
        bot.edit_message_text(f"✅ Downloaded `{file_name}`. Processing...", chat_id, download_wait_msg.message_id)
        logger.info(f"Downloaded {file_name} for user {user_id}")
        user_folder = get_user_folder(user_id)

        if file_ext == '.zip':
            handle_zip_file(downloaded_file_content, file_name, message)
        else:
            file_path = os.path.join(user_folder, file_name)
            with open(file_path, 'wb') as f: f.write(downloaded_file_content)
            logger.info(f"Saved single file to {file_path}")
            if file_ext == '.js': handle_js_file(file_path, user_id, user_folder, file_name, message)
            elif file_ext == '.py': handle_py_file(file_path, user_id, user_folder, file_name, message)
    except telebot.apihelper.ApiTelegramException as e:
         logger.error(f"Telegram API Error handling file for {user_id}: {e}", exc_info=True)
         if "file is too big" in str(e).lower():
              bot.reply_to(message, f"❌ Telegram API Error: File too large to download (~20MB limit).")
         else: bot.reply_to(message, f"❌ Telegram API Error: {str(e)}. Try later.")
    except Exception as e:
        logger.error(f"❌ General error handling file for {user_id}: {e}", exc_info=True)
        bot.reply_to(message, f"❌ Unexpected error: {str(e)}")

# --- Callback Query Handlers (for Inline Buttons) ---
@bot.callback_query_handler(func=lambda call: call.data == "force_join_check")
def force_join_recheck(call):
    if not check_user_access(call, check_referral=False):
        return
    user_id = call.from_user.id

    if is_user_joined_all(user_id):
        bot.answer_callback_query(call.id, "✅ All channels verified!")
        _logic_send_welcome(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ Sab channels join karo pehle", show_alert=True)

@bot.callback_query_handler(func=lambda call: True) 
def handle_callbacks(call):

    try:
        if call.data.startswith("cb_"):
            unpacked_data = unpack_callback(call.data)
            if unpacked_data is None:
                bot.answer_callback_query(call.id, "Invalid callback.")
                return
            logger.info(f"Unpacked callback {call.data} -> {unpacked_data}")
        else:
            unpacked_data = call.data
    except Exception as e:
        logger.error(f"Callback unpack error: {e}", exc_info=True)
        unpacked_data = call.data

    call.data = unpacked_data # Override for routing

    user_id = call.from_user.id
    data = call.data
    logger.info(f"Callback: User={user_id}, Data='{data}'")
    logger.info(f"CALLBACK TYPE = {type(data)}")

    # Access check (referrals needed for file uploads/hosting options)
    need_referral_check = data in ['upload', 'check_files', 'send_command', 'send_to_process', 'view_all_logs'] or data.startswith(('file_', 'start_', 'stop_', 'restart_', 'delete_', 'logs_', 'sendcmd_select_', 'viewlog_'))
    if not check_user_access(call, check_referral=need_referral_check):
        return

    if bot_locked and user_id not in admin_ids and data not in ['back_to_main', 'speed', 'stats']:
        bot.answer_callback_query(call.id, "⚠️ Bot locked by admin.", show_alert=True)
        return
    try:
        if data == 'upload': upload_callback(call)
        elif data == 'check_files': check_files_callback(call)
        elif data.startswith("chk_page_"): check_files_callback(call)
        elif data.startswith('file_'): file_control_callback(call)
        elif data.startswith('start_'): start_bot_callback(call)
        elif data.startswith('stop_'): stop_bot_callback(call)
        elif data.startswith('restart_'): restart_bot_callback(call)
        elif data.startswith('delete_'): delete_bot_callback(call)
        elif data.startswith('logs_'): logs_bot_callback(call)
        elif data == 'speed': speed_callback(call)
        elif data == 'back_to_main': back_to_main_callback(call)
        elif data.startswith('confirm_broadcast_'): handle_confirm_broadcast(call)
        elif data == 'cancel_broadcast': handle_cancel_broadcast(call)
        # --- New Send Command Callbacks ---
        elif data == 'send_command': send_command_callback(call)
        elif data == 'send_to_process': send_to_process_callback(call)
        elif data.startswith('sendcmd_select_'): sendcmd_select_callback(call)
        elif data == 'view_all_logs': view_all_logs_callback(call)
        elif data.startswith('viewlog_'): viewlog_callback(call)
        # --- Admin Callbacks ---
        elif data == 'subscription': admin_required_callback(call, subscription_management_callback)
        elif data == 'stats': stats_callback(call)
        elif data == 'lock_bot': admin_required_callback(call, lock_bot_callback)
        elif data == 'unlock_bot': admin_required_callback(call, unlock_bot_callback)
        elif data == 'run_all_scripts': admin_required_callback(call, run_all_scripts_callback)
        elif data == 'broadcast': admin_required_callback(call, broadcast_init_callback) 
        elif data == 'admin_panel': admin_required_callback(call, admin_panel_callback)
        elif data == 'add_admin': owner_required_callback(call, add_admin_init_callback) 
        elif data == 'remove_admin': owner_required_callback(call, remove_admin_init_callback) 
        elif data == 'list_admins': admin_required_callback(call, list_admins_callback)
        elif data == 'add_subscription': admin_required_callback(call, add_subscription_init_callback) 
        elif data == 'remove_subscription': admin_required_callback(call, remove_subscription_init_callback) 
        elif data == 'check_subscription': admin_required_callback(call, check_subscription_init_callback) 
        elif data == 'change_password': owner_required_callback(call, change_password_init_callback)
        elif data == 'toggle_referral': owner_required_callback(call, toggle_referral_callback)
        elif data == 'user_management': admin_required_callback(call, user_management_callback)
        elif data == 'users_list': admin_required_callback(call, users_list_callback)
        elif data == 'banned_users': admin_required_callback(call, banned_users_callback)
        elif data == 'ban_user_init': admin_required_callback(call, ban_user_init_callback)
        elif data == 'unban_user_init': admin_required_callback(call, unban_user_init_callback)
        else:
            bot.answer_callback_query(call.id, "Unknown action.")
            logger.warning(f"Unhandled callback data: {data} from user {user_id}")
    except Exception as e:
        logger.error(f"Error handling callback '{data}' for {user_id}: {e}", exc_info=True)
        try: bot.answer_callback_query(call.id, "Error processing request.", show_alert=True)
        except Exception as e_ans: logger.error(f"Failed to answer callback after error: {e_ans}")

def admin_required_callback(call, func_to_run):
    if call.from_user.id not in admin_ids:
        bot.answer_callback_query(call.id, "⚠️ Admin permissions required.", show_alert=True)
        return
    func_to_run(call) 

def owner_required_callback(call, func_to_run):
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "⚠️ Owner permissions required.", show_alert=True)
        return
    func_to_run(call)

# --- New Send Command Callback Functions ---
def send_command_callback(call):
    bot.answer_callback_query(call.id)
    try:
        bot.edit_message_text("📤 Send Command Options:",
                              call.message.chat.id, call.message.message_id, 
                              reply_markup=create_send_command_menu())
    except Exception as e:
        logger.error(f"Error showing send command menu: {e}")

def send_to_process_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "📝 Send the command you want to execute:")
    bot.register_next_step_handler(msg, lambda m: send_to_process_init(m))

def sendcmd_select_callback(call):
    try:
        script_key = call.data.replace('sendcmd_select_', '')
        bot.answer_callback_query(call.id, f"Selected script: {script_key}")
        msg = bot.send_message(call.message.chat.id, f"📝 Enter command to send to {script_key}:")
        bot.register_next_step_handler(msg, lambda m: process_send_command(m, script_key))
    except Exception as e:
        logger.error(f"Error in sendcmd_select_callback: {e}")
        bot.answer_callback_query(call.id, "Error selecting script.")

def view_all_logs_callback(call):
    bot.answer_callback_query(call.id)
    view_all_logs(call.message)

def viewlog_callback(call):
    try:
        _, user_id_str, log_filename = call.data.split('_', 2)
        user_id = int(user_id_str)
        requesting_user_id = call.from_user.id
        
        if not (requesting_user_id == user_id or requesting_user_id in admin_ids):
            bot.answer_callback_query(call.id, "⚠️ You can only view your own logs.", show_alert=True)
            return
            
        user_folder = get_user_folder(user_id)
        log_path = os.path.join(user_folder, log_filename)
        
        if not os.path.exists(log_path):
            bot.answer_callback_query(call.id, "❌ Log file not found.", show_alert=True)
            return
            
        bot.answer_callback_query(call.id, "📜 Sending log file...")
        send_log_file(call.message, log_path, log_filename)
        
    except Exception as e:
        logger.error(f"Error in viewlog_callback: {e}")
        bot.answer_callback_query(call.id, "Error viewing log.")

# ... (rest of the existing callback functions remain the same)

def upload_callback(call):
    user_id = call.from_user.id
    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    if current_files >= file_limit:
        limit_str = str(file_limit) if file_limit != float('inf') else "Unlimited"
        bot.answer_callback_query(call.id, f"⚠️ File limit ({current_files}/{limit_str}) reached.", show_alert=True)
        return
    bot.answer_callback_query(call.id) 
    bot.send_message(call.message.chat.id, "📤 Send your Python (`.py`), JS (`.js`), or ZIP (`.zip`) file.")

def check_files_callback(call):
    try:
        bot.answer_callback_query(call.id)
    except:
        pass
        
    try:
        if call.data.startswith("cb_"):
            unpacked = unpack_callback(call.data)
        else:
            unpacked = call.data
        if unpacked == 'check_files' or call.data == 'check_files':
            page = 0
        elif unpacked and unpacked.startswith('chk_page_'):
            page = int(unpacked.split('_')[2])
        else:
            page = 0
            
        _logic_check_files(call, page)
    except Exception as e:
        logger.error(f"Error in check_files_callback: {e}", exc_info=True)
        try: bot.answer_callback_query(call.id, "An error occurred.", show_alert=True)
        except: pass

def file_control_callback(call):
    try:
        bot.answer_callback_query(call.id)
    except:
        pass
        
    try:
        if call.data.startswith("cb_"):
            unpacked = unpack_callback(call.data)
        else:
            unpacked = call.data
        parts = unpacked.split('_', 2)
        if len(parts) == 3:
            _, script_owner_id_str, file_name = parts
        else:
            return # Invalid
            
        script_owner_id = int(script_owner_id_str)
        requesting_user_id = call.from_user.id

        if not (requesting_user_id == script_owner_id or requesting_user_id in admin_ids):
            try: bot.answer_callback_query(call.id, "⚠️ You can only manage your own files.", show_alert=True)
            except: pass
            return

        user_files_list = user_files.get(script_owner_id, [])
        if not any(f[0] == file_name for f in user_files_list):
            try: bot.answer_callback_query(call.id, "⚠️ File not found. It may have been deleted.", show_alert=True)
            except: pass
            return

        is_running = is_bot_running(script_owner_id, file_name)
        file_type = next((f[1] for f in user_files_list if f[0] == file_name), '?')
        
        # Gather rich stats
        pid_str = "N/A"
        cpu_str = "N/A"
        ram_str = "N/A"
        uptime_str = "N/A"
        
        script_key = f"{script_owner_id}_{file_name}"
        if is_running:
            proc_info = bot_scripts.get(script_key)
            if proc_info and proc_info.get('process'):
                try:
                    p = proc_info['process']
                    pid_str = str(p.pid)
                    cpu_str = f"{p.cpu_percent(interval=0.1):.1f}%"
                    ram_str = f"{p.memory_info().rss / 1024 / 1024:.1f} MB"
                    up_seconds = int(time.time() - p.create_time())
                    uptime_str = f"{up_seconds // 3600}h {(up_seconds % 3600) // 60}m {up_seconds % 60}s"
                except:
                    pass
                    
        # File info
        user_folder = get_user_folder(script_owner_id)
        file_path = os.path.join(user_folder, file_name)
        size_str = "N/A"
        upload_time = "N/A"
        deps_str = "None detected"
        if os.path.exists(file_path):
            size_mb = os.path.getsize(file_path) / 1024 / 1024
            size_str = f"{size_mb:.2f} MB"
            upload_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(file_path)))
            
            if file_type == 'py' and os.path.exists(os.path.join(user_folder, 'requirements.txt')):
                deps_str = "requirements.txt"
            elif file_type == 'js' and os.path.exists(os.path.join(user_folder, 'package.json')):
                deps_str = "package.json"

        status_icon = '🟢 Running' if is_running else '🔴 Stopped'
        
        text = (f"⚙️ *Control Panel*\n"
                f"📄 *File:* `{file_name}` ({file_type})\n"
                f"👤 *Owner:* `{script_owner_id}`\n"
                f"⚡ *Status:* {status_icon}\n"
                f"------------------------\n"
                f"🖥️ *PID:* {pid_str}\n"
                f"📈 *CPU:* {cpu_str}\n"
                f"🐏 *RAM:* {ram_str}\n"
                f"⏱️ *Uptime:* {uptime_str}\n"
                f"------------------------\n"
                f"☁️ *Uploaded:* {upload_time}\n"
                f"📦 *Size:* {size_str}\n"
                f"🧩 *Dependencies:* {deps_str}")
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        if is_running:
            markup.row(
                types.InlineKeyboardButton("🔴 Stop", callback_data=pack_callback(f'stop_{script_owner_id}_{file_name}')),
                types.InlineKeyboardButton("🔄 Restart", callback_data=pack_callback(f'restart_{script_owner_id}_{file_name}'))
            )
        else:
            markup.row(
                types.InlineKeyboardButton("🟢 Start", callback_data=pack_callback(f'start_{script_owner_id}_{file_name}'))
            )
            
        markup.row(
            types.InlineKeyboardButton("🗑️ Delete", callback_data=pack_callback(f'delete_{script_owner_id}_{file_name}')),
            types.InlineKeyboardButton("📜 Logs", callback_data=pack_callback(f'logs_{script_owner_id}_{file_name}'))
        )
        markup.row(
            types.InlineKeyboardButton("🔄 Refresh Stats", callback_data=pack_callback(f'file_{script_owner_id}_{file_name}')),
            types.InlineKeyboardButton("🔙 Back to List", callback_data=pack_callback('check_files'))
        )

        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" not in str(e).lower():
                logger.error(f"Error editing msg for {file_name} controls: {e}")
                
    except Exception as e:
        logger.error(f"Error in file_control_callback: {e}", exc_info=True)

def start_bot_callback(call):
    try:
        bot.answer_callback_query(call.id)
    except:
        pass
    try:
        unpacked = unpack_callback(call.data) if len(call.data) == 16 else call.data
        _, script_owner_id_str, file_name = unpacked.split('_', 2)
        script_owner_id = int(script_owner_id_str)
        requesting_user_id = call.from_user.id
        chat_id_for_reply = call.message.chat.id

        if not (requesting_user_id == script_owner_id or requesting_user_id in admin_ids):
            try: bot.answer_callback_query(call.id, "⚠️ Permission denied.", show_alert=True)
            except: pass
            return

        user_files_list = user_files.get(script_owner_id, [])
        file_info = next((f for f in user_files_list if f[0] == file_name), None)
        if not file_info:
            try: bot.answer_callback_query(call.id, "⚠️ File not found.", show_alert=True)
            except: pass
            return


        file_type = file_info[1]
        user_folder = get_user_folder(script_owner_id)
        file_path = os.path.join(user_folder, file_name)

        if is_bot_running(script_owner_id, file_name):
            try: bot.answer_callback_query(call.id, f"⚠️ Script already running.", show_alert=True)
            except: pass
            return

        try: bot.answer_callback_query(call.id, f"⏳ Starting...")
        except: pass

        if file_type == 'py':
            threading.Thread(target=run_script, args=(file_path, script_owner_id, user_folder, file_name, call.message)).start()
        elif file_type == 'js':
            threading.Thread(target=run_js_script, args=(file_path, script_owner_id, user_folder, file_name, call.message)).start()

        time.sleep(1.5)
        
        # Route back to file control view
        call.data = pack_callback(f"file_{script_owner_id}_{file_name}")
        file_control_callback(call)

    except Exception as e:
        logger.error(f"Error in start_bot_callback: {e}", exc_info=True)

def stop_bot_callback(call):
    try:
        bot.answer_callback_query(call.id)
    except:
        pass
    try:
        unpacked = unpack_callback(call.data) if len(call.data) == 16 else call.data
        _, script_owner_id_str, file_name = unpacked.split('_', 2)
        script_owner_id = int(script_owner_id_str)
        requesting_user_id = call.from_user.id
        chat_id_for_reply = call.message.chat.id

        if not (requesting_user_id == script_owner_id or requesting_user_id in admin_ids):
            try: bot.answer_callback_query(call.id, "⚠️ Permission denied.", show_alert=True)
            except: pass
            return

        user_files_list = user_files.get(script_owner_id, [])
        file_info = next((f for f in user_files_list if f[0] == file_name), None)
        if not file_info:
            try: bot.answer_callback_query(call.id, "⚠️ File not found.", show_alert=True)
            except: pass
            return


        if not is_bot_running(script_owner_id, file_name): 
            try: bot.answer_callback_query(call.id, f"⚠️ Script already stopped.", show_alert=True)
            except: pass
            return

        try: bot.answer_callback_query(call.id, f"⏳ Stopping...")
        except: pass
        
        script_key = f"{script_owner_id}_{file_name}"
        process_info = bot_scripts.get(script_key)
        if process_info:
            kill_process_tree(process_info)
            if script_key in bot_scripts: del bot_scripts[script_key]

        # Route back to file control view
        call.data = pack_callback(f"file_{script_owner_id}_{file_name}")
        file_control_callback(call)

    except Exception as e:
        logger.error(f"Error in stop_bot_callback: {e}", exc_info=True)

def restart_bot_callback(call):
    try:
        bot.answer_callback_query(call.id)
    except:
        pass
    try:
        unpacked = unpack_callback(call.data) if len(call.data) == 16 else call.data
        _, script_owner_id_str, file_name = unpacked.split('_', 2)
        script_owner_id = int(script_owner_id_str)
        requesting_user_id = call.from_user.id
        chat_id_for_reply = call.message.chat.id

        if not (requesting_user_id == script_owner_id or requesting_user_id in admin_ids):
            try: bot.answer_callback_query(call.id, "⚠️ Permission denied.", show_alert=True)
            except: pass
            return

        user_files_list = user_files.get(script_owner_id, [])
        file_info = next((f for f in user_files_list if f[0] == file_name), None)
        if not file_info:
            try: bot.answer_callback_query(call.id, "⚠️ File not found.", show_alert=True)
            except: pass
            return


        file_type = file_info[1]
        user_folder = get_user_folder(script_owner_id)
        file_path = os.path.join(user_folder, file_name)
        script_key = f"{script_owner_id}_{file_name}"

        try: bot.answer_callback_query(call.id, f"⏳ Restarting...")
        except: pass

        if is_bot_running(script_owner_id, file_name):
            process_info = bot_scripts.get(script_key)
            if process_info: kill_process_tree(process_info)
            if script_key in bot_scripts: del bot_scripts[script_key]
            time.sleep(1.0) 

        if file_type == 'py':
            threading.Thread(target=run_script, args=(file_path, script_owner_id, user_folder, file_name, call.message)).start()
        elif file_type == 'js':
            threading.Thread(target=run_js_script, args=(file_path, script_owner_id, user_folder, file_name, call.message)).start()

        time.sleep(1.5) 
        
        # Route back to file control view
        call.data = pack_callback(f"file_{script_owner_id}_{file_name}")
        file_control_callback(call)

    except Exception as e:
        logger.error(f"Error in restart_bot_callback: {e}", exc_info=True)

def delete_bot_callback(call):
    try:
        bot.answer_callback_query(call.id)
    except:
        pass
    try:
        unpacked = unpack_callback(call.data) if len(call.data) == 16 else call.data
        _, script_owner_id_str, file_name = unpacked.split('_', 2)
        script_owner_id = int(script_owner_id_str)
        requesting_user_id = call.from_user.id
        chat_id_for_reply = call.message.chat.id

        if not (requesting_user_id == script_owner_id or requesting_user_id in admin_ids):
            try: bot.answer_callback_query(call.id, "⚠️ Permission denied.", show_alert=True)
            except: pass
            return

        user_files_list = user_files.get(script_owner_id, [])
        file_info = next((f for f in user_files_list if f[0] == file_name), None)
        if not file_info:
            try: bot.answer_callback_query(call.id, "⚠️ File not found.", show_alert=True)
            except: pass
            return


        try: bot.answer_callback_query(call.id, f"🗑️ Deleting...")
        except: pass
        
        script_key = f"{script_owner_id}_{file_name}"
        if is_bot_running(script_owner_id, file_name):
            process_info = bot_scripts.get(script_key)
            if process_info: kill_process_tree(process_info)
            if script_key in bot_scripts: del bot_scripts[script_key]
            time.sleep(0.5) 

        user_folder = get_user_folder(script_owner_id)
        file_path = os.path.join(user_folder, file_name)
        log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass
        if os.path.exists(log_path):
            try: os.remove(log_path)
            except: pass

        remove_user_file_db(script_owner_id, file_name)
        
        try:
            bot.edit_message_text(f"🗑️ Record `{file_name}` deleted successfully.", chat_id_for_reply, call.message.message_id, parse_mode='Markdown')
        except: pass

    except Exception as e:
        logger.error(f"Error in delete_bot_callback: {e}", exc_info=True)

def logs_bot_callback(call):
    try:
        bot.answer_callback_query(call.id)
    except:
        pass
    try:
        unpacked = unpack_callback(call.data) if len(call.data) == 16 else call.data
        _, script_owner_id_str, file_name = unpacked.split('_', 2)
        script_owner_id = int(script_owner_id_str)
        requesting_user_id = call.from_user.id
        chat_id_for_reply = call.message.chat.id

        if not (requesting_user_id == script_owner_id or requesting_user_id in admin_ids):
            try: bot.answer_callback_query(call.id, "⚠️ Permission denied.", show_alert=True)
            except: pass
            return

        user_files_list = user_files.get(script_owner_id, [])
        file_info = next((f for f in user_files_list if f[0] == file_name), None)
        if not file_info:
            try: bot.answer_callback_query(call.id, "⚠️ File not found.", show_alert=True)
            except: pass
            return


        user_folder = get_user_folder(script_owner_id)
        log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        if not os.path.exists(log_path):
            try: bot.answer_callback_query(call.id, f"⚠️ No logs found.", show_alert=True)
            except: pass
            return

        try:
            log_content = ""
            file_size = os.path.getsize(log_path)
            max_log_kb = 20 # Tail small amount to avoid freeze
            
            if file_size == 0: 
                log_content = "(Log empty)"
            elif file_size > max_log_kb * 1024:
                 with open(log_path, 'rb') as f: 
                     f.seek(-max_log_kb * 1024, os.SEEK_END)
                     log_bytes = f.read()
                 log_content = log_bytes.decode('utf-8', errors='ignore')
                 log_content = f"(Last {max_log_kb} KB)\n...\n" + log_content
            else:
                 with open(log_path, 'r', encoding='utf-8', errors='ignore') as f: 
                     log_content = f.read()

            max_tg_msg = 3000
            if len(log_content) > max_tg_msg:
                log_content = log_content[-max_tg_msg:]
                first_nl = log_content.find('\n')
                if first_nl != -1: log_content = "...\n" + log_content[first_nl+1:]
                
            if not log_content.strip(): log_content = "(No visible content)"

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 Refresh Logs", callback_data=pack_callback(f'logs_{script_owner_id}_{file_name}')))
            markup.add(types.InlineKeyboardButton("🔙 Back to Controls", callback_data=pack_callback(f'file_{script_owner_id}_{file_name}')))
            
            text = f"📜 *Logs for* `{file_name}`:\n```\n{log_content}\n```"
            bot.edit_message_text(text, chat_id_for_reply, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error reading/sending log: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Error in logs_bot_callback: {e}", exc_info=True)

def speed_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    start_cb_ping_time = time.time() 
    try:
        bot.edit_message_text("🏃 Testing speed...", chat_id, call.message.message_id)
        bot.send_chat_action(chat_id, 'typing') 
        response_time = round((time.time() - start_cb_ping_time) * 1000, 2)
        status = "🔓 Unlocked" if not bot_locked else "🔒 Locked"
        if user_id == OWNER_ID: user_level = "🤍 Owner"
        elif user_id in admin_ids: user_level = "🌙 Admin"
        elif user_id in user_subscriptions and user_subscriptions[user_id].get('expiry', datetime.min) > datetime.now(): user_level = "⭐ Premium"
        else: user_level = "🆓 Free User"
        speed_msg = (f"⚡ Bot Speed & Status:\n\n⏱️ API Response Time: {response_time} ms\n"
                     f"🚦 Bot Status: {status}\n"
                     f"👤 Your Level: {user_level}")
        bot.answer_callback_query(call.id) 
        bot.edit_message_text(speed_msg, chat_id, call.message.message_id, reply_markup=create_main_menu_inline(user_id))
    except Exception as e:
         logger.error(f"Error during speed test (cb): {e}", exc_info=True)
         bot.answer_callback_query(call.id, "Error in speed test.", show_alert=True)
         try: bot.edit_message_text("〽️ Main Menu", chat_id, call.message.message_id, reply_markup=create_main_menu_inline(user_id))
         except Exception: pass

def back_to_main_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    limit_str = str(file_limit) if file_limit != float('inf') else "Unlimited"
    expiry_info = ""
    if user_id == OWNER_ID: user_status = "🤍 Owner"
    elif user_id in admin_ids: user_status = "🌙 Admin"
    elif user_id in user_subscriptions:
        expiry_date = user_subscriptions[user_id].get('expiry')
        if expiry_date and expiry_date > datetime.now():
            user_status = "⭐ Premium"; days_left = (expiry_date - datetime.now()).days
            expiry_info = f"\n⏳ Subscription expires in: {days_left} days"
        else: user_status = "🆓 Free User (Expired Sub)"
    else: user_status = "🆓 Free User"
    main_menu_text = (f"〽️ Welcome back, {call.from_user.first_name}!\n\n🆔 ID: `{user_id}`\n"
                      f"🔰 Status: {user_status}{expiry_info}\n📁 Files: {current_files} / {limit_str}\n\n"
                      f"👇 Use buttons or type commands.")
    try:
        bot.answer_callback_query(call.id)
        bot.edit_message_text(main_menu_text, chat_id, call.message.message_id,
                              reply_markup=create_main_menu_inline(user_id), parse_mode='Markdown')
    except telebot.apihelper.ApiTelegramException as e:
         if "message is not modified" in str(e): logger.warning("Msg not modified (back_to_main).")
         else: logger.error(f"API error on back_to_main: {e}")
    except Exception as e: logger.error(f"Error handling back_to_main: {e}", exc_info=True)

# --- Admin Callback Implementations ---
def subscription_management_callback(call):
    bot.answer_callback_query(call.id)
    try:
        bot.edit_message_text("💳 Subscription Management\nSelect action:",
                              call.message.chat.id, call.message.message_id, reply_markup=create_subscription_menu())
    except Exception as e: logger.error(f"Error showing sub menu: {e}")

def stats_callback(call):
    bot.answer_callback_query(call.id)
    _logic_statistics(call.message)
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                      reply_markup=create_main_menu_inline(call.from_user.id))
    except Exception as e:
        logger.error(f"Error updating menu after stats_callback: {e}")

def lock_bot_callback(call):
    global bot_locked; bot_locked = True
    logger.warning(f"Bot locked by Admin {call.from_user.id}")
    bot.answer_callback_query(call.id, "🔒 Bot locked.")
    try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=create_main_menu_inline(call.from_user.id))
    except Exception as e: logger.error(f"Error updating menu (lock): {e}")

def unlock_bot_callback(call):
    global bot_locked; bot_locked = False
    logger.warning(f"Bot unlocked by Admin {call.from_user.id}")
    bot.answer_callback_query(call.id, "🔓 Bot unlocked.")
    try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=create_main_menu_inline(call.from_user.id))
    except Exception as e: logger.error(f"Error updating menu (unlock): {e}")

def run_all_scripts_callback(call):
    _logic_run_all_scripts(call)

def broadcast_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "📢 Send message to broadcast.\n/cancel to abort.")
    bot.register_next_step_handler(msg, process_broadcast_message)

def process_broadcast_message(message):
    user_id = message.from_user.id
    if user_id not in admin_ids: bot.reply_to(message, "⚠️ Not authorized."); return
    if message.text and message.text.lower() == '/cancel': bot.reply_to(message, "Broadcast cancelled."); return

    broadcast_content = message.text
    if not broadcast_content and not (message.photo or message.video or message.document or message.sticker or message.voice or message.audio):
         bot.reply_to(message, "⚠️ Cannot broadcast empty message. Send text or media, or /cancel.")
         msg = bot.send_message(message.chat.id, "📢 Send broadcast message or /cancel.")
         bot.register_next_step_handler(msg, process_broadcast_message)
         return

    target_count = len(active_users)
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("✅ Confirm & Send", callback_data=f"confirm_broadcast_{message.message_id}"),
               types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_broadcast"))

    preview_text = broadcast_content[:1000].strip() if broadcast_content else "(Media message)"
    bot.reply_to(message, f"⚠️ Confirm Broadcast:\n\n```\n{preview_text}\n```\n" 
                          f"To **{target_count}** users. Sure?", reply_markup=markup, parse_mode='Markdown')

def handle_confirm_broadcast(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    if user_id not in admin_ids: bot.answer_callback_query(call.id, "⚠️ Admin only.", show_alert=True); return
    try:
        original_message = call.message.reply_to_message
        if not original_message: raise ValueError("Could not retrieve original message.")

        broadcast_text = None
        broadcast_photo_id = None
        broadcast_video_id = None

        if original_message.text:
            broadcast_text = original_message.text
        elif original_message.photo:
            broadcast_photo_id = original_message.photo[-1].file_id
        elif original_message.video:
            broadcast_video_id = original_message.video.file_id
        else:
            raise ValueError("Message has no text or supported media for broadcast.")

        bot.answer_callback_query(call.id, "🚀 Starting broadcast...")
        bot.edit_message_text(f"📢 Broadcasting to {len(active_users)} users...",
                              chat_id, call.message.message_id, reply_markup=None)
        thread = threading.Thread(target=execute_broadcast, args=(
            broadcast_text, broadcast_photo_id, broadcast_video_id, 
            original_message.caption if (broadcast_photo_id or broadcast_video_id) else None,
            chat_id))
        thread.start()
    except ValueError as ve: 
        logger.error(f"Error retrieving msg for broadcast confirm: {ve}")
        bot.edit_message_text(f"❌ Error starting broadcast: {ve}", chat_id, call.message.message_id, reply_markup=None)
    except Exception as e:
        logger.error(f"Error in handle_confirm_broadcast: {e}", exc_info=True)
        bot.edit_message_text("❌ Unexpected error during broadcast confirm.", chat_id, call.message.message_id, reply_markup=None)

def handle_cancel_broadcast(call):
    bot.answer_callback_query(call.id, "Broadcast cancelled.")
    bot.delete_message(call.message.chat.id, call.message.message_id)
    if call.message.reply_to_message:
        try: bot.delete_message(call.message.chat.id, call.message.reply_to_message.message_id)
        except: pass

def execute_broadcast(broadcast_text, photo_id, video_id, caption, admin_chat_id):
    sent_count = 0; failed_count = 0; blocked_count = 0
    start_exec_time = time.time() 
    users_to_broadcast = list(active_users); total_users = len(users_to_broadcast)
    logger.info(f"Executing broadcast to {total_users} users.")
    batch_size = 25; delay_batches = 1.5

    for i, user_id_bc in enumerate(users_to_broadcast):
        try:
            if broadcast_text:
                bot.send_message(user_id_bc, broadcast_text, parse_mode='Markdown')
            elif photo_id:
                bot.send_photo(user_id_bc, photo_id, caption=caption, parse_mode='Markdown' if caption else None)
            elif video_id:
                bot.send_video(user_id_bc, video_id, caption=caption, parse_mode='Markdown' if caption else None)
            sent_count += 1
        except telebot.apihelper.ApiTelegramException as e:
            err_desc = str(e).lower()
            if any(s in err_desc for s in ["bot was blocked", "user is deactivated", "chat not found", "kicked from", "restricted"]): 
                logger.warning(f"Broadcast failed to {user_id_bc}: User blocked/inactive.")
                blocked_count += 1
            elif "flood control" in err_desc or "too many requests" in err_desc:
                retry_after = 5; match = re.search(r"retry after (\d+)", err_desc)
                if match: retry_after = int(match.group(1)) + 1 
                logger.warning(f"Flood control. Sleeping {retry_after}s...")
                time.sleep(retry_after)
                try:
                    if broadcast_text: bot.send_message(user_id_bc, broadcast_text, parse_mode='Markdown')
                    elif photo_id: bot.send_photo(user_id_bc, photo_id, caption=caption, parse_mode='Markdown' if caption else None)
                    elif video_id: bot.send_video(user_id_bc, video_id, caption=caption, parse_mode='Markdown' if caption else None)
                    sent_count += 1
                except Exception as e_retry: logger.error(f"Broadcast retry failed to {user_id_bc}: {e_retry}"); failed_count +=1
            else: logger.error(f"Broadcast failed to {user_id_bc}: {e}"); failed_count += 1
        except Exception as e: logger.error(f"Unexpected error broadcasting to {user_id_bc}: {e}"); failed_count += 1

        if (i + 1) % batch_size == 0 and i < total_users - 1:
            logger.info(f"Broadcast batch {i//batch_size + 1} sent. Sleeping {delay_batches}s...")
            time.sleep(delay_batches)
        elif i % 5 == 0: time.sleep(0.2) 

    duration = round(time.time() - start_exec_time, 2)
    result_msg = (f"📢 Broadcast Complete!\n\n✅ Sent: {sent_count}\n❌ Failed: {failed_count}\n"
                  f"🚫 Blocked/Inactive: {blocked_count}\n👥 Targets: {total_users}\n⏱️ Duration: {duration}s")
    logger.info(result_msg)
    try: bot.send_message(admin_chat_id, result_msg)
    except Exception as e: logger.error(f"Failed to send broadcast result to admin {admin_chat_id}: {e}")

def admin_panel_callback(call):
    bot.answer_callback_query(call.id)
    try:
        bot.edit_message_text("👑 Admin Panel\nManage admins (Owner actions may be restricted).",
                              call.message.chat.id, call.message.message_id, reply_markup=create_admin_panel())
    except Exception as e: logger.error(f"Error showing admin panel: {e}")

def add_admin_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "👑 Enter User ID to promote to Admin.\n/cancel to abort.")
    bot.register_next_step_handler(msg, process_add_admin_id)

def process_add_admin_id(message):
    owner_id_check = message.from_user.id 
    if owner_id_check != OWNER_ID: bot.reply_to(message, "⚠️ Owner only."); return
    if message.text.lower() == '/cancel': bot.reply_to(message, "Admin promotion cancelled."); return
    try:
        new_admin_id = int(message.text.strip())
        if new_admin_id <= 0: raise ValueError("ID must be positive")
        if new_admin_id == OWNER_ID: bot.reply_to(message, "⚠️ Owner is already Owner."); return
        if new_admin_id in admin_ids: bot.reply_to(message, f"⚠️ User `{new_admin_id}` already Admin."); return
        add_admin_db(new_admin_id) 
        logger.warning(f"Admin {new_admin_id} added by Owner {owner_id_check}.")
        bot.reply_to(message, f"✅ User `{new_admin_id}` promoted to Admin.")
        try: bot.send_message(new_admin_id, "🎉 Congrats! You are now an Admin.")
        except Exception as e: logger.error(f"Failed to notify new admin {new_admin_id}: {e}")
    except ValueError:
        bot.reply_to(message, "⚠️ Invalid ID. Send numerical ID or /cancel.")
        msg = bot.send_message(message.chat.id, "👑 Enter User ID to promote or /cancel.")
        bot.register_next_step_handler(msg, process_add_admin_id)
    except Exception as e: logger.error(f"Error processing add admin: {e}", exc_info=True); bot.reply_to(message, "Error.")

def remove_admin_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "👑 Enter User ID of Admin to remove.\n/cancel to abort.")
    bot.register_next_step_handler(msg, process_remove_admin_id)

def process_remove_admin_id(message):
    owner_id_check = message.from_user.id
    if owner_id_check != OWNER_ID: bot.reply_to(message, "⚠️ Owner only."); return
    if message.text.lower() == '/cancel': bot.reply_to(message, "Admin removal cancelled."); return
    try:
        admin_id_remove = int(message.text.strip())
        if admin_id_remove <= 0: raise ValueError("ID must be positive")
        if admin_id_remove == OWNER_ID: bot.reply_to(message, "⚠️ Owner cannot remove self."); return
        if admin_id_remove not in admin_ids: bot.reply_to(message, f"⚠️ User `{admin_id_remove}` not Admin."); return
        if remove_admin_db(admin_id_remove): 
            logger.warning(f"Admin {admin_id_remove} removed by Owner {owner_id_check}.")
            bot.reply_to(message, f"✅ Admin `{admin_id_remove}` removed.")
            try: bot.send_message(admin_id_remove, "ℹ️ You are no longer an Admin.")
            except Exception as e: logger.error(f"Failed to notify removed admin {admin_id_remove}: {e}")
        else: bot.reply_to(message, f"❌ Failed to remove admin `{admin_id_remove}`. Check logs.")
    except ValueError:
        bot.reply_to(message, "⚠️ Invalid ID. Send numerical ID or /cancel.")
        msg = bot.send_message(message.chat.id, "👑 Enter Admin ID to remove or /cancel.")
        bot.register_next_step_handler(msg, process_remove_admin_id)
    except Exception as e: logger.error(f"Error processing remove admin: {e}", exc_info=True); bot.reply_to(message, "Error.")

def list_admins_callback(call):
    bot.answer_callback_query(call.id)
    try:
        admin_list_str = "\n".join(f"- `{aid}` {'(Owner)' if aid == OWNER_ID else ''}" for aid in sorted(list(admin_ids)))
        if not admin_list_str: admin_list_str = "(No Owner/Admins configured!)"
        bot.edit_message_text(f"👑 Current Admins:\n\n{admin_list_str}", call.message.chat.id,
                              call.message.message_id, reply_markup=create_admin_panel(), parse_mode='Markdown')
    except Exception as e: logger.error(f"Error listing admins: {e}")

def change_password_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "🔑 Enter the new bot password.\n/cancel to abort.")
    bot.register_next_step_handler(msg, process_change_password)

def process_change_password(message):
    global BOT_PASSWORD
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "⚠️ Owner only.")
        return
    if message.text and message.text.strip().lower() == '/cancel':
        bot.reply_to(message, "Password change cancelled.")
        return
    new_password = message.text.strip() if message.text else ""
    if len(new_password) < 3:
        bot.reply_to(message, "⚠️ Password too short (minimum 3 characters). Try again.")
        msg = bot.send_message(message.chat.id, "🔑 Enter the new bot password.\n/cancel to abort.")
        bot.register_next_step_handler(msg, process_change_password)
        return
    BOT_PASSWORD = new_password
    logger.warning(f"Bot password changed by Owner {message.from_user.id}.")
    bot.reply_to(message, f"✅ Bot password has been changed successfully.\n\nNew password: `{BOT_PASSWORD}`", parse_mode='Markdown')

def toggle_referral_callback(call):
    global referral_enabled
    bot.answer_callback_query(call.id)
    referral_enabled = not referral_enabled
    status = "ON ✅" if referral_enabled else "OFF ❌"
    logger.warning(f"Referral system toggled to {status} by Owner {call.from_user.id}.")
    try:
        bot.edit_message_text(
            f"👑 Admin Panel\nReferral system is now: **{status}**",
            call.message.chat.id, call.message.message_id,
            reply_markup=create_admin_panel(), parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error toggling referral: {e}")

def user_management_callback(call):
    bot.answer_callback_query(call.id)
    try:
        bot.edit_message_text(
            "👥 User Management\nSelect an option below:",
            call.message.chat.id, call.message.message_id,
            reply_markup=create_user_management_menu()
        )
    except Exception as e:
        logger.error(f"Error showing user management menu: {e}")

def users_list_callback(call):
    bot.answer_callback_query(call.id, "Generating users list, please wait...")
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('SELECT user_id FROM active_users')
        users = c.fetchall()
        conn.close()

        if not users:
            bot.send_message(call.message.chat.id, "No active users found.")
            return

        with io.StringIO() as f:
            f.write(f"Total Active Users: {len(users)}\n")
            f.write("-" * 40 + "\n")
            for i, (uid,) in enumerate(users):
                if i % 10 == 0: time.sleep(0.1) # Avoid flood limits
                try:
                    chat = bot.get_chat(uid)
                    username = f"@{chat.username}" if chat.username else "No Username"
                    name = chat.first_name or "Unknown"
                    f.write(f"ID: {uid} | Name: {name} | Username: {username}\n")
                except Exception:
                    f.write(f"ID: {uid} | Name: Unknown | Username: Unknown (Cannot fetch)\n")
            
            f.seek(0)
            bot.send_document(call.message.chat.id, f, visible_file_name="users_list.txt", caption=f"👥 Total Active Users: {len(users)}")
    except Exception as e:
        logger.error(f"Error exporting users list: {e}")
        bot.send_message(call.message.chat.id, "❌ Error generating users list.")

def banned_users_callback(call):
    bot.answer_callback_query(call.id, "Generating banned users list...")
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('SELECT user_id, is_perm_banned, temp_ban_until FROM user_security WHERE is_perm_banned = 1 OR temp_ban_until IS NOT NULL')
        banned = c.fetchall()
        conn.close()

        if not banned:
            bot.send_message(call.message.chat.id, "No banned users found.")
            return

        with io.StringIO() as f:
            f.write(f"Total Banned Users: {len(banned)}\n")
            f.write("-" * 40 + "\n")
            for uid, is_perm, temp_until in banned:
                status = "Permanently Banned" if is_perm else f"Temporarily Banned until {temp_until}"
                f.write(f"ID: {uid} | Status: {status}\n")
            
            f.seek(0)
            bot.send_document(call.message.chat.id, f, visible_file_name="banned_users.txt", caption=f"🚫 Total Banned Users: {len(banned)}")
    except Exception as e:
        logger.error(f"Error exporting banned users list: {e}")
        bot.send_message(call.message.chat.id, "❌ Error generating banned users list.")

def ban_user_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "🚫 Enter User ID to ban permanently.\n/cancel to abort.")
    bot.register_next_step_handler(msg, process_ban_user_id)

def process_ban_user_id(message):
    if message.from_user.id not in admin_ids: return
    if message.text.lower() == '/cancel': bot.reply_to(message, "Ban cancelled."); return
    try:
        ban_id = int(message.text.strip())
        if ban_id in admin_ids: bot.reply_to(message, "⚠️ Cannot ban an admin/owner."); return
        
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO user_security (user_id) VALUES (?)', (ban_id,))
        c.execute('UPDATE user_security SET is_perm_banned = 1 WHERE user_id = ?', (ban_id,))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, f"✅ User `{ban_id}` has been permanently banned.")
        try: bot.send_message(ban_id, "🚫 You have been permanently banned by an admin.")
        except: pass
    except ValueError:
        bot.reply_to(message, "⚠️ Invalid ID format.")
    except Exception as e:
        logger.error(f"Error banning user: {e}")
        bot.reply_to(message, "❌ Error processing ban.")

def unban_user_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "✅ Enter User ID to unban (clears both perm and temp bans).\n/cancel to abort.")
    bot.register_next_step_handler(msg, process_unban_user_id)

def process_unban_user_id(message):
    if message.from_user.id not in admin_ids: return
    if message.text.lower() == '/cancel': bot.reply_to(message, "Unban cancelled."); return
    try:
        unban_id = int(message.text.strip())
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('UPDATE user_security SET is_perm_banned = 0, temp_ban_until = NULL, password_failures = 0 WHERE user_id = ?', (unban_id,))
        affected = c.rowcount
        conn.commit()
        conn.close()
        
        if affected > 0:
            bot.reply_to(message, f"✅ User `{unban_id}` has been unbanned.")
            try: bot.send_message(unban_id, "✅ Your ban has been lifted. You can now use the bot.")
            except: pass
        else:
            bot.reply_to(message, f"⚠️ User `{unban_id}` not found in security database or was not banned.")
    except ValueError:
        bot.reply_to(message, "⚠️ Invalid ID format.")
    except Exception as e:
        logger.error(f"Error unbanning user: {e}")
        bot.reply_to(message, "❌ Error processing unban.")

def add_subscription_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "💳 Enter User ID & days (e.g., `12345678 30`).\n/cancel to abort.")
    bot.register_next_step_handler(msg, process_add_subscription_details)

def process_add_subscription_details(message):
    admin_id_check = message.from_user.id 
    if admin_id_check not in admin_ids: bot.reply_to(message, "⚠️ Not authorized."); return
    if message.text.lower() == '/cancel': bot.reply_to(message, "Sub add cancelled."); return
    try:
        parts = message.text.split();
        if len(parts) != 2: raise ValueError("Incorrect format")
        sub_user_id = int(parts[0].strip()); days = int(parts[1].strip())
        if sub_user_id <= 0 or days <= 0: raise ValueError("User ID/days must be positive")

        current_expiry = user_subscriptions.get(sub_user_id, {}).get('expiry')
        start_date_new_sub = datetime.now()
        if current_expiry and current_expiry > start_date_new_sub: start_date_new_sub = current_expiry
        new_expiry = start_date_new_sub + timedelta(days=days)
        save_subscription(sub_user_id, new_expiry)

        logger.info(f"Sub for {sub_user_id} by admin {admin_id_check}. Expiry: {new_expiry:%Y-%m-%d}")
        bot.reply_to(message, f"✅ Sub for `{sub_user_id}` by {days} days.\nNew expiry: {new_expiry:%Y-%m-%d}")
        try: bot.send_message(sub_user_id, f"🎉 Sub activated/extended by {days} days! Expires: {new_expiry:%Y-%m-%d}.")
        except Exception as e: logger.error(f"Failed to notify {sub_user_id} of new sub: {e}")
    except ValueError as e:
        bot.reply_to(message, f"⚠️ Invalid: {e}. Format: `ID days` or /cancel.")
        msg = bot.send_message(message.chat.id, "💳 Enter User ID & days, or /cancel.")
        bot.register_next_step_handler(msg, process_add_subscription_details)
    except Exception as e: logger.error(f"Error processing add sub: {e}", exc_info=True); bot.reply_to(message, "Error.")

def remove_subscription_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "💳 Enter User ID to remove sub.\n/cancel to abort.")
    bot.register_next_step_handler(msg, process_remove_subscription_id)

def process_remove_subscription_id(message):
    admin_id_check = message.from_user.id
    if admin_id_check not in admin_ids: bot.reply_to(message, "⚠️ Not authorized."); return
    if message.text.lower() == '/cancel': bot.reply_to(message, "Sub removal cancelled."); return
    try:
        sub_user_id_remove = int(message.text.strip())
        if sub_user_id_remove <= 0: raise ValueError("ID must be positive")
        if sub_user_id_remove not in user_subscriptions:
            bot.reply_to(message, f"⚠️ User `{sub_user_id_remove}` no active sub in memory."); return
        remove_subscription_db(sub_user_id_remove) 
        logger.warning(f"Sub removed for {sub_user_id_remove} by admin {admin_id_check}.")
        bot.reply_to(message, f"✅ Sub for `{sub_user_id_remove}` removed.")
        try: bot.send_message(sub_user_id_remove, "ℹ️ Your subscription removed by admin.")
        except Exception as e: logger.error(f"Failed to notify {sub_user_id_remove} of sub removal: {e}")
    except ValueError:
        bot.reply_to(message, "⚠️ Invalid ID. Send numerical ID or /cancel.")
        msg = bot.send_message(message.chat.id, "💳 Enter User ID to remove sub from, or /cancel.")
        bot.register_next_step_handler(msg, process_remove_subscription_id)
    except Exception as e: logger.error(f"Error processing remove sub: {e}", exc_info=True); bot.reply_to(message, "Error.")

def check_subscription_init_callback(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "💳 Enter User ID to check sub.\n/cancel to abort.")
    bot.register_next_step_handler(msg, process_check_subscription_id)

def process_check_subscription_id(message):
    admin_id_check = message.from_user.id
    if admin_id_check not in admin_ids: bot.reply_to(message, "⚠️ Not authorized."); return
    if message.text.lower() == '/cancel': bot.reply_to(message, "Sub check cancelled."); return
    try:
        sub_user_id_check = int(message.text.strip())
        if sub_user_id_check <= 0: raise ValueError("ID must be positive")
        if sub_user_id_check in user_subscriptions:
            expiry_dt = user_subscriptions[sub_user_id_check].get('expiry')
            if expiry_dt:
                if expiry_dt > datetime.now():
                    days_left = (expiry_dt - datetime.now()).days
                    bot.reply_to(message, f"✅ User `{sub_user_id_check}` active sub.\nExpires: {expiry_dt:%Y-%m-%d %H:%M:%S} ({days_left} days left).")
                else:
                    bot.reply_to(message, f"⚠️ User `{sub_user_id_check}` expired sub (On: {expiry_dt:%Y-%m-%d %H:%M:%S}).")
                    remove_subscription_db(sub_user_id_check)
            else: bot.reply_to(message, f"⚠️ User `{sub_user_id_check}` in sub list, but expiry missing. Re-add if needed.")
        else: bot.reply_to(message, f"ℹ️ User `{sub_user_id_check}` no active sub record.")
    except ValueError:
        bot.reply_to(message, "⚠️ Invalid ID. Send numerical ID or /cancel.")
        msg = bot.send_message(message.chat.id, "💳 Enter User ID to check, or /cancel.")
        bot.register_next_step_handler(msg, process_check_subscription_id)
    except Exception as e: logger.error(f"Error processing check sub: {e}", exc_info=True); bot.reply_to(message, "Error.")

# --- Cleanup Function ---
def cleanup():
    logger.warning("Shutdown. Cleaning up processes...")
    script_keys_to_stop = list(bot_scripts.keys()) 
    if not script_keys_to_stop: logger.info("No scripts running. Exiting."); return
    logger.info(f"Stopping {len(script_keys_to_stop)} scripts...")
    for key in script_keys_to_stop:
        if key in bot_scripts: logger.info(f"Stopping: {key}"); kill_process_tree(bot_scripts[key])
        else: logger.info(f"Script {key} already removed.")
    logger.warning("Cleanup finished.")
atexit.register(cleanup)


# --- Process Monitor Thread ---
def process_monitor():
    while True:
        try:
            with DATA_LOCK:
                keys = list(bot_scripts.keys())
            for key in keys:
                script_info = bot_scripts.get(key)
                if not script_info: continue
                # Check if running
                proc = script_info.get('process')
                if proc:
                    try:
                        is_running = proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
                        if not is_running:
                            logger.info(f"Process {key} is zombie/stopped. Cleaning up.")
                            kill_process_tree(script_info)
                            with DATA_LOCK:
                                if key in bot_scripts:
                                    del bot_scripts[key]
                    except Exception as e:
                        logger.error(f"Error checking {key}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Monitor error: {e}", exc_info=True)
            
        # GC: Clean up old callbacks
        try:
            with sqlite3.connect(DATABASE_PATH, check_same_thread=False) as conn:
                c = conn.cursor()
                c.execute("DELETE FROM callback_registry WHERE created_at < datetime('now', '-1 day')")
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to cleanup callbacks: {e}")
            
        
        # --- Scheduled DB Maintenance & Backups (Part 7) ---
        try:
            current_time = int(time.time())
            if not hasattr(process_monitor, 'last_backup'):
                process_monitor.last_backup = current_time
            
            # Run every 24 hours
            if current_time - process_monitor.last_backup > 86400:
                logger.info("Running scheduled database maintenance and backup...")
                with sqlite3.connect(DATABASE_PATH, check_same_thread=False) as conn:
                    # Maintenance
                    conn.execute("VACUUM")
                    conn.execute("ANALYZE")
                    # Backup
                    backup_path = DATABASE_PATH + '.backup'
                    with sqlite3.connect(backup_path) as bck_conn:
                        conn.backup(bck_conn)
                logger.info("Database maintenance and backup completed.")
                process_monitor.last_backup = current_time
        except Exception as e:
            logger.error(f"Failed to perform DB maintenance: {e}", exc_info=True)
        # ---------------------------------------------------
        time.sleep(10)

def start_process_monitor():
    t = threading.Thread(target=process_monitor, daemon=True)
    t.start()
    logger.info("Process monitor background thread started.")
# ------------------------------


# --- Process Restoration ---
def restore_processes():
    logger.info("Restoring previously running processes from database...")
    try:
        with sqlite3.connect(DATABASE_PATH, check_same_thread=False) as conn:
            c = conn.cursor()
            c.execute('SELECT script_key, user_id, file_name, language FROM running_processes')
            rows = c.fetchall()
            for row in rows:
                script_key, user_id, file_name, language = row
                logger.info(f"Attempting to restore {script_key}...")
                # Note: Actual subprocess restoration would depend on the run_script functions,
                # For now, we clean them up as zombies if they are not actually running.
                with DATA_LOCK:
                    if script_key not in bot_scripts:
                         c.execute('DELETE FROM running_processes WHERE script_key = ?', (script_key,))
            conn.commit()
    except Exception as e:
        logger.error(f"Error restoring processes: {e}", exc_info=True)
# ------------------------------

# --- Main Execution ---
if __name__ == '__main__':
    logger.info("="*40 + "\n🤖 Bot Starting Up...\n" + f"🐍 Python: {sys.version.split()[0]}\n" +
                f"🔧 Base Dir: {BASE_DIR}\n📁 Upload Dir: {UPLOAD_BOTS_DIR}\n" +
                f"📊 Data Dir: {IROTECH_DIR}\n🔑 Owner ID: {OWNER_ID}\n🛡️ Admins: {admin_ids}\n" + "="*40)
    keep_alive()
    logger.info("🚀 Starting polling...")
    while True:
        try:
            bot.infinity_polling(logger_level=logging.INFO, timeout=60, long_polling_timeout=30)
        except requests.exceptions.ReadTimeout: logger.warning("Polling ReadTimeout. Restarting in 5s..."); time.sleep(5)
        except requests.exceptions.ConnectionError as ce: logger.error(f"Polling ConnectionError: {ce}. Retrying in 15s..."); time.sleep(15)
        except Exception as e:
            logger.critical(f"💥 Unrecoverable polling error: {e}", exc_info=True)
            logger.info("Restarting polling in 30s due to critical error..."); time.sleep(30)
        finally: logger.warning("Polling attempt finished. Will restart if in loop."); time.sleep(1)
