# Pemeriksaan Awal Sampel FraudShield

## Data yang diperiksa
- File: data/raw/2018-04-01.pkl
- Jumlah transaksi: 9.488
- Jumlah kolom: 9
- Waktu paling awal: 2018-04-01 00:00:31
- Waktu paling akhir: 2018-04-01 23:59:51

## Hasil pemeriksaan
- Semua kolom memiliki 9.488 nilai non-null menurut pandas.
- Jumlah kemunculan ulang ID transaksi: 0.
- Jumlah nominal transaksi nol atau negatif: 0.
- Nominal terkecil: 0,13.
- Nominal terbesar: 226,4.
- Waktu transaksi sudah berurutan dari awal ke akhir.
- Transaksi normal: 9.485.
- Transaksi fraud: 3.
- Persentase fraud: sekitar 0,0316%.

## Persiapan data
- CUSTOMER_ID, TERMINAL_ID, TX_TIME_SECONDS, dan TX_TIME_DAYS
  dikonversi dari object menjadi int64 saat script dijalankan.
- TX_FRAUD dipisahkan sebagai target y.
- TX_FRAUD dan TX_FRAUD_SCENARIO dikeluarkan dari calon input X.
- X belum merupakan kumpulan fitur final untuk model.
- File data mentah tidak ditimpa.

## Batasan
- Hasil ini hanya berlaku untuk sampel satu hari.
- Pemeriksaan ini belum membuktikan seluruh dataset bebas masalah.
- Tiga contoh fraud belum memadai untuk pelatihan dan evaluasi
  model yang dapat diandalkan.
- Belum ada model yang dilatih.

## Langkah berikutnya
- Memperluas data ke beberapa hari.
- Memeriksa kualitas dan distribusi label pada data gabungan.
- Menyusun pembagian data berdasarkan waktu sebelum pelatihan.