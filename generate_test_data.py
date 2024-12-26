import ccxt
import certifi
import pandas as pd

# Initialize the exchange
exchange = ccxt.binance({
    'cert': certifi.where()
})

# Define parameters for data fetching
symbol = 'BTC/USDT'
timeframe = '1h'  # Example: 1-hour timeframe
limit = 1000  # Maximum limit per request, Binance's limit is 1000
since = exchange.parse8601('2023-01-01T00:00:00Z')  # Start date

# Fetch data
ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit)

# Convert the data to a DataFrame
df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

# Convert the timestamp to a readable format
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

# Save the DataFrame to a CSV file
df.to_csv('btc_usdt_data.csv', index=False)