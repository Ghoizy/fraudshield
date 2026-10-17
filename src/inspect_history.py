from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from history_features import hitung_transaksi_24h


# 1. Menentukan lokasi folder data.
project_root = Path(__file__).resolve().parent.parent
raw_dir = project_root / "data" / "raw"


# 2. Membaca 30 file transaksi April.
tanggal_awal = date(2018, 4, 1)
daftar_tabel = []

for urutan in range(30):
    tanggal = tanggal_awal + timedelta(days=urutan)
    lokasi_file = raw_dir / f"{tanggal}.pkl"

    if not lokasi_file.is_file():
        raise FileNotFoundError(
            f"File belum tersedia: {lokasi_file}"
        )

    tabel_harian = pd.read_pickle(lokasi_file)
    daftar_tabel.append(tabel_harian)


# 3. Menggabungkan data dan mengurutkan transaksi.
df = pd.concat(daftar_tabel, ignore_index=True)

df = df.sort_values(
    ["TX_DATETIME", "TRANSACTION_ID"]
).reset_index(drop=True)


# 4. Memilih satu pelanggan sebagai contoh.
pelanggan_contoh = df["CUSTOMER_ID"].value_counts().idxmax()

transaksi_pelanggan = df.loc[
    df["CUSTOMER_ID"] == pelanggan_contoh
].copy()

print("PELANGGAN CONTOH")
print(f"Customer ID: {pelanggan_contoh}")
print(f"Jumlah transaksi: {len(transaksi_pelanggan)}")


# 5. Menghitung riwayat untuk lima transaksi pertama.
hasil_contoh = []

for _, transaksi in transaksi_pelanggan.head(5).iterrows():
    jumlah_sebelumnya = hitung_transaksi_24h(
        data=transaksi_pelanggan,
        customer_id=transaksi["CUSTOMER_ID"],
        waktu_transaksi=transaksi["TX_DATETIME"],
    )

    hasil_contoh.append({
        "TRANSACTION_ID": transaksi["TRANSACTION_ID"],
        "TX_DATETIME": transaksi["TX_DATETIME"],
        "TX_AMOUNT": transaksi["TX_AMOUNT"],
        "CUSTOMER_TX_COUNT_24H": jumlah_sebelumnya,
    })


tabel_contoh = pd.DataFrame(hasil_contoh)

print("\nCONTOH FITUR RIWAYAT 24 JAM")
print(tabel_contoh.to_string(index=False))


# 6. Menampilkan hasil perhitungan.
tabel_contoh = pd.DataFrame(hasil_contoh)

print("\nCONTOH FITUR RIWAYAT 24 JAM")
print(tabel_contoh.to_string(index=False))