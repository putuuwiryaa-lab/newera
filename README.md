# NewEra - Automated Market Data Scraper & Sync

Skrip scraper otomatis untuk mengumpulkan data pengeluaran angka historis dari 58 pasaran dan menyinkronkannya secara berkala ke **Google Cloud Firestore (Firebase)** menggunakan **GitHub Actions**.

---

## 🚀 Fitur Utama

- **Cakupan 58 Pasaran**: Mengambil data lengkap (Singapore, Hongkong, Sydney, Cambodia, Bullseye, dll.).
- **Kapasitas Data**: Mengambil hingga **500 data result terakhir** per pasaran.
- **Eksekusi Otomatis**: Berjalan otomatis setiap 3 jam menggunakan GitHub Actions (`cron: '0 */3 * * *'`).
- **Manual Trigger**: Dilengkapi `workflow_dispatch` sehingga scraping dapat dipicu manual kapan saja dari tab Actions GitHub.
- **Penyimpanan Firebase Firestore**: Data tersimpan terstruktur di koleksi `markets`.
- **Aman & Terisolasi**: Kredensial service account dilindungi melalui GitHub Secrets dan `.gitignore`.

---

## 📁 Struktur Dokumen Firestore (`markets`)

Setiap pasaran disimpan sebagai dokumen di koleksi `markets`:
```json
{
  "id": "SINGAPORE",
  "name": "SINGAPORE",
  "history_data": "8713 1564 3216 ... (500 angka terakhir)",
  "order": 6,
  "updated_at": "2026-09-07T17:35:00Z"
}
```

---

## ⚙️ Konfigurasi GitHub Actions

1. Buka repositori di GitHub: **Settings** > **Secrets and variables** > **Actions**.
2. Buat secret baru:
   - **Name**: `FIREBASE_SERVICE_ACCOUNT`
   - **Secret**: Tempelkan isi file JSON Private Key Service Account Firebase Anda.
3. Alur kerja akan otomatis aktif dan berjalan setiap 3 jam.

---

## 💻 Menjalankan Secara Lokal

1. Pasang dependensi:
   ```bash
   pip install -r requirements.txt
   ```
2. Pastikan file `firebase-key.json` tersedia di direktori kerja (file ini sudah diabaikan oleh `.gitignore`).
3. Jalankan scraper:
   ```bash
   python scraper.py
   ```
   *(Jika file kredensial tidak ditemukan, skrip akan otomatis beralih ke mode dry-run).*
