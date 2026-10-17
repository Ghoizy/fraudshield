from pathlib import Path

import numpy as np
import pandas as pd


project_root = Path(__file__).resolve().parent.parent

input_path = (
    project_root
    / "data"
    / "processed"
    / "transactions_history_24h.pkl"
)

output_dir = (
    project_root
    / "data"
    / "processed"
    / "history_v1"
)


# 1. Membaca data yang sudah memiliki fitur riwayat.
df = pd.read_pickle(input_path)

df["TX_DATETIME"] = pd.to_datetime(
    df["TX_DATETIME"],
    errors="raise",
)

df = df.sort_values(
    ["TX_DATETIME", "TRANSACTION_ID"]
).reset_index(drop=True)


# 2. Membuat fitur dasar dari waktu transaksi.
df["TX_HOUR"] = df["TX_DATETIME"].dt.hour

df["TX_IS_WEEKEND"] = (
    df["TX_DATETIME"].dt.dayofweek >= 5
).astype("int64")


# 3. Menentukan daftar input model secara eksplisit.
feature_columns = [
    "TX_AMOUNT",
    "TX_HOUR",
    "TX_IS_WEEKEND",
    "CUSTOMER_TX_COUNT_24H",
    "CUSTOMER_AMOUNT_MEAN_24H",
    "CUSTOMER_AMOUNT_RATIO_24H",
    "CUSTOMER_NO_HISTORY_24H",
    "CUSTOMER_ZERO_MEAN_24H",
    "TERMINAL_TX_COUNT_24H",
]

metadata_columns = [
    "TRANSACTION_ID",
    "TX_DATETIME",
    "CUSTOMER_ID",
    "TERMINAL_ID",
]


# 4. Memeriksa kelengkapan dan validitas data.
kolom_wajib = feature_columns + metadata_columns + ["TX_FRAUD"]

kolom_hilang = set(kolom_wajib) - set(df.columns)

if kolom_hilang:
    raise ValueError(
        f"Kolom belum tersedia: {sorted(kolom_hilang)}"
    )

if df[kolom_wajib].isna().any().any():
    raise ValueError("Ada nilai kosong pada kolom yang diperlukan.")

if df["TRANSACTION_ID"].duplicated().any():
    raise ValueError("Ada ID transaksi yang berulang.")

if not df["TX_FRAUD"].isin([0, 1]).all():
    raise ValueError("Label TX_FRAUD harus bernilai 0 atau 1.")

fitur_numerik = df[feature_columns].astype("float64")

if not np.isfinite(fitur_numerik.to_numpy()).all():
    raise ValueError("Ada fitur dengan nilai tidak valid atau tak hingga.")


# 5. Memastikan data berada dalam periode eksperimen.
dalam_april = (
    (df["TX_DATETIME"] >= pd.Timestamp("2018-04-01"))
    & (df["TX_DATETIME"] < pd.Timestamp("2018-05-01"))
)

if not dalam_april.all():
    raise ValueError("Ada transaksi di luar periode April 2018.")


# 6. Menentukan batas waktu setiap bagian.
periode = {
    "train": ("2018-04-01", "2018-04-19"),
    "validation": ("2018-04-19", "2018-04-25"),
    "test": ("2018-04-25", "2018-05-01"),
}

dataset = {}

for nama, (awal, akhir) in periode.items():
    mask = (
        (df["TX_DATETIME"] >= pd.Timestamp(awal))
        & (df["TX_DATETIME"] < pd.Timestamp(akhir))
    )

    bagian = df.loc[mask].copy()

    if bagian.empty:
        raise ValueError(f"Bagian {nama} tidak memiliki transaksi.")

    X = (
        fitur_numerik.loc[mask]
        .reset_index(drop=True)
        .copy()
    )

    y = (
        bagian["TX_FRAUD"]
        .astype("int64")
        .reset_index(drop=True)
        .copy()
    )

    metadata = (
        bagian[metadata_columns]
        .reset_index(drop=True)
        .copy()
    )

    dataset[nama] = {
        "X": X,
        "y": y,
        "metadata": metadata,
    }

    print(f"\nBAGIAN: {nama.upper()}")
    print(f"Jumlah transaksi: {len(X)}")
    print(f"Jumlah fitur: {X.shape[1]}")
    print(f"Waktu awal: {metadata['TX_DATETIME'].min()}")
    print(f"Waktu akhir: {metadata['TX_DATETIME'].max()}")


# 7. Memastikan tidak ada baris yang hilang saat pembagian.
jumlah_total = sum(
    len(bagian["X"])
    for bagian in dataset.values()
)

if jumlah_total != len(df):
    raise AssertionError(
        "Jumlah transaksi setelah pembagian tidak sesuai."
    )


# 8. Menyimpan ketiga bagian setelah pemeriksaan selesai.
output_dir.mkdir(parents=True, exist_ok=True)

for nama, bagian in dataset.items():
    lokasi_output = output_dir / f"{nama}.pkl"
    pd.to_pickle(bagian, lokasi_output)
    print(f"\nTersimpan: {lokasi_output}")

print("\nPERSIAPAN DATA SELESAI")