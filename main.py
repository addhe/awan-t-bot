import ccxt
import os
import logging
import time

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

# Ambil saldo akun
balance = exchange.fetch_balance()

# Definisikan simbol dan quantity
symbol = 'BTC/USDT'
quantity = 0.01

# Definisikan take profit dan stop loss
take_profit = 1.005  # 0.5% dari harga beli
stop_loss = 0.995  # 0.5% dari harga beli

# Definisikan MA yang digunakan
ma_period = 50

def get_ma(ticker):
    prices = [ticker['last'] for _ in range(ma_period)]
    return sum(prices) / len(prices)

def place_order(side, amount):
    try:
        order = exchange.create_order(symbol=symbol, 
                                      type='market',
                                      side=side,
                                      amount=amount)
        return order
    except Exception as e:
        logging.error(f'Gagal menempatkan order: {e}')

def take_profit_order(order, take_profit_price):
    try:
        # Buat order jual dengan harga take profit
        take_profit_order = exchange.create_order(symbol=symbol, 
                                                  type='limit',
                                                  side='sell',
                                                  amount=order['amount'],
                                                  price=take_profit_price)
        return take_profit_order
    except Exception as e:
        logging.error(f'Gagal menempatkan order take profit: {e}')

def stop_loss_order(order, stop_loss_price):
    try:
        # Buat order jual dengan harga stop loss
        stop_loss_order = exchange.create_order(symbol=symbol, 
                                                type='stop_market',
                                                side='sell',
                                                amount=order['amount'],
                                                params={'stopPx': stop_loss_price})
        return stop_loss_order
    except Exception as e:
        logging.error(f'Gagal menempatkan order stop loss: {e}')

def main():
    # Cek saldo yang Anda miliki
    balance = exchange.fetch_balance()
    if balance['USDT']['free'] < 10000:
        logging.error('Saldo yang Anda miliki tidak cukup!')
        return

    # Ambil harga pasar
    ticker = exchange.fetch_ticker(symbol)
    market_price = ticker['last']

    # Cek apakah harga pasar sudah bergerak naik di atas MA
    ma = get_ma(ticker)
    if market_price > ma:
        # Tempatkan order beli
        order = place_order('buy', quantity)
        logging.info(f'Menempatkan order beli {symbol} dengan harga {market_price}')

        # Tempatkan order take profit dan stop loss
        take_profit_price = market_price * take_profit
        stop_loss_price = market_price * stop_loss
        take_profit_order_result = take_profit_order(order, take_profit_price)
        stop_loss_order_result = stop_loss_order(order, stop_loss_price)
        logging.info(f'Menempatkan order take profit {symbol} dengan harga {take_profit_price}')
        logging.info(f'Menempatkan order stop loss {symbol} dengan harga {stop_loss_price}')

    else:
        logging.info(f'Harga pasar {market_price} belum bergerak naik di atas MA {ma}')

if __name__ == '__main__':
    while True:
        try:
            main()
            # Tambahkan waktu tunggu untuk menghindari penggunaan sumber daya yang berlebihan
            time.sleep(5)
        except Exception as e:
            logging.error(f'Terjadi kesalahan: {e}')