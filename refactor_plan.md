# Rencana Refactoring bot.py

Setelah mempelajari codebase, saya menemukan beberapa area untuk perbaikan. Bot sudah memiliki struktur dasar yang baik, tetapi masih ada beberapa masalah yang perlu diatasi:

## Masalah Utama

1. **File Terlalu Besar**: bot.py memiliki 624+ baris kode yang membuatnya sulit dimaintain
2. **Single Responsibility Principle**: SpotTradingBot bertanggung jawab untuk terlalu banyak hal
3. **Duplikasi Logic**: Beberapa logic trading terduplikasi antara bot dan strategy classes
4. **Error Handling**: Error handling tersebar di seluruh kode dan tidak konsisten
5. **Asynchronous Logic**: Beberapa method adalah async dan beberapa tidak, membuat flow control sulit dipahami

## Rencana Refactoring

### 1. Pisahkan Komponen

Split bot.py menjadi beberapa modul:

```
src/
  ├── exchange/
  │    ├── __init__.py
  │    ├── connector.py      # Exchange connection, API calls
  │    └── order_manager.py  # Order execution, tracking
  │
  ├── core/
  │    ├── __init__.py
  │    ├── trading_bot.py    # Core bot logic (simplified)
  │    └── position_manager.py # Position tracking, risk management
  │
  ├── strategies/            # Existing strategies folder
  │
  └── utils/                 # Existing utils folder
```

### 2. Refactor Class SpotTradingBot

```python
# src/core/trading_bot.py
class TradingBot:
    def __init__(self, config):
        self.config = config
        self.exchange = None
        self.strategy = None
        self.position_manager = None
        self.monitor = None
        
    async def initialize(self):
        # Initialize components
        self.exchange = ExchangeConnector(self.config['exchange'])
        self.strategy = self._load_strategy(self.config['strategy'])
        self.position_manager = PositionManager(self.exchange, self.config['trading'])
        self.monitor = StatusMonitor(self.config['monitor'])
        
    async def run(self):
        # Main loop (simplified)
```

### 3. Extract Exchange Logic

```python
# src/exchange/connector.py
class ExchangeConnector:
    def __init__(self, config):
        self.config = config
        self.exchange = self._initialize_exchange()
        self.rate_limiter = RateLimiter(config['rate_limit'])
    
    def _initialize_exchange(self):
        # Setup exchange connection
    
    async def fetch_ohlcv(self, symbol, timeframe, limit):
        # Fetch market data with rate limiting
    
    async def get_balance(self, asset=None):
        # Get account balance with rate limiting
```

### 4. Position Management

```python
# src/core/position_manager.py
class PositionManager:
    def __init__(self, exchange, config):
        self.exchange = exchange
        self.config = config
        self.active_trades = {}
    
    async def open_position(self, symbol, signal_data):
        # Execute buy order and track position
    
    async def close_position(self, symbol, reason):
        # Execute sell order and record trade
    
    async def check_positions(self, market_data):
        # Check all open positions for exit conditions
```

### 5. Konsistensi Error Handling

Buat utility decorator untuk error handling:

```python
# src/utils/error_handlers.py
def handle_exchange_errors(func):
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ccxt.NetworkError as e:
            # Handle network errors
        except ccxt.ExchangeError as e:
            # Handle exchange errors
        except Exception as e:
            # Handle unexpected errors
    return wrapper
```

### 6. Standardisasi Asynchronous Logic

- Jadikan semua method di ExchangeConnector asynchronous
- Gunakan async/await secara konsisten untuk I/O bound operations

### 7. Dependency Injection

- Gunakan dependency injection untuk komponen utama
- Ini membuatnya lebih mudah untuk testing dan memungkinkan komponen untuk dimock

### 8. Implementasi Logging yang Lebih Baik

- Gunakan struktured logging untuk memudahkan parsing
- Tambahkan context ke log messages (trade_id, symbol, etc.)

## Rencana Implementasi

### Fase 1: Ekstraksi Komponen
1. Buat struktur folder baru
2. Extract exchange logic ke `ExchangeConnector`
3. Extract position management ke `PositionManager`

### Fase 2: Refactoring Core Bot
1. Buat TradingBot class baru di `core/trading_bot.py`
2. Migrasi main loop dan initialization logic

### Fase 3: Meningkatkan Error Handling dan Logging
1. Implement error handling decorators
2. Standardisasi logging format dan level

### Fase 4: Testing dan Validasi
1. Uji setiap komponen secara terpisah
2. Uji integrasi antar komponen
3. Uji full system dengan testnet

## Manfaat Refactoring

1. **Maintainability**: Kode lebih mudah dipahami dan dimaintain
2. **Testability**: Komponen yang lebih kecil lebih mudah ditest
3. **Flexibility**: Lebih mudah untuk mengganti komponen (e.g., exchange, strategy)
4. **Scalability**: Mudah untuk menambahkan fitur baru tanpa mengubah logic yang ada
5. **Reliability**: Error handling yang lebih baik dan konsisten
