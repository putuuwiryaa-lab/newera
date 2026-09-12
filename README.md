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

## Engine parity dan health

Python tetap sumber prediksi production. `engine.py` hanya menambahkan metadata
`tier_ranked_digits`; formula dan aturan bobot tidak berubah. Fixtures deterministik
ada di `tests/fixtures/parity_histories.json`; ekspor untuk engine TypeScript:

```sh
python scripts/export_parity.py --output ../parity-python.json
pip install -r requirements-dev.txt
ruff check --select E9,F63,F7,F82 .
python -m compileall -q engine.py scraper.py production_evaluator.py production_health.py state_contract.py monitor_health.py scripts tests
python -m unittest discover -s tests -v
```

Frontend menjalankan `npm run parity -- --backend ../newera`. Audit 6 history / 22
snapshot (44 perbandingan shared-state dan independent lifecycle) menemukan divergence
pada BBFS, faktor BBFS, Paito, dan label calibration twin. AI rankings/tier, bobot AI,
dan dead digits cocok pada fixture ini. Hasil bukan klaim parity universal atau edge.
Laporan lengkap dan baseline review tersedia di repo `newera-web`,
`docs/engine-parity-health.md`. CI mengunci snapshot Python; perubahan formula harus
terlihat dalam review. Jangan memperbarui baseline hanya untuk meloloskan tes.

Setiap sync menyimpan `production_health` dengan HEALTHY / STALE / DRIFT / ERROR.
Pemeriksaan mencakup exact engine/evaluator version, basis count/last draw, prediction
state, evaluator projection, dan integritas counter prospective. Precedence:
ERROR > DRIFT > STALE > HEALTHY. Batas freshness scraper 26 jam; ini tidak membuktikan
source upstream sudah menerbitkan draw terbarunya. Frontend juga membandingkan output
TypeScript dengan Python pada history dan bobot tersimpan yang sama.

```sh
# Read-only REST audit; tidak memerlukan service account
python monitor_health.py --report health-report.json
# Khusus workflow/operasi dengan Firebase credential: tulis field health saja
python monitor_health.py --write --fail-on-error --report health-report.json
```

Workflow scraper menjalankan monitoring setelah sync dan mengunggah artifact health.
Concurrent scraper runs diserialkan. Scrape/sync error disimpan sebagai ERROR bila
Firestore dapat diakses; stale-check di web tetap bekerja jika proses tidak berjalan.

Evaluator legacy dengan **nol** live draw boleh dimigrasi ke bucket live-only kosong
tanpa mengubah metrik replay. Live positif tanpa bucket adalah ERROR. Batch draw
terlewat tidak dipalsukan sebagai prospective: counter sebelumnya dipertahankan dan
`unscored_draws` bertambah. History correction mempertahankan evaluator dan memasang
`evaluation_blocked_reason`; web menahan evidence tersebut sampai recovery diaudit.
State rusak/versi tak cocok tidak otomatis ditimpa replay baru. Simpan state asli dan
tentukan validitas observasi sebelum recovery; jangan sekadar menghapus quarantine.

Urutan rollout yang disarankan: backend, lalu frontend. State v2 lama tetap kompatibel;
migrasi bucket nol-live berjalan pada sync berikutnya. Minimum prospective 30 draw
dan aturan evidence Wilson 95% CI tetap berlaku.
