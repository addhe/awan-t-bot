import ccxt
import os
import logging
import time
import pandas as pd
import requests
from numpy import log, mean, std
from logging.handlers import RotatingFileHandler

# Konfigurasi Logging
log_handler = RotatingFileHandler('trade_log.log', maxBytes=5*1024*1024, backupCount=2)
logging.basicConfig(handlers=[log_handler], level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Muat API_KEY dan API_SECRET dari variabel lingkungan
API_KEY = os.environ.get('API_KEY_BINANCE')
API_SECRET = os.environ.get('API_SECRET_BINANCE')

if API_KEY is None or API_SECRET is None:
    logging.error('API_KEY atau API_SECRET tidak ditemukan di environment variabel')
    exit(1)

# Inisialisasi exchange
exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'options': {
        'defaultType': 'future'
    }
})

# Aktifkan mode sandbox
exchange.set_sandbox_mode(True)

# Definisikan konfigurasi
CONFIG = {
    'symbol': 'BTC/USDT',
    'max_positions': 5,
    'profit_target_percent': 0.01,  # 1% target profit
    'stop_loss_percent': 0.02,  # 2% stop loss
    'timeframe': '5m',
    'ema_short_period': 13,
    'ema_long_period': 26,
    'risk_percentage': 2  # Percent of balance to risk per trade
}

TELEGRAM_CONFIG = {
    'bot_token': os.environ.get('TELEGRAM_BOT_TOKEN'),
    'chat_id': os.environ.get('TELEGRAM_CHAT_ID')
}

def send_telegram_notification(message):
    bot_token = TELEGRAM_CONFIG['bot_token']
    chat_id = TELEGRAM_CONFIG['chat_id']
    if bot_token and chat_id:
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {"chat_id": chat_id, "text": message}
            requests.post(url, json=payload)
        except Exception as e:
            logging.error(f'Error sending Telegram notification: {e}')
    else:
        logging.error('Telegram bot token or chat ID not set')

def fetch_ohlcv(symbol, limit=50, timeframe='5m'):
    try:
        return exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    except ccxt.RequestTimeout as e:
        logging.error(f'Request timeout: {e}')
    except ccxt.NetworkError as e:
        logging.error(f'Network error: {e}')
    except Exception as e:
        logging.error(f'Gagal mendapatkan data harga: {e}')
    return None

def calculate_indicators(df):
    df['ema_short'] = df['close'].ewm(span=CONFIG['ema_short_period'], adjust=False).mean()
    df['ema_long'] = df['close'].ewm(span=CONFIG['ema_long_period'], adjust=False).mean()
    df['macd'] = df['ema_short'] - df['ema_long']
    df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    return df

def count_active_positions():
    try:
        positions = exchange.fetch_positions([CONFIG['symbol']])
        logging.info(f'Fetched positions: {positions}')
        
        # Use 'contracts' or 'positionAmt' from 'info' to determine open positions
        active_positions_count = 0
        for position in positions:
            contracts = position.get('contracts', 0)
            position_amt = float(position['info'].get('positionAmt', '0'))

            if contracts > 0 or position_amt != 0:
                active_positions_count += 1

        return active_positions_count
    except Exception as e:
        logging.error(f'Gagal mendapatkan posisi: {e}')
        return 0

def dynamic_stop_loss_take_profit(market_price, volatility):
    stop_loss_price = market_price - (market_price * (CONFIG['stop_loss_percent'] + volatility))
    take_profit_price = market_price + (market_price * (CONFIG['profit_target_percent'] - volatility))
    return stop_loss_price, take_profit_price

def place_order_with_sl_tp(side, amount, stop_loss_price, take_profit_price):
    try:
        order = exchange.create_order(symbol=CONFIG['symbol'], 
                                      type='market',
                                      side=side,
                                      amount=amount)
        if order:
            logging.info(f'Order berhasil: {order}')
            send_telegram_notification(f"Order {side.capitalize()} berhasil: {amount} {CONFIG['symbol']} at {order['price']}")
            # Set stop loss and take profit
            exchange.create_order(symbol=CONFIG['symbol'],
                                  type='stop_market',
                                  side='sell' if side == 'buy' else 'buy',
                                  amount=amount,
                                  params={'stopPx': stop_loss_price})
            # Handle take profit similarly
        return order
    except Exception as e:
        logging.error(f'Gagal membuat order dengan stop-loss dan take-profit: {e}')
        return None

def calculate_position_size(balance, market_price):
    risk_amount = balance['USDT']['total'] * CONFIG['risk_percentage'] / 100
    return risk_amount / market_price

def main():
    balance = exchange.fetch_balance()
    if balance['USDT']['free'] < 100:
        logging.error('Saldo yang Anda miliki tidak cukup!')
        return

    if count_active_positions() >= CONFIG['max_positions']:
        logging.info(f'Maksimal {CONFIG["max_positions"]} posisi telah terbuka, menunggu peluang berikutnya.')
        return

    ohlcv = fetch_ohlcv(CONFIG['symbol'], timeframe=CONFIG['timeframe'])
    if ohlcv is None:
        return

    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df = calculate_indicators(df)

    market_price = df['close'].iloc[-1]
    ema_short = df['ema_short'].iloc[-1]
    ema_long = df['ema_long'].iloc[-1]
    rsi = df['rsi'].iloc[-1]
    macd_line = df['macd'].iloc[-1]
    signal_line = df['signal'].iloc[-1]

    volatility = (max(df['high']) - min(df['low'])) / market_price  # Basic volatility metric

    if pd.isnull([ema_short, ema_long, rsi, macd_line, signal_line]).any():
        return

    quantity = calculate_position_size(balance, market_price)

    logging.info(f'EMA Short: {ema_short}, EMA Long: {ema_long}, RSI: {rsi}, MACD: {macd_line}, Signal: {signal_line}, Harga Pasar: {market_price}')

    stop_loss_price, take_profit_price = dynamic_stop_loss_take_profit(market_price, volatility)

    # Adjusted RSI thresholds for a less restrictive strategy
    if ema_short > ema_long and rsi < 40 and macd_line > signal_line:
        logging.info('Sinyal Beli yang kuat terdeteksi')
        place_order_with_sl_tp('buy', quantity, stop_loss_price, take_profit_price)
    elif ema_short < ema_long and rsi > 60 and macd_line < signal_line:
        logging.info('Sinyal Jual yang kuat terdeteksi')
        place_order_with_sl_tp('sell', quantity, stop_loss_price, take_profit_price)
    else:
        logging.info('Tidak ada sinyal trading yang jelas')

if __name__ == '__main__':
    while True:
        try:
            main()
            time.sleep(60)  # Menunggu 1 menit untuk mengulang
        except Exception as e:
            logging.error(f'Terjadi kesalahan: {e}')