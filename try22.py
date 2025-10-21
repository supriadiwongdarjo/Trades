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
import threading
import sqlite3
import pickle
import random

# Load environment variables dari file .env
load_dotenv()
warnings.filterwarnings('ignore')

# ==================== KONFIGURASI MULTI API KEY ====================
API_KEYS = [
    {
        'API_KEY': os.getenv('BINANCE_API_KEY'),
        'API_SECRET': os.getenv('BINANCE_API_SECRET')
    },
    {
        'API_KEY': os.getenv('BINANCE_API_KEY_2'),
        'API_SECRET': os.getenv('BINANCE_API_SECRET_2')
    },
    {
        'API_KEY': os.getenv('BINANCE_API_KEY_3'),
        'API_SECRET': os.getenv('BINANCE_API_SECRET_3')
    }
]

# Filter out None values
API_KEYS = [key for key in API_KEYS if key['API_KEY'] and key['API_SECRET']]

if not API_KEYS:
    raise ValueError("❌ Tidak ada API Key yang valid ditemukan!")

print(f"✅ {len(API_KEYS)} API Keys loaded")

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
RSI_MIN_15M = 35
RSI_MAX_15M = 65
EMA_SHORT_15M = 12
EMA_LONG_15M = 26
MACD_FAST_15M = 8
MACD_SLOW_15M = 21
MACD_SIGNAL_15M = 7
LRO_PERIOD_15M = 20
VOLUME_PERIOD_15M = 15

RSI_MIN_5M = 35
RSI_MAX_5M = 68
EMA_SHORT_5M = 5
EMA_LONG_5M = 20
MACD_FAST_5M = 8
MACD_SLOW_5M = 21
MACD_SIGNAL_5M = 8
LRO_PERIOD_5M = 20
VOLUME_PERIOD_5M = 10

VOLUME_RATIO_MIN = 0.8

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
SEND_TELEGRAM_NOTIFICATIONS = True

# ==================== TELEGRAM CONTROL SYSTEM ====================
TELEGRAM_CONTROL_ENABLED = True
BOT_RUNNING = False
ADMIN_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Configuration file
CONFIG_FILE = 'bot_config.json'

# File Configuration
LOG_FILE = 'trading_log1.txt'
TRADE_HISTORY_FILE = 'trade_history1.json'
BOT_STATE_FILE = 'bot_state1.json'

# Coin List - dipersingkat untuk testing
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
current_api_key_index = 0

# Sistem Adaptasi
market_state = {
    'trending': False,
    'volatile': False,
    'last_trend_check': None,
    'adx_value': 0
}

coin_performance = {}
dynamic_threshold = 30
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
LOSS_STREAK_COOLDOWN = 600
WIN_STREAK_LIMIT = 3
WIN_STREAK_THRESHOLD_DECREASE = 5
EMA_ALPHA = 0.3
MIN_POSITION_SIZING = 0.1
MAX_ADAPTATION_PERCENT = 0.25

# ==================== API KEY ROTATION SYSTEM ====================
class APIRotationManager:
    def __init__(self, api_keys):
        self.api_keys = api_keys
        self.current_index = 0
        self.failed_keys = {}
        self.key_usage_count = {i: 0 for i in range(len(api_keys))}
        self.last_rotation = time.time()
        self.rotation_interval = 300  # Rotate every 5 minutes
        
    def get_current_client(self):
        """Get current active client"""
        return initialize_binance_client()
    
    def rotate_if_needed(self):
        """Rotate API key jika diperlukan"""
        current_time = time.time()
        
        # Rotate berdasarkan waktu
        if current_time - self.last_rotation > self.rotation_interval:
            self.rotate_key()
            return True
            
        # Rotate jika current key bermasalah
        if self.current_index in self.failed_keys:
            fail_time = self.failed_keys[self.current_index]
            if current_time - fail_time < 60:  # Key baru saja gagal
                self.rotate_key()
                return True
                
        return False
    
    def rotate_key(self):
        """Rotate ke API key berikutnya"""
        old_index = self.current_index
        self.current_index = (self.current_index + 1) % len(self.api_keys)
        self.last_rotation = time.time()
        
        print(f"🔄 API Key rotated: {old_index} -> {self.current_index}")
        
        # Reinitialize client dengan key baru
        global client
        client = self.initialize_with_current_key()
        
    def initialize_with_current_key(self):
        """Initialize client dengan current key"""
        try:
            api_key = self.api_keys[self.current_index]
            new_client = Client(api_key['API_KEY'], api_key['API_SECRET'], {"timeout": 30})
            print(f"✅ Client initialized with API Key {self.current_index}")
            return new_client
        except Exception as e:
            print(f"❌ Failed to initialize with API Key {self.current_index}: {e}")
            self.mark_key_failed()
            return None
    
    def mark_key_failed(self):
        """Tandai key saat ini sebagai gagal"""
        self.failed_keys[self.current_index] = time.time()
        print(f"❌ API Key {self.current_index} marked as failed")
        self.rotate_key()
    
    def mark_request_success(self):
        """Tandai request berhasil"""
        self.key_usage_count[self.current_index] += 1
        
    def get_usage_stats(self):
        """Dapatkan statistik penggunaan API key"""
        return self.key_usage_count

# Initialize API Rotation Manager
api_manager = APIRotationManager(API_KEYS)

# ==================== ADVANCED RATE LIMITING SYSTEM ====================
class SmartRateLimiter:
    def __init__(self):
        self.last_request_time = 0
        self.min_interval = 0.2  # 200ms between requests
        self.request_count = 0
        self.window_start = time.time()
        self.max_requests_per_minute = 40  # Conservative limit
        
    def wait_if_needed(self):
        """Wait jika diperlukan untuk mematuhi rate limits"""
        current_time = time.time()
        
        # Reset counter setiap menit
        if current_time - self.window_start > 60:
            self.request_count = 0
            self.window_start = current_time
            
        # Check minute limit
        if self.request_count >= self.max_requests_per_minute:
            sleep_time = 60 - (current_time - self.window_start)
            if sleep_time > 0:
                print(f"⏳ Rate limit: waiting {sleep_time:.1f}s")
                time.sleep(sleep_time)
                self.request_count = 0
                self.window_start = time.time()
        
        # Wait between requests
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_interval:
            sleep_time = self.min_interval - time_since_last
            time.sleep(sleep_time)
            
        self.last_request_time = time.time()
        self.request_count += 1

# Global rate limiter
rate_limiter = SmartRateLimiter()

def rate_limited_request(func):
    """Decorator untuk rate limiting"""
    def wrapper(*args, **kwargs):
        rate_limiter.wait_if_needed()
        try:
            result = func(*args, **kwargs)
            api_manager.mark_request_success()
            return result
        except Exception as e:
            if "API key" in str(e) or "IP banned" in str(e) or "too much" in str(e).lower():
                print(f"🔄 API issue detected, rotating key: {e}")
                api_manager.mark_key_failed()
                rate_limiter.wait_if_needed()  # Extra wait after error
                return func(*args, **kwargs)  # Retry with new key
            raise e
    return wrapper

# ==================== CACHE SYSTEM ====================
def setup_cache_db():
    """Setup SQLite untuk cache data"""
    try:
        conn = sqlite3.connect('trading_cache.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS kline_cache (
                symbol TEXT,
                interval TEXT,
                timestamp INTEGER,
                data BLOB,
                PRIMARY KEY (symbol, interval, timestamp)
            )
        ''')
        conn.commit()
        conn.close()
        print("✅ Cache database initialized")
    except Exception as e:
        print(f"❌ Cache setup error: {e}")

def cache_klines_data(symbol, interval, data):
    """Cache klines data"""
    try:
        conn = sqlite3.connect('trading_cache.db')
        cursor = conn.cursor()
        timestamp = int(time.time() // 300) * 300  # Cache for 5 minutes
        
        cursor.execute('''
            INSERT OR REPLACE INTO kline_cache (symbol, interval, timestamp, data)
            VALUES (?, ?, ?, ?)
        ''', (symbol, interval, timestamp, pickle.dumps(data)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Cache error: {e}")

def get_cached_data(symbol, interval):
    """Get cached klines data"""
    try:
        conn = sqlite3.connect('trading_cache.db')
        cursor = conn.cursor()
        timestamp = int(time.time() // 300) * 300
        
        cursor.execute('''
            SELECT data FROM kline_cache 
            WHERE symbol=? AND interval=? AND timestamp=?
        ''', (symbol, interval, timestamp))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return pickle.loads(result[0])
    except:
        pass
    return None

# ==================== TELEGRAM & LOGGING ====================
def send_ip_to_telegram():
    """Kirim IP server ke Telegram untuk whitelist"""
    try:
        ip = requests.get("https://api.ipify.org", timeout=10).text.strip()
        print(f"🌍 Server Public IP: {ip}")

        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            msg = f"🚀 Bot started on Render\n🌐 Public IP: {ip}\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": msg},
                timeout=10
            )
    except Exception as e:
        print(f"⚠️ Gagal kirim IP: {e}")

def send_telegram_message(message):
    """Send notification to Telegram dengan improved error handling"""
    if not SEND_TELEGRAM_NOTIFICATIONS or not TELEGRAM_BOT_TOKEN:
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

# ... (Keep all the existing Telegram, logging, and configuration functions unchanged)
# [Semua fungsi Telegram, logging, dan configuration management tetap sama seperti sebelumnya]
# Untuk menghemat space, saya tidak menulis ulang semuanya

def write_log(entry):
    """Write trading log to file"""
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(entry + '\n')
    except Exception as e:
        print(f"❌ Error writing to log file: {e}")

def initialize_logging():
    """Initialize log file with header"""
    try:
        if not os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + '\n')
                f.write("🚀 ADVANCED TRADING BOT - 2TF (M15 + M5) + LRO STRATEGY\n")
                f.write("=" * 80 + '\n')
                f.write(f"Bot Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Initial Capital: ${INITIAL_INVESTMENT}\n")
                f.write(f"TP: +{TAKE_PROFIT_PCT*100}% | SL: -{STOP_LOSS_PCT*100}%\n")
                f.write(f"Position Sizing: {POSITION_SIZING_PCT*100}%\n")
                f.write(f"Monitoring: {len(COINS)} coins\n")
                f.write(f"API Keys: {len(API_KEYS)} available\n")
                f.write("Timeframes: M15 + M5 dengan LRO\n")
                f.write("=" * 80 + '\n\n')
            print(f"✅ Log file initialized: {LOG_FILE}")
    except Exception as e:
        print(f"❌ Error initializing log file: {e}")

# ==================== BINANCE UTILITIES DENGAN ROTATION ====================
def initialize_binance_client():
    """Initialize Binance client dengan rotation system"""
    global client
    try:
        # Use API manager to get client
        client = api_manager.initialize_with_current_key()
        if client:
            print(f"✅ Binance client initialized with API Key {api_manager.current_index}")
            return True
        else:
            return False
    except Exception as e:
        print(f"❌ Failed to initialize Binance client: {e}")
        return False

@rate_limited_request
def get_klines_data(symbol, interval, limit=50):
    """Get klines data dengan rate limiting dan rotation"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Rotate API key jika diperlukan
            api_manager.rotate_if_needed()
            
            klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
            if klines and len(klines) >= 20:
                processed_data = process_klines_data(klines)
                if processed_data:
                    cache_klines_data(symbol, interval, processed_data)
                return processed_data
            else:
                print(f"   ⚠️ Insufficient data for {symbol} {interval}: {len(klines) if klines else 0} candles")
                time.sleep(1)
                
        except Exception as e:
            print(f"   ⚠️ Attempt {attempt + 1} failed for {symbol}: {e}")
            if attempt < max_retries - 1:
                if "API key" in str(e) or "IP banned" in str(e) or "too much" in str(e).lower():
                    api_manager.mark_key_failed()
                    print(f"   🔄 Rotating API key due to error: {e}")
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                print(f"   ❌ All attempts failed for {symbol}")
    
    return None

@rate_limited_request
def get_current_price(symbol):
    """Get current price dengan rate limiting"""
    try:
        ticker = client.get_symbol_ticker(symbol=symbol)
        price = float(ticker['price'])
        precision = get_price_precision(symbol)
        return round(price, precision)
    except Exception as e:
        print(f"❌ Error getting price for {symbol}: {e}")
        return None

@rate_limited_request
def get_symbol_info(symbol):
    """Get symbol information dengan rate limiting"""
    try:
        info = client.get_symbol_info(symbol)
        return info
    except Exception as e:
        return None

# ... (Keep all other existing functions but ensure they use rate_limited_request decorator where needed)

def get_two_timeframe_data(symbol):
    """Get data dengan validation yang ketat dan rate limiting"""
    try:
        test_price = get_current_price(symbol)
        if not test_price:
            print(f"   💀 INVALID SYMBOL: {symbol} - skipping")
            return None, None
        
        print(f"   📊 Fetching data for {symbol}...")
        
        # Gunakan cache jika available
        cached_15m = get_cached_data(symbol, Client.KLINE_INTERVAL_15MINUTE)
        cached_5m = get_cached_data(symbol, Client.KLINE_INTERVAL_5MINUTE)
        
        data_15m = cached_15m
        data_5m = cached_5m
        
        # Jika cache tidak available, fetch dari API
        if not data_15m:
            data_15m = get_klines_data(symbol, Client.KLINE_INTERVAL_15MINUTE, 40)
        if not data_5m:
            data_5m = get_klines_data(symbol, Client.KLINE_INTERVAL_5MINUTE, 40)
        
        if data_15m is None or data_5m is None:
            print(f"   📭 No data received for {symbol}")
            return None, None
            
        min_data_points = 20
        if (len(data_15m['close']) < min_data_points or 
            len(data_5m['close']) < min_data_points):
            print(f"   📭 Insufficient data points for {symbol}")
            return None, None
            
        print(f"   ✅ Data OK: M15({len(data_15m['close'])}), M5({len(data_5m['close'])})")
        return data_15m, data_5m
        
    except Exception as e:
        print(f"❌ Error get_two_timeframe_data untuk {symbol}: {e}")
        return None, None

# ==================== OPTIMIZED COIN SCANNING ====================
def get_coins_batch(batch_size=15):
    """Split coins into batches untuk mengurangi request"""
    for i in range(0, len(COINS), batch_size):
        yield COINS[i:i + batch_size]

def monitor_coins_optimized():
    """Optimized coin monitoring dengan batch processing"""
    global buy_signals, BOT_RUNNING
    
    buy_signals = []
    signals_found = 0
    total_scanned = 0
    
    print(f"\n🔍 OPTIMIZED SCANNING - {len(COINS)} coins in batches")
    
    for batch in get_coins_batch(15):  # Process 15 coins per batch
        if not BOT_RUNNING:
            print("🛑 Scanning interrupted by /stop command")
            return []
            
        batch_signals = process_coin_batch(batch)
        buy_signals.extend(batch_signals)
        signals_found += len(batch_signals)
        total_scanned += len(batch)
        
        print(f"   📊 Batch complete: {len(batch)} coins, {len(batch_signals)} signals")
        
        # Jika sudah menemukan sinyal, stop scanning
        if buy_signals:
            print(f"   ⚡ STOPPING SCAN - Found {len(buy_signals)} signals")
            return buy_signals
            
        # Delay antara batch
        if total_scanned < len(COINS):
            print("   💤 Batch delay: 3 seconds...")
            time.sleep(3)
    
    print(f"\n📊 SCAN COMPLETE: No signals found in {len(COINS)} coins")
    return []

def process_coin_batch(coins_batch):
    """Process a batch of coins"""
    batch_signals = []
    
    for coin in coins_batch:
        if not BOT_RUNNING:
            break
            
        try:
            analysis = analyze_coin_improved(coin)
            
            if analysis and analysis['buy_signal']:
                print(f"   🚨 SIGNAL FOUND: {coin} - Confidence: {analysis['confidence']:.1f}%")
                batch_signals.append(analysis)
                
                telegram_msg = f"🚨 <b>BUY SIGNAL DETECTED</b>\n• {coin}: {analysis['confidence']:.1f}%\n• Price: ${analysis['current_price']:.6f}"
                send_telegram_message(telegram_msg)
        
        except Exception as e:
            print(f"   ⚠️ {coin}: Error - {e}")
            continue
            
    return batch_signals

# ==================== MAIN BOT LOGIC OPTIMIZED ====================
def main_optimized():
    """Main bot function yang dioptimalkan untuk menghindari IP banned"""
    global current_investment, active_position, twm, BOT_RUNNING
    
    print("🚀 Starting OPTIMIZED BOT - MULTI API KEY SYSTEM")

    # Load configuration dan state
    update_global_variables_from_config()
    initialize_logging()
    load_trade_history()
    load_bot_state()
    setup_cache_db()
    
    if not initialize_binance_client():
        print("❌ Binance client gagal diinisialisasi")
        return
    
    startup_msg = (f"🤖 <b>BOT STARTED - OPTIMIZED VERSION</b>\n"
                  f"Coins: {len(COINS)}\n"
                  f"API Keys: {len(API_KEYS)} available\n"
                  f"Mode: {'LIVE' if ORDER_RUN else 'SIMULATION'}\n"
                  f"Status: MENUNGGU PERINTAH /start")
    send_telegram_message(startup_msg)
    
    consecutive_errors = 0
    last_feedback_check = 0
    last_telegram_check = 0
    last_api_stats = time.time()
    
    print("✅ Bot siap. Gunakan Telegram untuk mengontrol (/start untuk mulai)")
    
    while True:
        try:
            current_time = time.time()
            
            # Check Telegram commands
            if current_time - last_telegram_check > 3:
                if TELEGRAM_CONTROL_ENABLED:
                    handle_telegram_command()
                last_telegram_check = current_time
            
            if not BOT_RUNNING:
                time.sleep(1)
                continue
            
            # Check API stats periodically
            if current_time - last_api_stats > 60:
                stats = api_manager.get_usage_stats()
                print(f"📊 API Usage Stats: {stats}")
                last_api_stats = current_time
            
            if is_trading_paused():
                time.sleep(5)
                continue
            
            # Check connection dengan rotation
            try:
                api_manager.rotate_if_needed()
                client.ping()
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                print(f"❌ Connection error #{consecutive_errors}: {e}")
                
                if consecutive_errors >= 2:
                    print("🔄 Rotating API key due to consecutive errors")
                    api_manager.rotate_key()
                    consecutive_errors = 0
                    
                time.sleep(5)
                continue
            
            # Performance feedback
            if current_time - last_feedback_check > 300:
                trade_performance_feedback_loop()
                last_feedback_check = current_time
            
            # Monitor active position
            if active_position:
                monitor_active_position()
                time.sleep(0.5)
                continue
            
            # Scan for new signals dengan optimized approach
            print(f"\n🕐 Optimized scanning... (API Key: {api_manager.current_index}, Threshold: {dynamic_threshold}%)")
            signals = monitor_coins_optimized()
            
            if signals:
                signal = signals[0]
                if fast_execute_signal(signal):
                    print("✅ Trade executed successfully!")
                else:
                    print("❌ Execution failed, continuing scan...")
                    time.sleep(2)
            else:
                print("💤 No signals, waiting 5s...")
                time.sleep(5)
                
            save_bot_state()
                
        except KeyboardInterrupt:
            print(f"\n🛑 Bot stopped by user")
            send_telegram_message("🛑 <b>BOT DIHENTIKAN OLEH PENGGUNA</b>")
            BOT_RUNNING = False
            break
        except Exception as e:
            print(f"❌ Main loop error: {e}")
            time.sleep(10)
    
    stop_websocket_monitoring()
    save_bot_state()
    print("✅ Bot stopped completely")

def monitor_active_position():
    """Monitor position aktif (untuk simulation mode)"""
    global active_position
    
    if not active_position or ORDER_RUN:
        return
        
    current_price = get_current_price(active_position['symbol'])
    if current_price:
        pnl_pct = (current_price - active_position['entry_price']) / active_position['entry_price'] * 100
        print(f"📊 {active_position['symbol']}: ${current_price:.6f} | PnL: {pnl_pct:+.2f}%")
        
        if current_price >= active_position['take_profit']:
            execute_market_sell(active_position['symbol'], active_position['quantity'], 
                              active_position['entry_price'], "TAKE PROFIT")
        elif current_price <= active_position['stop_loss']:
            execute_market_sell(active_position['symbol'], active_position['quantity'], 
                              active_position['entry_price'], "STOP LOSS")

# ==================== ORDER MANAGEMENT DENGAN RATE LIMITING ====================
@rate_limited_request
def place_market_buy_order(symbol, investment_amount):
    """Place market buy order dengan rate limiting"""
    global current_investment
    
    try:
        print(f"🔹 BUY ORDER: {symbol}")
        
        # [Implementation tetap sama seperti sebelumnya]
        # ... existing implementation ...
        
    except Exception as e:
        print(f"❌ BUY error: {e}")
        return None

@rate_limited_request
def execute_market_sell(symbol, quantity, entry_price, exit_type):
    """Execute market sell order dengan rate limiting"""
    global current_investment, active_position
    
    try:
        # [Implementation tetap sama seperti sebelumnya]
        # ... existing implementation ...
        
    except Exception as e:
        print(f"❌ Fast SELL error: {e}")
        active_position = None
        return False

# Keep all other existing functions unchanged
# [Semua fungsi teknikal analysis, risk management, dll. tetap sama]

def main():
    main_optimized()

if __name__ == "__main__":
    send_ip_to_telegram()
    main()
