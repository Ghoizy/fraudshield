# Rencana Evaluasi Awal FraudShield

## Pembagian Data

Pembagian dilakukan berdasarkan TX_DATETIME.

- Train: 1–18 April 2018.
- Validation: 19–24 April 2018.
- Test: 25–30 April 2018.

Batas tanggal ditetapkan sebelum pelatihan model.

## Aturan Penggunaan

- Model belajar dari data train.
- Pemilihan model dan batas skor menggunakan validation.
- Test digunakan setelah keputusan pengembangan ditetapkan.
- Pengolahan yang mempelajari statistik data harus dilatih
  hanya menggunakan train.
- Fitur riwayat transaksi hanya menggunakan informasi
  yang tersedia sebelum transaksi dinilai.
- TX_FRAUD dan TX_FRAUD_SCENARIO tidak menjadi fitur input.

## Batasan

Ini merupakan evaluasi awal menggunakan dataset sintetis 30 hari.

Eksperimen awal mengasumsikan label transaksi train sudah tersedia
ketika model dilatih. Keterlambatan konfirmasi fraud belum dimodelkan.

Periode April sudah digunakan untuk eksplorasi awal.
Evaluasi akhir portfolio direncanakan memakai periode tambahan
yang belum digunakan untuk mengambil keputusan pengembangan.

## Fitur Model Awal

Input model awal:
- TX_AMOUNT: nominal transaksi.
- TX_HOUR: jam transaksi, 0–23.
- TX_IS_WEEKEND: 1 untuk Sabtu/Minggu, 0 untuk hari lainnya.

Target: TX_FRAUD.

Fitur dipilih secara eksplisit agar informasi target dan skenario
simulator tidak masuk ke input model.

Ketiga fitur hanya menggunakan informasi transaksi yang sedang dinilai.
Belum ada fitur riwayat pelanggan atau terminal.

Fitur waktu mengikuti waktu yang tercatat pada dataset.
Zona waktu tidak dikonversi pada tahap ini.

## Simulasi Kapasitas Pemeriksaan Manual

Asumsi awal: tim mampu memeriksa maksimal 100 transaksi per hari.

Dalam simulasi ini, seluruh transaksi dengan skor di atas atau
sama dengan threshold dimasukkan sebagai kandidat pemeriksaan.

Setiap kandidat dihitung sebagai satu pekerjaan pemeriksaan.
Penggabungan beberapa transaksi pelanggan yang sama belum diterapkan.

Threshold dibandingkan berdasarkan:
- Jumlah fraud yang tertangkap.
- Jumlah transaksi normal yang ikut ditandai.
- Precision dan recall.
- Jumlah kandidat pemeriksaan pada hari tersibuk.
- Jumlah hari yang melebihi kapasitas.

Penilaian menggunakan data validation.
Threshold operasional final belum ditetapkan.