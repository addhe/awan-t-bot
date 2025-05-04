# Coding Style Guide

Panduan ini mengatur standar penulisan kode Python di codebase trading bot ini.

---

## 1. Dasar: PEP8
- Ikuti seluruh kaidah [PEP8](https://peps.python.org/pep-0008/):
  - Penamaan, indentasi, whitespace, dsb.
  - Gunakan 4 spasi untuk indentasi.
  - Tidak menggunakan tab.

## 2. Maksimal 79 Karakter per Baris
- Setiap baris kode tidak boleh lebih dari 79 karakter.
- Untuk docstring dan komentar, maksimal 72 karakter per baris.
- Gunakan line continuation (`\`) atau pemisahan logika jika perlu.

## 3. Penamaan
- Fungsi dan variabel: snake_case
- Kelas: PascalCase
- Konstanta: UPPER_CASE

## 4. Import
- Import satu per baris.
- Urutan: standard library, third-party, internal.
- Gunakan absolute import jika memungkinkan.

## 5. Spasi & Whitespace
- Tidak ada trailing whitespace.
- 2 baris kosong antar fungsi/kelas tingkat atas.
- 1 baris kosong antar method dalam kelas.

## 6. Docstring
- Gunakan docstring pada setiap fungsi, kelas, dan modul utama.
- Format docstring: triple double-quote `"""`.
- Jelaskan argumen, return, dan behavior penting.

## 7. Komentar
- Komentar harus jelas, ringkas, dan relevan.
- Jangan gunakan komentar untuk menonaktifkan kode kecuali alasan jelas.

## 8. Linter & Formatter
- Gunakan `flake8` untuk linting dan pengecekan panjang baris.
- Gunakan `black` dengan opsi `--line-length 79` untuk auto-format.
- Pastikan kode bebas error lint sebelum PR di-merge.

## 9. Contoh
```python
class MyClass:
    """Contoh kelas dengan docstring."""

    def my_method(self, arg1: int, arg2: str) -> None:
        """Jelaskan fungsi dan argumen."""
        if arg1 > 0:
            print(arg2)
```

---

Ikuti panduan ini agar codebase tetap konsisten, mudah dibaca, dan maintainable.
