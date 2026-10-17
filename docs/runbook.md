# FraudShield — Panduan Operasional Lokal

## Cakupan

Panduan ini digunakan pada komputer Windows yang sudah memiliki:

- Folder project FraudShield.
- Environment Python `.venv` beserta dependency yang terpasang.
- Model dan konfigurasi di `models/frozen_v1`.
- Kode API, Risk Engine, dan penyimpanan keputusan.

Panduan instalasi dari komputer kosong belum termasuk dalam dokumen ini.

Semua perintah berikut dijalankan melalui PowerShell
dari folder utama project.

## 1. Masuk ke Folder Project

```powershell
Set-Location "$env:USERPROFILE\Projects\fraudshield"
```

Periksa interpreter Python:

```powershell
.\.venv\Scripts\python.exe --version
```

Pemanggilan langsung melalui `.venv` memastikan kita memakai
Python milik project tanpa perlu mengaktifkan environment terlebih dahulu.

## 2. Jalankan API di Terminal Pertama

```powershell
.\.venv\Scripts\python.exe -m uvicorn api:app --app-dir src --host 127.0.0.1 --port 8000
```

Tunggu sampai muncul pesan bahwa startup aplikasi selesai.

Terminal ini tetap digunakan oleh server selama API berjalan.
Gunakan terminal kedua untuk menjalankan perintah pemeriksaan.

Alamat layanan lokal:

http://127.0.0.1:8000

Dokumentasi interaktif:

http://127.0.0.1:8000/docs

## 3. Periksa API dari Terminal Kedua

Pastikan terminal kedua juga berada di folder utama project.

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
```

Hasil yang diharapkan adalah respons status layanan beserta
informasi versi model dan kebijakan.

Endpoint health tidak menjalankan transaksi.
Respons health juga tidak membuktikan seluruh fungsi penyimpanan sehat.

## 4. Lihat Keputusan yang Tersimpan

```powershell
.\.venv\Scripts\python.exe src/inspect_decisions.py
```

Perintah ini menampilkan catatan keputusan terbaru dari database.

Untuk mencari satu request tertentu:

```powershell
.\.venv\Scripts\python.exe src/inspect_decisions.py --request-id "GANTI_DENGAN_REQUEST_ID"
```

Ganti teks placeholder dengan request ID yang ingin diperiksa.

## 5. Lihat Ringkasan Monitoring

```powershell
.\.venv\Scripts\python.exe src/monitor_decisions.py
```

Informasi yang ditampilkan:

- Jumlah catatan keputusan.
- Jumlah ID transaksi unik.
- Jumlah ALLOW dan REVIEW.
- Persentase REVIEW.
- Rincian berdasarkan tanggal penyimpanan dalam UTC.

Script hanya membaca database.
Server API tidak harus aktif untuk menjalankan script ini.

Persentase REVIEW bukan persentase fraud.
Catatan keputusan juga tidak sama dengan jumlah seluruh request API.

## 6. Jalankan Pengujian Setelah Perubahan Kode

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

Periksa jumlah tes dan status akhir.

- OK: pengujian yang dijalankan lulus.
- FAILED atau ERROR: periksa rincian kegagalan.
- Ran 0 tests: belum ada pengujian yang berhasil ditemukan.

## 7. Hentikan API

Di terminal yang menjalankan Uvicorn, tekan:

Ctrl + C

Tunggu sampai proses shutdown selesai dan prompt PowerShell kembali.

## Lokasi File Penting

| Kegunaan | Lokasi |
|---|---|
| Model terpilih | models/frozen_v1/model.pkl |
| Konfigurasi pemilihan | models/frozen_v1/selection.json |
| Evaluasi test | reports/frozen_v1/test_evaluation.json |
| Pemeriksaan konsistensi | reports/frozen_v1/risk_engine_replay.json |
| Database keputusan API | data/runtime/fraudshield.db |
| Penjelasan model | docs/model_card.md |

## Masalah yang Umum

### Python tidak menemukan script

Periksa folder terminal:

```powershell
Get-Location
```

Periksa nama file:

```powershell
Get-ChildItem .\src -Name
```

Pastikan nama file pada perintah sama persis dengan file yang tersimpan.

### Port 8000 sudah digunakan

Periksa apakah server FraudShield masih berjalan di terminal lain.

Jika server tersebut masih diperlukan, gunakan server yang sudah aktif.
Jika hendak menggantinya, hentikan server lama dengan Ctrl + C terlebih dahulu.

### Database belum ditemukan

Pastikan API pernah berhasil memproses dan menyimpan keputusan.

Periksa apakah API menggunakan lokasi database yang sama dengan
script monitoring.

### Model gagal dimuat

Baca pesan error pada terminal server.
Periksa keberadaan file model, konfigurasi, dan kecocokan environment.

Jangan melatih ulang atau mengganti model hanya untuk menghilangkan
pesan error sebelum penyebabnya diketahui.

## Catatan Idempotensi

Input yang sama dengan Idempotency-Key yang sama mengembalikan
hasil tersimpan tanpa menambah catatan keputusan baru.

Input berbeda dengan Idempotency-Key yang sama menghasilkan HTTP 409.

Permintaan tanpa kunci idempotensi dapat menghasilkan catatan baru
meskipun ID transaksinya pernah digunakan.