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
- Penyebab: Token/chat_id salah, bot belum start, Telegram down.
- Solusi: Cek .env, test manual kirim pesan, cek log error.

### d. Bot error/crash saat runtime
- Penyebab: Error di strategi, API limit, koneksi exchange.
- Solusi: Cek log, pastikan rate limiter aktif, gunakan auto-restart (misal dengan supervisor).

---

## 2. FAQ

**Q: Apakah bot bisa berjalan di VPS/Cloud?**
A: Ya, selama ada Python dan koneksi internet.

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

### d. Catatan Penting

Mengingat strategi trading konservatif dengan Bollinger Bands + Stochastic RSI dan parameter min_confidence 0.7 (70%), normal jika bot tidak melakukan banyak trading dalam waktu singkat. Bot ini dirancang untuk mengutamakan kualitas sinyal dibanding kuantitas trading, sehingga mungkin tidak ada aktivitas trading selama beberapa jam.

---

Jika masalah belum terpecahkan, cek log dan dokumentasi lain, atau kontak maintainer.
