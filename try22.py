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

# Load environment variables dari file .env
load_dotenv()
warnings.filterwarnings('ignore')

# ==================== KONFIGURASI ====================
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

# ==================== DELAY CONFIGURATION ====================
# Konfigurasi delay untuk menghindari ban dari Binance
DELAY_BETWEEN_COINS = 1.2  # Delay 1.2 detik antara analisis coin
DELAY_BETWEEN_REQUESTS = 0.5  # Delay 0.5 detik antara requests
DELAY_AFTER_ERROR = 3.0  # Delay 3 detik setelah error

# Adjust for Render environment
if os.environ.get('RENDER'):
    DELAY_BETWEEN_COINS = 2.0
    DELAY_BETWEEN_REQUESTS = 1.0

# ==================== FUNGSI UNTUK DEPLOY DI RENDER ====================
def get_public_ip():
    """Mendapatkan IP publik yang digunakan untuk deploy di Render"""
    try:
        print("🌐 Checking public IP address...")
        
        # Coba beberapa services untuk mendapatkan IP
        services = [
            'https://api.ipify.org',
            'https://ident.me',
            'https://checkip.amazonaws.com',
            'https://ipinfo.io/ip'
        ]
        
        for service in services:
            try:
                response = requests.get(service, timeout=10)
                if response.status_code == 200:
                    ip = response.text.strip()
                    print(f"✅ Public IP: {ip} (from {service})")
                    
                    # Kirim IP ke Telegram untuk konfigurasi Binance
                    if SEND_TELEGRAM_NOTIFICATIONS and TELEGRAM_BOT_TOKEN and ADMIN_CHAT_ID:
                        ip_message = (
                            f"🌐 <b>BOT DEPLOYMENT INFO</b>\n"
                            f"Public IP: <code>{ip}</code>\n"
                            f"⚠️ <b>Tambahkan IP ini ke whitelist Binance API</b>\n"
                            f"1. Login ke Binance\n"
                            f"2. API Management\n"
                            f"3. Edit restrictions\n"
                            f"4. Tambahkan: <code>{ip}</code>"
                        )
                        send_telegram_message(ip_message)
                    
                    return ip
            except Exception as e:
                print(f"❌ Failed to get IP from {service}: {e}")
                continue
        
        print("❌ Could not determine public IP")
        return None
        
    except Exception as e:
        print(f"❌ Error getting public IP: {e}")
        return None

# ==================== RENDER FIX - BACKGROUND WORKER ====================
def run_background_worker():
    """Run as background worker for Render - no web server needed"""
    print("🔄 Running as Background Worker on Render...")
    
    # Get public IP for Binance whitelist
    public_ip = get_public_ip()
    
    # Initialize and start the bot
    main_improved_fast()

def create_simple_health_endpoint():
    """Create a simple health endpoint if running as web service"""
    try:
        from flask import Flask
        import os
        
        app = Flask(__name__)
        
        @app.route('/')
        def health_check():
            return {
                'status': 'running', 
                'service': 'trading-bot',
                'timestamp': datetime.now().isoformat()
            }
        
        @app.route('/health')
        def health():
            return {'status': 'healthy'}
        
        port = int(os.environ.get('PORT', 5000))
        print(f"🌐 Health endpoint running on port {port}")
        
        # Run in background thread to not block the bot
        import threading
        def run_flask():
            app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
        
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
    except ImportError:
        print("⚠️ Flask not installed, running as pure background worker")
    except Exception as e:
        print(f"⚠️ Health endpoint error: {e}")

def check_render_environment():
    """Check if running on Render and adjust configuration accordingly"""
    render_env = os.environ.get('RENDER', False)
    if render_env:
        print("🚀 Running on Render cloud platform")
        # Adjust delays for Render environment
        global DELAY_BETWEEN_COINS, DELAY_BETWEEN_REQUESTS
        DELAY_BETWEEN_COINS = 2.0  # Increase delays for Render
        DELAY_BETWEEN_REQUESTS = 1.0
        print(f"🔧 Adjusted delays for Render: {DELAY_BETWEEN_COINS}s between coins")
        return True
    return False

def check_binance_connection():
    """Test koneksi ke Binance dengan IP yang terdeteksi"""
    try:
        print("🔗 Testing Binance connection...")
        
        # Test koneksi dasar
        client.ping()
        print("✅ Binance connection test: SUCCESS")
        
        # Test mendapatkan server time
        server_time = client.get_server_time()
        local_time = int(time.time() * 1000)
        time_diff = server_time['serverTime'] - local_time
        print(f"⏰ Server time difference: {time_diff} ms")
        
        # Test mendapatkan price untuk satu symbol
        btc_price = get_current_price('BTCUSDT')
        if btc_price:
            print(f"💰 BTC price: ${btc_price:.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Binance connection test failed: {e}")
        
        # Kirim error ke Telegram
        if SEND_TELEGRAM_NOTIFICATIONS:
            error_msg = (
                f"🔴 <b>BINANCE CONNECTION FAILED</b>\n"
                f"Error: {str(e)}\n"
                f"⚠️ Pastikan:\n"
                f"• IP sudah di-whitelist di Binance\n"
                f"• API Key dan Secret benar\n"
                f"• Tidak ada IP restriction lain"
            )
            send_telegram_message(error_msg)
        
        return False

# ==================== TELEGRAM & LOGGING ====================
def load_config():
    """Load configuration from file"""
    default_config = {
        'trading_params': {
            'TAKE_PROFIT_PCT': 0.0060,
            'STOP_LOSS_PCT': 0.0170,
            'TRAILING_STOP_ACTIVATION': 0.0040,
            'TRAILING_STOP_PCT': 0.0080,
            'POSITION_SIZING_PCT': 0.4,
            'MAX_DRAWDOWN_PCT': 0.6,
            'ADAPTIVE_CONFIDENCE': True
        },
        'timeframe_params': {
            'RSI_MIN_15M': 30,
            'RSI_MAX_15M': 70,
            'EMA_SHORT_15M': 12,
            'EMA_LONG_15M': 26,
            'MACD_FAST_15M': 8,
            'MACD_SLOW_15M': 21,
            'MACD_SIGNAL_15M': 7,
            'LRO_PERIOD_15M': 20,
            'VOLUME_PERIOD_15M': 15,
            'RSI_MIN_5M': 33,
            'RSI_MAX_5M': 68,
            'EMA_SHORT_5M': 5,
            'EMA_LONG_5M': 20,
            'MACD_FAST_5M': 8,
            'MACD_SLOW_5M': 21,
            'MACD_SIGNAL_5M': 7,
            'LRO_PERIOD_5M': 20,
            'VOLUME_PERIOD_5M': 10,
            'VOLUME_RATIO_MIN': 0.5
        }
    }
    
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        else:
            save_config(default_config)
            return default_config
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return default_config

def save_config(config):
    """Save configuration to file"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"❌ Error saving config: {e}")
        return False

def update_global_variables_from_config():
    """Update global variables from config file"""
    global TAKE_PROFIT_PCT, STOP_LOSS_PCT, TRAILING_STOP_ACTIVATION, TRAILING_STOP_PCT
    global POSITION_SIZING_PCT, MAX_DRAWDOWN_PCT, ADAPTIVE_CONFIDENCE
    global RSI_MIN_15M, RSI_MAX_15M, EMA_SHORT_15M, EMA_LONG_15M, MACD_FAST_15M, MACD_SLOW_15M, MACD_SIGNAL_15M
    global LRO_PERIOD_15M, VOLUME_PERIOD_15M, RSI_MIN_5M, RSI_MAX_5M, EMA_SHORT_5M, EMA_LONG_5M
    global MACD_FAST_5M, MACD_SLOW_5M, MACD_SIGNAL_5M, LRO_PERIOD_5M, VOLUME_PERIOD_5M, VOLUME_RATIO_MIN
    
    config = load_config()
    trading_params = config['trading_params']
    timeframe_params = config['timeframe_params']
    
    # Update trading parameters
    TAKE_PROFIT_PCT = trading_params['TAKE_PROFIT_PCT']
    STOP_LOSS_PCT = trading_params['STOP_LOSS_PCT']
    TRAILING_STOP_ACTIVATION = trading_params['TRAILING_STOP_ACTIVATION']
    TRAILING_STOP_PCT = trading_params['TRAILING_STOP_PCT']
    POSITION_SIZING_PCT = trading_params['POSITION_SIZING_PCT']
    MAX_DRAWDOWN_PCT = trading_params['MAX_DRAWDOWN_PCT']
    ADAPTIVE_CONFIDENCE = trading_params['ADAPTIVE_CONFIDENCE']
    
    # Update timeframe parameters
    RSI_MIN_15M = timeframe_params['RSI_MIN_15M']
    RSI_MAX_15M = timeframe_params['RSI_MAX_15M']
    EMA_SHORT_15M = timeframe_params['EMA_SHORT_15M']
    EMA_LONG_15M = timeframe_params['EMA_LONG_15M']
    MACD_FAST_15M = timeframe_params['MACD_FAST_15M']
    MACD_SLOW_15M = timeframe_params['MACD_SLOW_15M']
    MACD_SIGNAL_15M = timeframe_params['MACD_SIGNAL_15M']
    LRO_PERIOD_15M = timeframe_params['LRO_PERIOD_15M']
    VOLUME_PERIOD_15M = timeframe_params['VOLUME_PERIOD_15M']
    RSI_MIN_5M = timeframe_params['RSI_MIN_5M']
    RSI_MAX_5M = timeframe_params['RSI_MAX_5M']
    EMA_SHORT_5M = timeframe_params['EMA_SHORT_5M']
    EMA_LONG_5M = timeframe_params['EMA_LONG_5M']
    MACD_FAST_5M = timeframe_params['MACD_FAST_5M']
    MACD_SLOW_5M = timeframe_params['MACD_SLOW_5M']
    MACD_SIGNAL_5M = timeframe_params['MACD_SIGNAL_5M']
    LRO_PERIOD_5M = timeframe_params['LRO_PERIOD_5M']
    VOLUME_PERIOD_5M = timeframe_params['VOLUME_PERIOD_5M']
    VOLUME_RATIO_MIN = timeframe_params['VOLUME_RATIO_MIN']

def handle_telegram_command():
    """Check for Telegram commands and execute them"""
    global BOT_RUNNING, active_position
    
    try:
        # Get updates from Telegram bot
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data['ok'] and data['result']:
                for update in data['result']:
                    if 'message' in update and 'text' in update['message']:
                        message = update['message']['text']
                        chat_id = update['message']['chat']['id']
                        
                        # Only process commands from admin
                        if str(chat_id) != ADMIN_CHAT_ID:
                            continue
                            
                        # Process commands
                        if message.startswith('/'):
                            process_telegram_command(message, chat_id, update['update_id'])
                            
    except Exception as e:
        print(f"❌ Telegram command error: {e}")

def process_telegram_command(command, chat_id, update_id):
    """Process individual Telegram commands"""
    global BOT_RUNNING, active_position
    
    try:
        if command == '/start':
            if not BOT_RUNNING:
                BOT_RUNNING = True
                send_telegram_message("🤖 <b>BOT DIAKTIFKAN</b>\nBot trading sekarang berjalan.")
            else:
                send_telegram_message("⚠️ Bot sudah berjalan.")
                
        elif command == '/stop':
            if BOT_RUNNING:
                BOT_RUNNING = False  # ✅ LANGSUNG SET FALSE - INI YANG MEMBATALKAN LOOP
                # Stop WebSocket monitoring
                stop_websocket_monitoring()
                send_telegram_message("🛑 <b>BOT DIHENTIKAN</b>\nTrading dihentikan.")
                
                # ✅ TAMBAHKAN LOG INI UNTUK KONFIRMASI
                print("🛑 BOT STOPPED via Telegram command")
            else:
                send_telegram_message("⚠️ Bot sudah dalam keadaan berhenti.")
                
        elif command == '/status':
            send_bot_status(chat_id)
            
        elif command == '/log':
            send_log_file(chat_id)
            
        elif command == '/config':
            send_current_config(chat_id)
            
        elif command.startswith('/set '):
            if not BOT_RUNNING:
                handle_config_change(command, chat_id)
            else:
                send_telegram_message("❌ <b>BOT MASIH BERJALAN</b>\nHentikan bot terlebih dahulu dengan /stop sebelum mengubah konfigurasi.")
                
        elif command == '/help':
            send_help_message(chat_id)
            
        elif command == '/ip':
            # Perintah untuk mendapatkan IP saat ini
            current_ip = get_public_ip()
            if current_ip:
                send_telegram_message(f"🌐 <b>CURRENT PUBLIC IP</b>\n<code>{current_ip}</code>")
            
        # Mark update as processed
        mark_update_processed(update_id)
        
    except Exception as e:
        send_telegram_message(f"❌ <b>ERROR PROCESSING COMMAND</b>\n{str(e)}")

def send_bot_status(chat_id):
    """Send current bot status"""
    global BOT_RUNNING, active_position, current_investment, trade_history, performance_state
    
    status_msg = (
        f"🤖 <b>BOT STATUS</b>\n"
        f"┌────────────────────────────┐\n"
        f"│ Status: {'🟢 BERJALAN' if BOT_RUNNING else '🔴 BERHENTI'}\n"
        f"│ Modal: ${current_investment:.2f}\n"
        f"│ Total Trade: {len(trade_history)}\n"
        f"│ Win Rate: {calculate_winrate():.1f}%\n"
    )
    
    if active_position:
        pnl_pct = (get_current_price(active_position['symbol']) - active_position['entry_price']) / active_position['entry_price'] * 100
        status_msg += f"│ Posisi Aktif: {active_position['symbol']}\n"
        status_msg += f"│ PnL: {pnl_pct:+.2f}%\n"
    else:
        status_msg += "│ Posisi Aktif: Tidak ada\n"
        
    status_msg += (
        f"│ Loss Streak: {performance_state.get('loss_streak', 0)}\n"
        f"│ Win Streak: {performance_state.get('win_streak', 0)}\n"
        f"└────────────────────────────┘"
    )
    
    send_telegram_message(status_msg)

def send_log_file(chat_id):
    """Send log file to Telegram"""
    try:
        if os.path.exists(LOG_FILE):
            # Read last 100 lines of log file
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                last_lines = lines[-100:]  # Last 100 lines
                log_content = ''.join(last_lines)
            
            if len(log_content) > 4000:
                log_content = log_content[-4000:]  # Trim if too long
                
            send_telegram_message(f"📋 <b>LOG TERAKHIR</b>\n<pre>{log_content}</pre>")
        else:
            send_telegram_message("❌ File log tidak ditemukan.")
    except Exception as e:
        send_telegram_message(f"❌ Error membaca log: {str(e)}")

def send_current_config(chat_id):
    """Send current configuration"""
    config = load_config()
    trading_params = config['trading_params']
    timeframe_params = config['timeframe_params']
    
    config_msg = (
        f"⚙️ <b>KONFIGURASI SAAT INI</b>\n"
        f"┌────────────────────────────┐\n"
        f"│ <b>TRADING PARAMS</b>\n"
        f"│ TP: {trading_params['TAKE_PROFIT_PCT']*100:.2f}%\n"
        f"│ SL: {trading_params['STOP_LOSS_PCT']*100:.2f}%\n"
        f"│ Position: {trading_params['POSITION_SIZING_PCT']*100:.1f}%\n"
        f"│ Trailing Act: {trading_params['TRAILING_STOP_ACTIVATION']*100:.2f}%\n"
        f"│ Trailing SL: {trading_params['TRAILING_STOP_PCT']*100:.2f}%\n"
        f"├────────────────────────────┤\n"
        f"│ <b>M15 PARAMS</b>\n"
        f"│ RSI: {timeframe_params['RSI_MIN_15M']}-{timeframe_params['RSI_MAX_15M']}\n"
        f"│ EMA: {timeframe_params['EMA_SHORT_15M']}/{timeframe_params['EMA_LONG_15M']}\n"
        f"│ MACD: {timeframe_params['MACD_FAST_15M']}/{timeframe_params['MACD_SLOW_15M']}/{timeframe_params['MACD_SIGNAL_15M']}\n"
        f"├────────────────────────────┤\n"
        f"│ <b>M5 PARAMS</b>\n"
        f"│ RSI: {timeframe_params['RSI_MIN_5M']}-{timeframe_params['RSI_MAX_5M']}\n"
        f"│ EMA: {timeframe_params['EMA_SHORT_5M']}/{timeframe_params['EMA_LONG_5M']}\n"
        f"│ MACD: {timeframe_params['MACD_FAST_5M']}/{timeframe_params['MACD_SLOW_5M']}/{timeframe_params['MACD_SIGNAL_5M']}\n"
        f"└────────────────────────────┘\n"
        f"Gunakan /help untuk melihat cara mengubah konfigurasi."
    )
    
    send_telegram_message(config_msg)

def handle_config_change(command, chat_id):
    """Handle configuration changes via Telegram"""
    try:
        parts = command.split()
        if len(parts) < 3:
            send_telegram_message("❌ Format: /set [parameter] [value]")
            return
            
        param_name = parts[1]
        param_value = ' '.join(parts[2:])
        
        config = load_config()
        updated = False
        
        # Check trading parameters
        if param_name in config['trading_params']:
            old_value = config['trading_params'][param_name]
            # Convert value to appropriate type
            if isinstance(old_value, bool):
                config['trading_params'][param_name] = param_value.lower() in ('true', '1', 'yes', 'y')
            elif isinstance(old_value, float):
                config['trading_params'][param_name] = float(param_value)
            elif isinstance(old_value, int):
                config['trading_params'][param_name] = int(param_value)
            updated = True
            
        # Check timeframe parameters  
        elif param_name in config['timeframe_params']:
            old_value = config['timeframe_params'][param_name]
            if isinstance(old_value, int):
                config['timeframe_params'][param_name] = int(param_value)
            elif isinstance(old_value, float):
                config['timeframe_params'][param_name] = float(param_value)
            updated = True
            
        if updated:
            if save_config(config):
                update_global_variables_from_config()
                send_telegram_message(f"✅ <b>KONFIGURASI DIPERBARUI</b>\n{param_name} = {param_value}")
            else:
                send_telegram_message("❌ Gagal menyimpan konfigurasi.")
        else:
            send_telegram_message(f"❌ Parameter '{param_name}' tidak ditemukan.")
            
    except ValueError:
        send_telegram_message("❌ Format nilai tidak valid.")
    except Exception as e:
        send_telegram_message(f"❌ Error: {str(e)}")

def send_help_message(chat_id):
    """Send help message with available commands"""
    help_msg = (
        f"📖 <b>BOT TRADING COMMANDS</b>\n"
        f"┌────────────────────────────┐\n"
        f"│ /start - Mulai bot trading\n"
        f"│ /stop - Hentikan bot\n"
        f"│ /status - Status bot saat ini\n"
        f"│ /log - Tampilkan log terakhir\n"
        f"│ /config - Tampilkan konfigurasi\n"
        f"│ /help - Tampilkan pesan bantuan\n"
        f"│ /ip - Tampilkan IP publik\n"
        f"├────────────────────────────┤\n"
        f"│ <b>UBAH KONFIGURASI</b>\n"
        f"│ /set [param] [value]\n"
        f"│ Contoh:\n"
        f"│ /set TAKE_PROFIT_PCT 0.008\n"
        f"│ /set RSI_MIN_15M 35\n"
        f"│ /set POSITION_SIZING_PCT 0.3\n"
        f"└────────────────────────────┘\n"
        f"<i>Hanya bisa diubah saat bot berhenti</i>"
    )
    
    send_telegram_message(help_msg)

def mark_update_processed(update_id):
    """Mark Telegram update as processed"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        params = {'offset': update_id + 1}
        requests.get(url, params=params, timeout=5)
    except:
        pass

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

def log_position_closed(symbol, entry_price, exit_price, quantity, exit_type):
    """Log when position is closed dengan integrated feedback loop"""
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
        
        # Update recent trades untuk feedback system
        recent_trades.append(pnl_pct)
        
        # Update dynamic threshold (existing system)
        update_dynamic_threshold()
        
        # TRIGGER FEEDBACK LOOP - sistem adaptasi baru
        trade_performance_feedback_loop()
        
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
                      f"│ Loss Streak: {performance_state['loss_streak']}\n"
                      f"└────────────────────────────┘")
        
        send_telegram_message(telegram_msg)
        
        # HENTIKAN WEBSOCKET SETELAH SELL
        stop_websocket_monitoring()
        
    except Exception as e:
        print(f"❌ Error logging position close: {e}")

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
    """Load bot state termasuk performance data"""
    global coin_performance, dynamic_threshold, recent_trades, failed_coins, performance_state
    
    try:
        if os.path.exists(BOT_STATE_FILE):
            with open(BOT_STATE_FILE, 'r') as f:
                state = json.load(f)
                
            coin_performance = state.get('coin_performance', {})
            dynamic_threshold = max(30, state.get('dynamic_threshold', 30))  # MINIMAL 30
            recent_trades = deque(state.get('recent_trades', []), maxlen=10)
            performance_state = state.get('performance_state', performance_state)
            
            # Clean old failed coins (older than 24 hours)
            current_time = time.time()
            failed_coins = {
                coin: timestamp for coin, timestamp in state.get('failed_coins', {}).items()
                if current_time - timestamp < 86400
            }
            
            print(f"✅ Loaded bot state: threshold: {dynamic_threshold}, loss_streak: {performance_state.get('loss_streak', 0)}")
    except Exception as e:
        print(f"❌ Error loading bot state: {e}")

def save_bot_state():
    """Save bot state termasuk performance data"""
    try:
        state = {
            'coin_performance': coin_performance,
            'dynamic_threshold': dynamic_threshold,
            'recent_trades': list(recent_trades),
            'failed_coins': failed_coins,
            'performance_state': performance_state,
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
        dynamic_threshold = min(40, dynamic_threshold + 2)  # Boleh naik sampai 50
        print(f"📊 Winrate rendah ({winrate:.1%}), naikkan threshold ke {dynamic_threshold}")
    elif winrate > 0.7:
        # TIDAK BOLEH TURUN DI BAWAH 30
        dynamic_threshold = max(30, dynamic_threshold - 1)  # MINIMAL 30
        print(f"📊 Winrate tinggi ({winrate:.1%}), turunkan threshold ke {dynamic_threshold}")

# ==================== BINANCE UTILITIES ====================
def trade_performance_feedback_loop():
    """Adaptive feedback loop - panggil setelah trade ditutup atau periodik"""
    global recent_trades, performance_state, dynamic_threshold, POSITION_SIZING_PCT, current_investment

    try:
        now = time.time()
        
        # Skip jika belum ada trade yang cukup
        if len(recent_trades) < 2:
            return

        # Collect recent PnL%
        recent = list(recent_trades)
        
        # Compute metrics
        wins = sum(1 for v in recent if v > 0)
        losses = sum(1 for v in recent if v <= 0)
        rolling_winrate = wins / len(recent) if recent else 0
        avg_pnl = sum(recent) / len(recent) if recent else 0

        # Update EMA PnL
        ema_prev = performance_state.get('ema_pnl', 0.0)
        ema_new = EMA_ALPHA * avg_pnl + (1 - EMA_ALPHA) * ema_prev
        performance_state['ema_pnl'] = ema_new

        # Update streaks dari trade_history
        if trade_history:
            loss_streak = 0
            win_streak = 0
            
            # Check last 5 trades untuk streak
            for trade in reversed(trade_history[-5:]):
                pnl_pct = trade.get('pnl_pct', 0)
                if pnl_pct <= 0:
                    if win_streak == 0:
                        loss_streak += 1
                    else:
                        break
                else:
                    if loss_streak == 0:
                        win_streak += 1
                    else:
                        break
            
            performance_state['loss_streak'] = loss_streak
            performance_state['win_streak'] = win_streak
            performance_state['total_trades'] = len(trade_history)
            performance_state['total_wins'] = wins

        # Log metrics
        print(f"[FEEDBACK] Winrate: {rolling_winrate:.1%}, Avg PnL: {avg_pnl:.3f}%, EMA: {ema_new:.3f}%, Loss Streak: {performance_state['loss_streak']}")

        # RULE 1: Loss Streak Adaptation
        if (performance_state['loss_streak'] >= LOSS_STREAK_LIMIT and 
            now - performance_state.get('last_adaptation_time', 0) > 120):
            
            old_threshold = dynamic_threshold
            old_position_size = POSITION_SIZING_PCT
            
            # Naikkan threshold - BOLEH NAIK TANPA BATAS ATAS
            dynamic_threshold = dynamic_threshold + LOSS_STREAK_THRESHOLD_INCREASE
            
            # Turunkan position size (tapi jangan kurang dari minimum)
            new_pos_size = max(MIN_POSITION_SIZING, POSITION_SIZING_PCT * LOSS_STREAK_POSITION_SIZER_MULT)
            max_allowed_reduction = POSITION_SIZING_PCT * (1 - MAX_ADAPTATION_PERCENT)
            POSITION_SIZING_PCT = max(new_pos_size, max_allowed_reduction)
            
            # Set pause dan update waktu adaptasi
            performance_state['paused_until'] = now + LOSS_STREAK_COOLDOWN
            performance_state['last_adaptation_time'] = now

            # Kirim notifikasi
            adaptation_msg = (
                f"⚠️ <b>ADAPTATION TRIGGERED - LOSS STREAK</b>\n"
                f"Loss Streak: {performance_state['loss_streak']}\n"
                f"Threshold: {old_threshold} → {dynamic_threshold}\n"
                f"Position Size: {old_position_size:.1%} → {POSITION_SIZING_PCT:.1%}\n"
                f"Cooldown: {LOSS_STREAK_COOLDOWN//60} menit"
            )
            send_telegram_message(adaptation_msg)
            write_log(f"[ADAPTATION] Loss streak {performance_state['loss_streak']} -> threshold {old_threshold}->{dynamic_threshold}, position {old_position_size:.3f}->{POSITION_SIZING_PCT:.3f}")

        # RULE 2: Win Streak Reward
        if performance_state.get('win_streak', 0) < WIN_STREAK_LIMIT:
            performance_state['reward_triggered'] = False

        elif (performance_state['win_streak'] >= WIN_STREAK_LIMIT and 
              now - performance_state.get('last_adaptation_time', 0) > 120) and not performance_state.get('reward_triggered', False):
            
            old_threshold = dynamic_threshold
            old_position_size = POSITION_SIZING_PCT
            
            # Turunkan threshold - TIDAK BOLEH TURUN DI BAWAH 30
            dynamic_threshold = max(30, dynamic_threshold - WIN_STREAK_THRESHOLD_DECREASE)
            
            # Naikkan position size (tapi hati-hati)
            new_pos_size = min(0.6, POSITION_SIZING_PCT * 1.15)  # Maksimal 60%
            max_allowed_increase = POSITION_SIZING_PCT * (1 + MAX_ADAPTATION_PERCENT)
            POSITION_SIZING_PCT = min(new_pos_size, max_allowed_increase)
            
            performance_state['last_adaptation_time'] = now
            performance_state['reward_triggered'] = True

            # Kirim notifikasi positif
            reward_msg = (
                f"✅ <b>PERFORMANCE REWARD - WIN STREAK</b>\n"
                f"Win Streak: {performance_state['win_streak']}\n"
                f"Threshold: {old_threshold} → {dynamic_threshold}\n"
                f"Position Size: {old_position_size:.1%} → {POSITION_SIZING_PCT:.1%}"
            )
            send_telegram_message(reward_msg)
            write_log(f"[REWARD] Win streak {performance_state['win_streak']} -> threshold {old_threshold}->{dynamic_threshold}, position {old_position_size:.3f}->{POSITION_SIZING_PCT:.3f}")

        # RULE 3: Very Poor Performance Emergency Stop
        if (len(recent_trades) >= 5 and rolling_winrate < 0.2 and 
            now - performance_state.get('last_adaptation_time', 0) > 300):
            
            performance_state['paused_until'] = now + 1800  # 30 menit
            emergency_msg = (
                f"🛑 <b>EMERGENCY STOP - POOR PERFORMANCE</b>\n"
                f"Win Rate: {rolling_winrate:.1%}\n"
                f"Avg PnL: {avg_pnl:.3f}%\n"
                f"Bot paused for 30 minutes"
            )
            send_telegram_message(emergency_msg)
            write_log(f"[EMERGENCY] Poor performance - winrate {rolling_winrate:.1%} -> paused 30min")

        # Save state
        save_bot_state()

    except Exception as e:
        print(f"❌ Feedback loop error: {e}")

def is_trading_paused():
    """Cek apakah trading sedang dipause karena poor performance"""
    global performance_state
    
    now = time.time()
    paused_until = performance_state.get('paused_until', 0)
    
    if now < paused_until:
        remaining = paused_until - now
        if remaining > 60:  # Only log if more than 1 minute remaining
            print(f"🔒 Trading paused due to performance. Resuming in {int(remaining/60)} minutes")
        return True
    
    return False

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
    """Calculate EMA dengan error handling yang lebih baik"""
    if prices is None or len(prices) < period:
        print(f"   ⚠️ EMA: Not enough data (need {period}, got {len(prices) if prices else 0})")
        return None
    
    try:
        # Pastikan tidak ada NaN atau infinite values
        prices_clean = [float(price) for price in prices if price is not None and not math.isnan(price)]
        
        if len(prices_clean) < period:
            return None
            
        # Gunakan pandas EMA yang lebih stabil
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
    """Get klines data dengan processing yang benar"""
    try:
        # Tambahkan retry mechanism
        for attempt in range(3):
            try:
                klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
                if klines and len(klines) >= 20:
                    # Process data dengan benar
                    closes = []
                    highs = []
                    lows = []
                    volumes = []
                    
                    for kline in klines:
                        closes.append(float(kline[4]))  # Close price
                        highs.append(float(kline[2]))   # High price
                        lows.append(float(kline[3]))    # Low price
                        volumes.append(float(kline[5])) # Volume
                    
                    processed_data = {
                        'close': closes,
                        'high': highs,
                        'low': lows,
                        'volume': volumes
                    }
                    
                    return processed_data
                else:
                    print(f"   ⚠️ Insufficient data for {symbol} {interval}: {len(klines) if klines else 0} candles")
                    time.sleep(1)
            except Exception as e:
                print(f"   ⚠️ Attempt {attempt + 1} failed: {e}")
                time.sleep(2)
        
        return None
    except Exception as e:
        print(f"❌ Final error get_klines_data untuk {symbol}: {str(e)}")
        return None

def get_two_timeframe_data(symbol):
    """Get data dengan validation yang ketat"""
    try:
        # Cek apakah symbol valid dengan get_price dulu
        test_price = get_current_price(symbol)
        if not test_price:
            print(f"   💀 INVALID SYMBOL: {symbol} - skipping")
            return None, None
        
        print(f"   📊 Fetching data for {symbol}...")
        data_15m = get_klines_data(symbol, Client.KLINE_INTERVAL_15MINUTE, 40)
        data_5m = get_klines_data(symbol, Client.KLINE_INTERVAL_5MINUTE, 40)
        
        # Validasi data yang diterima
        if data_15m is None or data_5m is None:
            print(f"   📭 No data received for {symbol}")
            return None, None
            
        # Validasi length data
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

# ==================== SISTEM SINYAL YANG DIPERBAIKI ====================
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
        
        confidence = (m15_score * 0.6) + (m5_score * 0.4)
        confidence = min(95, max(confidence, 0))
        
        current_price = get_current_price(symbol)
        if current_price is None:
            print(f"   💰 Cannot get price for {symbol}")
            return None
        
        # PERUBAHAN PENTING: Confidence harus >= dynamic_threshold untuk sinyal buy
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

# ==================== ORDER MANAGEMENT ====================
def get_precise_quantity(symbol, investment_amount):
    """Dapatkan quantity yang tepat untuk order - DIPERBAIKI untuk minimum $5.5"""
    try:
        current_price = get_current_price(symbol)
        if not current_price or current_price <= 0:
            print(f"   ❌ Tidak bisa mendapatkan harga untuk {symbol}")
            return None
            
        # Hitung quantity teoritis
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
        adjusted_quantity = theoretical_quantity * 1.0
        precise_quantity = round_step_size(adjusted_quantity, symbol)
        
        if not precise_quantity:
            print(f"   ❌ Gagal round quantity untuk {symbol}")
            return None
            
        return precise_quantity
        
    except Exception as e:
        print(f"❌ Error di get_precise_quantity: {e}")
        return None

def calculate_position_size(symbol):
    """Hitung ukuran position - DIPERBAIKI untuk minimum $5.5"""
    global current_investment
    
    # Hitung position size berdasarkan persentase
    position_value = current_investment * POSITION_SIZING_PCT
    
    print(f"💰 Position calculation for {symbol}:")
    print(f"   Capital: ${current_investment:.2f}")
    print(f"   {POSITION_SIZING_PCT*100}% = ${position_value:.2f}")
    
    # PASTIKAN MINIMAL $5.5 (sesuai INITIAL_INVESTMENT)
    if position_value < INITIAL_INVESTMENT:
        print(f"   ⚠️ Below minimum ${INITIAL_INVESTMENT}, adjusting...")
        position_value = INITIAL_INVESTMENT
    
    # Batasi maksimal 60% dari capital
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

def place_market_buy_order(symbol, investment_amount):
    """Place market buy order - DIPERBAIKI untuk minimum $5.5"""
    global current_investment
    
    try:
        print(f"🔹 BUY ORDER: {symbol}")
        
        # Cek balance untuk live trading
        free_balance = 0  # ✅ INISIALISASI DULU
        if ORDER_RUN:
            try:
                balance = client.get_asset_balance(asset='USDT')
                free_balance = float(balance['free'])
                if free_balance < investment_amount:
                    print(f"❌ Insufficient balance. Need: ${investment_amount:.2f}, Available: ${free_balance:.2f}")
                    return None
            except Exception as e:
                print(f"⚠️ Balance check skipped: {e}")
                # ✅ JIKA GAGAL CEK BALANCE, GUNAKAN INVESTMENT AMOUNT DEFAULT
                free_balance = investment_amount * 2  # Asumsikan cukup
        
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
        print(f"   Our minimum: ${INITIAL_INVESTMENT}")
        
        # PASTIKAN MEMENUHI MINIMAL KITA ($5.5) DAN MINIMAL BINANCE
        required_minimum = max(min_notional, INITIAL_INVESTMENT)
        if calculated_value < required_minimum:
            print(f"   ⚠️ Below required minimum ${required_minimum}, adjusting...")
            
            # Hitung ulang dengan required minimum
            required_investment = required_minimum * 1.02  # Tambah 2% untuk aman
            theoretical_quantity = required_investment / current_price
            
            print(f"   Adjusted investment: ${required_investment:.2f}")
            print(f"   Adjusted quantity: {theoretical_quantity:.8f}")
            
            # ✅ PERBAIKI: GUNAKAN VARIABLE YANG SUDAH DIINISIALISASI
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
        
        # Final check minimum requirements
        if final_order_value < required_minimum:
            print(f"❌ Still below required minimum after rounding: ${final_order_value:.2f} < ${required_minimum:.2f}")
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
    """Execute market sell order dengan proses cepat"""
    global current_investment, active_position
    
    try:
        print(f"🔹 FAST SELL: {symbol} ({exit_type})")
        
        current_price = get_current_price(symbol)
        if not current_price:
            print(f"   ❌ Cannot get current price for {symbol}")
            return False

        # CEK BALANCE SEBELUM JUAL
        if ORDER_RUN:
            asset = symbol.replace('USDT', '')
            try:
                balance_info = client.get_asset_balance(asset=asset)
                if balance_info:
                    available_balance = float(balance_info['free'])
                    print(f"   💰 Available {asset}: {available_balance}")
                    
                    if available_balance <= 0:
                        print(f"   ❌ No {asset} balance available")
                        active_position = None  # Reset position
                        return False
                        
                    # Adjust quantity jika perlu
                    if quantity > available_balance:
                        print(f"   ⚠️ Adjusting quantity from {quantity} to {available_balance}")
                        quantity = available_balance
            except Exception as e:
                print(f"   ⚠️ Balance check error: {e}")

        # QUANTITY CEPAT - gunakan quantity asli untuk simulasi
        if not ORDER_RUN:
            # SIMULASI CEPAT
            log_position_closed(symbol, entry_price, current_price, quantity, exit_type)
            active_position = None
            return True

        # LIVE TRADING - CEPAT dengan error handling
        precise_quantity = round_step_size(quantity, symbol)
        if not precise_quantity:
            precise_quantity = round(quantity, 6)

        # CEK ULANG SEBELUM ORDER
        if precise_quantity <= 0:
            print(f"   ❌ Invalid quantity: {precise_quantity}")
            active_position = None
            return False

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
            print(f"   ✅ SELL successful: {executed_qty} {symbol} at ${exit_price}")
            return True
            
        # JIKA GAGAL, reset position
        print(f"   ❌ SELL order failed for {symbol}")
        active_position = None
        return False

    except Exception as e:
        print(f"❌ Fast SELL error: {e}")
        active_position = None
        return False

# ==================== RISK MANAGEMENT ====================
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

# ==================== TRAILING STOP SYSTEM ====================
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
    
    # Cek jika sudah ada proses jual yang berjalan
    if active_position.get('selling_in_progress'):
        return False
    
    stop_loss = active_position['stop_loss']
    
    if current_price <= stop_loss:
        print(f"🛑 Trailing Stop hit for {symbol} at ${current_price:.6f}")
        quantity = active_position['quantity']
        entry_price = active_position['entry_price']
        
        # Tandai sedang proses jual
        active_position['selling_in_progress'] = True
        
        if execute_market_sell(symbol, quantity, entry_price, "TRAILING STOP"):
            pnl_pct = (current_price - entry_price) / entry_price * 100
            recent_trades.append(pnl_pct)
            update_dynamic_threshold()
            return True
        else:
            # Reset flag jika gagal
            active_position['selling_in_progress'] = False
    
    return False

# ==================== WEBSOCKET MANAGEMENT ====================
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
        
        # Jangan proses jika sedang dalam proses jual
        if active_position.get('selling_in_progress'):
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
            # Tandai sedang proses jual
            active_position['selling_in_progress'] = True
            if execute_market_sell(symbol, quantity, entry_price, "TAKE PROFIT"):
                pnl_pct = (current_price - entry_price) / entry_price * 100
                recent_trades.append(pnl_pct)
                update_dynamic_threshold()
            else:
                # Reset flag jika gagal
                active_position['selling_in_progress'] = False
            return
        
        # Cek Stop Loss (hanya jika trailing stop tidak aktif)
        stop_loss = active_position['stop_loss']
        if current_price <= stop_loss and not active_position.get('trailing_active', False):
            print(f"🛑 SL hit for {symbol} at ${current_price:.6f} (SL: ${stop_loss:.6f})")
            # Tandai sedang proses jual
            active_position['selling_in_progress'] = True
            if execute_market_sell(symbol, quantity, entry_price, "STOP LOSS"):
                pnl_pct = (current_price - entry_price) / entry_price * 100
                recent_trades.append(pnl_pct)
                update_dynamic_threshold()
            else:
                # Reset flag jika gagal
                active_position['selling_in_progress'] = False
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
    """Stop all WebSocket monitoring dengan error handling"""
    global twm
    
    try:
        if twm:
            print("🔌 Stopping WebSocket monitoring...")
            twm.stop()
            twm = None
            print("✅ WebSocket monitoring stopped")
    except Exception as e:
        print(f"❌ Error stopping WebSocket: {e}")
        twm = None  # Force reset

# ==================== MONITORING & EXECUTION YANG DIPERBAIKI ====================
def monitor_coins_until_signal():
    """Monitor coins sampai menemukan sinyal buy pertama - DENGAN INTERRUPTIBLE"""
    global buy_signals, BOT_RUNNING
    
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
    
    for i, coin in enumerate(COINS):
        # ✅ PERIKSA STATUS BOT SETIAP COIN - INI KUNCI UTAMA!
        if not BOT_RUNNING:
            print("🛑 Scanning interrupted by /stop command")
            return []
        
        try:
            print(f"   Checking {coin}...")
            
            # ✅ TAMBAHKAN DELAY ANTAR COIN UNTUK MENGHINDARI BAN
            if i > 0:
                print(f"   ⏳ Waiting {DELAY_BETWEEN_COINS}s before next coin...")
                time.sleep(DELAY_BETWEEN_COINS)
            
            analysis = analyze_coin_improved(coin)
            
            # ✅ TAMBAHKAN CEK BOT_RUNNING SETELAH ANALISIS
            if not BOT_RUNNING:
                print("🛑 Analysis interrupted by /stop command")
                return []
            
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
            
            # ✅ CEK BOT_RUNNING SETIAP 5 COIN UNTUK RESPONSIF
            if i % 5 == 0:
                if TELEGRAM_CONTROL_ENABLED:
                    handle_telegram_command()
                if not BOT_RUNNING:
                    print("🛑 Scanning interrupted during batch check")
                    return []
            
            # ✅ TAMBAHKAN DELAY ANTAR REQUEST
            time.sleep(DELAY_BETWEEN_REQUESTS)
            
        except Exception as e:
            print(f"   ⚠️ {coin}: Error - {e}")
            
            # ✅ TAMBAHKAN DELAY LEBIH PANJANG SETELAH ERROR
            print(f"   ⏳ Waiting {DELAY_AFTER_ERROR}s after error...")
            time.sleep(DELAY_AFTER_ERROR)
            
            # ✅ CEK BOT_RUNNING SETELAH ERROR JUGA
            if not BOT_RUNNING:
                print("🛑 Error handling interrupted by /stop command")
                return []
    
    print(f"\n📊 SCAN COMPLETE: No signals found in {len(COINS)} coins")
    return []

def fast_execute_signal(signal):
    """Execute trade dengan proses sangat cepat setelah sinyal ditemukan"""
    global active_position

    if not BOT_RUNNING:
        print("🛑 Execution cancelled by /stop command")
        return False
    
    symbol = signal['symbol']
    confidence = signal['confidence']
    current_price = signal['current_price']
    
    print(f"⚡ FAST EXECUTION: {symbol} (Confidence: {confidence:.1f}%)")
    
    # KONFIRMASI ULANG SUPER CEPAT
    print(f"   🔍 Quick re-confirmation...")
    quick_check = analyze_coin_improved(symbol)

    if not BOT_RUNNING:
        print("🛑 Quick confirmation interrupted by /stop command")
        return False
    
    if not quick_check or not quick_check['buy_signal']:
        print(f"   ❌ Signal disappeared, aborting...")
        failed_coins[symbol] = time.time()
        return False
    
    # POSITION SIZE CEPAT - GUNAKAN MINIMAL $5.5
    investment_amount = calculate_position_size(symbol)
    
    if not investment_amount:
        print(f"   ❌ Cannot calculate position size")
        return False
    
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

# ==================== MAIN BOT LOGIC YANG DIPERBAIKI ====================
def main_improved_fast():
    """Main bot function dengan Telegram control"""
    global current_investment, active_position, twm, BOT_RUNNING
    
    print("🚀 Starting BOT - TELEGRAM CONTROLLED VERSION")

    # Load configuration pertama kali
    update_global_variables_from_config()
    
    initialize_logging()
    load_trade_history()
    load_bot_state()
    
    if not initialize_binance_client():
        print("❌ Gagal inisialisasi Binance client")
        return
    
    # ✅ DAPATKAN IP PUBLIK UNTUK DEPLOY DI RENDER
    public_ip = get_public_ip()
    if public_ip:
        print(f"🌐 Bot running from IP: {public_ip}")
    
    # ✅ TEST KONEKSI BINANCE
    if not check_binance_connection():
        print("❌ Binance connection test failed. Check your API keys and IP whitelist.")
        return
    
    startup_msg = f"🤖 <b>BOT STARTED - TELEGRAM CONTROL</b>\nCoins: {len(COINS)}\nMode: {'LIVE' if ORDER_RUN else 'SIMULATION'}\nStatus: MENUNGGU PERINTAH /start"
    send_telegram_message(startup_msg)
    
    consecutive_errors = 0
    last_feedback_check = 0
    last_telegram_check = 0
    
    print("✅ Bot siap. Gunakan Telegram untuk mengontrol (/start untuk mulai)")
    
    while True:
        try:
            # CHECK TELEGRAM COMMANDS setiap 3 detik
            current_time = time.time()
            if current_time - last_telegram_check > 3:
                if TELEGRAM_CONTROL_ENABLED:
                    handle_telegram_command()
                last_telegram_check = current_time
            
            # Jika bot tidak running, tunggu saja
            if not BOT_RUNNING:
                time.sleep(1)
                continue
            
            # CEK PAUSE STATE - sistem adaptasi
            if is_trading_paused():
                time.sleep(5)
                continue
            
            # CEK KONEKSI SETIAP LOOP
            try:
                client.ping()
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                print(f"❌ Koneksi error #{consecutive_errors}: {e}")
                if consecutive_errors >= 3:
                    print("💀 Koneksi mati, restart required")
                    send_telegram_message("🔴 <b>KONEKSI BINANCE TERPUTUS</b>\nBot dihentikan otomatis.")
                    BOT_RUNNING = False
                    break
                time.sleep(30)
                continue
            
            # PERIODIC FEEDBACK CHECK (setiap 5 menit)
            if current_time - last_feedback_check > 300:  # 5 menit
                trade_performance_feedback_loop()
                last_feedback_check = current_time
            
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
            print(f"\n🕐 Scanning for signals... (Threshold: {dynamic_threshold}%, Position: {POSITION_SIZING_PCT:.1%})")
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
                print("💤 No signals, waiting 3s...")
                time.sleep(3)
                
            save_bot_state()
                
        except KeyboardInterrupt:
            print(f"\n🛑 Bot stopped by user")
            send_telegram_message("🛑 <b>BOT DIHENTIKAN OLEH PENGGUNA</b>")
            BOT_RUNNING = False
            break
        except Exception as e:
            print(f"❌ Main loop error: {e}")
            time.sleep(10)
    
    # Cleanup
    stop_websocket_monitoring()
    save_bot_state()
    print("✅ Bot stopped completely")

def main():
    main_improved_fast()

if __name__ == "__main__":
    # Check if running on Render
    is_render = check_render_environment()
    
    if is_render:
        # Option 1: Run as background worker (no web server)
        print("🔧 Starting as Background Worker...")
        run_background_worker()
        
        # Option 2: Uncomment below if you need health checks
        # create_simple_health_endpoint()
        # run_background_worker()
    else:
        # Local development
        main_improved_fast()


