from pathlib import Path

import pandas as pd

project_root = Path(__file__).resolve().parent.parent
data_path = project_root / "data" / "raw" / "2018-04-01.pkl"

df = pd.read_pickle(data_path)

# Simpan jawaban acuan secara terpisah
y = df["TX_FRAUD"].copy()

# Keluarkan informasi jawaban dari calon input
X = df.drop(columns=["TX_FRAUD", "TX_FRAUD_SCENARIO"]).copy()

print("KOLOM CALON INPUT:")
print(X.columns.tolist())

print("\nKOLOM TARGET:")
print(y.name)

print("LIMA TRANSAKSI PERTAMA")
print(df.head().to_string(index=False))

print("\nUKURAN DATA")
print(f"Jumlah baris: {df.shape[0]}")
print(f"Jumlah kolom: {df.shape[1]}")

print("\nTIPE DATA DAN NILAI TERISI")
df.info()

print("\nJUMLAH TRANSAKSI PER LABEL")
print(df["TX_FRAUD"].value_counts(dropna=False).sort_index())

print("\nPEMERIKSAAN ID TRANSAKSI")

jumlah_id_berulang = df["TRANSACTION_ID"].duplicated().sum()

print(f"Jumlah kemunculan ulang ID: {jumlah_id_berulang}")

print("\nPEMERIKSAAN NOMINAL TRANSAKSI")

jumlah_nominal_nol_atau_negatif = (df["TX_AMOUNT"] <= 0).sum()

print(f"Nominal nol atau negatif: {jumlah_nominal_nol_atau_negatif}")
print(f"Nominal terkecil: {df['TX_AMOUNT'].min()}")
print(f"Nominal terbesar: {df['TX_AMOUNT'].max()}")

print("\nPEMERIKSAAN WAKTU TRANSAKSI")

print(f"Waktu paling awal: {df['TX_DATETIME'].min()}")
print(f"Waktu paling akhir: {df['TX_DATETIME'].max()}")

waktu_berurutan = df["TX_DATETIME"].is_monotonic_increasing
print(f"Sudah berurutan dari awal ke akhir: {waktu_berurutan}")

print("\nPEMERIKSAAN TIPE ISI KOLOM")

kolom_diperiksa = [
    "CUSTOMER_ID",
    "TERMINAL_ID",
    "TX_TIME_SECONDS",
    "TX_TIME_DAYS",
]

for nama_kolom in kolom_diperiksa:
    print(f"\nKolom: {nama_kolom}")
    print(df[nama_kolom].map(type).value_counts())