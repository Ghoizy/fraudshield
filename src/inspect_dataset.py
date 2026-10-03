from datetime import date, timedelta
from pathlib import Path

import pandas as pd

project_root = Path(__file__).resolve().parent.parent
raw_dir = project_root / "data" / "raw"

tanggal_awal = date(2018, 4, 1)
jumlah_hari = 30
daftar_tabel = []

for urutan in range(jumlah_hari):
    tanggal = tanggal_awal + timedelta(days=urutan)
    lokasi_file = raw_dir / f"{tanggal}.pkl"

    if not lokasi_file.is_file():
        raise FileNotFoundError(f"File belum tersedia: {lokasi_file}")

    tabel_harian = pd.read_pickle(lokasi_file)
    daftar_tabel.append(tabel_harian)

    print(f"Dibaca: {tanggal} | {len(tabel_harian)} transaksi")

df = pd.concat(daftar_tabel, ignore_index=True)

print("\nRINGKASAN DATA GABUNGAN")
print(f"Jumlah file dibaca: {len(daftar_tabel)}")
print(f"Jumlah transaksi: {len(df)}")
print(f"Jumlah kolom: {df.shape[1]}")
print(f"Waktu paling awal: {df['TX_DATETIME'].min()}")
print(f"Waktu paling akhir: {df['TX_DATETIME'].max()}")

print("\nJUMLAH TRANSAKSI PER LABEL")
print(df["TX_FRAUD"].value_counts(dropna=False).sort_index())

print("\nPEMERIKSAAN DATA GABUNGAN")

print("\nJumlah nilai kosong per kolom:")
print(df.isna().sum())

jumlah_id_berulang = df["TRANSACTION_ID"].duplicated().sum()
print(f"\nJumlah kemunculan ulang ID: {jumlah_id_berulang}")

jumlah_nominal_nol = (df["TX_AMOUNT"] == 0).sum()
jumlah_nominal_negatif = (df["TX_AMOUNT"] < 0).sum()

print(f"Nominal nol, perlu dicatat: {jumlah_nominal_nol}")
print(f"Nominal negatif: {jumlah_nominal_negatif}")

waktu_berurutan = df["TX_DATETIME"].is_monotonic_increasing
print(f"Waktu sudah berurutan: {waktu_berurutan}")

print("\nDETAIL TRANSAKSI NOMINAL NOL ATAU NEGATIF")

transaksi_nominal_bermasalah = df[df["TX_AMOUNT"] <= 0]

print(transaksi_nominal_bermasalah.to_string(index=False))

print("\nPEMERIKSAAN TIPE ISI KOLOM DATA GABUNGAN")

kolom_diperiksa = [
    "CUSTOMER_ID",
    "TERMINAL_ID",
    "TX_TIME_SECONDS",
    "TX_TIME_DAYS",
]

for nama_kolom in kolom_diperiksa:
    print(f"\nKolom: {nama_kolom}")
    print(f"Tipe penyimpanan: {df[nama_kolom].dtype}")
    print("Tipe nilai di dalamnya:")
    print(df[nama_kolom].map(type).value_counts())

tipe_kolom = {
    "CUSTOMER_ID": "int64",
    "TERMINAL_ID": "int64",
    "TX_TIME_SECONDS": "int64",
    "TX_TIME_DAYS": "int64",
}

df = df.astype(tipe_kolom)

print("\nTIPE PENYIMPANAN SETELAH DIRAPIKAN")
print(df[list(tipe_kolom)].dtypes)

# Pastikan label hanya berisi 0 atau 1 sebelum dihitung.
if not df["TX_FRAUD"].isin([0, 1]).all():
    raise ValueError("TX_FRAUD harus terisi dengan nilai 0 atau 1.")

# Buat tabel sementara dengan tanggal tanpa jam.
data_harian = df.assign(
    tanggal=df["TX_DATETIME"].dt.date
)

# Kelompokkan transaksi berdasarkan tanggal.
ringkasan_harian = data_harian.groupby("tanggal").agg(
    jumlah_transaksi=("TRANSACTION_ID", "size"),
    jumlah_fraud=("TX_FRAUD", "sum"),
)

# Hitung persentase fraud pada masing-masing tanggal.
ringkasan_harian["persentase_fraud"] = (
    ringkasan_harian["jumlah_fraud"]
    / ringkasan_harian["jumlah_transaksi"]
    * 100
)

print("\nRINGKASAN TRANSAKSI PER HARI")
print(ringkasan_harian.round(4).to_string())