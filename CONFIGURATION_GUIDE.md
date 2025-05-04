# Configuration Guide

Dokumen ini menjelaskan semua parameter konfigurasi utama pada trading bot. Semua konfigurasi utama terdapat dalam file `config/settings.py` dan `.env`.

---

## 1. config/settings.py

File ini berisi konfigurasi untuk pasangan trading, strategi, parameter trading umum, sistem, logging, Telegram, dan exchange.

### a. `TRADING_PAIRS` (List of Dict)
Konfigurasi spesifik untuk setiap pasangan mata uang yang akan diperdagangkan.
Contoh item:
```python
{
    "symbol": "BTCUSDT",          # Simbol pasangan trading
    "min_quantity": 0.00001,     # Jumlah minimum order
    "price_precision": 2,        # Presisi harga (jumlah desimal)
    "quantity_precision": 5,     # Presisi kuantitas (jumlah desimal)
    "max_position_qty": 0.001,   # Jumlah maksimum posisi yang boleh dibuka untuk pair ini
    "timeframes": ["1h", "4h"],  # Timeframe yang digunakan untuk analisa pair ini
}
```

### b. `STRATEGY_CONFIG` (Dict)
Parameter spesifik untuk strategi trading yang digunakan (saat ini Bollinger + Stochastic).
- **`boll_length`**: Periode Bollinger Bands.
- **`boll_std`**: Standar deviasi Bollinger Bands.
- **`ema_length`**: Periode Exponential Moving Average (EMA).
- **`stoch_length`**: Periode Stochastic RSI.
- **`stoch_smooth_k`**: Periode %K smoothing Stochastic RSI.
- **`stoch_smooth_d`**: Periode %D smoothing Stochastic RSI.
- **`stoch_oversold`**: Level oversold Stochastic RSI.
- **`stoch_overbought`**: Level overbought Stochastic RSI.

### c. `TRADING_CONFIG` (Dict)
Parameter umum terkait eksekusi trading dan manajemen risiko.
- **`max_open_trades`**: Jumlah maksimum posisi yang boleh terbuka secara bersamaan di semua pair.
- **`position_size_pct`**: Persentase dari total balance yang dialokasikan untuk setiap trade (misal: 0.05 = 5%).
- **`stop_loss_pct`**: Persentase stop loss dari harga entry (misal: 0.02 = 2%).
- **`take_profit_pct`**: Persentase take profit dari harga entry (misal: 0.03 = 3%).
- **`trailing_stop_pct`**: Persentase trailing stop loss (misal: 0.01 = 1%).
- **`trailing_stop_activation_pct`**: Persentase profit minimum sebelum trailing stop diaktifkan (misal: 0.01 = 1%).

### d. `SYSTEM_CONFIG` (Dict)
Konfigurasi terkait sistem dan koneksi.
- **`connection_timeout`**: Waktu timeout koneksi (detik).
- **`read_timeout`**: Waktu timeout membaca respons (detik).
- **`retry_count`**: Jumlah percobaan ulang jika terjadi error koneksi/request.
- **`retry_delay`**: Jeda waktu antar percobaan ulang (detik).
- **`rate_limit_buffer`**: Persentase buffer untuk rate limit API (misal: 0.8 = gunakan 80% dari limit).

### e. `LOGGING_CONFIG` (Dict)
Konfigurasi logging aplikasi.
- **`level`**: Level logging minimum (e.g., "INFO", "DEBUG").
- **`format`**: Format pesan log.
- **`date_format`**: Format tanggal dan waktu pada log.
- **`file`**: Path file log.
- **`max_bytes`**: Ukuran maksimum file log sebelum rotasi.
- **`backup_count`**: Jumlah file log backup yang disimpan.

### f. `TELEGRAM_CONFIG` (Dict)
Konfigurasi notifikasi Telegram.
- **`enabled`**: Aktifkan (`True`) atau nonaktifkan (`False`) notifikasi Telegram.
- **`bot_token`**: Token bot Telegram (diambil dari environment variable `TELEGRAM_BOT_TOKEN`).
- **`chat_id`**: ID chat Telegram tujuan (diambil dari environment variable `TELEGRAM_CHAT_ID`).
- **`notification_level`**: Level minimum log yang akan dikirim sebagai notifikasi (e.g., "INFO").

### g. `EXCHANGE_CONFIG` (Dict)
Konfigurasi spesifik untuk koneksi ke exchange.
- **`name`**: Nama exchange (e.g., "binance").
- **`api_key`**: API Key exchange (diambil dari environment variable `BINANCE_API_KEY`).
- **`api_secret`**: API Secret exchange (diambil dari environment variable `BINANCE_API_SECRET`).
- **`testnet`**: Gunakan environment testnet (`True`) atau live (`False`) (diambil dari env var `USE_TESTNET`).

---

## 2. .env File

File ini digunakan untuk menyimpan kredensial sensitif seperti API key dan token Telegram agar tidak tersimpan langsung di kode. Pastikan file `.env` ada di root project dan berisi variabel berikut:

- **`BINANCE_API_KEY`**: API key Binance Anda.
- **`BINANCE_API_SECRET`**: API secret Binance Anda.
- **`TELEGRAM_BOT_TOKEN`**: Token bot Telegram Anda.
- **`TELEGRAM_CHAT_ID`**: ID chat Telegram Anda.
- **`USE_TESTNET`**: Set ke `True` untuk menggunakan Binance Testnet, atau `False` (atau biarkan kosong) untuk live trading.

---

**Tips:**
- Jangan commit file `.env` ke repository Git. Gunakan `.gitignore`.
- Selalu sesuaikan parameter di `config/settings.py` dengan profil risiko dan modal Anda.
- Lihat `README.md` untuk gambaran umum bot dan cara menjalankannya.
