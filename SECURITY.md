# Security Guide

Panduan keamanan untuk penggunaan dan pengembangan trading bot.

---

## 1. API Key & Credential
- **JANGAN** commit file .env atau credential ke repository.
- Gunakan file .env untuk menyimpan API key.
- Berikan permission file .env hanya untuk user terkait (`chmod 600 .env`).

## 2. Exchange Security
- Gunakan API key dengan permission minimum (hanya trading, no withdrawal).
- Regenerasi API key secara berkala.
- Aktifkan whitelist IP jika didukung exchange.

## 3. Code Security
- Review kode sebelum merge PR.
- Hindari dependency tidak resmi/berisiko.
- Update dependency secara berkala.

## 4. Operational Security
- Jalankan bot di environment terisolasi (virtualenv/docker jika perlu).
- Backup data status/log secara rutin.
- Monitor aktivitas bot dan log untuk deteksi anomali.

## 5. Incident Response
- Jika credential bocor, segera revoke dan ganti API key.
- Laporkan potensi vulnerability ke maintainer secara privat.

---

Dengan mengikuti panduan ini, risiko keamanan dapat diminimalisir.
