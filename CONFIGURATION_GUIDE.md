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
- **`min_confidence`**: Nilai minimum confidence level untuk melakukan trading (0.0-1.0). Default: 0.7 (70%).
- **`timeframe_weights`**: Bobot untuk setiap timeframe dalam analisis multi-timeframe. Contoh: `{"15m": 0.1, "1h": 0.3, "4h": 0.3, "1d": 0.3}`.

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
- **`redis_host`**: Host Redis server (default: "redis").
- **`redis_port`**: Port Redis server (default: 6379).
- **`redis_password`**: Password Redis server (diambil dari environment variable).
- **`redis_db`**: Nomor database Redis (default: 0).
- **`postgres_host`**: Host PostgreSQL server (default: "postgres").
- **`postgres_port`**: Port PostgreSQL server (default: 5432).
- **`postgres_user`**: Username PostgreSQL (diambil dari environment variable).
- **`postgres_password`**: Password PostgreSQL (diambil dari environment variable).
- **`postgres_db`**: Nama database PostgreSQL (default: "tradingdb").
- **`retry_delay`**: Jeda waktu antar percobaan ulang (detik).
- **`rate_limit_buffer`**: Persentase buffer untuk rate limit API (misal: 0.8 = gunakan 80% dari limit).
- **`main_loop_interval_seconds`**: The target duration (in seconds) for each main processing cycle. The bot will sleep at the end of each cycle to meet this target duration.
- **`status_update_interval_seconds`**: How frequently (in seconds) the bot logs a detailed status update (e.g., 3600 for every hour).
- **`health_check_interval_seconds`**: How frequently (in seconds) the bot checks the exchange connection and system health (e.g., 300 for every 5 minutes).

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

## 2. `.env`

File ini berisi kredensial dan API keys yang tidak boleh dimasukkan ke dalam version control.

- **`EXCHANGE_API_KEY`**: API key untuk exchange.
- **`EXCHANGE_API_SECRET`**: API secret untuk exchange.
- **`TELEGRAM_BOT_TOKEN`**: Token bot Telegram untuk notifikasi.
- **`TELEGRAM_CHAT_ID`**: ID chat Telegram untuk mengirim notifikasi.
- **`REDIS_PASSWORD`**: Password untuk Redis server.
- **`POSTGRES_USER`**: Username untuk PostgreSQL.
- **`POSTGRES_PASSWORD`**: Password untuk PostgreSQL.
- **`POSTGRES_DB`**: Nama database PostgreSQL (default: tradingdb).

## 3. Docker Configuration

Bot trading sekarang mendukung deployment menggunakan Docker dan Docker Compose.

### a. `docker-compose.yml`

File ini mengkonfigurasi tiga layanan utama:

1. **trading-bot**: Container bot trading utama
   - Build dari Dockerfile
   - Menggunakan volume untuk menyimpan log dan data
   - Terhubung ke Redis dan PostgreSQL

2. **redis**: Container Redis untuk caching
   - Menggunakan image Redis resmi
   - Menggunakan konfigurasi dari `redis.conf`
   - Data disimpan di volume `redis-data`
   - Diproteksi dengan password

3. **postgres**: Container PostgreSQL dengan TimescaleDB
   - Menggunakan image TimescaleDB
   - Data disimpan di volume `postgres-data`
   - Diinisialisasi dengan script `init-postgres.sql`
   - Diproteksi dengan username dan password

### b. `redis.conf`

Konfigurasi Redis untuk memastikan persistensi data:

- **`appendonly yes`**: Mengaktifkan Append-Only File (AOF) untuk persistensi
- **`appendfsync everysec`**: Menyinkronkan AOF setiap detik
- **`save 900 1`**: Menyimpan RDB snapshot jika minimal 1 key berubah dalam 900 detik
- **`save 300 10`**: Menyimpan RDB snapshot jika minimal 10 key berubah dalam 300 detik
- **`save 60 10000`**: Menyimpan RDB snapshot jika minimal 10000 key berubah dalam 60 detik

### c. `init-postgres.sql`

Script SQL untuk menginisialisasi database PostgreSQL:

- Membuat ekstensi TimescaleDB
- Membuat tabel untuk data OHLCV
- Membuat tabel untuk indikator
- Membuat tabel untuk trades
- Membuat tabel untuk signals
- Mengubah tabel OHLCV dan indikator menjadi hypertable TimescaleDB

---

## 3. Monitoring Tools

Bot ini dilengkapi dengan beberapa tools untuk monitoring performa dan status trading:

### a. `status_check.py`
Script untuk memeriksa status bot dan posisi aktif.
- Menampilkan balance, posisi aktif, dan performa trading
- Memperbarui harga terkini untuk posisi aktif
- Mengekstrak confidence level dari log trading
- Menampilkan confidence level untuk setiap pasangan trading

### b. `confidence_check.py`
Script khusus untuk menganalisis confidence level sinyal trading.
- **Parameter:**
  - `-t, --time`: Jumlah jam log yang dianalisis (default: 1)
  - `-d, --detailed`: Menampilkan kondisi detail untuk setiap timeframe
  - `-n, --no-update`: Tidak memperbarui file status
- **Output:**
  - Tabel confidence level untuk semua pasangan trading
  - Perbandingan dengan threshold confidence dari konfigurasi
  - Kondisi detail yang terpenuhi/tidak terpenuhi (dengan flag `-d`)

### c. Status Files
Bot menyimpan status dalam beberapa file JSON:
- **`status/bot_status.json`**: Status umum bot dan performa
- **`status/active_trades.json`**: Posisi trading yang aktif
- **`status/completed_trades.json`**: Riwayat trading yang selesai
- **`status/confidence_levels.json`**: Confidence level terbaru untuk setiap pasangan

---

**Tips:**
- Jangan commit file `.env` ke repository Git. Gunakan `.gitignore`.
- Selalu sesuaikan parameter di `config/settings.py` dengan profil risiko dan modal Anda.
- Gunakan `confidence_check.py -d` untuk memahami mengapa bot tidak melakukan trading.
- Turunkan nilai `min_confidence` jika ingin bot lebih agresif dalam trading.
- Lihat `README.md` untuk gambaran umum bot dan cara menjalankannya.
