# Module Overview

Dokumen ini memberikan gambaran singkat setiap modul utama dalam codebase trading bot.

---

## bot.py
- Entry point utama. Menginisialisasi bot, memuat konfigurasi, menjalankan event loop.

## config/
- settings.py: Parameter utama trading (jumlah posisi, alokasi, dsb).
- strategy_config.py: Parameter strategi.

## src/core/
- trading_bot.py: Orkestrasi bot, main loop, eksekusi sinyal, monitoring.
- position_manager.py: Manajemen posisi, risk, lifecycle trade.

## src/exchange/
- connector.py: Integrasi API exchange (order, saldo, data harga).

## src/strategies/
- boll_stoch_strategy.py, spot_strategy.py: Logika sinyal trading, indikator teknikal, buy/sell decision.

## src/utils/
- status_monitor.py: Logging status bot dan trade.
- error_handlers.py: Dekorator error handling.
- structured_logger.py: Logging terstruktur.
- rate_limiter.py: Rate limit API.
- telegram_utils.py: Integrasi notifikasi Telegram.

## tests/
- Unit test dan integrasi.

---

Untuk detail lebih lanjut, lihat architecture.md dan inline docstring di masing-masing modul.
