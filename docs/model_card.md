# FraudShield — Model Card

## Identitas

- Versi model: fraudshield-v1
- Kandidat terpilih: logistic_basic
- Algoritma: Logistic Regression
- Versi kebijakan: review-policy-v1
- Threshold REVIEW: 0.05

## Tujuan

Model memberikan skor risiko transaksi untuk membantu menentukan
transaksi yang perlu diperiksa manual.

Keputusan yang dihasilkan:

- ALLOW: skor risiko di bawah 0.05.
- REVIEW: skor risiko sama dengan atau di atas 0.05.

Keputusan merupakan rekomendasi sistem.
ALLOW tidak menjamin transaksi bebas fraud.
REVIEW tidak membuktikan transaksi merupakan fraud.

Versi ini tidak menjalankan pemblokiran pembayaran otomatis.

## Data dan Pembagian Waktu

Project menggunakan data transaksi sintetis April 2018.

- Training: 1–18 April 2018.
- Validation: 19–24 April 2018.
- Test: 25–30 April 2018.

Pemilihan model dan threshold menggunakan data validation.
Hasil test digunakan untuk melaporkan performa model terpilih.

Data April sudah digunakan dalam eksplorasi project.
Karena itu, hasil ini diperlakukan sebagai evaluasi internal,
bukan bukti validasi independen pada data dunia nyata.

## Input Model

Model terpilih menggunakan tiga fitur:

1. TX_AMOUNT: nominal transaksi.
2. TX_HOUR: jam transaksi, diturunkan dari TX_DATETIME.
3. TX_IS_WEEKEND: penanda akhir pekan, diturunkan dari TX_DATETIME.

TRANSACTION_ID digunakan untuk identifikasi transaksi,
bukan sebagai fitur prediksi.

TX_FRAUD adalah target saat pelatihan dan evaluasi.
TX_FRAUD_SCENARIO merupakan informasi skenario simulator.
Keduanya tidak digunakan sebagai input model.

Fitur riwayat pelanggan dan terminal telah dieksplorasi
pada kandidat lain, tetapi tidak digunakan oleh model terpilih.

## Pemilihan Model

Pemilihan mempertimbangkan recall dan beban pemeriksaan manual
pada data validation, dengan asumsi kapasitas 100 review per hari.

Pada threshold 0.05, model terpilih menghasilkan:

- Fraud tertangkap: 123.
- Transaksi normal yang masuk REVIEW: 266.
- Fraud terlewat: 336.
- Total REVIEW: 389.
- REVIEW terbanyak dalam sehari: 71.

Asumsi kapasitas ini digunakan untuk evaluasi kebijakan.
API belum menerapkan pembatasan antrean 100 review per hari.

## Hasil Evaluasi Test

| Ukuran | Hasil |
|---|---:|
| Jumlah transaksi | 57.767 |
| Jumlah fraud | 526 |
| Average precision | 0,272860 |
| Precision pada threshold 0.05 | 38,98% |
| Recall pada threshold 0.05 | 26,24% |
| True positive | 138 |
| False positive | 216 |
| False negative | 388 |
| True negative | 57.025 |
| Total REVIEW | 354 |
| REVIEW terbanyak dalam sehari | 70 |
| Hari dengan REVIEW melebihi 100 | 0 |

Model menangkap 138 dari 526 transaksi fraud.
Sebanyak 388 transaksi fraud masih mendapat keputusan ALLOW.

## Konsistensi Implementasi

Pemeriksaan terhadap 57.767 transaksi test membandingkan
hasil evaluasi batch dengan penilaian satu per satu melalui Risk Engine.

- Skor berbeda di luar toleransi: 0.
- Keputusan berbeda: 0.
- Status pemeriksaan: lulus.

Pemeriksaan ini membuktikan konsistensi hasil pada data tersebut.
Pemeriksaan ini bukan pengujian beban atau jaminan performa produksi.

## Keterbatasan

- Data bersifat sintetis dan hanya mencakup periode yang terbatas.
- Recall masih rendah: sebagian besar fraud pada test terlewat.
- Skor belum divalidasi sebagai probabilitas fraud yang terkalibrasi.
- Beban REVIEW pada data mendatang dapat berbeda.
- Model terpilih belum menggunakan pola riwayat pelanggan atau terminal.
- Monitoring keputusan belum mengukur precision dan recall produksi
  karena belum tersedia label hasil investigasi untuk transaksi API.
- Versi ini digunakan untuk demonstrasi portfolio dan pengembangan,
  belum untuk keputusan keuangan nyata.

## Lokasi Bukti

- Pemilihan model: models/frozen_v1/selection.json
- Evaluasi test: reports/frozen_v1/test_evaluation.json
- Konsistensi engine: reports/frozen_v1/risk_engine_replay.json