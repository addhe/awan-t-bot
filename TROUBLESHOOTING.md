# Troubleshooting & FAQ

Panduan mengatasi masalah umum pada trading bot.

---

## 1. Masalah Umum

### a. Error indikator (misal: 'bb_upper')
- Penyebab: Data harga kurang, indikator gagal dihitung.
- Solusi: Pastikan data cukup panjang, cek log, gunakan fallback (sudah otomatis di versi terbaru).

### b. Bot tidak eksekusi order
- Penyebab: API key salah, saldo tidak cukup, parameter salah.
- Solusi: Cek file .env, cek saldo di exchange, cek konfigurasi di settings.py.

### c. Tidak ada notifikasi Telegram
- Penyebab: Token/chat_id salah, bot belum start, Telegram down, interval update belum tercapai.
- Solusi: Cek .env, test manual kirim pesan, cek log error, atau kirim status manual (lihat bagian 3).

### d. Bot error/crash saat runtime
- Penyebab: Error di strategi, API limit, koneksi exchange.
- Solusi: Cek log, pastikan rate limiter aktif, gunakan auto-restart (misal dengan supervisor).

---

## 2. FAQ

**Q: Apakah bot bisa berjalan di VPS/Cloud?**
A: Ya, selama ada Python dan koneksi internet.

**Q: Berapa interval default untuk update status Telegram?**
A: Default adalah 5 menit (300 detik), dapat diubah di `SYSTEM_CONFIG` pada `settings.py`.

**Q: Apakah data Redis dan PostgreSQL hilang saat rebuild Docker?**
A: Tidak, data disimpan di volume Docker yang persisten dan tidak akan hilang saat rebuild.

---

## 3. Panduan Manual

### a. Memicu Pengiriman Status ke Telegram Secara Manual

Jika Anda ingin menerima update status tanpa menunggu interval default (5 menit), Anda dapat memicu pengiriman status secara manual dengan cara berikut:

#### Menggunakan Python Script

```bash
# Dari dalam container Docker
docker exec -it awan-trading-bot python -c "from src.utils.telegram_utils import send_telegram_message; from src.utils.status_monitor import BotStatusMonitor; import asyncio; asyncio.run(send_telegram_message(BotStatusMonitor().format_status_message()))"
```

#### Menggunakan status_check.py

```bash
# Dari dalam container Docker
docker exec -it awan-trading-bot python status_check.py
```

Status check script akan memperbarui harga saat ini untuk posisi aktif dan mengirimkan laporan status ke Telegram.

**Q: Bagaimana cara menambah strategi baru?**
A: Tambahkan file di `src/strategies/`, update konfigurasi, dan pastikan strategi baru di-load oleh core bot.

**Q: Apakah bot support multi-exchange?**
A: Secara desain, ya. Implementasi konektor baru di `src/exchange/`.

**Q: Bagaimana cara update bot tanpa kehilangan data trade?**
A: Backup folder status/logs sebelum update.

## 3. Memeriksa Komponen Bot

### a. Cara Memeriksa Seluruh Sistem Bot

Untuk melihat semua komponen dan sistem bot berjalan dengan lengkap:

1. **Menjalankan bot utama**:
   ```bash
   ./start.sh
   # atau
   python bot.py
   ```
   Ini akan menginisialisasi semua komponen (termasuk Redis dan PostgreSQL) dan mulai melakukan analisis pasar dan trading.

2. **Memeriksa status bot**:
   ```bash
   python status_check.py
   ```
   Menampilkan status umum bot, active trades, dan confidence levels.

3. **Memeriksa confidence levels secara detail**:
   ```bash
   python confidence_check.py
   ```
   Menampilkan confidence levels secara lebih detail untuk semua pasangan trading.

4. **Memeriksa log aktivitas bot**:
   ```bash
   tail -f logs/trading_bot.log
   ```
   Menampilkan aktivitas bot secara real-time.

### b. Memeriksa Redis dan PostgreSQL

1. **Memeriksa Redis**:
   ```bash
   redis-cli -a "$REDIS_PASSWORD"
   > KEYS *                # Melihat semua key
   > GET confidence_levels # Melihat confidence levels
   > KEYS "signal:*"       # Melihat semua sinyal
   > GET "signal:BTCUSDT"  # Melihat sinyal untuk BTCUSDT
   ```

2. **Memeriksa PostgreSQL**:
   ```bash
   psql -U "$POSTGRES_USER" -d tradingdb
   > SELECT * FROM trades LIMIT 10;        # Melihat 10 trade terakhir
   > SELECT * FROM signals LIMIT 10;       # Melihat 10 sinyal terakhir
   > SELECT * FROM market_data LIMIT 10;   # Melihat 10 data pasar terakhir
   ```

3. **Memeriksa sinkronisasi data**:
   ```bash
   python src/utils/data_sync.py
   ```
   Memicu sinkronisasi data antara Redis dan PostgreSQL secara manual.

### c. Troubleshooting Database

1. **Redis tidak terhubung**:
   - Cek status container: `docker ps | grep redis`
   - Restart container: `docker restart trading-redis`
   - Cek log Redis: `docker logs trading-redis`

2. **PostgreSQL tidak terhubung**:
   - Cek status container: `docker ps | grep postgres`
   - Restart container: `docker restart trading-postgres`
   - Cek log PostgreSQL: `docker logs trading-postgres`

3. **Data tidak tersinkronisasi**:
   - Cek log bot untuk error sinkronisasi
   - Jalankan sinkronisasi manual: `python src/utils/data_sync.py`
   - Pastikan kedua database terhubung dengan benar

### d. Troubleshooting Docker

1. **Masalah Permission pada Log File**:
   Jika Anda melihat error seperti berikut:
   ```
   ./run.sh: line XX: /app/logs/trading_bot.log: Permission denied
   ```
   Solusi:
   ```bash
   # Masuk ke server dan jalankan:
   sudo mkdir -p /path/to/awan-t-bot/logs
   sudo chmod -R 777 /path/to/awan-t-bot/logs
   
   # Atau jika menggunakan docker-compose:
   docker-compose down
   sudo mkdir -p ./logs
   sudo chmod -R 777 ./logs
   docker-compose up -d
   ```

2. **Command Not Found dalam Container**:
   Jika Anda melihat error seperti:
   ```
   ./run.sh: line XX: pgrep: command not found
   ```
   Solusi:
   ```bash
   # Modifikasi Dockerfile untuk menambahkan package yang diperlukan
   # Tambahkan baris berikut ke Dockerfile:
   RUN apt-get update && apt-get install -y procps
   
   # Kemudian rebuild container:
   docker-compose build
   docker-compose up -d
   ```

3. **Container Restart Terus-menerus**:
   - Cek logs untuk error: `docker-compose logs -f trading-bot`
   - Pastikan semua environment variables terkonfigurasi dengan benar di `.env`
   - Pastikan volume mounts memiliki permission yang benar

4. **Permission Denied pada File Status**:
   Jika Anda melihat error seperti:
   ```
   PermissionError: [Errno 13] Permission denied: 'status/confidence_levels.json'
   PermissionError: [Errno 13] Permission denied: 'status/active_trades.json'
   ```
   Solusi:
   ```bash
   # Buat direktori status jika belum ada
   mkdir -p status
   
   # Berikan permission penuh
   chmod -R 777 status
   
   # Restart container bot
   docker-compose restart trading-bot
   ```
   
   Pastikan semua direktori yang di-mount ke container memiliki permission yang benar:
   ```bash
   # Berikan permission untuk semua direktori yang digunakan bot
   chmod -R 777 logs status data
   ```

5. **Bot Tidak Berjalan di Docker**:
   Jika `status_check.py` menunjukkan bot berstatus running tetapi tidak ada proses Python yang berjalan:
   
   ```bash
   # Periksa apakah bot berjalan
   docker exec -it awan-trading-bot ps aux | grep python
   
   # Jika tidak ada hasil, periksa log untuk error
   docker exec -it awan-trading-bot tail -n 100 /app/logs/trading_bot.log
   ```
   
   Jika Anda melihat error seperti `pgrep: command not found`:
   ```bash
   # Tambahkan baris ini ke Dockerfile
   RUN apt-get update && apt-get install -y procps
   
   # Rebuild dan restart container
   docker-compose build
   docker-compose up -d
   ```
   
   Jika bot terus crash dan restart:
   ```bash
   # Periksa log untuk error spesifik
   docker exec -it awan-trading-bot tail -n 200 /app/logs/trading_bot.log
   
   # Reset restart counter dengan restart container
   docker-compose restart trading-bot
   ```

6. **ImportError untuk Redis atau PostgreSQL**:
   Jika Anda melihat error seperti:
   ```
   ImportError: cannot import name 'REDIS_CONFIG' from 'config.settings'
   ImportError: cannot import name 'POSTGRES_CONFIG' from 'config.settings'
   ```
   
   Ini berarti konfigurasi Redis atau PostgreSQL belum ditambahkan ke file `config/settings.py`. Solusi:
   
   ```bash
   # Edit file settings.py dan tambahkan konfigurasi Redis dan PostgreSQL
   nano config/settings.py
   ```
   
   Tambahkan kode berikut sebelum CONFIG dictionary:
   
   ```python
   # Redis configuration
   REDIS_CONFIG = {
       "host": os.getenv("REDIS_HOST", "trading-redis"),  # Nama container Redis di docker-compose
       "port": int(os.getenv("REDIS_PORT", "6379")),
       "password": os.getenv("REDIS_PASSWORD", ""),
       "db": int(os.getenv("REDIS_DB", "0")),
       "decode_responses": True,
       "socket_timeout": 5,
       "socket_connect_timeout": 5,
       "retry_on_timeout": True,
       "health_check_interval": 30,
   }
   
   # PostgreSQL configuration
   POSTGRES_CONFIG = {
       "host": os.getenv("POSTGRES_HOST", "trading-postgres"),  # Nama container PostgreSQL di docker-compose
       "port": int(os.getenv("POSTGRES_PORT", "5432")),
       "user": os.getenv("POSTGRES_USER", "postgres"),
       "password": os.getenv("POSTGRES_PASSWORD", ""),
       "database": os.getenv("POSTGRES_DB", "tradingdb"),
       "sslmode": os.getenv("POSTGRES_SSLMODE", "disable"),
       "application_name": "awan-trading-bot",
       "connect_timeout": 10,
   }
   ```
   
   Dan perbarui CONFIG dictionary:
   
   ```python
   CONFIG = {
       # ... konfigurasi lainnya ...
       "redis": REDIS_CONFIG,
       "postgres": POSTGRES_CONFIG,
   }
   ```
   
   Kemudian restart container bot:
   ```bash
   docker-compose restart trading-bot
   ```

7. **Koneksi Redis atau PostgreSQL Gagal**:
   Jika Anda melihat error seperti:
   ```
   Failed to connect to Redis: Error -3 connecting to redis:6379. Temporary failure in name resolution.
   ```
   
   Ini berarti bot tidak dapat terhubung ke container Redis atau PostgreSQL. Solusi:
   
   ```bash
   # Pastikan host di settings.py menggunakan nama container yang benar
   nano config/settings.py
   ```
   
   Ubah konfigurasi host:
   ```python
   # Redis configuration
   REDIS_CONFIG = {
       "host": os.getenv("REDIS_HOST", "trading-redis"),  # Nama container Redis di docker-compose
       # ...
   }
   
   # PostgreSQL configuration
   POSTGRES_CONFIG = {
       "host": os.getenv("POSTGRES_HOST", "trading-postgres"),  # Nama container PostgreSQL di docker-compose
       # ...
   }
   ```
   
   Kemudian copy file ke container dan restart:
   ```bash
   docker cp config/settings.py awan-trading-bot:/app/config/settings.py
   docker-compose restart trading-bot
   ```

8. **Module Not Found Error**:
   Jika Anda melihat error seperti:
   ```
   ModuleNotFoundError: No module named 'psycopg2'
   ModuleNotFoundError: No module named 'redis'
   ```
   
   Ini berarti dependensi yang diperlukan belum diinstal di container. Solusi:
   
   ```bash
   # Tambahkan dependensi ke requirements.txt
   echo "psycopg2-binary>=2.9.3" >> requirements.txt
   echo "redis>=4.3.4" >> requirements.txt
   
   # Instal dependensi di dalam container
   docker exec -it awan-trading-bot pip install psycopg2-binary redis
   
   # Atau rebuild container
   docker-compose build
   docker-compose up -d
   ```

9. **TypeError pada RedisManager atau PostgresManager**:
   Jika Anda melihat error seperti:
   ```
   TypeError: __init__() takes 1 positional argument but 2 were given
   ```
   
   Ini berarti class manager tidak menerima parameter konfigurasi. Solusi:
   
   ```python
   # Perbarui class RedisManager di src/utils/redis_manager.py
   def __init__(self, config=None):
       """Initialize Redis connection
       
       Args:
           config (dict, optional): Redis configuration dictionary. If None, use environment variables.
       """
       # Get Redis configuration from config or environment variables
       if config is None:
           # Fallback to environment variables
           redis_host = os.environ.get("REDIS_HOST", "localhost")
           # ... konfigurasi lainnya ...
       else:
           # Use provided config
           redis_host = config.get("host", "localhost")
           # ... konfigurasi lainnya ...
   ```
   
   Kemudian copy file ke container dan restart:
   ```bash
   docker cp src/utils/redis_manager.py awan-trading-bot:/app/src/utils/redis_manager.py
   docker-compose restart trading-bot
   ```

### e. Catatan Penting

Mengingat strategi trading konservatif dengan Bollinger Bands + Stochastic RSI dan parameter min_confidence 0.7 (70%), normal jika bot tidak melakukan banyak trading dalam waktu singkat. Bot ini dirancang untuk mengutamakan kualitas sinyal dibanding kuantitas trading, sehingga mungkin tidak ada aktivitas trading selama beberapa jam.

---

Jika masalah belum terpecahkan, cek log dan dokumentasi lain, atau kontak maintainer.
