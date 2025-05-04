# Product Requirement Document (PRD)
## Trading Bot

---

## 1. Purpose
Trading Bot ini bertujuan untuk mengotomasi aktivitas trading aset kripto (seperti BTC, ETH, SOL) dengan strategi teknikal, manajemen risiko, dan monitoring yang terintegrasi. Bot ini dapat dijalankan secara otomatis, memantau pasar, membuka dan menutup posisi sesuai sinyal strategi, serta memberikan notifikasi status/risiko kepada user.

---

## 2. Scope
- Mendukung trading otomatis di exchange kripto (misal: Binance, Bybit) via API.
- Mendukung beberapa strategi trading berbasis indikator teknikal (Bollinger Bands, EMA, Stochastic RSI, dll).
- Manajemen posisi dan risiko (jumlah posisi maksimum, alokasi modal per trade, stop loss, take profit).
- Monitoring status bot dan trade secara real-time.
- Logging, error handling, dan notifikasi (misal Telegram).
- Konfigurasi mudah melalui file settings.

---

## 3. User Stories
- **Sebagai trader**, saya ingin bot dapat berjalan otomatis 24/7 agar saya tidak perlu memantau market terus-menerus.
- **Sebagai trader**, saya ingin dapat mengatur parameter trading (jumlah posisi, alokasi modal, risk) sesuai preferensi.
- **Sebagai trader**, saya ingin menerima notifikasi jika terjadi error, posisi terbuka/tertutup, atau risiko tertentu.
- **Sebagai developer**, saya ingin dapat menambah strategi baru dengan mudah.
- **Sebagai developer**, saya ingin dapat menguji dan memonitor performa bot secara modular.

---

## 4. Functional Requirements
### 4.1 Trading Core
- Bot dapat berjalan terus-menerus (daemon/background process).
- Mengambil data harga secara periodik dari exchange.
- Menjalankan strategi untuk menghasilkan sinyal buy/sell.
- Mengeksekusi order (buka/tutup posisi) sesuai sinyal dan konfigurasi.
- Membatasi jumlah posisi terbuka sesuai parameter.
- Menghitung dan menerapkan alokasi modal per trade.
- Mendukung stop loss, take profit, dan trailing stop.

### 4.2 Strategy Module
- Mendukung strategi berbasis indikator teknikal (Bollinger Bands, EMA, Stochastic RSI).
- Modular: strategi baru dapat ditambahkan tanpa mengubah core bot.
- Setiap strategi dapat dikonfigurasi parameternya.

### 4.3 Risk & Position Management
- Membatasi risk per trade dan total posisi terbuka.
- Menutup posisi jika mencapai stop loss/take profit.
- Monitoring unrealized PnL dan notifikasi jika melebihi threshold risiko.

### 4.4 Monitoring & Logging
- Logging aktivitas bot (trade, error, status) ke file.
- Menyimpan status dan histori trade secara terstruktur.
- Status bot dapat dicek secara manual (misal via status_check.py).

### 4.5 Notification & Error Handling
- Notifikasi ke Telegram jika trade dieksekusi, terjadi error, atau status penting lain.
- Error handling robust: bot tidak crash jika terjadi error di strategi/exchange.

### 4.6 Configuration
- Semua parameter utama dapat diatur melalui file konfigurasi (config/settings.py, .env).
- Dukungan multi-exchange dan multi-strategy (extensible).

### 4.7 Testing
- Unit test untuk core logic, strategi, dan utilitas.

---

## 5. Non-Functional Requirements
- **Reliability:** Bot harus tetap berjalan walau ada error minor (fail-safe, auto-retry).
- **Extensibility:** Mudah menambah strategi, exchange, atau modul baru.
- **Security:** API key tidak boleh hardcoded, gunakan .env.
- **Performance:** Latensi rendah dalam eksekusi order dan pengambilan data.
- **Maintainability:** Struktur codebase modular, mudah dipahami dan dikembangkan.

---

## 6. Out of Scope
- Trading aset non-kripto.
- Interface GUI/web (CLI dan notifikasi saja).
- Backtesting (hanya live trading, kecuali ditambahkan di masa depan).

---

## 7. Success Metrics
- Bot dapat berjalan 24/7 tanpa crash.
- Semua order dan status tercatat dengan benar.
- Notifikasi berjalan sesuai event penting.
- Error handling mencegah bot berhenti mendadak.
- User dapat mengubah parameter dan menambah strategi dengan mudah.

---

## 8. Future Improvements (Nice to Have)
- Backtesting dan simulasi strategi.
- Dashboard web untuk monitoring.
- Integrasi exchange lebih banyak.
- Visualisasi performa trading.

---

Dokumen ini menjadi acuan pengembangan, pengujian, dan evaluasi codebase trading bot.
