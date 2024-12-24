import ccxt
import os
import logging
import time
import numpy as np

# Konfigurasi Logging
logging.basicConfig(filename='trade_log.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

# Definisikan simbol dan kuantitas
symbol = 'BTC/USDT'
max_positions = 5
profit_target_percent = 0.01  # 1% target profit
stop_loss_percent = 0.02  # 2% stop loss
timeframe = '5m'  # Menggunakan 5 menit sebagai contoh

# EMA periods
ema_short_period = 13
ema_long_period = 26

def fetch_prices(symbol, limit=50, timeframe='5m'):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        close_prices = [ohlcv[i][4] for i in range(limit)]  # Ambil penutupan harga
        return close_prices
    except Exception as e:
        logging.error(f'Gagal mendapatkan data harga: {e}')
        return []

def calculate_ema(prices, period):
    if len(prices) < period:
        logging.error('Tidak cukup data untuk menghitung EMA')
        return None
    return np.mean(prices[-period:])

def calculate_rsi(data, period=14):
    if len(data) <= period:
        logging.error('Tidak cukup data untuk menghitung RSI')
        return np.zeros_like(data)

    deltas = np.diff(data)
    seed = deltas[:period + 1]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / down if down != 0 else 0
    rsi = np.zeros_like(data)
    rsi[:period] = 100. - 100. / (1. + rs)

    for i in range(period, len(data)):
        delta = deltas[i - 1] 
        upval = max(0, delta)
        downval = abs(min(0, delta))
        up = (up * (period - 1) + upval) / period
        down = (down * (period - 1) + downval) / period
        rs = up / down if down != 0 else 0
        rsi[i] = 100. - 100. / (1. + rs)

    return rsi

def calculate_macd(prices, short_period=12, long_period=26, signal_period=9):
    if len(prices) < long_period:
        logging.error('Tidak cukup data untuk menghitung MACD')
        return None, None

    short_ema = np.mean(prices[-short_period:])
    long_ema = np.mean(prices[-long_period:])
    macd_line = short_ema - long_ema
    signal_line = np.mean(prices[-signal_period:])

    return macd_line, signal_line

def count_active_positions():
    try:
        positions = exchange.fetch_positions([symbol])
        return len([p for p in positions if p['amount'] > 0])
    except Exception as e:
        logging.error(f'Gagal mendapatkan posisi: {e}')
        return 0

def place_order_with_sl_tp(side, amount, stop_loss_price, take_profit_price):
    try:
        order = exchange.create_order(symbol=symbol, 
                                      type='market',
                                      side=side,
                                      amount=amount)
        if order:
            logging.info(f'Order berhasil: {order}')
            # Set stop loss and take profit
            exchange.create_order(symbol=symbol,
                                  type='stop_market',
                                  side='sell' if side == 'buy' else 'buy',
                                  amount=amount,
                                  params={'stopPx': stop_loss_price})
            # Implementasi take profit tergantung pada logika order exchange khusus
        return order
    except Exception as e:
        logging.error(f'Gagal membuat order dengan stop-loss dan take-profit: {e}')
        return None

def calculate_position_size(balance, market_price, risk_percent):
    risk_amount = balance['USDT']['total'] * risk_percent / 100
    return risk_amount / market_price

def main():
    balance = exchange.fetch_balance()
    if balance['USDT']['free'] < 100:
        logging.error('Saldo yang Anda miliki tidak cukup!')
        return

    current_positions = count_active_positions()
    if current_positions >= max_positions:
        logging.info(f'Maksimal {max_positions} posisi telah terbuka, menunggu peluang berikutnya.')
        return

    prices = fetch_prices(symbol, timeframe=timeframe)
    if not prices:
        return

    ema_short = calculate_ema(prices, ema_short_period)
    ema_long = calculate_ema(prices, ema_long_period)
    rsi = calculate_rsi(prices, 14)[-1]
    macd_line, signal_line = calculate_macd(prices)
    market_price = prices[-1]

    if ema_short is None or ema_long is None or rsi is None or macd_line is None or signal_line is None:
        return

    quantity = calculate_position_size(balance, market_price, risk_percent=2)

    logging.info(f'EMA Short: {ema_short}, EMA Long: {ema_long}, RSI: {rsi}, MACD: {macd_line}, Signal: {signal_line}, Harga Pasar: {market_price}')

    if ema_short > ema_long and rsi < 30 and macd_line > signal_line:
        logging.info('Sinyal Beli yang kuat terdeteksi')
        stop_loss_price = market_price - (market_price * stop_loss_percent)
        take_profit_price = market_price + (market_price * profit_target_percent)
        place_order_with_sl_tp('buy', quantity, stop_loss_price, take_profit_price)
    elif ema_short < ema_long and rsi > 70 and macd_line < signal_line:
        logging.info('Sinyal Jual yang kuat terdeteksi')
        stop_loss_price = market_price + (market_price * stop_loss_percent)
        take_profit_price = market_price - (market_price * profit_target_percent)
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