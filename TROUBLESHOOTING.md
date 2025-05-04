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

---

Jika masalah belum terpecahkan, cek log dan dokumentasi lain, atau kontak maintainer.
