from datetime import date, timedelta
from math import isclose, isfinite
from pathlib import Path

import pandas as pd

from history_features import (
    hitung_transaksi_24h,
    tambah_fitur_riwayat_24h,
    tambah_rasio_nominal_24h,
    tambah_riwayat_terminal_24h,
)


# =========================================================
# 1. MENENTUKAN LOKASI DATA
# =========================================================

project_root = Path(__file__).resolve().parent.parent

raw_dir = project_root / "data" / "raw"
output_dir = project_root / "data" / "processed"


# =========================================================
# 2. MEMBACA DATA TRANSAKSI SELAMA 30 HARI
# =========================================================

tanggal_awal = date(2018, 4, 1)
daftar_tabel = []

for urutan in range(30):
    tanggal = tanggal_awal + timedelta(days=urutan)
    lokasi_file = raw_dir / f"{tanggal}.pkl"

    if not lokasi_file.is_file():
        raise FileNotFoundError(
            f"File belum tersedia: {lokasi_file}"
        )

    tabel = pd.read_pickle(lokasi_file)
    daftar_tabel.append(tabel)


df = pd.concat(daftar_tabel, ignore_index=True)

if df.empty:
    raise ValueError("Data transaksi kosong.")

df["TX_DATETIME"] = pd.to_datetime(
    df["TX_DATETIME"],
    errors="raise",
)

df = df.sort_values(
    ["TX_DATETIME", "TRANSACTION_ID"]
).reset_index(drop=True)


# =========================================================
# 3. MEMBUAT FITUR RIWAYAT PELANGGAN
# =========================================================

print("Menghitung fitur riwayat seluruh pelanggan...")

df_history = tambah_fitur_riwayat_24h(df)

print("\nKOLOM SETELAH FITUR PELANGGAN:")
print(df_history.columns.tolist())

kolom_pelanggan = [
    "CUSTOMER_TX_COUNT_24H",
    "CUSTOMER_AMOUNT_MEAN_24H",
    "CUSTOMER_NO_HISTORY_24H",
]

kolom_hilang = [
    kolom
    for kolom in kolom_pelanggan
    if kolom not in df_history.columns
]

if kolom_hilang:
    raise ValueError(
        f"Fitur pelanggan belum lengkap: {kolom_hilang}. "
        "Periksa fungsi tambah_fitur_riwayat_24h "
        "di history_features.py."
    )


# =========================================================
# 4. MEMBUAT RASIO NOMINAL DAN RIWAYAT TERMINAL
# =========================================================

df_history = tambah_rasio_nominal_24h(df_history)
df_history = tambah_riwayat_terminal_24h(df_history)


# =========================================================
# 5. MEMERIKSA JUMLAH BARIS DAN FITUR
# =========================================================

if len(df_history) != len(df):
    raise AssertionError(
        "Jumlah baris berubah setelah pembuatan fitur."
    )

# Memastikan setiap baris masih merujuk transaksi yang sama.
if not df_history["TRANSACTION_ID"].equals(df["TRANSACTION_ID"]):
    raise AssertionError(
        "Urutan atau ID transaksi berubah."
    )

kolom_fitur_riwayat = [
    "CUSTOMER_TX_COUNT_24H",
    "CUSTOMER_AMOUNT_MEAN_24H",
    "CUSTOMER_AMOUNT_RATIO_24H",
    "CUSTOMER_NO_HISTORY_24H",
    "CUSTOMER_ZERO_MEAN_24H",
    "TERMINAL_TX_COUNT_24H",
]

for kolom in kolom_fitur_riwayat:
    if kolom not in df_history.columns:
        raise ValueError(f"Kolom belum tersedia: {kolom}")

    if df_history[kolom].isna().any():
        raise ValueError(f"Ada nilai kosong pada kolom {kolom}")

    if not df_history[kolom].map(isfinite).all():
        raise ValueError(
            f"Ada nilai tidak valid atau tak hingga pada kolom {kolom}"
        )


# =========================================================
# 6. MEMERIKSA SAMPEL 30 TRANSAKSI
# =========================================================

sampel = df_history.sample(
    n=min(30, len(df_history)),
    random_state=42,
)

for _, transaksi in sampel.iterrows():
    transaction_id = transaksi["TRANSACTION_ID"]

    waktu_sekarang = pd.Timestamp(
        transaksi["TX_DATETIME"]
    ).to_pydatetime()

    batas_awal = waktu_sekarang - timedelta(hours=24)

    # A. Memeriksa jumlah transaksi pelanggan.
    jumlah_acuan = hitung_transaksi_24h(
        data=df,
        customer_id=transaksi["CUSTOMER_ID"],
        waktu_transaksi=waktu_sekarang,
    )

    jumlah_cepat = transaksi["CUSTOMER_TX_COUNT_24H"]

    if jumlah_acuan != jumlah_cepat:
        raise AssertionError(
            f"Jumlah transaksi pelanggan berbeda pada "
            f"transaksi {transaction_id}: "
            f"acuan={jumlah_acuan}, cepat={jumlah_cepat}"
        )

    # B. Mengambil riwayat pelanggan dengan cara sederhana.
    riwayat = df.loc[
        (df["CUSTOMER_ID"] == transaksi["CUSTOMER_ID"])
        & (df["TX_DATETIME"] >= batas_awal)
        & (df["TX_DATETIME"] < waktu_sekarang)
    ]

    # C. Memeriksa rata-rata nominal sebelumnya.
    if len(riwayat) > 0:
        rata_rata_acuan = riwayat["TX_AMOUNT"].mean()
    else:
        rata_rata_acuan = 0.0

    rata_rata_cepat = transaksi["CUSTOMER_AMOUNT_MEAN_24H"]

    if not isclose(
        rata_rata_acuan,
        rata_rata_cepat,
        rel_tol=1e-9,
        abs_tol=1e-8,
    ):
        raise AssertionError(
            f"Rata-rata berbeda pada transaksi {transaction_id}: "
            f"acuan={rata_rata_acuan}, cepat={rata_rata_cepat}"
        )

    # D. Memeriksa penanda tidak ada riwayat.
    tanpa_riwayat_acuan = int(len(riwayat) == 0)

    if transaksi["CUSTOMER_NO_HISTORY_24H"] != tanpa_riwayat_acuan:
        raise AssertionError(
            f"Penanda tidak ada riwayat salah pada "
            f"transaksi {transaction_id}"
        )

    # E. Memeriksa rasio nominal.
    if rata_rata_acuan > 0:
        rasio_acuan = transaksi["TX_AMOUNT"] / rata_rata_acuan
    else:
        rasio_acuan = 0.0

    rasio_cepat = transaksi["CUSTOMER_AMOUNT_RATIO_24H"]

    if not isclose(
        rasio_acuan,
        rasio_cepat,
        rel_tol=1e-9,
        abs_tol=1e-8,
    ):
        raise AssertionError(
            f"Rasio berbeda pada transaksi {transaction_id}: "
            f"acuan={rasio_acuan}, cepat={rasio_cepat}"
        )

    # F. Memeriksa penanda ada riwayat dengan rata-rata nol.
    zero_mean_acuan = int(
        len(riwayat) > 0 and rata_rata_acuan == 0
    )

    if transaksi["CUSTOMER_ZERO_MEAN_24H"] != zero_mean_acuan:
        raise AssertionError(
            f"Penanda rata-rata nol salah pada "
            f"transaksi {transaction_id}"
        )

    # G. Memeriksa jumlah transaksi terminal.
    riwayat_terminal = df.loc[
        (df["TERMINAL_ID"] == transaksi["TERMINAL_ID"])
        & (df["TX_DATETIME"] >= batas_awal)
        & (df["TX_DATETIME"] < waktu_sekarang)
    ]

    jumlah_terminal_acuan = len(riwayat_terminal)
    jumlah_terminal_cepat = transaksi["TERMINAL_TX_COUNT_24H"]

    if jumlah_terminal_acuan != jumlah_terminal_cepat:
        raise AssertionError(
            f"Jumlah transaksi terminal berbeda pada "
            f"transaksi {transaction_id}: "
            f"acuan={jumlah_terminal_acuan}, "
            f"cepat={jumlah_terminal_cepat}"
        )


print(
    f"\nPEMERIKSAAN LULUS: "
    f"{len(sampel)} transaksi cocok."
)


# =========================================================
# 7. MENAMPILKAN RINGKASAN DAN CONTOH HASIL
# =========================================================

print("\nRINGKASAN HASIL")
print(f"Jumlah baris awal: {len(df)}")
print(f"Jumlah baris hasil: {len(df_history)}")
print(f"Jumlah fitur riwayat: {len(kolom_fitur_riwayat)}")

kolom_tampil = [
    "TRANSACTION_ID",
    "CUSTOMER_ID",
    "TERMINAL_ID",
    "TX_DATETIME",
    "TX_AMOUNT",
    "CUSTOMER_TX_COUNT_24H",
    "CUSTOMER_AMOUNT_MEAN_24H",
    "CUSTOMER_AMOUNT_RATIO_24H",
    "CUSTOMER_NO_HISTORY_24H",
    "CUSTOMER_ZERO_MEAN_24H",
    "TERMINAL_TX_COUNT_24H",
]

pelanggan_contoh = (
    df_history["CUSTOMER_ID"].value_counts().idxmax()
)

contoh = df_history.loc[
    df_history["CUSTOMER_ID"] == pelanggan_contoh,
    kolom_tampil,
].head(5)

print(f"\nCONTOH HASIL PELANGGAN {pelanggan_contoh}")
print(contoh.to_string(index=False))


# =========================================================
# 8. MENYIMPAN DATA HASIL PENGOLAHAN
# =========================================================

output_dir.mkdir(parents=True, exist_ok=True)

output_path = output_dir / "transactions_history_24h.pkl"

df_history.to_pickle(output_path)

print(f"\nData tersimpan: {output_path}")