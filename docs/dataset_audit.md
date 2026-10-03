# Pemeriksaan Dataset FraudShield

## Cakupan Data

- Sumber: dataset sintetis Fraud Detection Handbook.
- Periode: 1–30 April 2018.
- Jumlah file harian: 30.
- Jumlah transaksi: 288.062.
- Jumlah kolom: 9.
- Script pemeriksaan: src/inspect_dataset.py.

## Distribusi Label

- Transaksi berlabel normal (TX_FRAUD = 0): 286.360.
- Transaksi berlabel fraud (TX_FRAUD = 1): 1.702.
- Persentase fraud: sekitar 0,59%.

Jumlah transaksi normal jauh lebih banyak daripada transaksi fraud.
Ketidakseimbangan ini perlu diperhatikan saat memilih metrik evaluasi.

## Hasil Pemeriksaan

- Jumlah kemunculan ulang ID transaksi: 0.
- Jumlah transaksi bernominal nol: 4.
- Jumlah transaksi bernominal negatif: 0.
- Waktu transaksi sudah berurutan dari awal ke akhir.
- Waktu paling awal: 2018-04-01 00:00:31.
- Waktu paling akhir: 2018-04-30 23:58:13.

## Keputusan untuk Nominal Nol

Keempat transaksi bernominal nol dipertahankan pada tahap ini.

ID transaksi:
- 129590
- 187419
- 207512
- 238779

Nominal nol dicatat sebagai temuan tersendiri dan dibedakan
dari nominal negatif. Belum ada dasar yang cukup untuk
menghapus atau mengganti nilai pada keempat transaksi tersebut.

Keputusan mempertahankan transaksi tidak didasarkan pada label fraud.

File data mentah tidak diubah.

## Aturan Input Model

- TX_FRAUD digunakan sebagai target yang ingin diprediksi.
- TX_FRAUD tidak boleh dimasukkan sebagai fitur input.
- TX_FRAUD_SCENARIO tidak boleh dimasukkan sebagai fitur input
  karena merupakan informasi skenario dari simulator.
- Kolom lain masih merupakan calon input, bukan fitur final.

## Batasan Pemeriksaan

Pemeriksaan ini belum membuktikan bahwa seluruh aspek kualitas
data sudah benar atau bahwa data sudah siap langsung dilatih.

Data 30 hari digunakan untuk tahap awal pengembangan.
Belum ada model yang dilatih atau dievaluasi.

## Perapian Tipe dan Ringkasan Harian

Empat kolom berikut dikonversi menjadi int64 pada data gabungan:
- CUSTOMER_ID
- TERMINAL_ID
- TX_TIME_SECONDS
- TX_TIME_DAYS

CUSTOMER_ID dan TERMINAL_ID tetap diperlakukan sebagai identitas.
Besar-kecil nilai ID tidak menunjukkan tingkat risiko.

Script juga memeriksa bahwa TX_FRAUD hanya berisi 0 atau 1,
kemudian menampilkan jumlah transaksi, jumlah fraud, dan
persentase fraud untuk setiap tanggal.