# Strategi Trading Bot

Dokumen ini menjelaskan secara detail strategi trading yang digunakan oleh Awan Trading Bot, termasuk perhitungan confidence level, kondisi entry/exit, dan manajemen posisi.

## 1. Strategi Dasar: Bollinger Bands + Stochastic RSI

Awan Trading Bot menggunakan kombinasi indikator teknikal untuk mengidentifikasi peluang trading dengan pendekatan konservatif yang mengutamakan kualitas sinyal dibanding kuantitas trading.

### Indikator Utama

1. **Bollinger Bands (BB)**
   - Periode: 20 candle (default)
   - Standar Deviasi: 2 (default)
   - Fungsi: Mengukur volatilitas dan mengidentifikasi area oversold/overbought

2. **Exponential Moving Average (EMA)**
   - Periode: 50 candle (default)
   - Fungsi: Konfirmasi tren dan filter sinyal

3. **Stochastic RSI**
   - Periode: 14 candle (default)
   - Smoothing K: 3 (default)
   - Smoothing D: 3 (default)
   - Level Oversold: 20 (default)
   - Level Overbought: 80 (default)
   - Fungsi: Mengidentifikasi momentum dan reversal

### Analisis Multi-Timeframe

Bot menganalisis beberapa timeframe secara bersamaan, dengan bobot berbeda untuk setiap timeframe:

| Timeframe | Bobot | Keterangan |
|-----------|-------|------------|
| 15m       | 0.1   | Sinyal jangka pendek |
| 1h        | 0.3   | Sinyal jangka menengah |
| 4h        | 0.3   | Sinyal jangka menengah-panjang |
| 1d        | 0.3   | Sinyal jangka panjang |

Timeframe yang lebih panjang memiliki bobot lebih tinggi karena memberikan sinyal yang lebih reliable, sementara timeframe pendek membantu timing entry yang lebih presisi.

## 2. Perhitungan Confidence Level

Confidence level adalah metrik utama yang menentukan seberapa kuat sinyal trading berdasarkan kondisi-kondisi teknikal yang terpenuhi.

### Kondisi untuk Sinyal Buy

Untuk setiap timeframe, bot memeriksa 4 kondisi:

1. **is_oversold**: Stochastic RSI berada di bawah level oversold (default: 20)
2. **price_above_ema**: Harga berada di atas EMA
3. **stoch_crossover**: Stochastic %K > %D (crossover)
4. **price_below_bb_lower**: Harga berada di bawah Bollinger Band bawah

### Perhitungan Confidence untuk Buy

1. Untuk setiap timeframe, hitung berapa kondisi yang terpenuhi dari 4 kondisi di atas
2. Bagi dengan total kondisi untuk mendapatkan persentase kondisi yang terpenuhi
3. Kalikan dengan bobot timeframe
4. Jumlahkan hasil dari semua timeframe

**Contoh Perhitungan:**
- 1h: 3 dari 4 kondisi terpenuhi = 0.75 × 0.3 = 0.225
- 4h: 2 dari 4 kondisi terpenuhi = 0.5 × 0.3 = 0.15
- Total confidence = 0.225 + 0.15 = 0.375

### Kondisi untuk Sinyal Sell

Untuk menutup posisi (sell), bot memeriksa 4 kondisi:

1. **is_overbought**: Stochastic RSI berada di atas level overbought (default: 80)
2. **price_below_ema**: Harga berada di bawah EMA
3. **stoch_crossunder**: Stochastic %K < %D (crossunder)
4. **price_above_bb_upper**: Harga berada di atas Bollinger Band atas

### Perhitungan Confidence untuk Sell

Untuk sinyal sell, confidence dihitung dengan cara yang berbeda:
- Jika semua kondisi terpenuhi, confidence = min((stoch_k - 80) / 20, 1.0)
- Ini berarti confidence untuk sell hanya berdasarkan seberapa overbought Stochastic RSI (skala 80-100)

## 3. Logika Keputusan Trading

### Keputusan Buy (Membuka Posisi)

Bot akan membuka posisi beli jika:

1. Sinyal adalah "buy" (setidaknya satu timeframe memenuhi semua kondisi buy)
2. Confidence level > threshold (default: 0.5 atau nilai `min_confidence` yang dikonfigurasi)
3. Tidak ada posisi aktif untuk pasangan tersebut
4. Jumlah posisi aktif < `max_open_trades`
5. Ada saldo USDT yang cukup

**Penting:** Bot menggunakan pendekatan konservatif dengan `min_confidence` default 0.7 (70%). Ini berarti bot hanya akan trading jika minimal 70% kondisi terpenuhi di semua timeframe yang dianalisis.

### Keputusan Sell (Menutup Posisi)

Bot akan menutup posisi jika salah satu kondisi terpenuhi:

1. **Take Profit**: Harga mencapai target profit (default: 3% dari harga entry)
2. **Stop Loss**: Harga turun di bawah level stop loss (default: 2% dari harga entry)
3. **Trailing Stop**: Harga turun dari level tertinggi dengan persentase tertentu setelah mencapai aktivasi trailing stop
4. **Sinyal Teknikal**: Semua kondisi sell terpenuhi di salah satu timeframe

## 4. Manajemen Risiko

### Alokasi Modal

- Setiap trade menggunakan maksimal 5% dari total balance (`position_size_pct`)
- Maksimal 3 posisi terbuka bersamaan (`max_open_trades`)

### Stop Loss dan Take Profit

- Stop Loss: 2% dari harga entry (`stop_loss_pct`)
- Take Profit: 3% dari harga entry (`take_profit_pct`)
- Trailing Stop: 1% dari harga tertinggi setelah profit 1% (`trailing_stop_pct`, `trailing_stop_activation_pct`)

### Proteksi Drawdown

- Daily loss limit: 3% (`daily_loss_limit`)
- Drawdown protection: 5% (`drawdown_limit`)

## 5. Monitoring Confidence Level

Bot menyediakan dua cara untuk memonitor confidence level:

### 1. Status Check

```bash
./status_check.py
```

Menampilkan confidence level terkini untuk semua pasangan trading sebagai bagian dari status bot.

### 2. Confidence Check

```bash
# Basic confidence check
./confidence_check.py

# Detailed confidence check with conditions
./confidence_check.py -d

# Check confidence from last 3 hours
./confidence_check.py -t 3
```

Menampilkan confidence level secara detail, termasuk kondisi-kondisi yang terpenuhi atau tidak terpenuhi untuk setiap timeframe.

## 6. Contoh Skenario

### Skenario 1: Confidence Level Tinggi (0.75)

**Kondisi:**
- 1h: 3 dari 4 kondisi terpenuhi (is_oversold, price_above_ema, stoch_crossover)
- 4h: 3 dari 4 kondisi terpenuhi (is_oversold, price_above_ema, stoch_crossover)

**Perhitungan:**
- 1h: 3/4 = 0.75 × 0.3 = 0.225
- 4h: 3/4 = 0.75 × 0.3 = 0.225
- Total confidence = 0.225 + 0.225 = 0.45

Dengan `min_confidence` = 0.7, bot tidak akan melakukan trading meskipun confidence level cukup tinggi.

### Skenario 2: Confidence Level Sangat Tinggi (0.875)

**Kondisi:**
- 1h: 4 dari 4 kondisi terpenuhi (is_oversold, price_above_ema, stoch_crossover, price_below_bb_lower)
- 4h: 3 dari 4 kondisi terpenuhi (is_oversold, price_above_ema, stoch_crossover)

**Perhitungan:**
- 1h: 4/4 = 1.0 × 0.3 = 0.3
- 4h: 3/4 = 0.75 × 0.3 = 0.225
- Total confidence = 0.3 + 0.225 = 0.525

Dengan `min_confidence` = 0.5, bot akan melakukan trading karena confidence level > threshold.

## 7. Penyesuaian Strategi

Strategi dapat disesuaikan dengan mengubah parameter di `config/settings.py`:

```python
# Strategy Configuration
STRATEGY_CONFIG = {
    "boll_length": 20,
    "boll_std": 2,
    "ema_length": 50,
    "stoch_length": 14,
    "stoch_smooth_k": 3,
    "stoch_smooth_d": 3,
    "stoch_oversold": 20,
    "stoch_overbought": 80,
    "min_confidence": 0.7,  # Threshold confidence untuk trading
    "timeframe_weights": {  # Bobot untuk setiap timeframe
        "15m": 0.1,
        "1h": 0.3,
        "4h": 0.3,
        "1d": 0.3
    }
}
```

### Tips Penyesuaian

1. **Untuk Trading Lebih Agresif:**
   - Turunkan `min_confidence` (misal: 0.5)
   - Turunkan `stoch_oversold` (misal: 30)
   - Naikkan `stoch_overbought` (misal: 70)

2. **Untuk Trading Lebih Konservatif:**
   - Naikkan `min_confidence` (misal: 0.8)
   - Turunkan `stoch_oversold` (misal: 10)
   - Naikkan `stoch_overbought` (misal: 90)
   - Naikkan bobot timeframe yang lebih panjang

## 8. Ekspektasi Frekuensi Trading

Dengan pendekatan konservatif dan `min_confidence` default 0.7, bot mungkin tidak melakukan trading selama beberapa jam atau bahkan hari. Ini adalah perilaku yang diharapkan karena bot didesain untuk mengutamakan kualitas sinyal dibanding kuantitas trading.

Frekuensi trading dapat diperkirakan sebagai berikut:
- Dengan `min_confidence` = 0.7: ~1-3 trade per minggu per pasangan
- Dengan `min_confidence` = 0.6: ~3-5 trade per minggu per pasangan
- Dengan `min_confidence` = 0.5: ~5-10 trade per minggu per pasangan

**Catatan:** Frekuensi aktual akan bervariasi tergantung kondisi pasar. Selalu monitor performa bot dan sesuaikan parameter sesuai kebutuhan.
