import ccxt

API_KEY_BINANCE='example_key'
API_SECRET_BINANCE='example_secret'

exchange = ccxt.binance({'apiKey':API_KEY,
                        'secret':API_SECRET,
                        'options':{'defaultType':'future'}})

exchange.set_sandbox_mode(True)

exchange.fetch_balance()

symbol = 'BTC/USDT'

quantity = 0.01

order = exchange.create_order(symbol=symbol,
                              type='market',
                              side='buy',
                              amount=quantity)

order