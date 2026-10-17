from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from features import buat_fitur


# Tentukan lokasi data mentah.
project_root = Path(__file__).resolve().parent.parent
raw_dir = project_root / "data" / "raw"

# Baca data 1–30 April.
tanggal_awal = date(2018, 4, 1)
daftar_tabel = []

for urutan in range(30):
    tanggal = tanggal_awal + timedelta(days=urutan)
    lokasi_file = raw_dir / f"{tanggal}.pkl"

    if not lokasi_file.is_file():
        raise FileNotFoundError(f"File belum tersedia: {lokasi_file}")

    daftar_tabel.append(pd.read_pickle(lokasi_file))

df = pd.concat(daftar_tabel, ignore_index=True)

# Rapikan tipe penyimpanan.
tipe_kolom = {
    "CUSTOMER_ID": "int64",
    "TERMINAL_ID": "int64",
    "TX_TIME_SECONDS": "int64",
    "TX_TIME_DAYS": "int64",
}

df = df.astype(tipe_kolom)

# Urutkan berdasarkan waktu, lalu ID untuk waktu yang sama.
df = df.sort_values(
    ["TX_DATETIME", "TRANSACTION_ID"]
).reset_index(drop=True)

# Tentukan batas pembagian.
awal_data = pd.Timestamp("2018-04-01")
awal_validation = pd.Timestamp("2018-04-19")
awal_test = pd.Timestamp("2018-04-25")
akhir_data = pd.Timestamp("2018-05-01")

waktu = df["TX_DATETIME"]

# Pilih transaksi untuk setiap bagian.
train = df[
    (waktu >= awal_data) & (waktu < awal_validation)
].copy()

validation = df[
    (waktu >= awal_validation) & (waktu < awal_test)
].copy()

test = df[
    (waktu >= awal_test) & (waktu < akhir_data)
].copy()

bagian_data = {
    "TRAIN": train,
    "VALIDATION": validation,
    "TEST": test,
}

# Pastikan setiap bagian memiliki data.
for nama, tabel in bagian_data.items():
    if tabel.empty:
        raise ValueError(f"Bagian {nama} kosong.")

# Pastikan seluruh baris tercakup.
total_terbagi = len(train) + len(validation) + len(test)

if total_terbagi != len(df):
    raise ValueError("Ada baris yang tidak tercakup dalam pembagian.")

# Pastikan ID transaksi unik pada dataset sumber.
if df["TRANSACTION_ID"].duplicated().any():
    raise ValueError("Ada ID transaksi yang berulang.")

# Periksa apakah ada ID yang masuk ke beberapa bagian.
id_train = set(train["TRANSACTION_ID"])
id_validation = set(validation["TRANSACTION_ID"])
id_test = set(test["TRANSACTION_ID"])

if (
    id_train & id_validation
    or id_train & id_test
    or id_validation & id_test
):
    raise ValueError("Ada transaksi yang masuk ke lebih dari satu bagian.")

# Periksa urutan waktu antarbagian.
if not (
    train["TX_DATETIME"].max()
    < validation["TX_DATETIME"].min()
    and validation["TX_DATETIME"].max()
    < test["TX_DATETIME"].min()
):
    raise ValueError("Urutan waktu antarbagian tidak sesuai.")

# Tampilkan hasil.
print("\nHASIL PEMBAGIAN DATA")

for nama, tabel in bagian_data.items():
    print(f"\n{nama}")
    print(f"Jumlah transaksi: {len(tabel)}")
    print(f"Waktu awal: {tabel['TX_DATETIME'].min()}")
    print(f"Waktu akhir: {tabel['TX_DATETIME'].max()}")

print(f"\nTotal transaksi terbagi: {total_terbagi}")
print("Pemeriksaan pembagian: LULUS")

# Siapkan folder untuk hasil pengolahan.
processed_dir = project_root / "data" / "processed"
processed_dir.mkdir(parents=True, exist_ok=True)

print("\nPEMBENTUKAN DAN PENYIMPANAN FITUR")

for nama, tabel in bagian_data.items():
    # Pisahkan input model dan jawaban acuan.
    X = buat_fitur(tabel)
    y = tabel["TX_FRAUD"].copy()

    # Simpan identitas transaksi untuk penelusuran.
    metadata = tabel[
        ["TRANSACTION_ID", "TX_DATETIME"]
    ].copy()

    # Pastikan input dan target tetap berpasangan.
    if not X.index.equals(y.index):
        raise ValueError(f"Urutan input dan target {nama} berbeda.")

    if X.isna().any().any():
        raise ValueError(f"Ada fitur kosong pada bagian {nama}.")

    if not y.isin([0, 1]).all():
        raise ValueError(f"Target {nama} harus berisi 0 atau 1.")

    # Simpan ketiga komponen dalam satu paket.
    paket_data = {
        "X": X,
        "y": y,
        "metadata": metadata,
    }

    lokasi_output = processed_dir / f"{nama.lower()}.pkl"
    pd.to_pickle(paket_data, lokasi_output)

    print(f"\n{nama}")
    print(f"Ukuran input: {X.shape}")
    print(f"Jumlah target: {len(y)}")
    print(f"Kolom input: {X.columns.tolist()}")
    print(f"Tersimpan: {lokasi_output.name}")