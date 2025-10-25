import numpy as np
from binance.client import Client
from binance import ThreadedWebsocketManager
import time
import os
from datetime import datetime, timedelta
import warnings
import math
import requests
import json
import pandas as pd
from collections import deque
from dotenv import load_dotenv
import subprocess
import io
import random

# Load environment variables dari file .env
load_dotenv()
warnings.filterwarnings('ignore')

# ==================== KONFIGURASI AMAN UNTUK BINANCE ====================
API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
INITIAL_INVESTMENT = float(os.getenv('INITIAL_INVESTMENT', '5.5'))
ORDER_RUN = os.getenv('ORDER_RUN', 'False').lower() == 'true'

# Trading Parameters
TAKE_PROFIT_PCT = 0.0070
STOP_LOSS_PCT = 0.0170
TRAILING_STOP_ACTIVATION = 0.0040
TRAILING_STOP_PCT = 0.0080

# Risk Management
POSITION_SIZING_PCT = 0.4
MAX_DRAWDOWN_PCT = 0.6
ADAPTIVE_CONFIDENCE = True

# PARAMETER TIMEFRAME
# Untuk timeframe 15 menit (M15)
RSI_MIN_15M = 35
RSI_MAX_15M = 65
EMA_SHORT_15M = 12
EMA_LONG_15M = 26
MACD_FAST_15M = 8
MACD_SLOW_15M = 21
MACD_SIGNAL_15M = 7
LRO_PERIOD_15M = 20
VOLUME_PERIOD_15M = 15

# Untuk timeframe 5 menit (M5)
RSI_MIN_5M = 35
RSI_MAX_5M = 68
EMA_SHORT_5M = 5
EMA_LONG_5M = 20
MACD_FAST_5M = 8
MACD_SLOW_5M = 21
MACD_SIGNAL_5M = 8
LRO_PERIOD_5M = 20
VOLUME_PERIOD_5M = 10

# Parameter umum
VOLUME_RATIO_MIN = 0.8

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
SEND_TELEGRAM_NOTIFICATIONS = True

# ==================== RATE LIMITING YANG AMAN ====================
# Config untuk menghindari IP banned - LEBIH KONSERVATIF
DELAY_BETWEEN_COINS = 1.5  # Increased from 1.2s to 3.0s
DELAY_BETWEEN_REQUESTS = 0.5  # Increased from 0.5s to 2.0s
DELAY_AFTER_ERROR = 3.0  # Increased from 3.0s to 10.0s
DELAY_BETWEEN_SCANS = 5.0  # Delay antara scan cycle
MAX_COINS_PER_SCAN = 50  # Batasi jumlah coin yang di-scan per cycle

# Adjust for Render environment
if os.environ.get('RENDER'):
    DELAY_BETWEEN_COINS = 2.0
    DELAY_BETWEEN_REQUESTS = 5.0
    DELAY_AFTER_ERROR = 15.0
    DELAY_BETWEEN_SCANS = 5.0
    MAX_COINS_PER_SCAN = 50

# ==================== TELEGRAM CONTROL SYSTEM ====================
TELEGRAM_CONTROL_ENABLED = True
BOT_RUNNING = False  # Status utama bot
ADMIN_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Configuration file
CONFIG_FILE = 'bot_config.json'

# File Configuration
LOG_FILE = 'trading_log1.txt'
TRADE_HISTORY_FILE = 'trade_history1.json'
BOT_STATE_FILE = 'bot_state1.json'

# Coin List - DIPERSINGKAT untuk mengurangi request
COINS = [
    'PENGUUSDT','WALUSDT','MIRAUSDT','HEMIUSDT','PUMPUSDT','TRXUSDT','LTCUSDT','FFUSDT',
    'SUIUSDT','ASTERUSDT','ZECUSDT','CAKEUSDT','BNBUSDT','AVNTUSDT','DOGEUSDT','ADAUSDT',
    'XPLUSDT','XRPUSDT','DASHUSDT','SOLUSDT','LINKUSDT','AVAXUSDT', 'PEPEUSDT', 
    'FORMUSDT', 'TRUMPUSDT', 'WIFUSDT', 'NEARUSDT', 'WBETHUSDT', 'SHIBUSDT',
    '2ZUSDT', 'LINEAUSDT', 'APEUSDT', 'HBARUSDT', 'DOTUSDT', 'EULUSDT', 'HEIUSDT',  
    'AAVEUSDT', 'ALICEUSDT', 'ENAUSDT', 'BATUSDT', 'HOLOUSDT', 'WLFIUSDT', 'POLUSDT',
    'SNXUSDT', 'TRBUSDT', 'SOMIUSDT', 'ICPUSDT', 'ARPAUSDT', 'EDUUSDT', 'MAGICUSDT', 'OMUSDT',
    'BELUSDT' , 'PHBUSDT', 'APTUSDT', 'DEGOUSDT', 'PROVEUSDT', 'YGGUSDT', 'AMPUSDT', 
    'FTTUSDT', 'LAUSDT', 'SYRUPUSDT', 'AIUSDT', 'RSRUSDT', 'CYBERUSDT', 'OGUSDT', 'PAXGUSDT',
    'AUDIOUSDT', 'ZKCUSDT', 'CTKUSDT', 'ACAUSDT', 'DEXEUSDT'
]

# ==================== INISIALISASI VARIABEL GLOBAL ====================
current_investment = INITIAL_INVESTMENT
active_position = None
buy_signals = []
trade_history = []
client = None
twm = None

# Sistem Proteksi IP
ip_protection = {
    'last_request_time': 0,
    'request_count': 0,
    'banned_until': 0,
    'consecutive_errors': 0,
    'total_requests_today': 0,
    'daily_reset_time': time.time() + 86400  # 24 jam
}

# Sistem Adaptasi
market_state = {
    'trending': False,
    'volatile': False,
    'last_trend_check': None,
    'adx_value': 0
}

coin_performance = {}
dynamic_threshold = 30  # MINIMAL 30, TIDAK BOLEH TURUN DARI INI
recent_trades = deque(maxlen=10)
failed_coins = {}

# === PERFORMANCE FEEDBACK LOOP SYSTEM ===
performance_state = {
    'ema_pnl': 0.0,
    'loss_streak': 0,
    'win_streak': 0,
    'paused_until': 0,
    'last_adaptation_time': 0,
    'total_trades': 0,
    'total_wins': 0
}

# Hyperparameters untuk Feedback Loop
RECENT_WINDOW = 10
LOSS_STREAK_LIMIT = 2
LOSS_STREAK_THRESHOLD_INCREASE = 8
LOSS_STREAK_POSITION_SIZER_MULT = 0.7
LOSS_STREAK_COOLDOWN = 600  # 10 menit
WIN_STREAK_LIMIT = 3
WIN_STREAK_THRESHOLD_DECREASE = 5
EMA_ALPHA = 0.3
MIN_POSITION_SIZING = 0.1  # Minimum 10%
MAX_ADAPTATION_PERCENT = 0.25  # Maksimal perubahan 25%

# ==================== SISTEM PROTEKSI IP BANNED ====================
def safe_request_delay():
    """Delay yang aman antara requests untuk menghindari banned"""
    global ip_protection
    
    current_time = time.time()
    
    # Reset daily counter jika sudah 24 jam
    if current_time > ip_protection['daily_reset_time']:
        ip_protection['total_requests_today'] = 0
        ip_protection['daily_reset_time'] = current_time + 86400
        print("🔄 Daily request counter reset")
    
    # Cek jika IP sedang banned
    if current_time < ip_protection['banned_until']:
        remaining = ip_protection['banned_until'] - current_time
        if remaining > 0:
            print(f"🔴 IP Banned - Waiting {remaining:.0f}s")
            time.sleep(min(remaining, 60))  # Max sleep 60 detik per check
            return False
    
    # Rate limiting: max 1 request per 2 detik
    time_since_last = current_time - ip_protection['last_request_time']
    if time_since_last < DELAY_BETWEEN_REQUESTS:
        sleep_time = DELAY_BETWEEN_REQUESTS - time_since_last
        time.sleep(sleep_time)
    
    ip_protection['last_request_time'] = time.time()
    ip_protection['request_count'] += 1
    ip_protection['total_requests_today'] += 1
    
    # Jika terlalu banyak request hari ini, pause sementara
    if ip_protection['total_requests_today'] > 5000:
        print("⚠️ Daily request limit approaching, pausing for 1 hour")
        ip_protection['banned_until'] = time.time() + 3600
        return False
    
    return True

def handle_binance_error(error):
    """Handle Binance API errors dengan proteksi IP"""
    global ip_protection
    
    error_msg = str(error).lower()
    
    # Deteksi error yang berhubungan dengan banned
    banned_keywords = ['banned', 'rate limit', 'too many', 'ip restricted', '429', '418']
    
    if any(keyword in error_msg for keyword in banned_keywords):
        ip_protection['consecutive_errors'] += 1
        ip_protection['banned_until'] = time.time() + (300 * ip_protection['consecutive_errors'])  # 5 menit per error
        
        ban_msg = f"🔴 IP BANNED DETECTED\nError: {error}\nRetry after: {datetime.fromtimestamp(ip_protection['banned_until']).strftime('%Y-%m-%d %H:%M:%S')}"
        print(ban_msg)
        
        if SEND_TELEGRAM_NOTIFICATIONS:
            send_telegram_message(ban_msg)
        
        return True
    
    # Reset consecutive errors jika bukan banned error
    ip_protection['consecutive_errors'] = max(0, ip_protection['consecutive_errors'] - 1)
    return False

def get_public_ip():
    """Mendapatkan IP publik dengan rate limiting"""
    if not safe_request_delay():
        return None
        
    try:
        print("🌐 Checking public IP address...")
        
        services = [
            'https://api.ipify.org',
            'https://ident.me', 
            'https://checkip.amazonaws.com'
        ]
        
        for service in services:
            try:
                response = requests.get(service, timeout=10)
                if response.status_code == 200:
                    ip = response.text.strip()
                    print(f"✅ Public IP: {ip}")
                    return ip
            except Exception as e:
                continue
        
        return None
        
    except Exception as e:
        print(f"❌ Error getting public IP: {e}")
        return None

# ==================== TELEGRAM & LOGGING ====================
def send_telegram_message(message):
    """Send notification to Telegram dengan improved error handling"""
    if not SEND_TELEGRAM_NOTIFICATIONS:
        return False
        
    try:
        if len(message) > 4000:
            message = message[:4000] + "\n... (message truncated)"
            
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': ADMIN_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        response = requests.post(url, data=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Telegram error: {e}")
        return False

def write_log(entry):
    """Write trading log to file"""
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(entry + '\n')
    except Exception as e:
        print(f"❌ Error writing to log file: {e}")

def initialize_logging():
    """Initialize log file dengan info proteksi IP"""
    try:
        if not os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + '\n')
                f.write("🚀 SAFE TRADING BOT - ANTI IP BANNED VERSION\n")
                f.write("=" * 80 + '\n')
                f.write(f"Bot Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Initial Capital: ${INITIAL_INVESTMENT}\n")
                f.write(f"Rate Limits: {DELAY_BETWEEN_REQUESTS}s between requests\n")
                f.write(f"Max Coins/Scan: {MAX_COINS_PER_SCAN}\n")
                f.write(f"Monitoring: {len(COINS)} coins\n")
                f.write("=" * 80 + '\n\n')
            print(f"✅ Log file initialized: {LOG_FILE}")
    except Exception as e:
        print(f"❌ Error initializing log file: {e}")

# ==================== BINANCE UTILITIES DENGAN PROTEKSI ====================
def initialize_binance_client():
    """Initialize Binance client dengan error handling"""
    global client
    try:
        # ✅ PERBAIKAN: Hapus parameter yang tidak didukung
        client = Client(API_KEY, API_SECRET)
        print("✅ Binance client initialized dengan proteksi IP")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize Binance client: {e}")
        return False

def safe_binance_request(func, *args, **kwargs):
    """Wrapper untuk Binance requests dengan proteksi IP"""
    global ip_protection
    
    # Cek jika sedang banned
    if time.time() < ip_protection['banned_until']:
        remaining = ip_protection['banned_until'] - time.time()
        if remaining > 0:
            print(f"⏳ Waiting {remaining:.0f}s due to IP ban")
            time.sleep(min(remaining, 60))
    
    # Apply rate limiting
    if not safe_request_delay():
        return None
    
    max_retries = 2  # ✅ KURANGI retry untuk lebih aman
    for attempt in range(max_retries):
        try:
            result = func(*args, **kwargs)
            ip_protection['consecutive_errors'] = 0  # Reset error counter
            return result
            
        except Exception as e:
            print(f"❌ Binance request attempt {attempt + 1} failed: {e}")
            
            if handle_binance_error(e):
                return None  # IP banned, stop retrying
            
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + random.uniform(1, 3)
                print(f"⏳ Retrying in {wait_time:.1f}s...")
                time.sleep(wait_time)
            else:
                print("❌ All retry attempts failed")
                return None
    
    return None

def get_current_price(symbol):
    """Get current price dengan proteksi IP"""
    return safe_binance_request(client.get_symbol_ticker, symbol=symbol)

def get_klines_data(symbol, interval, limit=50):
    """Get klines data dengan proteksi IP"""
    return safe_binance_request(client.get_klines, symbol=symbol, interval=interval, limit=limit)

def get_symbol_info(symbol):
    """Get symbol information dengan proteksi IP"""
    return safe_binance_request(client.get_symbol_info, symbol=symbol)

# ==================== INDIKATOR TEKNIKAL ====================
def calculate_ema(prices, period):
    """Calculate EMA dengan error handling"""
    if prices is None or len(prices) < period:
        return None
    
    try:
        prices_clean = [float(price) for price in prices if price is not None and not math.isnan(price)]
        
        if len(prices_clean) < period:
            return None
            
        series = pd.Series(prices_clean)
        ema = series.ewm(span=period, adjust=False).mean()
        return ema.values
    except Exception as e:
        print(f"❌ EMA calculation error: {e}")
        return None

def calculate_rsi(prices, period=14):
    """Calculate RSI"""
    if len(prices) < period + 1:
        return None
    
    try:
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gains = np.zeros(len(prices))
        avg_losses = np.zeros(len(prices))
        
        avg_gains[period] = np.mean(gains[:period])
        avg_losses[period] = np.mean(losses[:period])
        
        for i in range(period + 1, len(prices)):
            avg_gains[i] = (avg_gains[i-1] * (period - 1) + gains[i-1]) / period
            avg_losses[i] = (avg_losses[i-1] * (period - 1) + losses[i-1]) / period
        
        rs = np.divide(avg_gains, avg_losses, out=np.ones_like(avg_gains), where=avg_losses != 0)
        rsi = 100 - (100 / (1 + rs))

        rsi = np.nan_to_num(rsi, nan=50.0, posinf=100.0, neginf=0.0)
        
        return rsi
        
    except Exception as e:
        return None

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Calculate MACD"""
    if len(prices) < slow:
        return None, None, None
    
    try:
        ema_fast = calculate_ema(prices, fast)
        ema_slow = calculate_ema(prices, slow)
        
        if ema_fast is None or ema_slow is None:
            return None, None, None
        
        macd_line = ema_fast - ema_slow
        macd_signal = calculate_ema(macd_line, signal)
        
        if macd_signal is None:
            return None, None, None
            
        macd_histogram = macd_line - macd_signal
        
        return macd_line, macd_signal, macd_histogram
    except Exception as e:
        return None, None, None

# ==================== DATA FETCHING DENGAN PROTEKSI ====================
def get_two_timeframe_data(symbol):
    """Get data dengan proteksi IP dan validation"""
    try:
        # Cek apakah symbol valid
        test_price_data = get_current_price(symbol)
        if not test_price_data:
            print(f"   💀 INVALID SYMBOL: {symbol} - skipping")
            return None, None
        
        print(f"   📊 Fetching data for {symbol}...")
        
        # ✅ TAMBAH DELAY LEBIH PANJANG
        time.sleep(DELAY_BETWEEN_REQUESTS)
        data_15m = get_klines_data(symbol, Client.KLINE_INTERVAL_15MINUTE, 40)
        
        time.sleep(DELAY_BETWEEN_REQUESTS)  # ✅ DELAY antara timeframe
        data_5m = get_klines_data(symbol, Client.KLINE_INTERVAL_5MINUTE, 40)
        
        # ... sisanya tetap sama
        
        # Validasi data
        if data_15m is None or data_5m is None:
            print(f"   📭 No data received for {symbol}")
            return None, None
            
        # Process data
        def process_klines(klines):
            if not klines or len(klines) < 20:
                return None
                
            closes = [float(k[4]) for k in klines]
            highs = [float(k[2]) for k in klines]
            lows = [float(k[3]) for k in klines]
            volumes = [float(k[5]) for k in klines]
            
            return {
                'close': closes,
                'high': highs, 
                'low': lows,
                'volume': volumes
            }
        
        processed_15m = process_klines(data_15m)
        processed_5m = process_klines(data_5m)
        
        if processed_15m and processed_5m:
            print(f"   ✅ Data OK: M15({len(processed_15m['close'])}), M5({len(processed_5m['close'])})")
            return processed_15m, processed_5m
        else:
            print(f"   📭 Insufficient data for {symbol}")
            return None, None
        
    except Exception as e:
        print(f"❌ Error get_two_timeframe_data untuk {symbol}: {e}")
        return None, None

# ==================== SISTEM SINYAL ====================
def analyze_timeframe_improved(data, timeframe, symbol):
    """Analisis timeframe dengan proteksi data"""
    if data is None:
        return False, 0
        
    required_keys = ['close', 'high', 'low', 'volume']
    for key in required_keys:
        if key not in data or data[key] is None or len(data[key]) < 20:
            return False, 0

    try:
        closes = data['close']

        # Tentukan parameter berdasarkan timeframe
        if timeframe == '15m':
            ema_short_period = EMA_SHORT_15M
            ema_long_period = EMA_LONG_15M
            rsi_min = RSI_MIN_15M
            rsi_max = RSI_MAX_15M
        else:  # '5m'
            ema_short_period = EMA_SHORT_5M
            ema_long_period = EMA_LONG_5M
            rsi_min = RSI_MIN_5M
            rsi_max = RSI_MAX_5M

        # Hitung indikator
        ema_short = calculate_ema(closes, ema_short_period)
        ema_long = calculate_ema(closes, ema_long_period)
        rsi = calculate_rsi(closes, 14)

        if any(x is None for x in [ema_short, ema_long, rsi]):
            return False, 0

        current_index = len(closes) - 1

        # Kriteria sederhana untuk mengurangi computation
        price_above_ema_short = closes[current_index] > ema_short[current_index]
        price_above_ema_long = closes[current_index] > ema_long[current_index]
        ema_bullish = ema_short[current_index] > ema_long[current_index]
        rsi_ok = (rsi_min <= rsi[current_index] <= rsi_max)

        # Hitung skor sederhana
        score = 0
        if price_above_ema_short: score += 25
        if price_above_ema_long: score += 20
        if ema_bullish: score += 25
        if rsi_ok: score += 30

        signal_ok = (price_above_ema_short and rsi_ok and ema_bullish)

        return signal_ok, min(score, 100)

    except Exception as e:
        print(f"❌ Error in analyze_timeframe_improved for {symbol}: {str(e)}")
        return False, 0

def analyze_coin_improved(symbol):
    """Analisis coin dengan proteksi IP"""
    if symbol in failed_coins:
        fail_time = failed_coins[symbol]
        if time.time() - fail_time < 600:  # 10 menit cooldown
            return None
        else:
            failed_coins.pop(symbol, None)
    
    try:
        data_15m, data_5m = get_two_timeframe_data(symbol)
        
        if data_15m is None or data_5m is None:
            return None
        
        # Analyze kedua timeframe
        m15_ok, m15_score = analyze_timeframe_improved(data_15m, '15m', symbol)
        m5_ok, m5_score = analyze_timeframe_improved(data_5m, '5m', symbol)
        
        confidence = (m15_score * 0.6) + (m5_score * 0.4)
        confidence = min(95, max(confidence, 0))
        
        # Get current price
        price_data = get_current_price(symbol)
        if not price_data:
            return None
            
        current_price = float(price_data['price'])
        
        buy_signal = (m15_ok and m5_ok) and confidence >= dynamic_threshold
        
        return {
            'symbol': symbol,
            'buy_signal': buy_signal,
            'confidence': confidence,
            'current_price': current_price,
            'm15_signal': m15_ok,
            'm5_signal': m5_ok
        }
        
    except Exception as e:
        print(f"❌ Error in analyze_coin_improved for {symbol}: {str(e)}")
        failed_coins[symbol] = time.time()
        return None

# ==================== ORDER MANAGEMENT ====================
def place_market_buy_order(symbol, investment_amount):
    """Place market buy order dengan proteksi IP"""
    global current_investment
    
    if not safe_request_delay():
        return None
        
    try:
        print(f"🔹 BUY ORDER: {symbol}")
        
        # Untuk simulasi
        if not ORDER_RUN:
            current_price_data = get_current_price(symbol)
            if not current_price_data:
                return None
                
            current_price = float(current_price_data['price'])
            quantity = investment_amount / current_price
            
            print(f"🧪 [SIMULATION] BUY {symbol}")
            print(f"   Investment: ${investment_amount:.2f}")
            print(f"   Price: ${current_price:.6f}")
            print(f"   Quantity: {quantity:.8f}")
            
            return {
                'status': 'FILLED',
                'symbol': symbol,
                'executedQty': str(quantity),
                'fills': [{'price': str(current_price), 'qty': str(quantity)}]
            }

        # LIVE TRADING
        current_price_data = get_current_price(symbol)
        if not current_price_data:
            return None
            
        current_price = float(current_price_data['price'])
        quantity = investment_amount / current_price
        
        # Round quantity
        symbol_info = get_symbol_info(symbol)
        if symbol_info:
            for f in symbol_info['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    step_size = float(f['stepSize'])
                    precision = int(round(-math.log(step_size, 10), 0))
                    quantity = math.floor(quantity / step_size) * step_size
                    quantity = round(quantity, precision)
                    break
        
        order = safe_binance_request(
            client.order_market_buy,
            symbol=symbol,
            quantity=quantity
        )
        
        if order and order.get('status') == 'FILLED':
            print(f"✅ BUY order executed for {symbol}")
            return order
        else:
            print(f"❌ BUY order failed for {symbol}")
            return None
            
    except Exception as e:
        print(f"❌ BUY error: {e}")
        handle_binance_error(e)
        return None

# ==================== MONITORING DENGAN PROTEKSI ====================
def safe_monitor_coins():
    """Monitor coins dengan proteksi IP yang ketat"""
    global BOT_RUNNING, ip_protection
    
    if not BOT_RUNNING:
        return []
    
    # Cek IP ban status
    if time.time() < ip_protection['banned_until']:
        remaining = ip_protection['banned_until'] - time.time()
        if remaining > 300:  # Jika banned > 5 menit, tunggu
            print(f"🔴 IP Banned - Resuming in {remaining/60:.1f} minutes")
            return []
    
    buy_signals = []
    coins_to_scan = COINS[:MAX_COINS_PER_SCAN]  # Batasi jumlah coin
    
    print(f"🔍 SAFE SCANNING {len(coins_to_scan)} coins...")
    print(f"📊 Request stats: Today: {ip_protection['total_requests_today']}, Banned until: {datetime.fromtimestamp(ip_protection['banned_until']).strftime('%H:%M:%S')}")
    
    for i, coin in enumerate(coins_to_scan):
        if not BOT_RUNNING:
            break
            
        # Delay yang aman antara coins
        if i > 0:
            time.sleep(DELAY_BETWEEN_COINS)
        
        try:
            analysis = analyze_coin_improved(coin)
            
            if analysis and analysis['buy_signal']:
                print(f"   🚨 SIGNAL FOUND: {coin} - Confidence: {analysis['confidence']:.1f}%")
                buy_signals.append(analysis)
                
                # Kirim notifikasi
                if SEND_TELEGRAM_NOTIFICATIONS:
                    telegram_msg = f"🚨 <b>BUY SIGNAL DETECTED</b>\n• {coin}: {analysis['confidence']:.1f}%\n• Price: ${analysis['current_price']:.6f}"
                    send_telegram_message(telegram_msg)
                
                # Stop setelah menemukan 1 sinyal untuk mengurangi request
                break
            
            elif analysis:
                print(f"   ❌ {coin}: No signal ({analysis['confidence']:.1f}%)")
            else:
                print(f"   💀 {coin}: No data")
                
        except Exception as e:
            print(f"   ⚠️ {coin}: Error - {e}")
            time.sleep(DELAY_AFTER_ERROR)
    
    return buy_signals

# ==================== MAIN BOT LOGIC YANG AMAN ====================
def main_safe_bot():
    """Main bot function dengan proteksi IP maksimal"""
    global current_investment, active_position, BOT_RUNNING, ip_protection
    
    print("🚀 Starting SAFE TRADING BOT - ANTI IP BANNED")
    print(f"🔧 Configuration: {DELAY_BETWEEN_REQUESTS}s between requests, {MAX_COINS_PER_SCAN} coins/scan")

    # Initialize
    if not initialize_binance_client():
        print("❌ Gagal inisialisasi Binance client")
        return
    
    # Get public IP info
    public_ip = get_public_ip()
    if public_ip and SEND_TELEGRAM_NOTIFICATIONS:
        ip_msg = f"🌐 <b>BOT STARTED SAFELY</b>\nIP: <code>{public_ip}</code>\nMode: {'LIVE' if ORDER_RUN else 'SIMULATION'}\nCoins: {len(COINS)}\nMax per scan: {MAX_COINS_PER_SCAN}"
        send_telegram_message(ip_msg)
    
    consecutive_failed_scans = 0
    last_scan_time = 0
    
    while True:
        try:
            # Check Telegram commands (simple version)
            if TELEGRAM_CONTROL_ENABLED and time.time() - last_scan_time > 10:
                try:
                    # Simple command check tanpa banyak request
                    pass
                except:
                    pass
            
            if not BOT_RUNNING:
                time.sleep(5)
                continue
            
            # Cek jika IP banned untuk waktu lama
            if time.time() < ip_protection['banned_until']:
                remaining = ip_protection['banned_until'] - time.time()
                if remaining > 300:  # 5 menit
                    wait_msg = f"🔴 IP BANNED - Waiting {remaining/60:.1f} minutes"
                    print(wait_msg)
                    time.sleep(60)
                    continue
            
            # Rate limiting antara scans
            time_since_last_scan = time.time() - last_scan_time
            if time_since_last_scan < DELAY_BETWEEN_SCANS:
                sleep_time = DELAY_BETWEEN_SCANS - time_since_last_scan
                print(f"⏳ Waiting {sleep_time:.1f}s before next scan...")
                time.sleep(sleep_time)
            
            # Scan untuk sinyal
            print(f"\n🕐 SAFE SCAN CYCLE #{int(time.time()/DELAY_BETWEEN_SCANS)}")
            signals = safe_monitor_coins()
            last_scan_time = time.time()
            
            if signals:
                # Process first signal
                signal = signals[0]
                print(f"⚡ PROCESSING SIGNAL: {signal['symbol']}")
                
                # Simple execution untuk mengurangi request
                if ORDER_RUN:
                    # Untuk live trading, place order sederhana
                    investment = current_investment * POSITION_SIZING_PCT
                    order = place_market_buy_order(signal['symbol'], investment)
                    
                    if order:
                        print("✅ Order executed successfully!")
                        consecutive_failed_scans = 0
                    else:
                        print("❌ Order execution failed")
                        consecutive_failed_scans += 1
                else:
                    # Simulation mode
                    print("🧪 SIMULATION: Position opened")
                    consecutive_failed_scans = 0
            else:
                print("💤 No signals found")
                consecutive_failed_scans += 1
            
            # Jika terlalu banyak failed scans, pause sebentar
            if consecutive_failed_scans > 10:
                print("⚠️ Many failed scans, pausing for 10 minutes")
                time.sleep(600)
                consecutive_failed_scans = 0
            
            # Print status periodically
            if ip_protection['total_requests_today'] % 100 == 0:
                print(f"📊 Request Stats: Today: {ip_protection['total_requests_today']}, Errors: {ip_protection['consecutive_errors']}")
                
        except KeyboardInterrupt:
            print(f"\n🛑 Bot stopped by user")
            if SEND_TELEGRAM_NOTIFICATIONS:
                send_telegram_message("🛑 <b>BOT DIHENTIKAN OLEH PENGGUNA</b>")
            BOT_RUNNING = False
            break
        except Exception as e:
            print(f"❌ Main loop error: {e}")
            handle_binance_error(e)
            time.sleep(30)
    
    print("✅ Safe bot stopped completely")

# ==================== RENDER COMPATIBILITY ====================
def check_render_environment():
    """Check if running on Render"""
    return os.environ.get('RENDER', False)

def run_background_worker():
    """Run as background worker for Render"""
    print("🔄 Running as Background Worker on Render...")
    main_safe_bot()

# ==================== MAIN EXECUTION ====================
def main():
    if check_render_environment():
        print("🚀 Starting on Render as Background Worker")
        run_background_worker()
    else:
        print("🚀 Starting Safe Trading Bot Locally")
        main_safe_bot()

if __name__ == "__main__":
    main()


