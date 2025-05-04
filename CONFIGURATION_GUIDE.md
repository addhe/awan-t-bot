# Configuration Guide

Dokumen ini menjelaskan semua parameter konfigurasi utama pada trading bot.

---

## 1. config/settings.py
- **max_open_trades**: Jumlah maksimum posisi terbuka bersamaan.
- **allocation_per_trade**: Persentase alokasi modal per trade (misal 0.2 = 20%).
- **min_allocation_usdt**: Minimum USDT per trade.
- **max_allocation_usdt**: Maksimum USDT per trade.
- **order_timeout**: Waktu maksimal menunggu order (detik).
- **cancel_after**: Otomatis cancel order jika belum filled setelah sekian detik.
- **max_trade_retry**: Jumlah maksimum percobaan eksekusi order.
- **TIMEFRAMES**: Timeframe yang digunakan untuk analisa.

## 2. config/strategy_config.py
- **trading_pairs**: List pair yang didukung.
- **boll_window, boll_std**: Parameter Bollinger Bands.
- **ema_window**: Window EMA.
- **stoch_window, stoch_smooth_k, stoch_smooth_d**: Parameter Stochastic RSI.
- **min_confidence, max_spread**: Filter sinyal.
- **position_size**: Persentase modal per posisi.
- **stop_loss, take_profit, trailing_stop**: Risk management.

## 3. .env
- **API_KEY_BINANCE**: API key exchange.
- **API_SECRET_BINANCE**: API secret exchange.
- **TELEGRAM_TOKEN**: Token bot Telegram.
- **TELEGRAM_CHAT_ID**: ID chat Telegram.

---

**Tips:**
- Jangan commit file .env ke repo.
- Selalu sesuaikan parameter dengan profil risiko dan modal Anda.
- Lihat README.md untuk contoh konfigurasi.
