# Testing Guide

Panduan menjalankan dan menambah test pada trading bot.

---

## 1. Menjalankan Test
- Pastikan semua dependency sudah terinstall (`pip install -r requirements.txt`).
- Jalankan semua test dengan:
  ```bash
  pytest
  ```
- Untuk test async:
  ```bash
  pytest --asyncio-mode=auto
  ```

## 2. Struktur Test
- Semua test ada di folder `tests/`.
- Test unit per modul: `tests/unit/`
- Test integrasi (jika ada): `tests/integration/`
- Mocking dependency: gunakan `pytest-mock` atau `unittest.mock`.

## 3. Menambah Test Baru
- Tambahkan file/fungsi test baru di folder sesuai modul yang di-test.
- Gunakan nama fungsi `test_nama_fungsi`.
- Sertakan minimal 1 test untuk setiap fitur/bugfix baru.

## 4. Coverage
- Untuk cek coverage:
  ```bash
  pytest --cov=src
  ```

## 5. Best Practice
- Test harus idempotent (bisa diulang tanpa efek samping).
- Hindari test yang tergantung API live/external (mock sebisa mungkin).
- Review hasil test sebelum merge PR.
