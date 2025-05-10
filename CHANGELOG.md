# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
- Initial changelog created.

## [2025-05-10]
### Added
- Sistem monitoring confidence level untuk sinyal trading
- Script `confidence_check.py` untuk analisis detail confidence level
- Metode baru di `status_monitor.py` untuk menyimpan dan menampilkan confidence level
- Fitur ekstraksi confidence level dari log di `status_check.py`
- Dokumentasi tentang ekspektasi frekuensi trading di README.md

### Fixed
- Perbaikan pada `position_manager.py` untuk memeriksa saldo sebelum mencoba menjual
- Perbaikan pada `status_check.py` untuk mendukung semua pasangan trading
- Perbaikan pada mekanisme take profit untuk memastikan posisi ditutup dengan benar
- Perbaikan pada script `stop.sh` untuk deteksi proses yang lebih baik

### Changed
- Pembaruan README.md dengan informasi tentang fitur monitoring confidence level
- Pembaruan CONFIGURATION_GUIDE.md dengan parameter dan tools baru
- Peningkatan format pesan status Telegram dengan informasi confidence level

## [2025-05-04]
- Major refactor completed: modularisasi core, strategi, exchange, utils.
- Penambahan dokumentasi arsitektur dan PRD.
- Penambahan pengecekan otomatis pada strategi untuk mencegah error indikator.
- Sinkronisasi README dengan implementasi codebase.
- Penghapusan file refactor_plan.md.
