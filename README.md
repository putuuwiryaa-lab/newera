# NewEra Backend

Backend Python untuk scraping history market, menjaga chronology data, menjalankan engine prediksi, dan menyinkronkan state production ke Google Cloud Firestore.

## Alur utama

```text
Sumber market
  -> scraper.py
  -> merge/validasi history + history_days
  -> engine.py
  -> next_prediction / last_audit
  -> Firestore collection: markets
  -> newera-web
```

Sumber scraper saat ini dibagi menjadi tiga kelompok: market standar, Sejahtera, dan Rajapaito. Nilai 4D yang sama secara berurutan tetap dianggap draw yang sah dan tidak didedup berdasarkan nilainya.

## Jadwal

Workflow `.github/workflows/scraper.yml` berjalan otomatis setiap **12 jam** (`0 */12 * * *`) dan juga mendukung `workflow_dispatch` untuk trigger manual.

Workflow correctness terpisah menjalankan compile check dan regression tests untuk branch perbaikan serta `main`.

## Firestore `markets`

Dokumen market menggunakan field utama berikut:

```json
{
  "id": "SGP | Singapore",
  "name": "SGP | Singapore",
  "history_data": "1234 5678 9012",
  "history_days": "Senin Rabu Kamis",
  "order": 1,
  "updated_at": "2026-09-11T00:00:00Z",
  "next_prediction": {
    "engine_version": "2026.09.11-v2",
    "basis_draw_count": 3,
    "basis_last_draw": "9012"
  },
  "last_audit": {}
}
```

`history_data` dan `history_days` dijaga tetap sejajar. Pada area overlap, hari valid dari source scrape terbaru diprioritaskan. Untuk source yang hanya menyediakan tanggal, weekday dihitung dari tanggal tersebut. Bila source tidak menyediakan hari valid, metadata existing dipertahankan.

## Prediction state

`next_prediction` adalah state forward production yang akan diaudit ketika draw berikutnya datang. State memiliki metadata:

- `engine_version`
- `basis_draw_count`
- `basis_last_draw`

State legacy, state dari engine versi lama, atau state yang basis history-nya tidak cocok akan direbuild tanpa membuat audit production palsu. Initial import juga diperlakukan sebagai warm-start, bukan sebagai kemenangan/kekalahan historis.

Jika history sumber dikoreksi tanpa menambah draw baru, prediction state dibangun ulang dan `last_audit` lama dihapus karena tidak lagi merepresentasikan basis data yang sama.

## History merge

Merge chronology menggunakan sequence alignment, bukan pencarian satu nilai 4D. Exact alignment diprioritaskan bila bukti overlap setara. Fuzzy alignment hanya diterima untuk koreksi kecil dengan anchor yang kuat. Jika tidak ada alignment yang cukup meyakinkan, history existing dipertahankan daripada ditimpa secara spekulatif.

## Firebase credential

GitHub Actions membaca service account dari secret:

```text
FIREBASE_SERVICE_ACCOUNT
```

Untuk lokal, `firebase-key.json` atau `serviceAccountKey.json` dapat digunakan. Tanpa credential, scraper berjalan dalam mode dry-run.

## Menjalankan lokal

```bash
pip install -r requirements.txt
python scraper.py
```

Menjalankan regression tests:

```bash
python -m py_compile engine.py scraper.py
python -m unittest discover -s tests -v
```
