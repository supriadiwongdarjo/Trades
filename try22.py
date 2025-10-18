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
warnings.filterwarnings('ignore')

# ==================== KONFIGURASI ====================
API_KEY = 'WnrNZOopN6XjF7WsGIH6lrhAAeZl6zyywLbFmtM9znce3WH4bHW0o3bOCpvBDrCK'
API_SECRET = 'wvBYG5HI7RM1XwnCn1mIvsV8yiY4oI8IPvb19HDhNsj7FPHQ0dyntmPDXp8lPmr1'
INITIAL_INVESTMENT = 5.5
ORDER_RUN = True

# Trading Parameters
TAKE_PROFIT_PCT = 0.0060
STOP_LOSS_PCT = 0.0170
TRAILING_STOP_ACTIVATION = 0.0040
TRAILING_STOP_PCT = 0.0080

# Risk Management
POSITION_SIZING_PCT = 0.4
MAX_DRAWDOWN_PCT = 0.6
ADAPTIVE_CONFIDENCE = True

# PARAMETER YANG BISA DIAKTUR - SESUAI TIMEFRAME
# Untuk timeframe 15 menit (M15)
RSI_MIN_15M = 30        # Bisa diubah: RSI minimum untuk M15 (semakin tinggi semakin ketat)
RSI_MAX_15M = 70        # Bisa diubah: RSI maximum untuk M15 (semakin rendah semakin ketat)
EMA_SHORT_15M = 12      # Bisa diubah: Periode EMA pendek M15
EMA_LONG_15M = 26       # Bisa diubah: Periode EMA panjang M15
MACD_FAST_15M = 8      # Bisa diubah: MACD fast M15
MACD_SLOW_15M = 21      # Bisa diubah: MACD slow M15
MACD_SIGNAL_15M = 5     # Bisa diubah: MACD signal M15
LRO_PERIOD_15M = 20     # Bisa diubah: Periode LRO M15
VOLUME_PERIOD_15M = 15  # Bisa diubah: Periode volume M15

# Untuk timeframe 5 menit (M5) - LEBIH SENSITIF
RSI_MIN_5M = 33         # Bisa diubah: RSI minimum untuk M5 (biasanya lebih tinggi dari M15)
RSI_MAX_5M = 68         # Bisa diubah: RSI maximum untuk M5 (biasanya lebih rendah dari M15)
EMA_SHORT_5M = 5        # Bisa diubah: Periode EMA pendek M5 (lebih pendek untuk sensitivitas)
EMA_LONG_5M = 20        # Bisa diubah: Periode EMA panjang M5 
MACD_FAST_5M = 8        # Bisa diubah: MACD fast M5 (lebih pendek)
MACD_SLOW_5M = 21       # Bisa diubah: MACD slow M5
MACD_SIGNAL_5M = 5      # Bisa diubah: MACD signal M5
LRO_PERIOD_5M = 20      # Bisa diubah: Periode LRO M5 (lebih pendek)
VOLUME_PERIOD_5M = 10   # Bisa diubah: Periode volume M5 (lebih pendek)

# Parameter umum
VOLUME_RATIO_MIN = 0.5  # Bisa diubah: Rasio volume minimum

# Telegram Configuration
TELEGRAM_BOT_TOKEN = '8094484109:AAF9Z3lQUxdQFqqeG6NKV9O1EC0vrxzJy0U'
TELEGRAM_CHAT_ID = '8041197505'
SEND_TELEGRAM_NOTIFICATIONS = True

# File Configuration
LOG_FILE = 'trading_log1.txt'
TRADE_HISTORY_FILE = 'trade_history1.json'
BOT_STATE_FILE = 'bot_state1.json'

# Coin List (tetap sama)
# COINS = [
#     'ZBTUSDT', 'ZKCUSDT', 'PHBUSDT', 'ALICEUSDT', 'KMNOUSDT', 'ENAUSDT', 'MAGICUSDT',
#     'PROVEUSDT', 'LAUSDT', 'EDUUSDT', 'STOUSDT', 'HEIUSDT', 'JTOUSDT', 'RLCUSDT', 'OGUSDT',
#     'LAUSDT' 
# ]

COINS = [
    # Layer 1 & Layer 2 Protocols (Volatilitas Menengah Stabil)
    "ADAUSDT",    # Cardano - pergerakan teknis clean
    "MATICUSDT",   # Polygon - volatilitas konsisten
    "ALGOUSDT",    # Algorand - pattern predictable
    "ARBUSDT",     # Arbitrum - movement smooth
    "AVAXUSDT",    # Avalanche - liquid dan stabil
    "ATOMUSDT",    # Cosmos - volatilitas terkontrol
    "FTMUSDT",     # Fantom - pergerakan teknis bagus
    "NEARUSDT",    # NEAR Protocol - volatilitas ideal
    "APTUSDT",     # Aptos - movement konsisten
    "SUIUSDT",     # Sui - volatilitas menengah
    "SEIUSDT",     # Sei - pattern predictable
    "INJUSDT",     # Injective - volatilitas terkendali
    "OSMOUSDT",    # Osmosis - pergerakan smooth
    
    # DeFi & Ecosystem Tokens
    "LINKUSDT",    # Chainlink - volatilitas stabil
    "DOTUSDT",     # Polkadot - movement konsisten
    "UNIUSDT",     # Uniswap - pergerakan teknis
    "AAVEUSDT",    # Aave - volatilitas menengah
    "COMPUSDT",    # Compound - pattern clean
    "MKRUSDT",     # Maker - movement predictable
    "SNXUSDT",     # Synthetix - volatilitas terkontrol
    
    # Gaming & Metaverse
    "SANDUSDT",    # The Sandbox - volatilitas ideal
    "MANAUSDT",    # Decentraland - pergerakan smooth
    "GALAUSDT",    # Gala - pattern konsisten
    "ENJUSDT",     # Enjin Coin - movement predictable
    
    # AI & Big Data
    "AGIXUSDT",    # SingularityNET - volatilitas menengah
    "OCEANUSDT",   # Ocean Protocol - pergerakan clean
    "FETUSDT",     # Fetch.ai - movement terkontrol
    "GRTUSDT",     # The Graph - volatilitas stabil
    
    # Infrastructure & Storage
    "FILUSDT",     # Filecoin - pergerakan konsisten
    "STORJUSDT",   # Storj - volatilitas menengah
    "ARUSDT",      # Arweave - pattern predictable
    
    # Exchange Tokens (yang volatilitasnya moderate)
    "FTTUSDT",     # FTX Token - movement smooth
    "LEOUSDT",     # LEO Token - volatilitas terkendali
    
    # Oracle & Middleware
    "BANDUSDT",    # Band Protocol - pergerakan clean
    "TRBUSDT",     # Tellor - volatilitas menengah
    
    # Liquid Staking & LSD
    "LDOUSDT",     # Lido DAO - movement predictable
    "RPLUSDT"      # Rocket Pool - volatilitas stabil
]

# COINS = [
#     'PENGUUSDT','WALUSDT','MIRAUSDT','HEMIUSDT','PUMPUSDT','TRXUSDT','LTCUSDT','FFUSDT',
#     'SUIUSDT','ASTERUSDT','ZECUSDT','CAKEUSDT','BNBUSDT','AVNTUSDT','DOGEUSDT','ADAUSDT',
#     'XPLUSDT','XRPUSDT','DASHUSDT','SOLUSDT','LINKUSDT','AVAXUSDT', 'PEPEUSDT', 
#     'FORMUSDT', 'TRUMPUSDT', 'WIFUSDT', 'NEARUSDT', 'WBETHUSDT', 'SHIBUSDT',
#     '2ZUSDT', 'LINEAUSDT', 'APEUSDT', 'HBARUSDT', 'DOTUSDT', 'EULUSDT', 'HEIUSDT',  
#     'AAVEUSDT', 'ALICEUSDT', 'ENAUSDT', 'BATUSDT', 'HOLOUSDT', 'WLFIUSDT', 'POLUSDT',
#     'SNXUSDT', 'TRBUSDT', 'SOMIUSDT', 'ICPUSDT', 'ARPAUSDT', 'EDUUSDT', 'MAGICUSDT', 'OMUSDT',
#     'BELUSDT' , 'PHBUSDT', 'APTUSDT', 'DEGOUSDT', 'PROVEUSDT', 'YGGUSDT', 'AMPUSDT', 
#     'FTTUSDT', 'LAUSDT', 'SYRUPUSDT', 'AIUSDT', 'RSRUSDT', 'CYBERUSDT', 'OGUSDT', 'PAXGUSDT',
#     'AUDIOUSDT', 'ZKCUSDT', 'CTKUSDT', 'ACAUSDT', 'DEXEUSDT'
# ]


# ==================== INISIALISASI VARIABEL GLOBAL ====================
current_investment = INITIAL_INVESTMENT
active_position = None
buy_signals = []
trade_history = []
client = None
twm = None

# Sistem Adaptasi
market_state = {
    'trending': False,
    'volatile': False,
    'last_trend_check': None,
    'adx_value': 0
}

coin_performance = {}
dynamic_threshold = 25
recent_trades = deque(maxlen=10)
failed_coins = {}

# ==================== TELEGRAM & LOGGING ====================
def send_telegram_message(message):
    """Send notification to Telegram"""
    if not SEND_TELEGRAM_NOTIFICATIONS:
        return
        
    try:
        if len(message) > 4000:
            message = message[:4000] + "\n... (message truncated)"
            
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
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
                f.write("Timeframes: M15 + M5 dengan LRO\n")
                f.write("=" * 80 + '\n\n')
            print(f"✅ Log file initialized: {LOG_FILE}")
    except Exception as e:
        print(f"❌ Error initializing log file: {e}")

def log_position_opened(symbol, entry_price, quantity, take_profit, stop_loss, confidence):
    """Log when position is opened"""
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        tp_pct = ((take_profit - entry_price) / entry_price) * 100
        sl_pct = ((entry_price - stop_loss) / entry_price) * 100
        
        log_entry = (f"[{timestamp}] 📈 POSITION OPENED | {symbol} | "
                    f"Entry: ${entry_price:.6f} | Qty: {quantity:.6f} | "
                    f"TP: ${take_profit:.6f} (+{tp_pct:.2f}%) | SL: ${stop_loss:.6f} (-{sl_pct:.2f}%) | "
                    f"Confidence: {confidence:.1f}% | Capital: ${current_investment:.2f}")
        
        write_log(log_entry)
        
        telegram_msg = (f"📈 <b>POSITION OPENED</b>\n"
                      f"┌────────────────────────────┐\n"
                      f"│ <b>{symbol}</b>\n"
                      f"├────────────────────────────┤\n"
                      f"│ Entry:      ${entry_price:.6f}\n"
                      f"│ Quantity:   {quantity:.6f}\n"
                      f"│ Take Profit: ${take_profit:.6f} (+{TAKE_PROFIT_PCT*100:.2f}%)\n"
                      f"│ Stop Loss:   ${stop_loss:.6f} (-{STOP_LOSS_PCT*100:.2f}%)\n"
                      f"│ Confidence:  {confidence:.1f}%\n"
                      f"│ Capital:     <b>${current_investment:.2f}</b>\n"
                      f"└────────────────────────────┘")
        
        send_telegram_message(telegram_msg)
        
    except Exception as e:
        print(f"❌ Error logging position open: {e}")

def log_position_closed(symbol, entry_price, exit_price, quantity, exit_type):
    """Log when position is closed"""
    global current_investment, trade_history
    
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        pnl = (exit_price - entry_price) * quantity
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
        
        current_investment += pnl
        
        # Add to trade history
        trade_record = {
            'timestamp': timestamp,
            'symbol': symbol,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'quantity': quantity,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'exit_type': exit_type,
            'capital_after': current_investment
        }
        trade_history.append(trade_record)
        save_trade_history()
        
        # Calculate winrate
        winrate = calculate_winrate()
        total_trades = len(trade_history)
        
        log_entry = (f"[{timestamp}] 📉 POSITION CLOSED | {symbol} | "
                    f"Exit: {exit_type} | Entry: ${entry_price:.6f} | Exit: ${exit_price:.6f} | "
                    f"PnL: ${pnl:.4f} ({pnl_pct:+.2f}%) | New Capital: ${current_investment:.2f}")
        
        write_log(log_entry)
        
        telegram_msg = (f"📉 <b>POSITION CLOSED - {exit_type}</b>\n"
                      f"┌────────────────────────────┐\n"
                      f"│ <b>{symbol}</b>\n"
                      f"├────────────────────────────┤\n"
                      f"│ Entry:    ${entry_price:.6f}\n"
                      f"│ Exit:     ${exit_price:.6f}\n"
                      f"│ PnL:      <b>{pnl_pct:+.2f}%</b>\n"
                      f"│ Amount:   ${pnl:.4f}\n"
                      f"│ New Capital: <b>${current_investment:.2f}</b>\n"
                      f"├────────────────────────────┤\n"
                      f"│ Win Rate:  {winrate:.1f}% ({total_trades} trades)\n"
                      f"└────────────────────────────┘")
        
        send_telegram_message(telegram_msg)
        
    except Exception as e:
        print(f"❌ Error logging position close: {e}")

def safe_sleep(seconds):
    """Sleep dengan interrupt handling"""
    try:
        time.sleep(seconds)
    except KeyboardInterrupt:
        raise
    except Exception:
        pass

# ==================== MANAJEMEN DATA ====================
def load_trade_history():
    """Load trade history from file"""
    global trade_history
    try:
        if os.path.exists(TRADE_HISTORY_FILE):
            with open(TRADE_HISTORY_FILE, 'r') as f:
                trade_history = json.load(f)
        print(f"✅ Loaded {len(trade_history)} previous trades")
    except Exception as e:
        print(f"❌ Error loading trade history: {e}")
        trade_history = []

def save_trade_history():
    """Save trade history to file"""
    try:
        with open(TRADE_HISTORY_FILE, 'w') as f:
            json.dump(trade_history, f, indent=2)
    except Exception as e:
        print(f"❌ Error saving trade history: {e}")

def calculate_winrate():
    """Calculate winrate from trade history"""
    if not trade_history:
        return 0.0
    
    wins = sum(1 for trade in trade_history if trade.get('pnl_pct', 0) > 0)
    return (wins / len(trade_history)) * 100

def load_bot_state():
    """Load bot state including performance data"""
    global coin_performance, dynamic_threshold, recent_trades, failed_coins
    
    try:
        if os.path.exists(BOT_STATE_FILE):
            with open(BOT_STATE_FILE, 'r') as f:
                state = json.load(f)
                
            coin_performance = state.get('coin_performance', {})
            dynamic_threshold = state.get('dynamic_threshold', 25)
            recent_trades = deque(state.get('recent_trades', []), maxlen=10)
            
            # Clean old failed coins (older than 24 hours)
            current_time = time.time()
            failed_coins = {
                coin: timestamp for coin, timestamp in state.get('failed_coins', {}).items()
                if current_time - timestamp < 86400
            }
            
            print(f"✅ Loaded bot state: threshold: {dynamic_threshold}")
    except Exception as e:
        print(f"❌ Error loading bot state: {e}")

def save_bot_state():
    """Save bot state including performance data"""
    try:
        state = {
            'coin_performance': coin_performance,
            'dynamic_threshold': dynamic_threshold,
            'recent_trades': list(recent_trades),
            'failed_coins': failed_coins,
            'last_update': time.time()
        }
        
        with open(BOT_STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"❌ Error saving bot state: {e}")

def update_dynamic_threshold():
    """Update confidence threshold based on recent performance"""
    global dynamic_threshold
    
    if len(recent_trades) < 5:
        return
    
    wins = sum(1 for trade in recent_trades if trade > 0)
    winrate = wins / len(recent_trades)
    
    if winrate < 0.5:
        dynamic_threshold = min(40, dynamic_threshold + 2)
        print(f"📊 Winrate rendah ({winrate:.1%}), naikkan threshold ke {dynamic_threshold}")
    elif winrate > 0.7:
        dynamic_threshold = max(20, dynamic_threshold - 1)
        print(f"📊 Winrate tinggi ({winrate:.1%}), turunkan threshold ke {dynamic_threshold}")

# ==================== BINANCE UTILITIES ====================
def initialize_binance_client():
    """Initialize Binance client with error handling"""
    global client
    try:
        client = Client(API_KEY, API_SECRET)
        print("✅ Binance client initialized")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize Binance client: {e}")
        return False

def sync_binance_time():
    """Sync time with Binance server"""
    try:
        server_time = client.get_server_time()
        local_time = int(time.time() * 1000)
        time_diff = server_time['serverTime'] - local_time
        client.time_offset = time_diff
        return True
    except Exception as e:
        print(f"❌ Time sync failed: {e}")
        return False

def get_symbol_info(symbol):
    """Get symbol information for price and quantity precision"""
    try:
        info = client.get_symbol_info(symbol)
        return info
    except Exception as e:
        return None

def get_price_precision(symbol):
    """Get price precision for symbol"""
    try:
        info = get_symbol_info(symbol)
        if info:
            for f in info['filters']:
                if f['filterType'] == 'PRICE_FILTER':
                    tick_size = float(f['tickSize'])
                    precision = 0
                    while tick_size < 1:
                        tick_size *= 10
                        precision += 1
                    return precision
        return 6
    except Exception as e:
        return 6

def get_quantity_precision(symbol):
    """Get quantity precision for symbol"""
    try:
        info = get_symbol_info(symbol)
        if info:
            for f in info['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    step_size = float(f['stepSize'])
                    precision = 0
                    while step_size < 1:
                        step_size *= 10
                        precision += 1
                    return precision
        return 2
    except Exception as e:
        return 2

def get_min_notional(symbol):
    """Get minimum notional requirement for symbol"""
    try:
        symbol_info = client.get_symbol_info(symbol)
        if symbol_info:
            for f in symbol_info['filters']:
                if f['filterType'] == 'MIN_NOTIONAL':
                    min_notional = float(f.get('minNotional', 10.0))
                    return min_notional
                elif f['filterType'] == 'NOTIONAL':
                    min_notional = float(f.get('minNotional', 10.0))
                    return min_notional
        return 10.0
    except Exception as e:
        return 10.0

def round_step_size(quantity, symbol):
    """Round quantity to appropriate step size dengan perbaikan error handling"""
    try:
        if quantity <= 0:
            print(f"   ⚠️ Invalid quantity for rounding: {quantity}")
            return None
            
        symbol_info = get_symbol_info(symbol)
        if not symbol_info:
            print(f"   ⚠️ No symbol info for {symbol}, using simple rounding")
            # Fallback: simple rounding to 6 decimal places
            return math.floor(quantity * 1000000) / 1000000
            
        for filter in symbol_info['filters']:
            if filter['filterType'] == 'LOT_SIZE':
                step_size = float(filter['stepSize'])
                
                # Cek minimum quantity
                min_qty = float(filter.get('minQty', step_size))
                if quantity < min_qty:
                    print(f"   ⚠️ Quantity {quantity} below minimum {min_qty}")
                    return None
                
                # Round to step size
                precision = int(round(-math.log(step_size, 10), 0))
                rounded_qty = math.floor(quantity / step_size) * step_size
                rounded_qty = round(rounded_qty, precision)
                
                if rounded_qty <= 0:
                    print(f"   ⚠️ Rounded quantity <= 0: {rounded_qty}")
                    return None
                    
                if rounded_qty < min_qty:
                    print(f"   ⚠️ Rounded quantity {rounded_qty} below minimum {min_qty}")
                    return None
                    
                print(f"   🔧 Quantity rounded: {quantity} -> {rounded_qty} (step: {step_size})")
                return float(rounded_qty)
                
        # Fallback jika tidak ada LOT_SIZE filter
        print(f"   ⚠️ No LOT_SIZE filter for {symbol}, using simple rounding")
        return math.floor(quantity * 1000000) / 1000000
        
    except Exception as e:
        print(f"❌ Error in round_step_size for {symbol}: {e}")
        # Fallback: simple rounding
        return math.floor(quantity * 1000000) / 1000000

def get_current_price(symbol):
    """Get current price with proper formatting"""
    try:
        ticker = client.get_symbol_ticker(symbol=symbol)
        price = float(ticker['price'])
        precision = get_price_precision(symbol)
        return round(price, precision)
    except Exception as e:
        return None

# ==================== INDIKATOR TEKNIKAL UNTUK 2 TIMEFRAME ====================
def calculate_ema(prices, period):
    """Calculate EMA menggunakan numpy"""
    if len(prices) < period:
        return None

    try:
        weights = np.exp(np.linspace(-1., 0., period))
        weights /= weights.sum()

        ema = np.convolve(prices, weights, mode='full')[:len(prices)]
        
        if len(ema) > period:
            ema[:period] = ema[period]
        else:
            ema[:] = np.mean(prices)
            
        return ema
    except Exception as e:
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

def calculate_linear_regression(prices, period=20):
    """Calculate Linear Regression Oscillator"""
    if len(prices) < period:
        return 0
    
    try:
        x = np.arange(period)
        y = prices[-period:]
        
        A = np.vstack([x, np.ones(len(x))]).T
        m, b = np.linalg.lstsq(A, y, rcond=None)[0]
        
        regression_line = m * x + b
        current_regression = regression_line[-1]
        current_price = prices[-1]
        
        lro = ((current_price - current_regression) / abs(current_regression)) * 100 if current_regression != 0 else 0
        
        return lro
    except Exception as e:
        return 0

def calculate_volume_profile(volumes, period=20):
    """Calculate volume profile and detect volume spikes"""
    if len(volumes) < period:
        return 1.0
    
    try:
        current_volume = volumes[-1]
        avg_volume = np.mean(volumes[-period:])
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        return volume_ratio
    except Exception as e:
        return 1.0

# ==================== DATA FETCHING UNTUK 2 TIMEFRAME ====================
def get_klines_data(symbol, interval, limit=50):
    """Get klines data dengan connection check yang lebih baik"""
    try:
        # Cek koneksi dulu
        try:
            client.ping()
        except Exception as e:
            print(f"❌ Koneksi Binance terputus: {e}")
            return None

        klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
        
        if not klines:
            print(f"   ❌ No klines data for {symbol}")
            return None
            
        if len(klines) < 20:
            print(f"   ⚠️ Insufficient data for {symbol}: {len(klines)} candles")
            return None
            
        opens = np.array([float(k[1]) for k in klines])
        highs = np.array([float(k[2]) for k in klines])
        lows = np.array([float(k[3]) for k in klines])
        closes = np.array([float(k[4]) for k in klines])
        volumes = np.array([float(k[5]) for k in klines])
        
        return {
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes
        }
    except Exception as e:
        print(f"❌ Error get_klines_data untuk {symbol}: {str(e)}")
        return None

def get_two_timeframe_data(symbol):
    """Get data dengan validation yang ketat"""
    try:
        # Cek apakah symbol valid dengan get_price dulu
        test_price = get_current_price(symbol)
        if not test_price:
            print(f"   💀 INVALID SYMBOL: {symbol} - skipping")
            return None, None
        
        data_15m = get_klines_data(symbol, Client.KLINE_INTERVAL_15MINUTE, 40)
        data_5m = get_klines_data(symbol, Client.KLINE_INTERVAL_5MINUTE, 40)
        
        return data_15m, data_5m
        
    except Exception as e:
        print(f"❌ Error get_two_timeframe_data untuk {symbol}: {e}")
        return None, None

# ==================== SISTEM SINYAL YANG DIPERBAIKI UNTUK MASING-MASING TIMEFRAME ====================
def analyze_timeframe_improved(data, timeframe, symbol):
    """Analisis timeframe dengan error handling"""
    # Validasi input data lebih ketat
    if data is None:
        return False, 0
        
    if not isinstance(data, dict):
        return False, 0
        
    required_keys = ['close', 'high', 'low', 'volume']
    for key in required_keys:
        if key not in data or data[key] is None or len(data[key]) < 20:
            return False, 0

    try:
        closes = data['close']
        highs = data['high']
        lows = data['low']
        volumes = data['volume']

        # TENTUKAN PARAMETER BERDASARKAN TIMEFRAME
        if timeframe == '15m':
            ema_short_period = EMA_SHORT_15M
            ema_long_period = EMA_LONG_15M
            rsi_min = RSI_MIN_15M
            rsi_max = RSI_MAX_15M
            macd_fast = MACD_FAST_15M
            macd_slow = MACD_SLOW_15M
            macd_signal = MACD_SIGNAL_15M
            lro_period = LRO_PERIOD_15M
            volume_period = VOLUME_PERIOD_15M
        else:  # '5m'
            ema_short_period = EMA_SHORT_5M
            ema_long_period = EMA_LONG_5M
            rsi_min = RSI_MIN_5M
            rsi_max = RSI_MAX_5M
            macd_fast = MACD_FAST_5M
            macd_slow = MACD_SLOW_5M
            macd_signal = MACD_SIGNAL_5M
            lro_period = LRO_PERIOD_5M
            volume_period = VOLUME_PERIOD_5M

        # Hitung indikator dengan error handling
        ema_short = calculate_ema(closes, ema_short_period)
        ema_long = calculate_ema(closes, ema_long_period)
        rsi = calculate_rsi(closes, 14)
        macd_line, macd_signal, macd_histogram = calculate_macd(closes, macd_fast, macd_slow, macd_signal)
        lro = calculate_linear_regression(closes, lro_period)
        volume_ratio = calculate_volume_profile(volumes, volume_period)

        # Validasi semua indikator tidak None
        if any(x is None for x in [ema_short, ema_long, rsi, macd_line]):
            return False, 0

        current_index = min(
            len(closes)-1, 
            len(ema_short)-1 if ema_short is not None else len(closes)-1,
            len(ema_long)-1 if ema_long is not None else len(closes)-1,
            len(rsi)-1 if rsi is not None else len(closes)-1
        )

        # KRITERIA dengan default value jika None
        price_above_ema_short = closes[current_index] > ema_short[current_index] if ema_short is not None else False
        price_above_ema_long = closes[current_index] > ema_long[current_index] if ema_long is not None else False
        ema_bullish = ema_short[current_index] > ema_long[current_index] if (ema_short is not None and ema_long is not None) else False
        
        rsi_ok = (rsi_min <= rsi[current_index] <= rsi_max) if rsi is not None else False
        macd_bullish = macd_line[current_index] > macd_signal[current_index] if (macd_signal is not None and macd_line is not None) else False
        volume_ok = volume_ratio > VOLUME_RATIO_MIN if volume_ratio is not None else False
        lro_positive = lro > -2 if lro is not None else False

        # Hitung skor
        score = 0
        if price_above_ema_short: score += 20
        if price_above_ema_long: score += 15
        if ema_bullish: score += 15
        if rsi_ok: score += 20
        if macd_bullish: score += 15
        if volume_ok: score += 10
        if lro_positive: score += 5

        signal_ok = (price_above_ema_short and rsi_ok and macd_bullish and 
                    volume_ok and lro_positive)

        return signal_ok, min(score, 100)

    except Exception as e:
        print(f"❌ Error in analyze_timeframe_improved for {symbol} ({timeframe}): {str(e)}")
        return False, 0

def analyze_coin_improved(symbol):
    """Analisis coin dengan error handling yang lebih baik"""
    if symbol in failed_coins:
        fail_time = failed_coins[symbol]
        if time.time() - fail_time < 300:
            return None
        else:
            failed_coins.pop(symbol, None)
    
    try:
        data_15m, data_5m = get_two_timeframe_data(symbol)
        
        # Validasi data lebih ketat
        if data_15m is None or data_5m is None:
            print(f"   📭 No data for {symbol}")
            return None
        
        # Validasi key yang diperlukan ada
        required_keys = ['close', 'high', 'low', 'volume']
        for data in [data_15m, data_5m]:
            for key in required_keys:
                if key not in data or data[key] is None or len(data[key]) == 0:
                    print(f"   📭 Missing {key} data for {symbol}")
                    return None
        
        # Analyze kedua timeframe
        m15_ok, m15_score = analyze_timeframe_improved(data_15m, '15m', symbol)
        m5_ok, m5_score = analyze_timeframe_improved(data_5m, '5m', symbol)
        
        # Pastikan score valid
        if m15_score is None: m15_score = 0
        if m5_score is None: m5_score = 0
        
        confidence = (m15_score * 0.5) + (m5_score * 0.5)
        confidence = min(95, max(confidence, 0))
        
        current_price = get_current_price(symbol)
        if current_price is None:
            print(f"   💰 Cannot get price for {symbol}")
            return None
        
        buy_signal = (m15_ok and m5_ok) and confidence >= dynamic_threshold
        
        return {
            'symbol': symbol,
            'buy_signal': buy_signal,
            'confidence': confidence,
            'current_price': current_price,
            'm15_signal': m15_ok if m15_ok is not None else False,
            'm5_signal': m5_ok if m5_ok is not None else False,
            'm15_score': m15_score,
            'm5_score': m5_score
        }
        
    except Exception as e:
        print(f"❌ Error in analyze_coin_improved for {symbol}: {str(e)}")
        failed_coins[symbol] = time.time()
        return None

# ==================== ORDER MANAGEMENT (TETAP SAMA) ====================
def get_precise_quantity(symbol, investment_amount):
    try:
        current_price = get_current_price(symbol)
        if not current_price or current_price <= 0:
            print(f"   ❌ Tidak bisa mendapatkan harga untuk {symbol}")
            return None
            
        theoretical_quantity = investment_amount / current_price
        
        if theoretical_quantity <= 0:
            print(f"   ❌ Quantity teoritis <= 0: {theoretical_quantity}")
            return None
            
        # Untuk simulasi, gunakan quantity sederhana
        if not ORDER_RUN:
            # Round to 6 decimal places for simulation
            precise_quantity = round(theoretical_quantity * 0.998, 6)
            print(f"   🔧 SIMULATION Qty: {precise_quantity} (dari ${investment_amount} / ${current_price})")
            return precise_quantity
            
        # Untuk live trading, gunakan rounding yang tepat
        adjusted_quantity = theoretical_quantity * 0.998
        precise_quantity = round_step_size(adjusted_quantity, symbol)
        
        if not precise_quantity:
            print(f"   ❌ Gagal round quantity untuk {symbol}")
            return None
            
        return precise_quantity
        
    except Exception as e:
        print(f"❌ Error di get_precise_quantity: {e}")
        return None
    
def get_adjusted_position_size(symbol):
    """Dapatkan position size yang sudah disesuaikan dengan minimum notional"""
    base_position = calculate_position_size(symbol)
    min_notional = get_min_notional(symbol)
    
    # Jika base position di bawah minimum, gunakan minimum
    if base_position < min_notional:
        adjusted_position = min_notional * 1.02  # Tambah 2% untuk aman
        
        # Pastikan tidak melebihi capital
        if adjusted_position > current_investment:
            print(f"❌ Minimum notional ${min_notional:.2f} exceeds capital ${current_investment:.2f}")
            return None
            
        return adjusted_position
    
    return base_position

def place_market_buy_order(symbol, investment_amount):
    """Place market buy order dengan penanganan minimum notional yang lebih baik"""
    global current_investment
    
    try:
        print(f"🔹 BUY ORDER: {symbol}")
        
        # Cek balance untuk live trading
        if ORDER_RUN:
            try:
                balance = client.get_asset_balance(asset='USDT')
                free_balance = float(balance['free'])
                if free_balance < investment_amount:
                    print(f"❌ Insufficient balance. Need: ${investment_amount:.2f}, Available: ${free_balance:.2f}")
                    return None
            except Exception as e:
                print(f"⚠️ Balance check skipped: {e}")
        
        current_price = get_current_price(symbol)
        if not current_price or current_price <= 0:
            print(f"❌ Cannot get price for {symbol}")
            return None

        # Hitung quantity
        theoretical_quantity = investment_amount / current_price
        
        if theoretical_quantity <= 0:
            print(f"❌ Invalid quantity: {theoretical_quantity}")
            return None

        # Dapatkan minimum notional
        min_notional = get_min_notional(symbol)
        calculated_value = theoretical_quantity * current_price
        
        print(f"   Calculated order value: ${calculated_value:.2f}")
        print(f"   Minimum notional: ${min_notional:.2f}")
        
        # Jika di bawah minimum, sesuaikan investment amount
        if calculated_value < min_notional:
            print(f"   ⚠️ Below minimum notional, adjusting...")
            
            # Hitung ulang dengan minimum notional
            required_investment = min_notional * 1.02  # Tambah 2% untuk aman
            theoretical_quantity = required_investment / current_price
            
            print(f"   Adjusted investment: ${required_investment:.2f}")
            print(f"   Adjusted quantity: {theoretical_quantity:.8f}")
            
            # Untuk live trading, cek ulang balance
            if ORDER_RUN and required_investment > free_balance:
                print(f"❌ Adjusted amount ${required_investment:.2f} exceeds balance ${free_balance:.2f}")
                return None

        # MODE SIMULASI
        if not ORDER_RUN:
            precise_quantity = round(theoretical_quantity, 6)
            
            print(f"🧪 [SIMULATION] BUY {symbol}")
            print(f"   Investment: ${investment_amount:.2f}")
            print(f"   Price: ${current_price:.6f}")
            print(f"   Quantity: {precise_quantity:.8f}")
            print(f"   Order Value: ${precise_quantity * current_price:.2f}")
            
            simulated_order = {
                'status': 'FILLED',
                'symbol': symbol,
                'executedQty': str(precise_quantity),
                'fills': [{'price': str(current_price), 'qty': str(precise_quantity)}]
            }
            return simulated_order

        # LIVE TRADING
        precise_quantity = round_step_size(theoretical_quantity, symbol)
        
        if not precise_quantity:
            print(f"❌ Cannot get precise quantity")
            return None
            
        final_order_value = precise_quantity * current_price
        print(f"   Final Quantity: {precise_quantity}")
        print(f"   Final Order Value: ${final_order_value:.2f}")
        
        # Final check minimum notional
        if final_order_value < min_notional:
            print(f"❌ Still below minimum after rounding: ${final_order_value:.2f} < ${min_notional:.2f}")
            return None
        
        order = client.order_market_buy(
            symbol=symbol,
            quantity=precise_quantity
        )
        
        if order and order.get('status') == 'FILLED':
            print(f"✅ BUY order executed for {symbol}")
            return order
        else:
            print(f"❌ BUY order failed for {symbol}")
            return None
            
    except Exception as e:
        print(f"❌ BUY error: {e}")
        return None

def execute_market_sell(symbol, quantity, entry_price, exit_type):
    """Execute market sell order dengan proses dipercepat"""
    global current_investment, active_position
    
    try:
        print(f"🔹 FAST SELL: {symbol} ({exit_type})")
        
        current_price = get_current_price(symbol)
        if not current_price:
            return False

        # QUANTITY CEPAT - gunakan quantity asli untuk simulasi
        if not ORDER_RUN:
            # SIMULASI CEPAT
            log_position_closed(symbol, entry_price, current_price, quantity, exit_type)
            active_position = None
            return True

        # LIVE TRADING - CEPAT
        precise_quantity = round_step_size(quantity, symbol)
        if not precise_quantity:
            precise_quantity = round(quantity, 6)

        sell_order = client.order_market_sell(
            symbol=symbol,
            quantity=precise_quantity
        )

        if sell_order and sell_order.get('status') == 'FILLED':
            executed_qty = float(sell_order.get('executedQty', 0))
            exit_price = current_price
            
            if sell_order.get('fills') and len(sell_order['fills']) > 0:
                exit_price = float(sell_order['fills'][0]['price'])
            
            log_position_closed(symbol, entry_price, exit_price, executed_qty, exit_type)
            active_position = None
            return True
            
        return False

    except Exception as e:
        print(f"❌ Fast SELL error: {e}")
        return False

# ==================== RISK MANAGEMENT (TETAP SAMA) ====================
def calculate_position_size(symbol):
    """Hitung ukuran position dengan penyesuaian minimum notional"""
    global current_investment
    
    # Hitung position size normal
    position_value = current_investment * POSITION_SIZING_PCT
    
    # Dapatkan minimum notional
    min_notional = get_min_notional(symbol)
    
    print(f"💰 Position calculation for {symbol}:")
    print(f"   Capital: ${current_investment:.2f}")
    print(f"   {POSITION_SIZING_PCT*100}% = ${position_value:.2f}")
    print(f"   Min Notional: ${min_notional:.2f}")
    
    # Jika position value di bawah minimum, naikkan ke minimum
    if position_value < min_notional:
        print(f"   ⚠️ Below minimum, adjusting to ${min_notional:.2f}")
        position_value = min_notional
    
    # Batasi maksimal 60% dari capital untuk kasus minimum yang tinggi
    max_position = current_investment * 0.6
    if position_value > max_position:
        print(f"   ⚠️ Above max limit, adjusting to ${max_position:.2f}")
        position_value = max_position
    
    # Pastikan tidak melebihi capital yang tersedia
    if position_value > current_investment:
        print(f"   ⚠️ Above available capital, adjusting to ${current_investment:.2f}")
        position_value = current_investment
    
    print(f"   ✅ Final Position: ${position_value:.2f}")
    return position_value

def check_portfolio_health():
    """Cek kesehatan portfolio"""
    global current_investment
    
    if current_investment < INITIAL_INVESTMENT * (1 - MAX_DRAWDOWN_PCT):
        stop_msg = (f"🛑 <b>BOT STOPPED - MAX DRAWDOWN REACHED</b>\n"
                  f"Initial: ${INITIAL_INVESTMENT:.2f}\n"
                  f"Current: <b>${current_investment:.2f}</b>\n"
                  f"Drawdown: <b>-{((INITIAL_INVESTMENT - current_investment)/INITIAL_INVESTMENT*100):.1f}%</b>")
        
        print("🛑 Maximum drawdown reached - Stopping bot")
        send_telegram_message(stop_msg)
        return False
    
    return True

# ==================== TRAILING STOP SYSTEM (TETAP SAMA) ====================
def update_trailing_stop(current_price):
    """Update trailing stop untuk position aktif"""
    global active_position
    
    if not active_position:
        return
    
    entry_price = active_position['entry_price']
    highest_price = active_position.get('highest_price', entry_price)
    
    if current_price > highest_price:
        active_position['highest_price'] = current_price
        highest_price = current_price
    
    price_increase_pct = (highest_price - entry_price) / entry_price
    
    if price_increase_pct >= TRAILING_STOP_ACTIVATION:
        new_stop_loss = highest_price * (1 - TRAILING_STOP_PCT)
        
        if new_stop_loss > active_position['stop_loss']:
            active_position['stop_loss'] = new_stop_loss
            active_position['trailing_active'] = True
            
            print(f"🔧 Trailing Stop updated: {new_stop_loss:.6f}")

def check_trailing_stop(current_price, symbol):
    """Check trailing stop conditions"""
    global active_position
    
    if not active_position or active_position['symbol'] != symbol:
        return False
    
    stop_loss = active_position['stop_loss']
    
    if current_price <= stop_loss:
        print(f"🛑 Trailing Stop hit for {symbol} at ${current_price:.6f}")
        quantity = active_position['quantity']
        entry_price = active_position['entry_price']
        
        if execute_market_sell(symbol, quantity, entry_price, "TRAILING STOP"):
            pnl_pct = (current_price - entry_price) / entry_price * 100
            recent_trades.append(pnl_pct)
            update_dynamic_threshold()
            
            active_position = None
            return True
    
    return False

# ==================== WEBSOCKET MANAGEMENT (TETAP SAMA) ====================
def handle_websocket_message(msg):
    """Handle WebSocket messages untuk real-time monitoring"""
    global active_position
    
    try:
        if msg['e'] == 'error':
            print(f"WebSocket error: {msg}")
            return
            
        symbol = msg['s']
        current_price = float(msg['c'])
        
        # Cek apakah ini coin yang kita pegang
        if not active_position or active_position['symbol'] != symbol:
            return
        
        print(f"📊 WebSocket Update: {symbol} = ${current_price:.6f}")
        
        entry_price = active_position['entry_price']
        quantity = active_position['quantity']
        
        # Update trailing stop
        update_trailing_stop(current_price)
        
        # Cek trailing stop terlebih dahulu
        if check_trailing_stop(current_price, symbol):
            return
        
        # Cek Take Profit
        take_profit = active_position['take_profit']
        if current_price >= take_profit:
            print(f"🎯 TP hit for {symbol} at ${current_price:.6f} (TP: ${take_profit:.6f})")
            if execute_market_sell(symbol, quantity, entry_price, "TAKE PROFIT"):
                pnl_pct = (current_price - entry_price) / entry_price * 100
                recent_trades.append(pnl_pct)
                update_dynamic_threshold()
            return
        
        # Cek Stop Loss (hanya jika trailing stop tidak aktif)
        stop_loss = active_position['stop_loss']
        if current_price <= stop_loss and not active_position.get('trailing_active', False):
            print(f"🛑 SL hit for {symbol} at ${current_price:.6f} (SL: ${stop_loss:.6f})")
            if execute_market_sell(symbol, quantity, entry_price, "STOP LOSS"):
                pnl_pct = (current_price - entry_price) / entry_price * 100
                recent_trades.append(pnl_pct)
                update_dynamic_threshold()
            return
                    
    except Exception as e:
        print(f"❌ WebSocket error: {e}")

def start_websocket_monitoring(symbol):
    """Start WebSocket monitoring for symbol"""
    global twm
    
    try:
        if twm is None:
            twm = ThreadedWebsocketManager(api_key=API_KEY, api_secret=API_SECRET)
            twm.start()
        
        print(f"🔌 Starting WebSocket monitoring for {symbol}")
        twm.start_symbol_ticker_socket(callback=handle_websocket_message, symbol=symbol)
        
    except Exception as e:
        print(f"❌ Error starting WebSocket for {symbol}: {e}")

def stop_websocket_monitoring():
    """Stop all WebSocket monitoring"""
    global twm
    
    try:
        if twm:
            print("🔌 Stopping WebSocket monitoring")
            twm.stop()
            twm = None
    except Exception as e:
        print(f"❌ Error stopping WebSocket: {e}")

# ==================== MONITORING & EXECUTION YANG DIPERBAIKI ====================
def monitor_coins_until_signal():
    """Monitor coins sampai menemukan sinyal buy pertama - TIDAK scan semua"""
    global buy_signals
    
    # CEK KONEKSI DULU
    try:
        client.ping()
        print(f"\n🔍 SCANNING coins until signal found...")
    except Exception as e:
        print(f"❌ BINANCE CONNECTION ERROR: {e}")
        print("💤 Waiting 60s before retry...")
        time.sleep(60)
        return []
    
    buy_signals = []
    
    for coin in COINS:
        try:
            print(f"   Checking {coin}...")
            analysis = analyze_coin_improved(coin)
            
            if analysis and analysis['buy_signal']:
                print(f"   🚨 SIGNAL FOUND: {coin} - Confidence: {analysis['confidence']:.1f}%")
                buy_signals.append(analysis)
                
                # KIRIM NOTIFIKASI CEPAT
                telegram_msg = f"🚨 <b>BUY SIGNAL DETECTED</b>\n• {coin}: {analysis['confidence']:.1f}%\n• Price: ${analysis['current_price']:.6f}"
                send_telegram_message(telegram_msg)
                
                # HENTIKAN SCANNING - LANGSUNG PROSES
                print(f"   ⚡ STOPPING SCAN - Processing {coin} immediately")
                return buy_signals
            
            elif analysis:
                print(f"   ❌ {coin}: No signal ({analysis['confidence']:.1f}%)")
            else:
                print(f"   💀 {coin}: No data")
            
            time.sleep(0.3)  # Delay lebih pendek untuk kecepatan
            
        except Exception as e:
            print(f"   ⚠️ {coin}: Error - {e}")
            time.sleep(0.5)
    
    print(f"\n📊 SCAN COMPLETE: No signals found in {len(COINS)} coins")
    return []

def fast_execute_signal(signal):
    """Execute trade dengan proses sangat cepat setelah sinyal ditemukan"""
    global active_position
    
    symbol = signal['symbol']
    confidence = signal['confidence']
    current_price = signal['current_price']
    
    print(f"⚡ FAST EXECUTION: {symbol} (Confidence: {confidence:.1f}%)")
    
    # KONFIRMASI ULANG SUPER CEPAT
    print(f"   🔍 Quick re-confirmation...")
    quick_check = analyze_coin_improved(symbol)
    
    if not quick_check or not quick_check['buy_signal']:
        print(f"   ❌ Signal disappeared, aborting...")
        failed_coins[symbol] = time.time()
        return False
    
    # POSITION SIZE CEPAT
    investment_amount = current_investment * POSITION_SIZING_PCT
    min_notional = get_min_notional(symbol)
    
    if investment_amount < min_notional:
        investment_amount = min_notional * 1.02
    
    print(f"   💰 Fast position: ${investment_amount:.2f}")
    
    # EKSEKUSI BUY CEPAT
    buy_order = place_market_buy_order(symbol, investment_amount)
    
    if buy_order and buy_order.get('status') == 'FILLED':
        # PROSES DATA CEPAT
        executed_qty = float(buy_order.get('executedQty', 0))
        
        if buy_order.get('fills') and len(buy_order['fills']) > 0:
            entry_price = float(buy_order['fills'][0]['price'])
        else:
            entry_price = current_price
        
        # SETUP TP/SL CEPAT
        price_precision = get_price_precision(symbol)
        entry_price = round(entry_price, price_precision)
        take_profit = round(entry_price * (1 + TAKE_PROFIT_PCT), price_precision)
        stop_loss = round(entry_price * (1 - STOP_LOSS_PCT), price_precision)
        
        active_position = {
            'symbol': symbol,
            'entry_price': entry_price,
            'quantity': executed_qty,
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'highest_price': entry_price,
            'trailing_active': False,
            'confidence': confidence,
            'timestamp': time.time()
        }
        
        # LOG CEPAT
        log_position_opened(symbol, entry_price, executed_qty, take_profit, stop_loss, confidence)
        
        # Start monitoring jika live
        if ORDER_RUN:
            start_websocket_monitoring(symbol)
        
        print(f"   ✅ FAST EXECUTION COMPLETE: {symbol}")
        return True
    
    print(f"   ❌ Fast execution failed for {symbol}")
    failed_coins[symbol] = time.time()
    return False

def fast_execute_with_confirmation(signal):
    """Execute trade dengan konfirmasi super cepat"""
    global active_position, buy_signals
    
    symbol = signal['symbol']
    
    # KONFIRMASI CEPAT - hanya untuk live trading
    if ORDER_RUN:
        quick_check = analyze_coin_improved(symbol)
        if not quick_check or not quick_check['buy_signal']:
            failed_coins[symbol] = time.time()
            return False
    
    # POSITION SIZE CEPAT
    investment_amount = current_investment * POSITION_SIZING_PCT
    min_notional = get_min_notional(symbol)
    
    if investment_amount < min_notional:
        investment_amount = min_notional
    
    # EKSEKUSI CEPAT
    buy_order = place_market_buy_order(symbol, investment_amount)
    
    if buy_order and buy_order.get('status') == 'FILLED':
        executed_qty = float(buy_order.get('executedQty', 0))
        entry_price = signal['current_price']
        
        if buy_order.get('fills') and len(buy_order['fills']) > 0:
            entry_price = float(buy_order['fills'][0]['price'])
        
        # SETUP CEPAT
        price_precision = get_price_precision(symbol)
        entry_price = round(entry_price, price_precision)
        take_profit = round(entry_price * (1 + TAKE_PROFIT_PCT), price_precision)
        stop_loss = round(entry_price * (1 - STOP_LOSS_PCT), price_precision)
        
        active_position = {
            'symbol': symbol,
            'entry_price': entry_price,
            'quantity': executed_qty,
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'highest_price': entry_price,
            'trailing_active': False,
            'confidence': signal['confidence'],
            'timestamp': time.time()
        }
        
        # LOG CEPAT
        log_position_opened(symbol, entry_price, executed_qty, take_profit, stop_loss, signal['confidence'])
        
        # Start monitoring jika live
        if ORDER_RUN:
            start_websocket_monitoring(symbol)
        
        # Clear signals untuk coin ini
        buy_signals = [s for s in buy_signals if s['symbol'] != symbol]
        return True
    
    failed_coins[symbol] = time.time()
    return False

def execute_with_confirmation(signal):
    """Execute trade dengan konfirmasi dan error handling yang lebih baik"""
    global active_position, buy_signals
    
    symbol = signal['symbol']
    print(f"\n🎯 Attempting to execute: {symbol} (Confidence: {signal['confidence']:.1f}%)")
    
    # Konfirmasi ulang sinyal
    print(f"   🔍 Confirming signal...")
    quick_check = analyze_coin_improved(symbol)
    if quick_check:
        confidence_drop = signal['confidence'] - quick_check['confidence']
        still_valid = (
            quick_check['buy_signal'] or 
            (quick_check['confidence'] >= dynamic_threshold * 0.8) or  # 80% dari threshold
            confidence_drop < 15  # Tidak turun lebih dari 15%
        )
        
        if not still_valid:
            print(f"   ❌ Signal changed significantly, skipping...")
            failed_coins[symbol] = time.time()
            return False
    else:
        print(f"   ❌ Cannot re-analyze, skipping...")
        failed_coins[symbol] = time.time()
        return False
    
    # Hitung position size
    investment_amount = get_adjusted_position_size(symbol)
    if not investment_amount:
        print(f"   ❌ Cannot calculate valid position size")
        return False
    
    print(f"   💰 Position size: ${investment_amount:.2f}")
    
    # Place buy order
    buy_order = place_market_buy_order(symbol, investment_amount)
    
    if buy_order and buy_order.get('status') == 'FILLED':
        # Dapatkan data eksekusi
        executed_qty = float(buy_order.get('executedQty', 0))
        
        if buy_order.get('fills') and len(buy_order['fills']) > 0:
            entry_price = float(buy_order['fills'][0]['price'])
        else:
            entry_price = signal['current_price']
        
        # Validasi entry price
        if entry_price <= 0:
            print(f"❌ Invalid entry price: {entry_price}")
            return False
        
        # Setup take profit dan stop loss
        price_precision = get_price_precision(symbol)
        entry_price = round(entry_price, price_precision)
        take_profit = round(entry_price * (1 + TAKE_PROFIT_PCT), price_precision)
        stop_loss = round(entry_price * (1 - STOP_LOSS_PCT), price_precision)
        
        print(f"   ✅ Entry: ${entry_price:.6f}")
        print(f"   🎯 TP: ${take_profit:.6f} (+{TAKE_PROFIT_PCT*100:.2f}%)")
        print(f"   🛑 SL: ${stop_loss:.6f} (-{STOP_LOSS_PCT*100:.2f}%)")
        
        # Set active position
        active_position = {
            'symbol': symbol,
            'entry_price': entry_price,
            'quantity': executed_qty,
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'highest_price': entry_price,
            'trailing_active': False,
            'confidence': signal['confidence'],
            'timestamp': time.time()
        }
        
        # Start WebSocket monitoring untuk real-time tracking
        if ORDER_RUN:
            start_websocket_monitoring(symbol)
        
        # Log position opened
        log_position_opened(symbol, entry_price, executed_qty, take_profit, stop_loss, signal['confidence'])
        
        # Clear buy signals setelah berhasil execute
        buy_signals = [s for s in buy_signals if s['symbol'] != symbol]
        return True
    
    print(f"❌ Buy order failed for {symbol}")
    failed_coins[symbol] = time.time()
    return False

def validate_position_data(symbol, entry_price, quantity):
    """Validasi data position sebelum eksekusi"""
    try:
        if not symbol or symbol.strip() == "":
            print("❌ Invalid symbol")
            return False
            
        if entry_price <= 0:
            print(f"❌ Invalid entry price: {entry_price}")
            return False
            
        if quantity <= 0:
            print(f"❌ Invalid quantity: {quantity}")
            return False
            
        current_price = get_current_price(symbol)
        if not current_price or current_price <= 0:
            print(f"❌ Cannot validate current price for {symbol}")
            return False
            
        # Cek apakah harga masih reasonable
        if abs(current_price - entry_price) / entry_price > 0.5:  # 50% deviation
            print(f"❌ Price deviation too large: entry=${entry_price}, current=${current_price}")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Error validating position data: {e}")
        return False

def print_buy_signals_details(signals):
    """Print detail sinyal buy dalam bentuk tabel"""
    if not signals:
        print("   📭 No buy signals found")
        return
        
    print(f"\n🎯 BUY SIGNALS DETAILS ({len(signals)} signals):")
    print("-"*80)
    print(f"{'SYMBOL':<12} {'CONFIDENCE':<10} {'M15':<6} {'M5':<6} {'PRICE':<12} {'STATUS':<10}")
    print("-"*80)
    
    for signal in signals:
        symbol = signal['symbol']
        confidence = f"{signal['confidence']:.1f}%"
        m15 = "✅" if signal['m15_signal'] else "❌"
        m5 = "✅" if signal['m5_signal'] else "❌"
        price = f"${signal['current_price']:.6f}"
        status = "🟢 HIGH" if signal['confidence'] >= 70 else "🟡 MEDIUM" if signal['confidence'] >= 50 else "🟠 LOW"
        
        print(f"{symbol:<12} {confidence:<10} {m15:<6} {m5:<6} {price:<12} {status:<10}")
    
    print("-"*80)

# ==================== MAIN BOT LOGIC YANG DIPERBAIKI ====================
def main_improved_fast():
    """Main bot function - STOP ketika ada sinyal"""
    global current_investment, active_position, twm
    
    print("🚀 Starting BOT - FAST EXECUTION Version")
    
    initialize_logging()
    load_trade_history()
    load_bot_state()
    
    if not initialize_binance_client():
        print("❌ Gagal inisialisasi Binance client")
        return
    
    startup_msg = f"🤖 <b>BOT STARTED - FAST EXECUTION</b>\nCoins: {len(COINS)}\nMode: {'LIVE' if ORDER_RUN else 'SIMULATION'}"
    send_telegram_message(startup_msg)
    
    consecutive_errors = 0
    
    while True:
        try:
            # CEK KONEKSI SETIAP LOOP
            try:
                client.ping()
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                print(f"❌ Koneksi error #{consecutive_errors}: {e}")
                if consecutive_errors >= 3:
                    print("💀 Koneksi mati, restart required")
                    break
                time.sleep(30)
                continue
            
            if active_position:
                # Monitoring position aktif saja
                current_price = get_current_price(active_position['symbol'])
                if current_price:
                    pnl_pct = (current_price - active_position['entry_price']) / active_position['entry_price'] * 100
                    print(f"📊 {active_position['symbol']}: ${current_price:.6f} | PnL: {pnl_pct:+.2f}%")
                    
                    # Untuk simulasi, cek TP/SL
                    if not ORDER_RUN:
                        if current_price >= active_position['take_profit']:
                            execute_market_sell(active_position['symbol'], active_position['quantity'], 
                                              active_position['entry_price'], "TAKE PROFIT")
                        elif current_price <= active_position['stop_loss']:
                            execute_market_sell(active_position['symbol'], active_position['quantity'], 
                                              active_position['entry_price'], "STOP LOSS")
                
                time.sleep(0.3)
                continue
            
            # SCAN HINGGA ADA SINYAL - BERHENTI KETIKA KETEMU
            print(f"\n🕐 Scanning for signals...")
            signals = monitor_coins_until_signal()
            
            if signals:
                # EKSEKUSI CEPAT sinyal pertama
                signal = signals[0]
                if fast_execute_signal(signal):
                    print("✅ Trade executed successfully!")
                else:
                    print("❌ Execution failed, continuing scan...")
                    time.sleep(2)
            else:
                # Tidak ada sinyal, tunggu sebentar lalu scan lagi
                print("💤 No signals, waiting 5s...")
                time.sleep(5)
                
            save_bot_state()
                
        except KeyboardInterrupt:
            print(f"\n🛑 Bot stopped by user")
            send_telegram_message("🛑 <b>BOT DIHENTIKAN OLEH PENGGUNA</b>")
            break
        except Exception as e:
            print(f"❌ Main loop error: {e}")
            time.sleep(10)
    
    stop_websocket_monitoring()
    save_bot_state()
    print("✅ Bot stopped")

def main_improved():
    """Main bot function - STOP Ngespam!"""
    global current_investment, active_position, twm, buy_signals
    
    print("🚀 Starting BOT - STOP Ngespam Version")
    
    initialize_logging()
    load_trade_history()
    load_bot_state()
    
    if not initialize_binance_client():
        print("❌ Gagal inisialisasi Binance client")
        return
    
    # CEK KONEKSI AWAL
    try:
        client.ping()
        print("✅ Koneksi Binance OK")
    except Exception as e:
        print(f"❌ Koneksi Binance gagal: {e}")
        return
    
    startup_msg = f"🤖 <b>BOT STARTED - STOP Ngespam Version</b>\nCoins: {len(COINS)}\nMode: {'LIVE' if ORDER_RUN else 'SIMULATION'}"
    send_telegram_message(startup_msg)
    
    last_scan_time = 0
    scan_interval = 10  # Scan setiap 2 MENIT saja!
    consecutive_errors = 0
    
    while True:
        try:
            current_time = time.time()
            
            # CEK KONEKSI SETIAP LOOP
            try:
                client.ping()
                consecutive_errors = 0  # Reset error counter
            except Exception as e:
                consecutive_errors += 1
                print(f"❌ Koneksi error #{consecutive_errors}: {e}")
                if consecutive_errors >= 3:
                    print("💀 Koneksi mati, restart required")
                    break
                time.sleep(30)
                continue
            
            if active_position:
                # Monitoring position aktif
                current_price = get_current_price(active_position['symbol'])
                if current_price:
                    pnl_pct = (current_price - active_position['entry_price']) / active_position['entry_price'] * 100
                    print(f"📊 {active_position['symbol']}: ${current_price:.6f} | PnL: {pnl_pct:+.2f}%")
                    
                    if not ORDER_RUN:
                        if current_price >= active_position['take_profit']:
                            execute_market_sell(active_position['symbol'], active_position['quantity'], 
                                              active_position['entry_price'], "TAKE PROFIT")
                        elif current_price <= active_position['stop_loss']:
                            execute_market_sell(active_position['symbol'], active_position['quantity'], 
                                              active_position['entry_price'], "STOP LOSS")
                
                time.sleep(1)
                continue
            
            # SCAN JIKA SUDAH WAKTUNYA
            if current_time - last_scan_time > scan_interval:
                print(f"\n🕐 Time to scan... (interval: {scan_interval}s)")
                buy_signals = monitor_coins_improved()
                last_scan_time = current_time
                
                # EKSEKUSI JIKA ADA SINYAL
                if buy_signals:
                    print_buy_signals_details(buy_signals)
                    
                    for signal in buy_signals[:2]:  # Coba 2 terbaik saja
                        if execute_with_confirmation(signal):
                            print("✅ Trade executed!")
                            break
                        else:
                            print("❌ Execution failed, trying next...")
                            time.sleep(2)
                
                save_bot_state()
            
            # DELAY ANTARA LOOP - PENTING!
            wait_time = 2
            print(f"💤 Waiting {wait_time}s...")
            time.sleep(wait_time)
                
        except KeyboardInterrupt:
            print(f"\n🛑 Bot stopped by user")
            send_telegram_message("🛑 <b>BOT DIHENTIKAN OLEH PENGGUNA</b>")
            break
        except Exception as e:
            print(f"❌ Main loop error: {e}")
            time.sleep(30)  # Tunggu 30 detik jika error
    
    stop_websocket_monitoring()
    save_bot_state()
    print("✅ Bot stopped")

def main():
    main_improved_fast()

if __name__ == "__main__":
    main()