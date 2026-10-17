import json
from pathlib import Path

import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_score,
    recall_score,
)
from sklearn.tree import DecisionTreeClassifier

from features import FEATURE_COLUMNS


# ============================================================
# 1. LOKASI FILE DAN PENGATURAN EKSPERIMEN
# ============================================================

project_root = Path(__file__).resolve().parent.parent
processed_dir = project_root / "data" / "processed"
models_dir = project_root / "models"
reports_dir = project_root / "reports"

kapasitas_per_hari = 100
daftar_threshold = [0.50, 0.20, 0.10, 0.05, 0.02, 0.01, 0.005]

parameter_tree = {
    "max_depth": 5,
    "min_samples_leaf": 50,
    "random_state": 42,
}


# ============================================================
# 2. BACA DATA DAN KONFIGURASI BASELINE
# ============================================================

paket_train = pd.read_pickle(processed_dir / "train.pkl")
paket_validation = pd.read_pickle(processed_dir / "validation.pkl")
paket_baseline = pd.read_pickle(
    models_dir / "logistic_baseline.pkl"
)

X_train = paket_train["X"]
y_train = paket_train["y"]

X_validation = paket_validation["X"]
y_validation = paket_validation["y"]
metadata_validation = paket_validation["metadata"]

if paket_baseline["sklearn_version"] != sklearn.__version__:
    raise ValueError("Versi scikit-learn berbeda dari versi baseline.")

if paket_baseline["feature_columns"] != FEATURE_COLUMNS:
    raise ValueError("Daftar fitur baseline berbeda dari fitur saat ini.")

for nama, X, y in [
    ("TRAIN", X_train, y_train),
    ("VALIDATION", X_validation, y_validation),
]:
    if X.columns.tolist() != FEATURE_COLUMNS:
        raise ValueError(f"Kolom input {nama} tidak sesuai.")

    if not X.index.equals(y.index):
        raise ValueError(f"Input dan target {nama} tidak sejajar.")

    if X.isna().any().any():
        raise ValueError(f"Ada input kosong pada {nama}.")

    if y.isna().any() or set(y.unique()) != {0, 1}:
        raise ValueError(f"{nama} harus memiliki label 0 dan 1.")

if not X_validation.index.equals(metadata_validation.index):
    raise ValueError("Metadata validation tidak sejajar dengan input.")

if metadata_validation["TX_DATETIME"].isna().any():
    raise ValueError("Ada waktu transaksi validation yang kosong.")

tanggal_validation = metadata_validation["TX_DATETIME"].dt.date


# ============================================================
# 3. SIAPKAN DUA PIPELINE DENGAN PREPROCESSING YANG SAMA
# ============================================================

# clone menyalin konfigurasi, tanpa membawa hasil pelatihan.
model_logistic = clone(paket_baseline["pipeline"])

model_tree = clone(paket_baseline["pipeline"])
model_tree.set_params(
    classifier=DecisionTreeClassifier(**parameter_tree)
)

daftar_model = {
    "LOGISTIC": model_logistic,
    "TREE": model_tree,
}

hasil_ap = []
hasil_threshold = []


# ============================================================
# 4. LATIH DAN EVALUASI MASING-MASING MODEL
# ============================================================

for nama, model in daftar_model.items():
    print(f"\nMelatih {nama}...", flush=True)

    model.fit(X_train, y_train)

    skor_train = model.predict_proba(X_train)[:, 1]
    skor_validation = model.predict_proba(X_validation)[:, 1]

    hasil_ap.append({
        "model": nama,
        "ap_train": float(
            average_precision_score(y_train, skor_train)
        ),
        "ap_validation": float(
            average_precision_score(y_validation, skor_validation)
        ),
    })

    for batas in daftar_threshold:
        prediksi = (
            skor_validation >= batas
        ).astype("int64")

        tn, fp, fn, tp = confusion_matrix(
            y_validation,
            prediksi,
            labels=[0, 1],
        ).ravel()

        review_harian = pd.DataFrame({
            "tanggal": tanggal_validation.to_numpy(),
            "ditandai": prediksi,
        }).groupby("tanggal")["ditandai"].sum()

        hasil_threshold.append({
            "model": nama,
            "threshold": batas,
            "precision": float(
                precision_score(
                    y_validation,
                    prediksi,
                    zero_division=0,
                )
            ),
            "recall": float(
                recall_score(
                    y_validation,
                    prediksi,
                    zero_division=0,
                )
            ),
            "fraud_tertangkap": int(tp),
            "normal_ikut_ditandai": int(fp),
            "fraud_lolos": int(fn),
            "total_review": int(prediksi.sum()),
            "review_harian_tertinggi": int(review_harian.max()),
            "hari_melebihi_kapasitas": int(
                (review_harian > kapasitas_per_hari).sum()
            ),
        })


# ============================================================
# 5. TAMPILKAN PERBANDINGAN
# ============================================================

tabel_ap = pd.DataFrame(hasil_ap)
tabel_threshold = pd.DataFrame(hasil_threshold)

print("\nPERBANDINGAN AVERAGE PRECISION")
print(tabel_ap.round(4).to_string(index=False))

print("\nPERBANDINGAN THRESHOLD PADA VALIDATION")
print(tabel_threshold.round(4).to_string(index=False))

print("\nKANDIDAT YANG MEMENUHI KAPASITAS VALIDATION")

kandidat = tabel_threshold[
    tabel_threshold["hari_melebihi_kapasitas"] == 0
].sort_values(
    ["recall", "normal_ikut_ditandai", "model", "threshold"],
    ascending=[False, True, True, False],
)

if kandidat.empty:
    print("Tidak ada kandidat yang memenuhi kapasitas.")
else:
    print(kandidat.round(4).to_string(index=False))


# ============================================================
# 6. SIMPAN MODEL TREE DAN LAPORAN PERBANDINGAN
# ============================================================

models_dir.mkdir(parents=True, exist_ok=True)
reports_dir.mkdir(parents=True, exist_ok=True)

paket_tree = {
    "pipeline": model_tree,
    "feature_columns": FEATURE_COLUMNS,
    "sklearn_version": sklearn.__version__,
    "train_period": ["2018-04-01", "2018-04-18"],
    "validation_period": ["2018-04-19", "2018-04-24"],
    "model_parameters": parameter_tree,
    "decision_threshold": None,
}

lokasi_model = models_dir / "decision_tree.pkl"
pd.to_pickle(paket_tree, lokasi_model)

laporan = {
    "evaluation_data": "validation",
    "jumlah_transaksi": len(y_validation),
    "jumlah_fraud": int(y_validation.sum()),
    "fitur": FEATURE_COLUMNS,
    "sklearn_version": sklearn.__version__,
    "parameter_tree": parameter_tree,
    "kapasitas_per_hari": kapasitas_per_hari,
    "hasil_ap": hasil_ap,
    "hasil_threshold": hasil_threshold,
}

lokasi_laporan = reports_dir / "tree_comparison_validation.json"

with lokasi_laporan.open("w", encoding="utf-8") as file:
    json.dump(laporan, file, indent=2, allow_nan=False)

print(f"\nModel Tree tersimpan: {lokasi_model}")
print(f"Laporan tersimpan: {lokasi_laporan}")
print("\nEksperimen selesai.")