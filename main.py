import ccxt
import os
import logging
import time
import numpy as np

# Konfigurasi logging
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
default_quantity = 0.01

# EMA periods
ema_short_period = 13
ema_long_period = 26

def fetch_prices(symbol, limit=30):
    # Mendapatkan data OHLC untuk hitung EMA
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1m', limit=limit)
        close_prices = [ohlcv[i][4] for i in range(limit)]  # Mendapatkan harga penutupan
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
    if len(data) < period + 1:
        logging.error('Tidak cukup data untuk menghitung RSI')
        return [None]

    deltas = np.diff(data)
    seed = deltas[:period + 1]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / down
    rsi = np.full_like(data, 100. - 100. / (1. + rs))

    for i in range(period, len(data)):
        delta = deltas[i - 1] 

        if delta > 0:
            upval = delta
            downval = 0.
        else:
            upval = 0.
            downval = -delta

        up = (up * (period - 1) + upval) / period
        down = (down * (period - 1) + downval) / period

        rs = up / down
        rsi[i] = 100. - 100. / (1. + rs)

    return rsi

def place_order_with_stop_loss(side, amount, stop_price):
    try:
        order = exchange.create_order(symbol=symbol, 
                                      type='market',
                                      side=side,
                                      amount=amount)
        if order:
            logging.info(f'Order berhasil: {order}')
            # Memastikan jenis order stop_market didukung dan parameter benar
            exchange.create_order(symbol=symbol,
                                  type='stop_market',
                                  side='sell' if side == 'buy' else 'buy',
                                  params={'amount': amount, 'stopPx': stop_price})
        return order
    except Exception as e:
        logging.error(f'Gagal membuat order dengan stop-loss: {e}')
        return None

def calculate_position_size(balance, market_price, risk_percent):
    risk_amount = balance['USDT']['total'] * risk_percent / 100
    return risk_amount / market_price

def main():
    balance = exchange.fetch_balance()
    if balance['USDT']['free'] < 100:
        logging.error('Saldo yang Anda miliki tidak cukup!')
        return

    prices = fetch_prices(symbol, 30)
    if not prices:
        return

    ema_short = calculate_ema(prices, ema_short_period)
    ema_long = calculate_ema(prices, ema_long_period)
    rsi = calculate_rsi(prices, 14)[-1]
    market_price = prices[-1]

    if ema_short is None or ema_long is None or rsi is None:
        return

    quantity = calculate_position_size(balance, market_price, risk_percent=2)

    logging.info(f'EMA Short: {ema_short}, EMA Long: {ema_long}, RSI: {rsi}, Harga Pasar: {market_price}')

    if ema_short > ema_long and rsi < 30:
        logging.info('Sinyal Beli: EMA pendek di atas EMA panjang dan RSI rendah')
        stop_loss_price = market_price - (market_price * 0.02)
        place_order_with_stop_loss('buy', quantity, stop_loss_price)
    elif ema_short < ema_long and rsi > 70:
        logging.info('Sinyal Jual: EMA pendek di bawah EMA panjang dan RSI tinggi')
        stop_loss_price = market_price + (market_price * 0.02)
        place_order_with_stop_loss('sell', quantity, stop_loss_price)
    else:
        logging.info('Tidak ada sinyal trading yang jelas')

if __name__ == '__main__':
    while True:
        try:
            main()
            time.sleep(300)  # Menunggu 5 menit untuk mengulang
        except Exception as e:
            logging.error(f'Terjadi kesalahan: {e}')