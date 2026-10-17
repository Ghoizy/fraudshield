import json
from pathlib import Path

import pandas as pd
import sklearn


# 1. Tentukan lokasi file dan kapasitas simulasi.
project_root = Path(__file__).resolve().parent.parent

kapasitas_per_hari = 100

lokasi_model = project_root / "models" / "logistic_baseline.pkl"
lokasi_data = project_root / "data" / "processed" / "validation.pkl"
lokasi_laporan = project_root / "reports" / "baseline_validation.json"


# 2. Baca model, data validation, dan laporan sebelumnya.
paket_model = pd.read_pickle(lokasi_model)
paket_data = pd.read_pickle(lokasi_data)

with lokasi_laporan.open("r", encoding="utf-8") as file:
    laporan_baseline = json.load(file)

model = paket_model["pipeline"]
X = paket_data["X"]
y = paket_data["y"]
metadata = paket_data["metadata"]


# 3. Pastikan data dan lingkungan sesuai.
if paket_model["sklearn_version"] != sklearn.__version__:
    raise ValueError("Versi scikit-learn berbeda dari versi model.")

if X.columns.tolist() != paket_model["feature_columns"]:
    raise ValueError("Kolom input berbeda dari kebutuhan model.")

if not X.index.equals(y.index):
    raise ValueError("Input dan target tidak sejajar.")

if not X.index.equals(metadata.index):
    raise ValueError("Input dan metadata tidak sejajar.")

if metadata["TX_DATETIME"].isna().any():
    raise ValueError("Ada waktu transaksi yang kosong.")

if y.isna().any() or set(y.unique()) != {0, 1}:
    raise ValueError("Validation harus memiliki label 0 dan 1.")


# 4. Bentuk tabel untuk analisis.
analisis = metadata.copy()
analisis["label"] = y
analisis["skor"] = model.predict_proba(X)[:, 1]
analisis["tanggal"] = analisis["TX_DATETIME"].dt.date

# Gunakan threshold yang sudah dicatat dalam laporan baseline.
daftar_threshold = [
    hasil["threshold"]
    for hasil in laporan_baseline["perbandingan_threshold_logistic"]
]

hasil_ringkasan = []
detail_harian = []


# 5. Hitung hasil setiap threshold.
for batas in daftar_threshold:
    ditandai = analisis["skor"] >= batas
    fraud = analisis["label"] == 1

    tp = int((ditandai & fraud).sum())
    fp = int((ditandai & ~fraud).sum())
    fn = int((~ditandai & fraud).sum())

    jumlah_ditandai = tp + fp
    jumlah_fraud = tp + fn

    precision = (
        tp / jumlah_ditandai
        if jumlah_ditandai > 0
        else 0.0
    )
    recall = tp / jumlah_fraud

    # Sertakan semua hari, termasuk hari tanpa peringatan.
    tabel_harian = analisis.assign(
        ditandai=ditandai.astype("int64")
    ).groupby("tanggal").agg(
        jumlah_transaksi=("TRANSACTION_ID", "size"),
        kandidat_review=("ditandai", "sum"),
    )

    melebihi_kapasitas = (
        tabel_harian["kandidat_review"] > kapasitas_per_hari
    )

    hasil_ringkasan.append({
        "threshold": float(batas),
        "precision": float(precision),
        "recall": float(recall),
        "fraud_tertangkap": tp,
        "normal_ikut_ditandai": fp,
        "fraud_lolos": fn,
        "total_review": jumlah_ditandai,
        "review_harian_tertinggi": int(
            tabel_harian["kandidat_review"].max()
        ),
        "hari_melebihi_kapasitas": int(
            melebihi_kapasitas.sum()
        ),
    })

    # Simpan rincian agar setiap hari bisa ditelusuri.
    for tanggal, baris in tabel_harian.iterrows():
        detail_harian.append({
            "threshold": float(batas),
            "tanggal": str(tanggal),
            "jumlah_transaksi": int(baris["jumlah_transaksi"]),
            "kandidat_review": int(baris["kandidat_review"]),
            "melebihi_kapasitas": bool(
                baris["kandidat_review"] > kapasitas_per_hari
            ),
        })


# 6. Tampilkan tabel ringkas.
ringkasan = pd.DataFrame(hasil_ringkasan)

print("\nSIMULASI BEBAN PEMERIKSAAN")
print(f"Kapasitas simulasi: {kapasitas_per_hari} transaksi per hari")
print(f"Jumlah hari validation: {analisis['tanggal'].nunique()}")
print(f"Jumlah fraud validation: {int(y.sum())}")

print()
print(ringkasan.round(4).to_string(index=False))


# 7. Simpan hasil analisis.
reports_dir = project_root / "reports"
reports_dir.mkdir(parents=True, exist_ok=True)

laporan = {
    "evaluation_data": "validation",
    "kapasitas_per_hari": kapasitas_per_hari,
    "jumlah_hari": int(analisis["tanggal"].nunique()),
    "ringkasan_threshold": hasil_ringkasan,
    "detail_harian": detail_harian,
}

lokasi_output = reports_dir / "review_workload_validation.json"

with lokasi_output.open("w", encoding="utf-8") as file:
    json.dump(laporan, file, indent=2, allow_nan=False)

print(f"\nLaporan tersimpan: {lokasi_output}")