
# --- Safe Back Navigation & State Preserver ---
@bot.callback_query_handler(func=lambda c: c.data in ['back_to_services', 'back_to_cats', 'cancel_order', 'back_cat', 'back_srv'])
def safe_back_handler(c):
    chat_id = c.message.chat.id
    bot.clear_step_handler_by_chat_id(chat_id)
    try:
        bot.answer_callback_query(c.id)
    except:
        pass

    if 'cat' in c.data:
        if 'show_categories' in globals():
            show_categories(chat_id, c.message.message_id)
        elif 'send_categories' in globals():
            send_categories(c.message)
    else:
        if 'show_services' in globals():
            show_services(chat_id, c.message.message_id)
        elif 'send_services' in globals():
            send_services(c.message)

import keep_alive
keep_alive.keep_alive()
import telebot
from telebot import types
import requests
import sqlite3
import datetime
import os
import time
import re
import threading
import random

# --- কনফিগারেশন ---
BOT_TOKEN = "8656424951:AAHEUoOikTfN2RW-ztfSzR93ktRdvJvwIpY"
SUPER_ADMIN_ID = 8851327780
SMM_API_URL = "https://my.smmgen.com/api/v2"
SMM_API_KEY = "3a822188552bd0017f91c72d06e46832"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

bot = telebot.TeleBot(BOT_TOKEN)

user_last_click = {}
order_lock = set()
deposit_state = {}
user_flow = {}
user_recent_msgs = {}

def is_spamming(user_id):
    now = time.time()
    if user_id in user_last_click and (now - user_last_click[user_id]) < 0.7:
        return True
    user_last_click[user_id] = now
    return False

def track_msg(user_id, msg_id):
    if user_id not in user_recent_msgs:
        user_recent_msgs[user_id] = []
    user_recent_msgs[user_id].append(msg_id)
    if len(user_recent_msgs[user_id]) > 30:
        user_recent_msgs[user_id].pop(0)

# --- ডাটাবেজ ইনিশিয়ালাইজেশন ---
def init_db():
    conn = sqlite3.connect("boost_enterprise_v4.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY, 
                    value TEXT
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    main_balance REAL DEFAULT 0.0,
                    bonus_balance REAL DEFAULT 0.0,
                    referral_balance_bdt REAL DEFAULT 0.0,
                    total_spent REAL DEFAULT 0.0,
                    role TEXT DEFAULT 'user',
                    referrer_id INTEGER DEFAULT 0,
                    has_deposited INTEGER DEFAULT 0,
                    fraud_strikes INTEGER DEFAULT 0,
                    last_daily_claim TEXT DEFAULT '',
                    is_banned INTEGER DEFAULT 0,
                    joined_at TEXT
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS services (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER,
                    sub_category TEXT,
                    tier_type TEXT,
                    refill_type TEXT,
                    name TEXT,
                    smm_service_id INTEGER UNIQUE,
                    base_price REAL,
                    min_qty INTEGER DEFAULT 10,
                    max_qty INTEGER DEFAULT 100000,
                    is_special INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
                    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    smm_order_id TEXT,
                    service_name TEXT,
                    link TEXT,
                    quantity INTEGER,
                    charge REAL,
                    status TEXT,
                    date TEXT
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS deposits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    method TEXT,
                    trx_id TEXT UNIQUE,
                    amount_bdt REAL,
                    usd_credited REAL,
                    photo_file_id TEXT,
                    status TEXT,
                    date TEXT
                 )''')
    
    defaults = [
        ('profit_margin', '27.56'),
        ('referral_pct', '20.0'),
        ('first_dep_bonus', '7.0'),
        ('daily_bonus_amount', '0.00013'),
        ('bonus_merge_threshold', '0.50'),
        ('ref_merge_threshold_bdt', '125.0'),
        ('usd_bdt_rate', '125.0'),
        ('min_deposit_bdt', '25.0'),
        ('maintenance', '0'),
        ('notice', '🚀 𝗪𝗲𝗹𝗰𝗼𝗺𝗲 𝘁𝗼 𝗦𝗼𝗰𝗶𝗮𝗹𝗕𝗼𝗼𝘀𝘁 𝗕𝗗! কম খরচে নিরাপদ সোশ্যাল প্রমোশন সেবা।'),
        ('bkash_num', '01965648802 (Personal / Send Money)'),
        ('nagad_num', '01910305557 (Personal / Send Money)'),
        ('rocket_num', '01965648802 (Personal / Send Money)')
    ]
    for k, v in defaults:
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
    conn.commit()
    conn.close()

init_db()

# --- হেল্পার ফাংশনস ---
def get_db():
    return sqlite3.connect("boost_enterprise_v4.db")

def get_setting(key):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else ""

def set_setting(key, value):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

# --- অ্যাডমিন পারমিশন কন্ট্রোল ---
def is_owner(user_id):
    return user_id == SUPER_ADMIN_ID

def is_super_admin(user_id):
    if user_id == SUPER_ADMIN_ID:
        return True
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE user_id=? AND role='superadmin2'", (user_id,))
    res = c.fetchone()
    conn.close()
    return res is not None

def is_admin(user_id):
    if user_id == SUPER_ADMIN_ID:
        return True
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE user_id=? AND role IN ('superadmin2', 'subadmin', 'admin')", (user_id,))
    res = c.fetchone()
    conn.close()
    return res is not None

def get_user(user_id, referrer=0):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, main_balance, bonus_balance, referral_balance_bdt, total_spent, role, referrer_id, has_deposited, fraud_strikes, last_daily_claim, is_banned FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if not row:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        role = "owner" if user_id == SUPER_ADMIN_ID else "user"
        ref_id = referrer if (referrer != user_id and referrer != 0) else 0
        c.execute("INSERT INTO users (user_id, main_balance, bonus_balance, referral_balance_bdt, total_spent, role, referrer_id, has_deposited, fraud_strikes, last_daily_claim, is_banned, joined_at) VALUES (?, 0.0, 0.0, 0.0, 0.0, ?, ?, 0, 0, '', 0, ?)", 
                  (user_id, role, ref_id, now))
        conn.commit()
        c.execute("SELECT user_id, main_balance, bonus_balance, referral_balance_bdt, total_spent, role, referrer_id, has_deposited, fraud_strikes, last_daily_claim, is_banned FROM users WHERE user_id=?", (user_id,))
        row = c.fetchone()
    conn.close()
    return row

def update_main_balance(user_id, amount):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET main_balance = ROUND(main_balance + ?, 5) WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def add_user_spent(user_id, amount):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET total_spent = ROUND(total_spent + ?, 5) WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

# --- অটো মার্জ ওয়ালেট ---
def check_and_merge_wallets(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT bonus_balance, referral_balance_bdt FROM users WHERE user_id=?", (user_id,))
    res = c.fetchone()
    if not res:
        conn.close()
        return

    bonus_bal, ref_bal_bdt = res
    bonus_threshold = float(get_setting('bonus_merge_threshold') or "0.50")
    ref_threshold_bdt = float(get_setting('ref_merge_threshold_bdt') or "125.0")
    usd_rate = float(get_setting('usd_bdt_rate') or "125.0")

    # বোনাস $0.50 হলে মেইন ওয়ালেটে যোগ হবে
    if bonus_bal >= bonus_threshold:
        c.execute("UPDATE users SET main_balance = ROUND(main_balance + ?, 5), bonus_balance = ROUND(bonus_balance - ?, 5) WHERE user_id=?", (bonus_bal, bonus_bal, user_id))
        try:
            bot.send_message(user_id, f"🎉 **বোনাস আনলক!** আপনার `${bonus_bal:.4f} USD` বোনাস ব্যালেন্স মূল ওয়ালেটে যুক্ত হয়েছে।", parse_mode="Markdown")
        except:
            pass

    # রেফারেল ইনকাম ৳১২৫ হলে মেইন ওয়ালেটে যোগ হবে
    if ref_bal_bdt >= ref_threshold_bdt:
        usd_to_add = round(ref_bal_bdt / usd_rate, 5)
        c.execute("UPDATE users SET main_balance = ROUND(main_balance + ?, 5), referral_balance_bdt = ROUND(referral_balance_bdt - ?, 5) WHERE user_id=?", (usd_to_add, ref_bal_bdt, user_id))
        try:
            bot.send_message(user_id, f"💰 **রেফারেল ইনকাম আনলক!** আপনার `৳{ref_bal_bdt:.2f} BDT` রেফারেল কমিশন `${usd_to_add:.4f} USD` হিসেবে মূল ওয়ালেটে যোগ হয়েছে।", parse_mode="Markdown")
        except:
            pass

    conn.commit()
    conn.close()

# --- কীবোর্ড মেনু ---
def user_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        "🚀 𝗡𝗲𝘄 𝗢𝗿𝗱𝗲𝗿", "🔥 𝗦𝗽𝗲𝗰𝗶𝗮𝗹 𝗢𝗳𝗳𝗲𝗿𝘀",
        "💎 𝗠𝘆 𝗪𝗮𝗹𝗹𝗲𝘁", "💳 𝗔𝗱𝗱 𝗙𝘂𝗻𝗱",
        "🎁 𝗗𝗮𝗶𝗹𝘆 𝗦𝗽𝗶𝗻", "👥 𝗥𝗲𝗳𝗲𝗿 & 𝗘𝗮𝗿𝗻",
        "📦 𝗠𝘆 𝗢𝗿𝗱𝗲𝗿𝘀", "💬 𝟮𝟰/𝟳 𝗦𝘂𝗽𝗽𝗼𝗿𝘁",
        "🧹 𝗖𝗹𝗲𝗮𝗿 𝗖𝗵𝗮𝘁", "📢 𝗡𝗼𝘁𝗶𝗰𝗲"
    )
    return markup

def cancel_inline():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Cancel (বাতিল করুন)", callback_data="cancel_action"))
    return markup

def admin_main_menu(is_primary_owner=False):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔄 Auto-Sync All (API)", callback_data="adm_autosync"),
        types.InlineKeyboardButton("🔥 স্পেশাল অফার সেট", callback_data="adm_manage_special"),
        types.InlineKeyboardButton("⚙️ রেট ও সেটিংস", callback_data="adm_menu_settings"),
        types.InlineKeyboardButton("👥 ইউজার ও ব্যালেন্স", callback_data="adm_menu_users"),
        types.InlineKeyboardButton("💳 পেমেন্ট ও প্রোভাইডার", callback_data="adm_menu_payments"),
        types.InlineKeyboardButton("📊 রিপোর্ট ও ব্যাকআপ", callback_data="adm_menu_reports")
    )
    if is_primary_owner:
        markup.add(types.InlineKeyboardButton("👮 স্টাফ ও সুপার অ্যাডমিন ২ ম্যানেজ", callback_data="adm_subadmin_manage"))
    markup.add(types.InlineKeyboardButton("❌ ক্লোজ ড্যাশবোর্ড", callback_data="cancel_action"))
    return markup

def validate_target_link(platform_name, link):
    link = link.lower()
    if "facebook" in platform_name.lower():
        return any(x in link for x in ["facebook.com", "fb.watch", "fb.com", "fb.me"])
    elif "instagram" in platform_name.lower():
        return any(x in link for x in ["instagram.com", "instagr.am"])
    elif "tiktok" in platform_name.lower():
        return "tiktok.com" in link or "vm.tiktok.com" in link
    elif "telegram" in platform_name.lower():
        return "t.me" in link or link.startswith("@")
    elif "youtube" in platform_name.lower():
        return any(x in link for x in ["youtube.com", "youtu.be"])
    return True

# --- ইউজার স্টার্ট ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    if is_spamming(message.chat.id):
        return

    ref_id = 0
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            ref_id = int(args[1].replace("ref_", ""))
        except:
            ref_id = 0

    user = get_user(message.chat.id, referrer=ref_id)
    if user[10] == 1:
        bot.send_message(message.chat.id, "🚫 আপনার অ্যাকাউন্টটি ব্যান করা হয়েছে।")
        return

    if get_setting('maintenance') == '1' and not is_admin(message.chat.id):
        bot.send_message(message.chat.id, "🛠️ বট বর্তমানে সংস্কারের জন্য বন্ধ আছে।")
        return

    welcome_text = (
        "╔════════════════════════╗\n"
        "   🚀 **𝗦𝗢𝗖𝗜𝗔𝗟 𝗕𝗢𝗢𝗦𝗧 𝗕𝗗** 🚀\n"
        "╚════════════════════════╝\n\n"
        "👋 স্বাগতম! সবচেয়ে দ্রুত ও কম খরচে সোশ্যাল মিডিয়া প্রমোশন নিতে নিচের মেনু ব্যবহার করুন।"
    )
    msg = bot.send_message(message.chat.id, welcome_text, reply_markup=user_keyboard(), parse_mode="Markdown")
    track_msg(message.chat.id, msg.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "cancel_action")
def handle_cancel(call):
    chat_id = call.message.chat.id
    if chat_id in user_flow:
        del user_flow[chat_id]
    if chat_id in deposit_state:
        del deposit_state[chat_id]
    bot.clear_step_handler_by_chat_id(chat_id)
    try:
        bot.edit_message_text("❌ পূর্ববর্তী মেনু।", chat_id, call.message.message_id)
    except:
        pass
    msg = bot.send_message(chat_id, "প্রধান মেনু:", reply_markup=user_keyboard())
    track_msg(chat_id, msg.message_id)

# --- 🧹 ক্লিয়ার চ্যাট ---
@bot.message_handler(func=lambda msg: msg.text == "🧹 𝗖𝗹𝗲𝗮𝗿 𝗖𝗵𝗮𝘁")
def clear_chat_history(message):
    chat_id = message.chat.id
    msgs_to_del = user_recent_msgs.get(chat_id, [])
    for m_id in msgs_to_del:
        try:
            bot.delete_message(chat_id, m_id)
        except:
            pass
    user_recent_msgs[chat_id] = []
    msg = bot.send_message(chat_id, "🧹 চ্যাট হিস্ট্রি সম্পূর্ণ পরিষ্কার করা হয়েছে!", reply_markup=user_keyboard())
    track_msg(chat_id, msg.message_id)

# --- 🎰 লাকি স্পিন হুইল ও বোনাস ---
@bot.message_handler(func=lambda msg: msg.text == "🎁 𝗗𝗮𝗶𝗹𝘆 𝗦𝗽𝗶𝗻")
def spin_wheel_bonus(message):
    if is_spamming(message.chat.id):
        return
    user = get_user(message.chat.id)
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    if user[9] == today:
        bot.send_message(message.chat.id, "⚠️ আপনি আজকের ডেইলি লাকি স্পিন সম্পন্ন করেছেন! আগামীকাল আবার আসুন।")
        return

    bonus_val = float(get_setting('daily_bonus_amount') or "0.00013")

    msg = bot.send_message(message.chat.id, "🎰 **লাকি স্পিন চাকা ঘুরছে...**\n\n`[ 🍒 | 🍋 | 🔔 ]`", parse_mode="Markdown")
    time.sleep(0.7)
    try:
        bot.edit_message_text("🎰 **লাকি স্পিন চাকা ঘুরছে...**\n\n`[ 🔔 | 💎 | 🍇 ]`", message.chat.id, msg.message_id, parse_mode="Markdown")
        time.sleep(0.7)
        bot.edit_message_text("🎰 **লাকি স্পিন চাকা ঘুরছে...**\n\n`[ 💎 | 💎 | 💎 ]`", message.chat.id, msg.message_id, parse_mode="Markdown")
        time.sleep(0.6)
    except:
        pass

    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET bonus_balance = ROUND(bonus_balance + ?, 5), last_daily_claim=? WHERE user_id=?", (bonus_val, today, message.chat.id))
    conn.commit()
    conn.close()

    result_text = (
        f"🎉 **JACKPOT! স্পিন সফল হয়েছে!** 🎉\n\n"
        f"🎁 আপনার বোনাস: `+${bonus_val:.5f} USD`\n"
        f"📌 $0.50 পূর্ণ হলেই মূল ওয়ালেটে যোগ হবে।"
    )
    try:
        bot.edit_message_text(result_text, message.chat.id, msg.message_id, parse_mode="Markdown")
    except:
        bot.send_message(message.chat.id, result_text, parse_mode="Markdown")
    check_and_merge_wallets(message.chat.id)

# --- ৩-টায়ার ওয়ালেট ---
@bot.message_handler(func=lambda msg: msg.text == "💎 𝗠𝘆 𝗪𝗮𝗹𝗹𝗲𝘁")
def my_wallet(message):
    if is_spamming(message.chat.id):
        return
    check_and_merge_wallets(message.chat.id)
    user = get_user(message.chat.id)
    usd_rate = float(get_setting('usd_bdt_rate'))
    bdt_equiv = user[1] * usd_rate
    
    spent = user[4]
    tier = "🥉 Bronze"
    if spent >= 50.0:
        tier = "🥇 Gold (VIP 5% Off)"
    elif spent >= 20.0:
        tier = "🥈 Silver (VIP 2% Off)"

    text = (
        f"╔═════════════════════════════╗\n"
        f"       💎 **USER WALLET HUB** 💎\n"
        f"╚═════════════════════════════╝\n\n"
        f"🆔 **ইউজার আইডি:** `{user[0]}`\n"
        f"🎭 **টিয়ার লেভেল:** `{tier}`\n\n"
        f"💵 **Main Balance:** `${user[1]:.4f} USD` (~৳{bdt_equiv:.2f} BDT)\n"
        f"🎁 **Bonus Balance:** `${user[2]:.5f} USD` (লক্ষ্য: $0.50)\n"
        f"👥 **Referral Income:** `৳{user[3]:.2f} BDT` (লক্ষ্য: ৳125)\n\n"
        f"📊 **মোট অর্ডার খরচ:** `${user[4]:.4f} USD`"
    )
    msg = bot.send_message(message.chat.id, text, parse_mode="Markdown")
    track_msg(message.chat.id, msg.message_id)

@bot.message_handler(func=lambda msg: msg.text == "📢 𝗡𝗼𝘁𝗶𝗰𝗲")
def show_notice(message):
    if is_spamming(message.chat.id):
        return
    bot.send_message(message.chat.id, f"📢 **সর্বশেষ নোটিশ:**\n\n{get_setting('notice')}", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "👥 𝗥𝗲𝗳𝗲𝗿 & 𝗘𝗮𝗿𝗻")
def refer_earn(message):
    if is_spamming(message.chat.id):
        return
    ref_pct = get_setting('referral_pct')
    user_id = message.chat.id
    bot_username = bot.get_me().username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE referrer_id=?", (user_id,))
    total_refs = c.fetchone()[0]
    conn.close()

    share_text = f"🔥 SocialBoost BD বট দিয়ে সবচেয়ে কম খরচে সোশ্যাল মিডিয়া সার্ভিস নিন! জয়েন লিংক: {ref_link}"
    share_url = f"https://t.me/share/url?url={ref_link}&text={share_text}"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📤 বন্ধুদের ইনভাইট করুন", url=share_url))

    text = (
        f"╔════════════════════════╗\n"
        f"   👥 **𝗜𝗡𝗩𝗜𝗧𝗘 & 𝗘𝗔𝗥𝗡 (২০%)** 👥\n"
        f"╚════════════════════════╝\n\n"
        f"🔗 **আপনার রেফারেল লিংক:**\n`{ref_link}`\n\n"
        f"💰 **কমিশন রেট:** প্রতি ডিপোজিটে `{ref_pct}%` ইনস্ট্যান্ট কমিশন!\n"
        f"📊 **আপনার মোট রেফার:** `{total_refs}` জন\n\n"
        f"📌 রেফারেল ইনকাম ৳১২৫ পূর্ণ হলেই স্বয়ংক্রিয়ভাবে মূল ওয়ালেটে যোগ হয়ে যাবে।"
    )
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

# --- ডিপোজিট সিস্টেম ---
@bot.message_handler(func=lambda msg: msg.text == "💳 𝗔𝗱𝗱 𝗙𝘂𝗻𝗱")
def start_deposit_flow(message):
    if is_spamming(message.chat.id):
        return
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM deposits WHERE user_id=? AND status='Pending'", (message.chat.id,))
    if c.fetchone():
        bot.send_message(message.chat.id, "⚠️ আপনার একটি ডিপোজিট রিকোয়েস্ট এখনও পেন্ডিং আছে। সেটি যাচাই শেষ হওয়া পর্যন্ত অপেক্ষা করুন।")
        conn.close()
        return
    conn.close()

    min_bdt = float(get_setting('min_deposit_bdt'))
    usd_rate = float(get_setting('usd_bdt_rate'))
    bonus_pct = get_setting('first_dep_bonus')
    user = get_user(message.chat.id)

    bonus_badge = f"🎁 প্রথম ডিপোজিটে পাবেন **{bonus_pct}% ক্যাশব্যাক বোনাস!**\n\n" if user[7] == 0 else ""

    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton("৳ ৫০", callback_data="depamt_50"),
        types.InlineKeyboardButton("৳ ১০০", callback_data="depamt_100"),
        types.InlineKeyboardButton("৳ ২০০", callback_data="depamt_200"),
        types.InlineKeyboardButton("৳ ৫০০", callback_data="depamt_500"),
        types.InlineKeyboardButton("৳ ১০০০", callback_data="depamt_1000"),
        types.InlineKeyboardButton("✏️ কাস্টম অ্যামাউন্ট", callback_data="depamt_custom")
    )
    markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_action"))

    text = (
        f"╔════════════════════╗\n"
        f"    💳 **𝗔𝗗𝗗 𝗙𝗨𝗡𝗗 (টাকা জমা)** 💳\n"
        f"╚════════════════════╝\n\n"
        f"{bonus_badge}"
        f"📌 রেট: `$1 USD = {usd_rate:.1f} BDT`\n"
        f"⚠️ সর্বনিম্ন ডিপোজিট: `৳{min_bdt:.1f}`\n\n"
        f"👇 কত টাকা ডিপোজিট করতে চান নির্বাচন করুন:"
    )
    msg = bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")
    track_msg(message.chat.id, msg.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("depamt_"))
def process_deposit_amount(call):
    amt_type = call.data.replace("depamt_", "")
    chat_id = call.message.chat.id

    if amt_type == "custom":
        try:
            bot.edit_message_text("✏️ কত টাকা ডিপোজিট করতে চান সংখ্যায় লিখুন (যেমন: 150):", chat_id, call.message.message_id, reply_markup=cancel_inline())
        except:
            pass
        bot.register_next_step_handler(call.message, get_custom_deposit_amt)
    else:
        amount_bdt = float(amt_type)
        show_payment_methods(call.message, amount_bdt)

def get_custom_deposit_amt(message):
    try:
        amount_bdt = float(message.text.strip())
        min_bdt = float(get_setting('min_deposit_bdt'))
        if amount_bdt < min_bdt:
            bot.send_message(message.chat.id, f"❌ সর্বনিম্ন ডিপোজিট `৳{min_bdt}`।", reply_markup=user_keyboard())
            return
        show_payment_methods(message, amount_bdt)
    except:
        bot.send_message(message.chat.id, "❌ সঠিক সংখ্যায় অ্যামাউন্ট দিন।", reply_markup=user_keyboard())

def show_payment_methods(message, amount_bdt):
    chat_id = message.chat.id
    deposit_state[chat_id] = {"amount_bdt": amount_bdt}

    usd_rate = float(get_setting('usd_bdt_rate'))
    usd_val = round(amount_bdt / usd_rate, 4)
    user = get_user(chat_id)
    bonus_pct = float(get_setting('first_dep_bonus')) if user[7] == 0 else 0.0
    bonus_usd = round((usd_val * bonus_pct) / 100.0, 4)
    total_usd = usd_val + bonus_usd
    deposit_state[chat_id]["total_usd"] = total_usd

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🔴 bKash (বিকাশ)", callback_data="paym_bkash"),
        types.InlineKeyboardButton("🟠 Nagad (নগদ)", callback_data="paym_nagad"),
        types.InlineKeyboardButton("🟣 Rocket (রকেট)", callback_data="paym_rocket"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_action")
    )
    text = (
        f"💰 **ডিপোজিট অ্যামাউন্ট:** `৳{amount_bdt:.2f} BDT`\n"
        f"💵 **ওয়ালেটে যোগ হবে:** `${total_usd:.3f} USD`\n\n"
        f"👇 পেমেন্ট মাধ্যম বেছে নিন:"
    )
    if hasattr(message, 'message_id'):
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("paym_"))
def process_payment_method(call):
    method = call.data.replace("paym_", "").upper()
    chat_id = call.message.chat.id

    if chat_id not in deposit_state:
        try:
            bot.answer_callback_query(call.id, "সেশন শেষ হয়েছে, আবার শুরু করুন।")
        except:
            pass
        return

    deposit_state[chat_id]["method"] = method
    num_info = get_setting(f"{method.lower()}_num")

    text = (
        f"╔════════════════════╗\n"
        f"    💳 **{method} PAYMENT** 💳\n"
        f"╚════════════════════╝\n\n"
        f"👉 **নম্বর:** `{num_info}`\n"
        f"💰 **টাকার পরিমাণ:** `৳{deposit_state[chat_id]['amount_bdt']:.2f}`\n\n"
        f"⚠️ **নির্দেশনা:** উপরের নম্বরে **Send Money** করে মেসেজে **TrxID** লিখে পাঠান:"
    )
    try:
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=cancel_inline(), parse_mode="Markdown")
    except:
        pass
    bot.register_next_step_handler(call.message, get_deposit_trxid)

def get_deposit_trxid(message):
    chat_id = message.chat.id
    if chat_id not in deposit_state:
        return
    
    trx_id = message.text.strip().upper()
    if len(trx_id) < 6 or not re.match("^[A-Za-z0-9]+$", trx_id):
        bot.send_message(chat_id, "❌ অবৈধ TrxID! সঠিক Transaction ID দিন:", reply_markup=cancel_inline())
        bot.register_next_step_handler(message, get_deposit_trxid)
        return

    deposit_state[chat_id]["trx_id"] = trx_id

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⏭️ স্ক্রিনশট ছাড়া সাবমিট করুন", callback_data="skip_screenshot"))
    markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_action"))

    bot.send_message(
        chat_id, 
        f"🔖 **TrxID:** `{trx_id}`\n\n📸 পেমেন্টের **স্ক্রিনশট** পাঠান (ঐচ্ছিক / Optional), অথবা নিচের বাটনে চাপ দিন:",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(message, get_deposit_photo)

def get_deposit_photo(message):
    chat_id = message.chat.id
    if chat_id not in deposit_state:
        return

    photo_id = message.photo[-1].file_id if message.photo else ""
    finalize_deposit_submission(chat_id, photo_id)

@bot.callback_query_handler(func=lambda call: call.data == "skip_screenshot")
def skip_photo_callback(call):
    chat_id = call.message.chat.id
    if chat_id in deposit_state:
        finalize_deposit_submission(chat_id, "")

def finalize_deposit_submission(chat_id, photo_id):
    state = deposit_state.get(chat_id)
    if not state:
        return

    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""INSERT INTO deposits (user_id, method, trx_id, amount_bdt, usd_credited, photo_file_id, status, date) 
                     VALUES (?, ?, ?, ?, ?, ?, 'Pending', ?)""",
                  (chat_id, state["method"], state["trx_id"], state["amount_bdt"], state["total_usd"], photo_id, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        dep_id = c.lastrowid
        conn.commit()
        conn.close()

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Approve", callback_data=f"apprv_{dep_id}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"rjct_{dep_id}")
        )
        caption = (
            f"🔔 **নতুন ডিপোজিট ভেরিফিকেশন!**\n\n"
            f"🆔 **User ID:** `{chat_id}`\n"
            f"💳 **Method:** {state['method']}\n"
            f"🔖 **TrxID:** `{state['trx_id']}` (ট্যাপ করে কপি করুন)\n"
            f"💰 **টাকা:** `৳{state['amount_bdt']:.2f}`\n"
            f"💵 **ক্রেডিট হবে:** `${state['total_usd']:.3f} USD`"
        )
        
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE role='superadmin2'")
        sa2_list = c.fetchall()
        conn.close()

        admin_ids = [SUPER_ADMIN_ID] + [u[0] for u in sa2_list]
        for a_id in set(admin_ids):
            try:
                if photo_id:
                    bot.send_photo(a_id, photo_id, caption=caption, reply_markup=markup, parse_mode="Markdown")
                else:
                    bot.send_message(a_id, caption, reply_markup=markup, parse_mode="Markdown")
            except:
                pass

        bot.send_message(chat_id, "✅ আপনার ডিপোজিট রিকোয়েস্ট জমা হয়েছে। অ্যাডমিন চেক করে ব্যালেন্স যুক্ত করবে।", reply_markup=user_keyboard())
    except sqlite3.IntegrityError:
        bot.send_message(chat_id, "❌ এই TrxID ইতিমধ্যে একবার সাবমিট করা হয়েছে!", reply_markup=user_keyboard())
    finally:
        if chat_id in deposit_state:
            del deposit_state[chat_id]

# --- ইন-বট সাপোর্ট ---
@bot.message_handler(func=lambda msg: msg.text == "💬 𝟮𝟰/𝟳 𝗦𝘂𝗽𝗽𝗼𝗿𝘁")
def trigger_support(message):
    if is_spamming(message.chat.id):
        return
    bot.send_message(
        message.chat.id,
        "✍️ আপনার প্রশ্ন বা সমস্যা বিস্তারিত লিখে পাঠান। আমাদের টিম সরাসরি উত্তর দেবে।",
        reply_markup=cancel_inline()
    )
    bot.register_next_step_handler(message, handle_user_support_msg)

def handle_user_support_msg(message):
    if message.text and message.text.startswith('/'):
        return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✉️ রিপ্লাই দিন", callback_data=f"rep_sup_{message.chat.id}"))
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE role='superadmin2'")
    sa2_list = c.fetchall()
    conn.close()

    admin_ids = [SUPER_ADMIN_ID] + [u[0] for u in sa2_list]
    for a_id in set(admin_ids):
        try:
            bot.send_message(
                a_id,
                f"📩 **নতুন সাপোর্ট টিকিট:**\n\n🆔 প্রেরক: `{message.chat.id}`\n\n💬 মেসেজ:\n{message.text}",
                reply_markup=markup,
                parse_mode="Markdown"
            )
        except:
            pass

    bot.send_message(message.chat.id, "✅ আপনার বার্তাটি অ্যাডমিনের কাছে পাঠানো হয়েছে।", reply_markup=user_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("rep_sup_"))
def admin_reply_ticket(call):
    if not is_admin(call.message.chat.id):
        return
    target_user_id = int(call.data.replace("rep_sup_", ""))
    bot.send_message(call.message.chat.id, f"ইউজার `{target_user_id}`-এর জন্য রিপ্লাই লিখুন:", reply_markup=cancel_inline(), parse_mode="Markdown")
    bot.register_next_step_handler(call.message, lambda m: send_admin_reply_to_user(m, target_user_id))

def send_admin_reply_to_user(message, target_user_id):
    try:
        bot.send_message(target_user_id, f"📩 **অ্যাডমিন সাপোর্ট রিপ্লাই:**\n\n{message.text}")
        bot.send_message(message.chat.id, f"✅ ইউজার `{target_user_id}`-কে রিপ্লাই পাঠানো সম্পন্ন।", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ মেসেজ পাঠানো যায়নি: {str(e)}")

# --- 🔥 স্পেশাল অফার সেকশন ---
@bot.message_handler(func=lambda msg: msg.text == "🔥 𝗦𝗽𝗲𝗰𝗶𝗮𝗹 𝗢𝗳𝗳𝗲𝗿𝘀")
def special_offers_menu(message):
    if is_spamming(message.chat.id):
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, name, base_price FROM services WHERE is_special=1 AND is_active=1")
    specials = c.fetchall()
    conn.close()

    if not specials:
        bot.send_message(message.chat.id, "🔥 বর্তমানে কোনো স্পেশাল অফার নেই। নিয়মিত সার্ভিস ব্রাউজ করুন।")
        return

    profit_margin = float(get_setting('profit_margin'))
    markup = types.InlineKeyboardMarkup(row_width=1)
    for s_id, s_name, base_p in specials:
        user_p = round(base_p * (1 + (profit_margin / 100.0)), 4)
        markup.add(types.InlineKeyboardButton(f"🏷️ {s_name} - ${user_p:.3f}/1k", callback_data=f"sel_srv_{s_id}"))
    markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_action"))
    
    bot.send_message(message.chat.id, "🔥 **HOT SPECIAL DEALS (সীমিত সময়ের অফার):**", reply_markup=markup, parse_mode="Markdown")

# --- মাল্টি-লেয়ার টপ ৫ অর্ডার ফ্লো ---
@bot.message_handler(func=lambda msg: msg.text == "🚀 𝗡𝗲𝘄 𝗢𝗿𝗱𝗲𝗿")
def select_category_order(message):
    if is_spamming(message.chat.id):
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT DISTINCT c.id, c.name 
        FROM categories c 
        INNER JOIN services s ON c.id = s.category_id 
        WHERE s.is_active=1
    """)
    cats = c.fetchall()
    conn.close()

    if not cats:
        bot.send_message(message.chat.id, "⚠️ সার্ভিস লোড করা নেই। অ্যাডমিন প্যানেল থেকে Auto-Sync Services করুন।")
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    for c_id, c_name in cats:
        markup.add(types.InlineKeyboardButton(c_name, callback_data=f"ord_cat_{c_id}"))
    markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_action"))
    bot.send_message(message.chat.id, "🎯 **প্ল্যাটফর্ম নির্বাচন করুন:**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("ord_cat_"))
def show_subcategories(call):
    cat_id = int(call.data.replace("ord_cat_", ""))
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT DISTINCT sub_category FROM services WHERE category_id=? AND is_active=1", (cat_id,))
    subs = c.fetchall()
    conn.close()

    markup = types.InlineKeyboardMarkup(row_width=1)
    for s in subs:
        sub_name = s[0]
        markup.add(types.InlineKeyboardButton(f"⚡ {sub_name}", callback_data=f"ord_sub_{cat_id}_{sub_name}"))
    markup.add(types.InlineKeyboardButton("🔙 ফিরে যান", callback_data="cancel_action"))
    try:
        bot.edit_message_text("📌 **সার্ভিসের ধরন বেছে নিন:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("ord_sub_"))
def show_tier_options(call):
    parts = call.data.split("_")
    cat_id, sub_name = int(parts[2]), parts[3]

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🟢 Budget (কমদামী)", callback_data=f"ord_tier_{cat_id}_{sub_name}_Budget"),
        types.InlineKeyboardButton("💎 VIP (দামী/হাই কোয়ালিটি)", callback_data=f"ord_tier_{cat_id}_{sub_name}_VIP"),
        types.InlineKeyboardButton("🔙 ফিরে যান", callback_data="cancel_action")
    )
    try:
        bot.edit_message_text("⚖️ **প্যাকেজ কোয়ালিটি নির্বাচন করুন:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("ord_tier_"))
def show_refill_options(call):
    parts = call.data.split("_")
    cat_id, sub_name, tier_type = int(parts[2]), parts[3], parts[4]

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("♾️ Lifetime Refill", callback_data=f"ord_ref_{cat_id}_{sub_name}_{tier_type}_Lifetime"),
        types.InlineKeyboardButton("🔄 30 Days Refill", callback_data=f"ord_ref_{cat_id}_{sub_name}_{tier_type}_30Days"),
        types.InlineKeyboardButton("⚡ No Refill (Instant)", callback_data=f"ord_ref_{cat_id}_{sub_name}_{tier_type}_NoRefill"),
        types.InlineKeyboardButton("🔙 ফিরে যান", callback_data="cancel_action")
    )
    try:
        bot.edit_message_text("🛡️ **রিফিল গ্যারান্টি ফিল্টার:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("ord_ref_"))
def show_filtered_top5_services(call):
    parts = call.data.split("_")
    cat_id, sub_name, tier_type, refill_type = int(parts[2]), parts[3], parts[4], parts[5]

    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT id, name, base_price FROM services 
                 WHERE category_id=? AND sub_category=? AND tier_type=? AND refill_type=? AND is_active=1 
                 ORDER BY base_price ASC LIMIT 5""", (cat_id, sub_name, tier_type, refill_type))
    srvs = c.fetchall()

    if not srvs:
        c.execute("""SELECT id, name, base_price FROM services 
                     WHERE category_id=? AND sub_category=? AND is_active=1 
                     ORDER BY base_price ASC LIMIT 5""", (cat_id, sub_name))
        srvs = c.fetchall()
    conn.close()

    profit_margin = float(get_setting('profit_margin'))
    markup = types.InlineKeyboardMarkup(row_width=1)
    for s_id, s_name, base_p in srvs:
        user_price = round(base_p * (1 + (profit_margin / 100.0)), 4)
        display_name = (s_name[:36] + '..') if len(s_name) > 36 else s_name
        markup.add(types.InlineKeyboardButton(f"⭐ {display_name} - ${user_price:.3f}/1k", callback_data=f"sel_srv_{s_id}"))
    markup.add(types.InlineKeyboardButton("🔙 ফিরে যান", callback_data="cancel_action"))
    
    try:
        bot.edit_message_text(f"🏆 **{sub_name} (টপ ৫টি সেরা প্যাকেজ):**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("sel_srv_"))
def start_order_placement(call):
    service_id = int(call.data.replace("sel_srv_", ""))
    user_flow[call.message.chat.id] = {"service_id": service_id}
    try:
        bot.edit_message_text("🔗 আপনার লিংকটি পাঠান (Target Link):\n*(লক্ষ্য রাখবেন আইডি/পোস্ট যেন পাবলিক থাকে)*", call.message.chat.id, call.message.message_id, reply_markup=cancel_inline())
    except:
        pass
    bot.register_next_step_handler(call.message, get_order_link_step)

def get_order_link_step(message):
    chat_id = message.chat.id
    if chat_id not in user_flow:
        return
    link = message.text.strip()

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT c.name FROM categories c INNER JOIN services s ON c.id=s.category_id WHERE s.id=?", (user_flow[chat_id]["service_id"],))
    plat_row = c.fetchone()
    conn.close()

    if plat_row and not validate_target_link(plat_row[0], link):
        bot.send_message(chat_id, f"❌ ভুল লিঙ্ক! আপনি {plat_row[0]}-এর জন্য সঠিক লিঙ্ক দেননি। পুনরায় লিঙ্ক পাঠান:", reply_markup=cancel_inline())
        bot.register_next_step_handler(message, get_order_link_step)
        return

    user_flow[chat_id]["link"] = link
    bot.send_message(chat_id, "🔢 পরিমাণ (Quantity) লিখুন (যেমন: 500, 1000):", reply_markup=cancel_inline())
    bot.register_next_step_handler(message, get_order_qty_step)

def get_order_qty_step(message):
    chat_id = message.chat.id
    if chat_id in order_lock:
        return
    
    try:
        quantity = int(message.text)
        state = user_flow.get(chat_id)
        if not state:
            return

        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT name, smm_service_id, base_price, min_qty, max_qty FROM services WHERE id=?", (state["service_id"],))
        srv = c.fetchone()
        conn.close()

        if not srv:
            bot.send_message(chat_id, "❌ সার্ভিস পাওয়া যায়নি।")
            return

        s_name, smm_id, base_p, min_q, max_q = srv
        if quantity < min_q or quantity > max_q:
            bot.send_message(chat_id, f"❌ পরিমাণের লিমিট ভঙ্গ হয়েছে!\nমিনিমাম: {min_q} | ম্যাক্সিমাম: {max_q}", reply_markup=cancel_inline())
            return

        profit_margin = float(get_setting('profit_margin'))
        user_unit_price = base_p * (1 + (profit_margin / 100.0))
        cost = round((quantity / 1000.0) * user_unit_price, 4)
        user = get_user(chat_id)

        # জিরো ব্যালেন্স সিকিউরিটি
        if user[1] < cost:
            bot.send_message(chat_id, f"❌ অপর্যাপ্ত মেইন ওয়ালেট ব্যালেন্স!\nখরচ: `${cost:.3f} USD`\nআপনার ব্যালেন্স: `${user[1]:.4f} USD`\nদয়া করে ব্যালেন্স যোগ করুন।", parse_mode="Markdown")
            return

        order_lock.add(chat_id)
        update_main_balance(chat_id, -cost)

        payload = {'key': SMM_API_KEY, 'action': 'add', 'service': smm_id, 'link': state["link"], 'quantity': quantity}
        try:
            res = requests.post(SMM_API_URL, data=payload, headers=HEADERS, timeout=15).json()
        except:
            res = {'error': 'Server Timeout'}

        if 'order' in res:
            smm_order_id = str(res['order'])
            add_user_spent(chat_id, cost)
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO orders (user_id, smm_order_id, service_name, link, quantity, charge, status, date) VALUES (?, ?, ?, ?, ?, ?, 'Processing', ?)",
                      (chat_id, smm_order_id, s_name, state["link"], quantity, cost, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            conn.close()

            bot.send_message(
                chat_id,
                f"╔════════════════════════╗\n"
                f"   ✅ **𝗢𝗥𝗗𝗘𝗥 𝗦𝗨𝗖𝗖𝗘𝗦𝗦𝗙𝗨𝗟**\n"
                f"╚════════════════════════╝\n\n"
                f"🔖 **Order ID:** `{smm_order_id}`\n"
                f"📌 **সার্ভিস:** `{s_name}`\n"
                f"🔢 **পরিমাণ:** `{quantity}`\n"
                f"💰 **মোট খরচ:** `${cost:.3f} USD`",
                parse_mode="Markdown",
                reply_markup=user_keyboard()
            )
            del user_flow[chat_id]
        else:
            update_main_balance(chat_id, cost)
            bot.send_message(chat_id, "⚠️ সার্ভিস প্রোভাইডার সার্ভার সাময়িক ব্যস্ত আছে। আপনার ব্যালেন্স রিফান্ড করা হয়েছে। কিছুক্ষণ পর চেষ্টা করুন।", parse_mode="Markdown")
            try:
                bot.send_message(SUPER_ADMIN_ID, f"🚨 **API Order Error:**\nUser: `{chat_id}`\nService: `{s_name}`\nError: `{str(res)}`", parse_mode="Markdown")
            except:
                pass

    except ValueError:
        bot.send_message(chat_id, "❌ সংখ্যায় সঠিক পরিমাণ দিন।")
    finally:
        order_lock.discard(chat_id)

# --- অর্ডার হিস্ট্রি ---
@bot.message_handler(func=lambda msg: msg.text == "📦 𝗠𝘆 𝗢𝗿𝗱𝗲𝗿𝘀")
def my_orders_list(message):
    if is_spamming(message.chat.id):
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT order_id, smm_order_id, service_name, status FROM orders WHERE user_id=? ORDER BY order_id DESC LIMIT 6", (message.chat.id,))
    orders = c.fetchall()
    conn.close()

    if not orders:
        bot.send_message(message.chat.id, "📦 আপনার কোনো অর্ডার হিস্ট্রি পাওয়া যায়নি।")
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for o_id, smm_id, s_name, st in orders:
        markup.add(types.InlineKeyboardButton(f"#{smm_id} - {s_name[:22]} [{st}]", callback_data=f"v_ord_{o_id}"))
    bot.send_message(message.chat.id, "📦 **আপনার সাম্প্রতিক অর্ডারসমূহ (বিস্তারিত দেখতে ট্যাপ করুন):**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("v_ord_"))
def view_order_details(call):
    o_id = int(call.data.replace("v_ord_", ""))
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT smm_order_id, service_name, link, quantity, charge, status, date FROM orders WHERE order_id=?", (o_id,))
    ord_info = c.fetchone()
    conn.close()

    if not ord_info:
        try:
            bot.answer_callback_query(call.id, "অর্ডার পাওয়া যায়নি।")
        except:
            pass
        return

    smm_id, name, link, qty, charge, status, o_date = ord_info
    
    try:
        st_res = requests.post(SMM_API_URL, data={'key': SMM_API_KEY, 'action': 'status', 'order': smm_id}, headers=HEADERS, timeout=4).json()
        if 'status' in st_res:
            status = st_res['status']
            conn = get_db()
            c = conn.cursor()
            c.execute("UPDATE orders SET status=? WHERE order_id=?", (status, o_id))
            conn.commit()
            conn.close()
    except:
        pass

    text = (
        f"🔖 **অর্ডার বিস্তারিত (#{smm_id}):**\n\n"
        f"📌 **সার্ভিস:** `{name}`\n"
        f"🔗 **লিংক:** {link}\n"
        f"🔢 **পরিমাণ:** `{qty}`\n"
        f"💰 **খরচ:** `${charge:.3f} USD`\n"
        f"📊 **স্ট্যাটাস:** **{status}**\n"
        f"📅 **তারিখ:** `{o_date}`"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔄 Refill", callback_data=f"refill_{smm_id}"),
        types.InlineKeyboardButton("❌ Cancel Request", callback_data=f"cnclreq_{smm_id}"),
        types.InlineKeyboardButton("💬 Report Issue", callback_data=f"repissue_{smm_id}"),
        types.InlineKeyboardButton("🔙 ফিরে যান", callback_data="cancel_action")
    )
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("refill_"))
def handle_refill(call):
    smm_id = call.data.replace("refill_", "")
    try:
        res = requests.post(SMM_API_URL, data={'key': SMM_API_KEY, 'action': 'refill', 'order': smm_id}, headers=HEADERS, timeout=5).json()
        if 'refill' in res:
            bot.answer_callback_query(call.id, f"✅ রিফিল রিকোয়েস্ট সফল! Refill ID: {res['refill']}", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "❌ এই অর্ডারে রিফিল প্রযোজ্য নয়।", show_alert=True)
    except:
        try:
            bot.answer_callback_query(call.id, "❌ সার্ভারে সংযোগ স্থাপন করা যায়নি।", show_alert=True)
        except:
            pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("cnclreq_"))
def handle_cancel_req(call):
    smm_id = call.data.replace("cnclreq_", "")
    bot.send_message(SUPER_ADMIN_ID, f"⚠️ **ইউজার অর্ডার বাতিলের রিকোয়েস্ট পাঠিয়েছে!**\nOrder ID: `{smm_id}`\nUser ID: `{call.message.chat.id}`", parse_mode="Markdown")
    try:
        bot.answer_callback_query(call.id, "✅ বাতিলের রিকোয়েস্ট অ্যাডমিনের কাছে পাঠানো হয়েছে।", show_alert=True)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("repissue_"))
def handle_report_issue(call):
    smm_id = call.data.replace("repissue_", "")
    bot.send_message(call.message.chat.id, f"অর্ডার `#{smm_id}` নিয়ে সমস্যাটি বিস্তারিত লিখুন:", reply_markup=cancel_inline())
    bot.register_next_step_handler(call.message, lambda m: send_order_issue(m, smm_id))

def send_order_issue(message, smm_id):
    bot.send_message(SUPER_ADMIN_ID, f"🚨 **অর্ডার ইস্যু রিপোর্ট:**\nOrder ID: `#{smm_id}`\nUser ID: `{message.chat.id}`\n\nবিবরণ:\n{message.text}", parse_mode="Markdown")
    bot.send_message(message.chat.id, "✅ আপনার রিপোর্টটি সফলভাবে অ্যাডমিনের কাছে পৌঁছেছে।", reply_markup=user_keyboard())

# --- ডিপোজিট অ্যাকশন ও রেফারেল কমিশন ---
@bot.callback_query_handler(func=lambda call: call.data.startswith(("apprv_", "rjct_")))
def handle_deposit_action(call):
    if not is_admin(call.message.chat.id):
        return
    
    action, dep_id = call.data.split("_")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, amount_bdt, usd_credited, status FROM deposits WHERE id=?", (dep_id,))
    dep = c.fetchone()
    
    if not dep or dep[3] != 'Pending':
        try:
            bot.answer_callback_query(call.id, "রিকোয়েস্টটি নিষ্পত্তি করা হয়েছে।")
        except:
            pass
        conn.close()
        return

    user_id, amount_bdt, usd_amount = dep[0], dep[1], dep[2]

    if action == "apprv":
        c.execute("UPDATE deposits SET status='Approved' WHERE id=?", (dep_id,))
        c.execute("UPDATE users SET main_balance = ROUND(main_balance + ?, 5), has_deposited = 1 WHERE user_id=?", (usd_amount, user_id))
        
        # রেফারেল কমিশন (২০% টাকায় জমা)
        c.execute("SELECT referrer_id FROM users WHERE user_id=?", (user_id,))
        ref_row = c.fetchone()
        if ref_row and ref_row[0] > 0:
            referrer_id = ref_row[0]
            ref_pct = float(get_setting('referral_pct'))
            commission_bdt = round((amount_bdt * ref_pct) / 100.0, 2)
            c.execute("UPDATE users SET referral_balance_bdt = ROUND(referral_balance_bdt + ?, 2) WHERE user_id=?", (commission_bdt, referrer_id))
            try:
                bot.send_message(referrer_id, f"🎉 অভিনন্দন! আপনার রেফারের ডিপোজিট থেকে `৳{commission_bdt:.2f} BDT` রেফারেল কমিশন জমা হয়েছে!", parse_mode="Markdown")
            except:
                pass

        conn.commit()
        conn.close()
        check_and_merge_wallets(user_id)
        if ref_row and ref_row[0] > 0:
            check_and_merge_wallets(ref_row[0])

        bot.send_message(user_id, f"🎉 আপনার ডিপোজিট অনুমোদিত হয়েছে!\n`${usd_amount:.3f} USD` মেইন ওয়ালেটে যোগ করা হয়েছে।", parse_mode="Markdown")
        try:
            bot.edit_message_text(f"✅ Approved: ${usd_amount:.3f} for User `{user_id}`", call.message.chat.id, call.message.message_id)
        except:
            pass
    else:
        c.execute("UPDATE deposits SET status='Rejected' WHERE id=?", (dep_id,))
        c.execute("UPDATE users SET fraud_strikes = fraud_strikes + 1 WHERE user_id=?", (user_id,))
        c.execute("SELECT fraud_strikes FROM users WHERE user_id=?", (user_id,))
        strikes = c.fetchone()[0]
        if strikes >= 3:
            c.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (user_id,))
            bot.send_message(user_id, "🚫 একাধিকবার ভুল TrxID দেওয়ায় অ্যাকাউন্ট ব্যান করা হয়েছে।")
        else:
            bot.send_message(user_id, f"❌ ডিপোজিট রিকোয়েস্ট বাতিল করা হয়েছে। (ওয়ার্নিং: {strikes}/৩)")
        
        conn.commit()
        conn.close()
        try:
            bot.edit_message_text(f"❌ Rejected for User `{user_id}` (Strikes: {strikes})", call.message.chat.id, call.message.message_id)
        except:
            pass

# --- অ্যাডমিন কন্ট্রোল প্যানেল ---
@bot.message_handler(commands=['admin'])
def admin_panel_root(message):
    if not is_admin(message.chat.id):
        return
    bot.send_message(message.chat.id, "👑 **অ্যাডমিন কন্ট্রোল ড্যাশবোর্ড**", reply_markup=admin_main_menu(is_owner(message.chat.id)), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_menu_"))
def handle_admin_submenus(call):
    if not is_admin(call.message.chat.id):
        return

    menu = call.data.replace("adm_menu_", "")
    markup = types.InlineKeyboardMarkup(row_width=2)

    if menu == "settings":
        markup.add(
            types.InlineKeyboardButton("📈 লাভ মার্জিন সেট", callback_data="adm_set_margin"),
            types.InlineKeyboardButton("💵 USD এক্সচেঞ্জ রেট", callback_data="adm_set_usd_rate"),
            types.InlineKeyboardButton("🎰 ডেইলি বোনাস সেট", callback_data="adm_set_daily_bonus"),
            types.InlineKeyboardButton("👥 রেফার কমিশন %", callback_data="adm_set_refpct"),
            types.InlineKeyboardButton("🎁 ডিপোজিট বোনাস %", callback_data="adm_set_bonus"),
            types.InlineKeyboardButton("⚙️ মিনিমাম ডিপোজিট", callback_data="adm_set_mindep"),
            types.InlineKeyboardButton("🛠️ মেইনটেন্যান্স অন/অফ", callback_data="adm_toggle_maint"),
            types.InlineKeyboardButton("🔙 মূল মেনু", callback_data="adm_root")
        )
        try:
            bot.edit_message_text("⚙️ **সিস্টেম সেটিংস ও পার্সেন্টেজ কন্ট্রোল:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        except:
            pass

    elif menu == "users":
        markup.add(
            types.InlineKeyboardButton("➕ ব্যালেন্স যোগ (USD)", callback_data="adm_add_bal"),
            types.InlineKeyboardButton("➖ ব্যালেন্স কর্তন (USD)", callback_data="adm_cut_bal"),
            types.InlineKeyboardButton("🚫 ইউজার ব্যান/আনব্যান", callback_data="adm_ban_user"),
            types.InlineKeyboardButton("🔙 মূল মেনু", callback_data="adm_root")
        )
        try:
            bot.edit_message_text("👥 **ইউজার ও ব্যালেন্স কন্ট্রোল:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        except:
            pass

    elif menu == "payments":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM deposits WHERE status='Pending'")
        pending_count = c.fetchone()[0]
        conn.close()

        markup.add(
            types.InlineKeyboardButton("🔴 বিকাশ নম্বর এডিট", callback_data="adm_edit_bkash"),
            types.InlineKeyboardButton("🟠 নগদ নম্বর এডিট", callback_data="adm_edit_nagad"),
            types.InlineKeyboardButton("🟣 রকেট নম্বর এডিট", callback_data="adm_edit_rocket"),
            types.InlineKeyboardButton("🌐 প্রোভাইডার ব্যালেন্স", callback_data="adm_api_bal"),
            types.InlineKeyboardButton("🔙 মূল মেনু", callback_data="adm_root")
        )
        try:
            bot.edit_message_text(f"💳 **পেমেন্ট কন্ট্রোল:**\n\n🔔 পেন্ডিং ডিপোজিট: `{pending_count}` টি", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        except:
            pass

    elif menu == "reports":
        markup.add(
            types.InlineKeyboardButton("📢 নোটিশ ব্রডকাস্ট", callback_data="adm_broadcast"),
            types.InlineKeyboardButton("📊 সেলস সামারি", callback_data="adm_summary"),
            types.InlineKeyboardButton("💾 ডাটাবেজ ব্যাকআপ", callback_data="adm_backup"),
            types.InlineKeyboardButton("🔙 মূল মেনু", callback_data="adm_root")
        )
        try:
            bot.edit_message_text("📊 **রিপোর্ট ও ব্রডকাস্ট প্যানেল:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        except:
            pass

@bot.callback_query_handler(func=lambda call: call.data == "adm_root")
def admin_root_return(call):
    try:
        bot.edit_message_text("👑 **অ্যাডমিন কন্ট্রোল ড্যাশবোর্ড**", call.message.chat.id, call.message.message_id, reply_markup=admin_main_menu(is_owner(call.message.chat.id)), parse_mode="Markdown")
    except:
        pass

# --- সুরক্ষিত অটো-সিঙ্ক ইঞ্জিন ---
@bot.callback_query_handler(func=lambda call: call.data == "adm_autosync")
def auto_sync_multitier(call):
    if not is_admin(call.message.chat.id):
        return

    try:
        bot.answer_callback_query(call.id, "সার্ভিস সিঙ্ক শুরু হয়েছে...")
    except:
        pass

    bot.send_message(call.message.chat.id, "⏳ SMMGen API থেকে ডেটা এনে সাজানো হচ্ছে, ১০-১৫ সেকেন্ড অপেক্ষা করুন...")

    def sync_worker():
        try:
            res = requests.post(SMM_API_URL, data={'key': SMM_API_KEY, 'action': 'services'}, headers=HEADERS, timeout=35).json()
            if not isinstance(res, list):
                bot.send_message(call.message.chat.id, f"❌ API এরর: `{str(res)}`", parse_mode="Markdown")
                return

            conn = get_db()
            c = conn.cursor()

            platforms = {
                "🔵 Facebook": 1,
                "🟣 Instagram": 2,
                "⚫ TikTok": 3,
                "🔷 Telegram": 4,
                "🔴 YouTube": 5
            }
            for p_name, p_id in platforms.items():
                c.execute("INSERT OR IGNORE INTO categories (id, name) VALUES (?, ?)", (p_id, p_name))

            bucket = {}

            for s in res:
                name = s.get('name', '')
                cat_name = s.get('category', '').lower()
                name_lower = name.lower()
                s_id = int(s.get('service'))
                rate = float(s.get('rate', 0.0))
                min_q = int(s.get('min', 10))
                max_q = int(s.get('max', 100000))

                plat_id = None
                sub_cat = None

                # 1. Telegram
                if "telegram" in cat_name or "tg" in cat_name:
                    plat_id = platforms["🔷 Telegram"]
                    if "member" in name_lower or "subscriber" in name_lower:
                        sub_cat = "Telegram Members"
                    elif "view" in name_lower:
                        sub_cat = "Telegram Views"
                    elif "reaction" in name_lower or "emoji" in name_lower:
                        sub_cat = "Telegram Reactions"
                    elif "story" in name_lower:
                        sub_cat = "Telegram Story Views"

                # 2. Facebook
                elif "facebook" in cat_name or "fb" in cat_name:
                    plat_id = platforms["🔵 Facebook"]
                    if "group" in name_lower and "member" in name_lower:
                        sub_cat = "Facebook Group Members"
                    elif "follower" in name_lower or "page like" in name_lower or "profile" in name_lower:
                        sub_cat = "Facebook Followers/Likes"
                    elif "reaction" in name_lower or "like" in name_lower:
                        sub_cat = "Facebook Post Reactions"
                    elif "comment" in name_lower:
                        sub_cat = "Facebook Comments"
                    elif "view" in name_lower or "reel" in name_lower or "video" in name_lower:
                        sub_cat = "Facebook Video/Reels Views"
                    elif "story" in name_lower:
                        sub_cat = "Facebook Story Services"

                # 3. Instagram
                elif "instagram" in cat_name or "ig" in cat_name:
                    plat_id = platforms["🟣 Instagram"]
                    if "follower" in name_lower:
                        sub_cat = "Instagram Followers"
                    elif "like" in name_lower:
                        sub_cat = "Instagram Likes"
                    elif "view" in name_lower or "reel" in name_lower:
                        sub_cat = "Instagram Views/Reels"
                    elif "comment" in name_lower:
                        sub_cat = "Instagram Comments"
                    elif "story" in name_lower:
                        sub_cat = "Instagram Story Services"

                # 4. TikTok
                elif "tiktok" in cat_name:
                    plat_id = platforms["⚫ TikTok"]
                    if "follower" in name_lower:
                        sub_cat = "TikTok Followers"
                    elif "like" in name_lower or "heart" in name_lower:
                        sub_cat = "TikTok Likes"
                    elif "view" in name_lower:
                        sub_cat = "TikTok Video Views"
                    elif "share" in name_lower or "save" in name_lower:
                        sub_cat = "TikTok Shares/Saves"

                # 5. YouTube
                elif "youtube" in cat_name or "yt" in cat_name:
                    plat_id = platforms["🔴 YouTube"]
                    if "subscriber" in name_lower:
                        sub_cat = "YouTube Subscribers"
                    elif "view" in name_lower or "watch" in name_lower:
                        sub_cat = "YouTube Views/WatchTime"
                    elif "like" in name_lower:
                        sub_cat = "YouTube Likes"

                if plat_id and sub_cat:
                    tier_type = "VIP" if ("hq" in name_lower or "real" in name_lower or "non drop" in name_lower or rate > 1.0) else "Budget"
                    
                    if "lifetime" in name_lower or "365" in name_lower or "forever" in name_lower:
                        refill_type = "Lifetime"
                    elif "30" in name_lower or "refill" in name_lower or "guaranteed" in name_lower:
                        refill_type = "30Days"
                    else:
                        refill_type = "NoRefill"

                    key = (plat_id, sub_cat, tier_type, refill_type)
                    if key not in bucket:
                        bucket[key] = []
                    bucket[key].append({
                        'name': name,
                        'smm_id': s_id,
                        'rate': rate,
                        'min': min_q,
                        'max': max_q
                    })

            c.execute("DELETE FROM services WHERE is_special=0")
            total_inserted = 0

            for (p_id, s_cat, t_type, r_type), srv_list in bucket.items():
                srv_list.sort(key=lambda x: x['rate'])
                top5 = srv_list[:5]
                for item in top5:
                    c.execute('''INSERT OR REPLACE INTO services (category_id, sub_category, tier_type, refill_type, name, smm_service_id, base_price, min_qty, max_qty, is_special, is_active)
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1)''',
                              (p_id, s_cat, t_type, r_type, item['name'], item['smm_id'], item['rate'], item['min'], item['max']))
                    total_inserted += 1

            conn.commit()
            conn.close()
            bot.send_message(call.message.chat.id, f"✅ **মাল্টি-লেয়ার অটো-সিঙ্ক সম্পন্ন!**\nমোট `{total_inserted}` টি সার্ভিস সাজানো হয়েছে।", parse_mode="Markdown")
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ সিঙ্ক ত্রুটি: `{str(e)}`", parse_mode="Markdown")

    threading.Thread(target=sync_worker, daemon=True).start()

# --- স্পেশাল অফার কন্ট্রোল ---
@bot.callback_query_handler(func=lambda call: call.data == "adm_manage_special")
def manage_special_deals(call):
    chat_id = call.message.chat.id
    bot.send_message(chat_id, "ফরম্যাট: `Bot_Service_ID 1` (স্পেশাল করতে) অথবা `Bot_Service_ID 0` (বাদ দিতে):", reply_markup=cancel_inline(), parse_mode="Markdown")
    bot.register_next_step_handler(call.message, process_set_special)

def process_set_special(message):
    try:
        s_id, is_sp = message.text.split()
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE services SET is_special=? WHERE id=?", (int(is_sp), int(s_id)))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ সার্ভিস ID {s_id}-এর স্পেশাল অফার স্ট্যাটাস আপডেট হয়েছে।")
    except:
        bot.send_message(message.chat.id, "❌ ভুল ফরম্যাট!")

# --- স্টাফ ও সুপার অ্যাডমিন ২ ম্যানেজমেন্ট ---
@bot.callback_query_handler(func=lambda call: call.data == "adm_subadmin_manage")
def start_staff_management(call):
    chat_id = call.message.chat.id
    if not is_owner(chat_id):
        bot.send_message(chat_id, "❌ শুধুমাত্র মূল সুপার অ্যাডমিন (Owner) কো-ওনার বা স্টাফ নিয়োগ/বাতিল করতে পারবেন।")
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE role='superadmin2'")
    current_sa2 = c.fetchall()
    conn.close()

    sa2_list = ", ".join([f"`{u[0]}`" for u in current_sa2]) or "কেউ নেই"
    
    text = (
        f"👮 **স্টাফ ও সুপার অ্যাডমিন ২ ম্যানেজমেন্ট:**\n\n"
        f"👑 বর্তমান Super Admin 2 ({len(current_sa2)}/5): {sa2_list}\n\n"
        f"👉 নিয়োগ বা বাতিল করতে ফরম্যাট লিখুন:\n"
        f"`UserID role`\n\n"
        f"📌 রোলসমূহ:\n"
        f"• `superadmin2` (কো-ওনার পাওয়ার)\n"
        f"• `subadmin` (শুধু ডিপোজিট/সাপোর্ট)\n"
        f"• `user` (ক্ষমতা বাতিল করে সাধারণ ইউজার করা)\n\n"
        f"উদা: `123456789 superadmin2` অথবা `123456789 user`"
    )
    bot.send_message(chat_id, text, reply_markup=cancel_inline(), parse_mode="Markdown")
    bot.register_next_step_handler(call.message, process_staff_role_change)

def process_staff_role_change(message):
    chat_id = message.chat.id
    if not is_owner(chat_id):
        return

    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.send_message(chat_id, "❌ ভুল ফরম্যাট! লিখুন: `UserID role`", parse_mode="Markdown")
            return

        target_id = int(parts[0])
        role = parts[1].lower()

        if target_id == SUPER_ADMIN_ID:
            bot.send_message(chat_id, "🚫 মূল সুপার অ্যাডমিনের রোল পরিবর্তন করা অসম্ভব!")
            return

        if role not in ['superadmin2', 'subadmin', 'user']:
            bot.send_message(chat_id, "❌ রোল হতে হবে: `superadmin2`, `subadmin` অথবা `user`")
            return

        conn = get_db()
        c = conn.cursor()

        if role == 'superadmin2':
            c.execute("SELECT COUNT(*) FROM users WHERE role='superadmin2'")
            total_sa2 = c.fetchone()[0]
            if total_sa2 >= 5:
                bot.send_message(chat_id, "⚠️ সর্বোচ্চ ৫ জন Super Admin 2 নির্ধারণ করা যাবে।")
                conn.close()
                return

        c.execute("UPDATE users SET role=? WHERE user_id=?", (role, target_id))
        conn.commit()
        conn.close()

        bot.send_message(chat_id, f"✅ ইউজার `{target_id}`-এর পদমর্যাদা সফলভাবে **{role}** করা হয়েছে।", parse_mode="Markdown")
        try:
            bot.send_message(target_id, f"🎖️ আপনাকে বটের **{role.upper()}** পদমর্যাদা প্রদান করা হয়েছে।", parse_mode="Markdown")
        except:
            pass

    except ValueError:
        bot.send_message(chat_id, "❌ আইডি অবশ্যই সঠিক সংখ্যা হতে হবে।")

# --- অ্যাডমিন এডিট অপশনস ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
def execute_admin_ops(call):
    if not is_admin(call.message.chat.id):
        return

    cmd = call.data
    chat_id = call.message.chat.id

    if cmd == "adm_set_margin":
        bot.send_message(chat_id, f"বর্তমান লাভ: `{get_setting('profit_margin')}%`\nনতুন শতকরা লাভ লিখুন:", reply_markup=cancel_inline(), parse_mode="Markdown")
        bot.register_next_step_handler(call.message, lambda m: [set_setting('profit_margin', str(float(m.text))), bot.send_message(chat_id, "✅ প্রফিট মার্জিন সেভ হয়েছে!")])

    elif cmd == "adm_set_daily_bonus":
        bot.send_message(chat_id, f"বর্তমান ডেইলি বোনাস: `${get_setting('daily_bonus_amount')} USD`\nনতুন বোনাস অ্যামাউন্ট লিখুন (যেমন: 0.00013):", reply_markup=cancel_inline(), parse_mode="Markdown")
        bot.register_next_step_handler(call.message, lambda m: [set_setting('daily_bonus_amount', str(float(m.text))), bot.send_message(chat_id, "✅ ডেইলি স্পিন বোনাস আপডেট সম্পন্ন!")])

    elif cmd == "adm_set_usd_rate":
        bot.send_message(chat_id, f"বর্তমান রেট: `1 USD = {get_setting('usd_bdt_rate')} BDT`\nনতুন রেট লিখুন:", reply_markup=cancel_inline(), parse_mode="Markdown")
        bot.register_next_step_handler(call.message, lambda m: [set_setting('usd_bdt_rate', str(float(m.text))), bot.send_message(chat_id, "✅ ডলার রেট আপডেট হয়েছে!")])

    elif cmd == "adm_set_refpct":
        bot.send_message(chat_id, f"বর্তমান রেফার কমিশন: `{get_setting('referral_pct')}%`\nনতুন হার লিখুন:", reply_markup=cancel_inline(), parse_mode="Markdown")
        bot.register_next_step_handler(call.message, lambda m: [set_setting('referral_pct', str(float(m.text))), bot.send_message(chat_id, "✅ রেফারেল কমিশন আপডেট সম্পন্ন!")])

    elif cmd == "adm_set_bonus":
        bot.send_message(chat_id, f"বর্তমান বোনাস: `{get_setting('first_dep_bonus')}%`\nনতুন বোনাস পার্সেন্টেজ লিখুন:", reply_markup=cancel_inline(), parse_mode="Markdown")
        bot.register_next_step_handler(call.message, lambda m: [set_setting('first_dep_bonus', str(float(m.text))), bot.send_message(chat_id, "✅ ডিপোজিট বোনাস রেট সেভ হয়েছে!")])

    elif cmd == "adm_set_mindep":
        bot.send_message(chat_id, f"বর্তমান মিনিমাম ডিপোজিট: `৳{get_setting('min_deposit_bdt')} BDT`\nনতুন লিমিট লিখুন (টাকায়):", reply_markup=cancel_inline(), parse_mode="Markdown")
        bot.register_next_step_handler(call.message, lambda m: [set_setting('min_deposit_bdt', str(float(m.text))), bot.send_message(chat_id, "✅ মিনিমাম ডিপোজিট সেভ হয়েছে!")])

    elif cmd == "adm_toggle_maint":
        curr = get_setting('maintenance')
        new_v = '0' if curr == '1' else '1'
        set_setting('maintenance', new_v)
        bot.send_message(chat_id, f"🛠️ মেইনটেন্যান্স মোড: **{'চালু (ON)' if new_v=='1' else 'বন্ধ (OFF)'}**", parse_mode="Markdown")

    elif cmd == "adm_edit_bkash":
        bot.send_message(chat_id, "নতুন বিকাশ নম্বর ও ধরন লিখুন:", reply_markup=cancel_inline())
        bot.register_next_step_handler(call.message, lambda m: [set_setting('bkash_num', m.text), bot.send_message(chat_id, "✅ বিকাশ নম্বর আপডেট হয়েছে!")])

    elif cmd == "adm_edit_nagad":
        bot.send_message(chat_id, "নতুন নগদ নম্বর ও ধরন লিখুন:", reply_markup=cancel_inline())
        bot.register_next_step_handler(call.message, lambda m: [set_setting('nagad_num', m.text), bot.send_message(chat_id, "✅ নগদ নম্বর আপডেট হয়েছে!")])

    elif cmd == "adm_edit_rocket":
        bot.send_message(chat_id, "নতুন রকেট নম্বর ও ধরন লিখুন:", reply_markup=cancel_inline())
        bot.register_next_step_handler(call.message, lambda m: [set_setting('rocket_num', m.text), bot.send_message(chat_id, "✅ রকেট নম্বর আপডেট হয়েছে!")])

    elif cmd == "adm_add_bal":
        bot.send_message(chat_id, "ফরম্যাট: `UserID USD_Amount`\n(উদা: 8851327780 1.5)", reply_markup=cancel_inline(), parse_mode="Markdown")
        bot.register_next_step_handler(call.message, add_user_bal_step)

    elif cmd == "adm_cut_bal":
        bot.send_message(chat_id, "ফরম্যাট: `UserID USD_Amount`\n(উদা: 8851327780 0.5)", reply_markup=cancel_inline(), parse_mode="Markdown")
        bot.register_next_step_handler(call.message, cut_user_bal_step)

    elif cmd == "adm_ban_user":
        bot.send_message(chat_id, "ইউজার আইডি দিন যাকে ব্যান/আনব্যান করবেন:", reply_markup=cancel_inline())
        bot.register_next_step_handler(call.message, toggle_ban_step)

    elif cmd == "adm_api_bal":
        try:
            res = requests.post(SMM_API_URL, data={'key': SMM_API_KEY, 'action': 'balance'}, headers=HEADERS, timeout=5).json()
            bot.send_message(chat_id, f"🌐 **SMMGen মূল ব্যালেন্স:** `${res.get('balance', 'N/A')} {res.get('currency', 'USD')}`", parse_mode="Markdown")
        except:
            bot.send_message(chat_id, "❌ API সংযোগ বিচ্ছিন্ন।")

    elif cmd == "adm_broadcast":
        bot.send_message(chat_id, "ব্রডকাস্ট মেসেজটি লিখুন:", reply_markup=cancel_inline())
        bot.register_next_step_handler(call.message, broadcast_step)

    elif cmd == "adm_summary":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*), SUM(charge) FROM orders")
        tot_ord, tot_rev = c.fetchone()
        c.execute("SELECT COUNT(*) FROM users")
        tot_usr = c.fetchone()[0]
        conn.close()
        bot.send_message(chat_id, f"📊 **সেলস সামারি রিপোর্ট:**\n\n👥 মোট ইউজার: `{tot_usr}`\n📦 মোট অর্ডার: `{tot_ord}`\n💰 মোট বিক্রি: `${tot_rev or 0:.3f} USD`", parse_mode="Markdown")

    elif cmd == "adm_backup":
        if os.path.exists("boost_enterprise_v4.db"):
            with open("boost_enterprise_v4.db", "rb") as doc:
                bot.send_document(chat_id, doc, caption="💾 ডাটাবেজ ব্যাকআপ ফাইল")
        else:
            bot.send_message(chat_id, "ডাটাবেজ ফাইল পাওয়া যায়নি।")

# --- সাব-স্টেপস ---
def add_user_bal_step(message):
    try:
        u_id, amt = message.text.split()
        update_main_balance(int(u_id), float(amt))
        bot.send_message(int(u_id), f"🎉 অ্যাডমিন আপনার ওয়ালেটে `${float(amt):.4f} USD` যোগ করেছেন।", parse_mode="Markdown")
        bot.send_message(message.chat.id, "✅ ব্যালেন্স সফলভাবে যোগ হয়েছে।")
    except:
        bot.send_message(message.chat.id, "❌ ভুল ফরম্যাট!")

def cut_user_bal_step(message):
    try:
        u_id, amt = message.text.split()
        update_main_balance(int(u_id), -float(amt))
        bot.send_message(int(u_id), f"⚠️ আপনার ওয়ালেট থেকে `${float(amt):.4f} USD` কর্তন করা হয়েছে।", parse_mode="Markdown")
        bot.send_message(message.chat.id, "✅ ব্যালেন্স কর্তন সম্পন্ন।")
    except:
        bot.send_message(message.chat.id, "❌ ভুল ফরম্যাট!")

def toggle_ban_step(message):
    try:
        u_id = int(message.text.strip())
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT is_banned FROM users WHERE user_id=?", (u_id,))
        row = c.fetchone()
        if row:
            new_ban = 0 if row[0] == 1 else 1
            c.execute("UPDATE users SET is_banned=? WHERE user_id=?", (new_ban, u_id))
            conn.commit()
            status = "ব্যান (Banned)" if new_ban == 1 else "আনব্যান (Unbanned)"
            bot.send_message(message.chat.id, f"✅ ইউজার `{u_id}` এখন **{status}**।", parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, "ইউজার পাওয়া যায়নি।")
        conn.close()
    except:
        bot.send_message(message.chat.id, "❌ সঠিক আইডি লিখুন।")

def broadcast_step(message):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE is_banned=0")
    users = c.fetchall()
    conn.close()
    set_setting('notice', message.text)
    sent = 0
    for u in users:
        try:
            bot.send_message(u[0], f"📢 **জরুরি নোটিশ:**\n\n{message.text}", parse_mode="Markdown")
            sent += 1
        except:
            pass
    bot.send_message(message.chat.id, f"✅ মোট {sent} জন ইউজারের কাছে নোটিশ ব্রডকাস্ট সম্পন্ন।")

# --- স্মার্ট আননোন ইনপুট হ্যান্ডলার ---
@bot.message_handler(func=lambda msg: True)
def handle_all_unknown_messages(message):
    if is_spamming(message.chat.id):
        return
    text = (
        "👋 আপনার মেসেজটি বুঝতে পারিনি।\n\n"
        "👇 সোশ্যাল সার্ভিস নিতে নিচের মেনু বাটন ব্যবহার করুন অথবা সহায়তার জন্য আমাদের সাপোর্ট বাটনে যোগাযোগ করুন।"
    )
    msg = bot.send_message(message.chat.id, text, reply_markup=user_keyboard())
    track_msg(message.chat.id, msg.message_id)

# --- ব্যাকগ্রাউন্ড ট্র্যাকার ---
def auto_order_tracker():
    while True:
        try:
            time.sleep(120)
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT order_id, user_id, smm_order_id, service_name, status FROM orders WHERE status IN ('Pending', 'Processing', 'In progress')")
            active_orders = c.fetchall()
            conn.close()

            for o_id, u_id, smm_id, s_name, old_st in active_orders:
                try:
                    res = requests.post(SMM_API_URL, data={'key': SMM_API_KEY, 'action': 'status', 'order': smm_id}, headers=HEADERS, timeout=5).json()
                    if 'status' in res:
                        new_st = res['status']
                        if new_st != old_st:
                            conn = get_db()
                            c = conn.cursor()
                            c.execute("UPDATE orders SET status=? WHERE order_id=?", (new_st, o_id))
                            conn.commit()
                            conn.close()

                            if new_st.lower() in ['completed', 'partial', 'canceled']:
                                emoji_st = "🎉" if new_st.lower() == 'completed' else "⚠️"
                                bot.send_message(
                                    u_id,
                                    f"{emoji_st} **অর্ডার স্ট্যাটাস আপডেট!**\n\n"
                                    f"🔖 **Order ID:** `#{smm_id}`\n"
                                    f"📌 **সার্ভিস:** `{s_name}`\n"
                                    f"📊 **নতুন স্ট্যাটাস:** **{new_st}**",
                                    parse_mode="Markdown"
                                )
                except:
                    pass
        except:
            pass

tracker_thread = threading.Thread(target=auto_order_tracker, daemon=True)
tracker_thread.start()

# --- বট লঞ্চিং ---
print("SocialBoost BD Enterprise Final is live and running...")

# Safe navigation
@bot.callback_query_handler(func=lambda c: c.data in ['back_to_services', 'back_to_cats', 'cancel_order', 'back_cat', 'back_srv'])
def safe_back_nav(c):
    try:
        bot.clear_step_handler_by_chat_id(c.message.chat.id)
    except:
        pass
    try:
        bot.answer_callback_query(c.id)
    except:
        pass
    if 'cat' in c.data:
        try:
            show_categories(c.message.chat.id, c.message.message_id)
        except:
            pass
    else:
        try:
            show_services(c.message.chat.id, c.message.message_id)
        except:
            pass



# --- Back Button & Navigation Handler ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('back_'))
def handle_back_navigation(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    target = call.data.split('_', 1)[1]
    
    try:
        bot.answer_callback_query(call.id)
    except:
        pass

    if target == 'main':
        bot.delete_state(chat_id) if hasattr(bot, 'delete_state') else None
        bot.send_message(chat_id, '🏠 প্রধান মেনু:', reply_markup=main_menu_markup())
    elif target == 'cats':
        show_categories(chat_id, message_id)
    elif target.startswith('cat_'):
        cat_id = target.split('_')[1]
        show_services(chat_id, cat_id, message_id)


@bot.callback_query_handler(func=lambda call: call.data in ['back_to_services', 'back_to_cats', 'back_service', 'back_cat'])
def handle_order_back(call):
    chat_id = call.message.chat.id
    bot.clear_step_handler_by_chat_id(chat_id)
    try:
        bot.answer_callback_query(call.id)
    except:
        pass
    if 'cats' in call.data or 'cat' in call.data:
        if 'show_categories' in globals():
            show_categories(chat_id, call.message.message_id)
        elif 'send_categories' in globals():
            send_categories(call.message)
    else:
        if 'show_services' in globals():
            show_services(chat_id, call.message.message_id)
        elif 'send_services' in globals():
            send_services(call.message)

bot.infinity_polling(timeout=60, long_polling_timeout=60)
