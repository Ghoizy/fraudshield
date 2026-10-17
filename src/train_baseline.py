import json
from pathlib import Path

import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from features import FEATURE_COLUMNS


# ============================================================
# 1. TENTUKAN LOKASI FILE
# ============================================================

project_root = Path(__file__).resolve().parent.parent

processed_dir = project_root / "data" / "processed"
models_dir = project_root / "models"
reports_dir = project_root / "reports"


# ============================================================
# 2. BACA DATA TRAIN DAN VALIDATION
# ============================================================

paket_train = pd.read_pickle(processed_dir / "train.pkl")
paket_validation = pd.read_pickle(processed_dir / "validation.pkl")

X_train = paket_train["X"]
y_train = paket_train["y"]

X_validation = paket_validation["X"]
y_validation = paket_validation["y"]


# ============================================================
# 3. PERIKSA INPUT DAN TARGET
# ============================================================

for nama, X, y in [
    ("TRAIN", X_train, y_train),
    ("VALIDATION", X_validation, y_validation),
]:
    if X.columns.tolist() != FEATURE_COLUMNS:
        raise ValueError(f"Kolom input {nama} tidak sesuai.")

    if not X.index.equals(y.index):
        raise ValueError(f"Input dan target {nama} tidak sejajar.")

    if X.isna().any().any():
        raise ValueError(f"Ada nilai input kosong pada {nama}.")

    if y.isna().any() or set(y.unique()) != {0, 1}:
        raise ValueError(f"{nama} harus memiliki label 0 dan 1.")


# ============================================================
# 4. SIAPKAN PENGOLAHAN FITUR
# ============================================================

preprocessor = ColumnTransformer(
    transformers=[
        (
            "nominal",
            StandardScaler(),
            ["TX_AMOUNT"],
        ),
        (
            "jam",
            OneHotEncoder(
                categories=[list(range(24))],
                sparse_output=False,
                handle_unknown="error",
            ),
            ["TX_HOUR"],
        ),
        (
            "akhir_pekan",
            "passthrough",
            ["TX_IS_WEEKEND"],
        ),
    ],
    remainder="drop",
)


# ============================================================
# 5. SIAPKAN MODEL
# ============================================================

model_dummy = DummyClassifier(strategy="prior")

model_logistic = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        ("classifier", LogisticRegression(max_iter=1000)),
    ]
)


# ============================================================
# 6. LATIH MODEL MENGGUNAKAN DATA TRAIN
# ============================================================

print("Melatih model pembanding...")
model_dummy.fit(X_train, y_train)

print("Melatih Logistic Regression...")
model_logistic.fit(X_train, y_train)

print("Pelatihan selesai.")


# ============================================================
# 7. EVALUASI PADA VALIDATION DENGAN THRESHOLD AWAL
# ============================================================

threshold_awal = 0.5

daftar_model = {
    "DUMMY": model_dummy,
    "LOGISTIC REGRESSION": model_logistic,
}

ringkasan_model = {}

print("\nHASIL EVALUASI VALIDATION")
print(f"Jumlah transaksi: {len(y_validation)}")
print(f"Jumlah fraud: {int(y_validation.sum())}")
print(f"Persentase fraud: {y_validation.mean() * 100:.4f}%")
print(f"Threshold awal: {threshold_awal}")

for nama, model in daftar_model.items():
    # Ambil estimasi probabilitas untuk kelas fraud (label 1).
    skor = model.predict_proba(X_validation)[:, 1]

    # Ubah skor menjadi prediksi normal (0) atau fraud (1).
    prediksi = (skor >= threshold_awal).astype("int64")

    accuracy = accuracy_score(y_validation, prediksi)

    precision = precision_score(
        y_validation,
        prediksi,
        zero_division=0,
    )

    recall = recall_score(
        y_validation,
        prediksi,
        zero_division=0,
    )

    ap = average_precision_score(y_validation, skor)

    tn, fp, fn, tp = confusion_matrix(
        y_validation,
        prediksi,
        labels=[0, 1],
    ).ravel()

    # Simpan hasil agar bisa digunakan dalam laporan.
    ringkasan_model[nama] = {
        "threshold": threshold_awal,
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "average_precision": float(ap),
        "transaksi_ditandai": int(prediksi.sum()),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }

    print(f"\nMODEL: {nama}")
    print(f"Accuracy: {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall: {recall:.4f}")
    print(f"Average Precision: {ap:.4f}")
    print(f"Jumlah ditandai fraud: {prediksi.sum()}")
    print(f"TN: {tn} | FP: {fp} | FN: {fn} | TP: {tp}")


# ============================================================
# 8. BANDINGKAN THRESHOLD LOGISTIC REGRESSION
# ============================================================

print("\nPERBANDINGAN THRESHOLD LOGISTIC REGRESSION")

skor_logistic = model_logistic.predict_proba(X_validation)[:, 1]

daftar_threshold = [
    0.50,
    0.20,
    0.10,
    0.05,
    0.02,
    0.01,
    0.005,
]

hasil_threshold = []

for batas in daftar_threshold:
    prediksi = (skor_logistic >= batas).astype("int64")

    tn, fp, fn, tp = confusion_matrix(
        y_validation,
        prediksi,
        labels=[0, 1],
    ).ravel()

    precision = precision_score(
        y_validation,
        prediksi,
        zero_division=0,
    )

    recall = recall_score(
        y_validation,
        prediksi,
        zero_division=0,
    )

    hasil_threshold.append({
        "threshold": batas,
        "precision": float(precision),
        "recall": float(recall),
        "transaksi_ditandai": int(prediksi.sum()),
        "persentase_ditandai": float(prediksi.mean() * 100),
        "fraud_tertangkap": int(tp),
        "normal_ikut_ditandai": int(fp),
        "fraud_lolos": int(fn),
    })

tabel_threshold = pd.DataFrame(hasil_threshold)

print(tabel_threshold.round(4).to_string(index=False))


# ============================================================
# 9. SIAPKAN FOLDER PENYIMPANAN
# ============================================================

models_dir.mkdir(parents=True, exist_ok=True)
reports_dir.mkdir(parents=True, exist_ok=True)


# ============================================================
# 10. SIMPAN PIPELINE MODEL
# ============================================================

paket_model = {
    "pipeline": model_logistic,
    "feature_columns": FEATURE_COLUMNS,
    "sklearn_version": sklearn.__version__,
    "train_period": ["2018-04-01", "2018-04-18"],
    "validation_period": ["2018-04-19", "2018-04-24"],
    "decision_threshold": None,
}

lokasi_model = models_dir / "logistic_baseline.pkl"

pd.to_pickle(paket_model, lokasi_model)


# ============================================================
# 11. SIMPAN LAPORAN EVALUASI
# ============================================================

laporan = {
    "evaluation_data": "validation",
    "jumlah_transaksi": len(y_validation),
    "jumlah_fraud": int(y_validation.sum()),
    "fitur": FEATURE_COLUMNS,
    "sklearn_version": sklearn.__version__,
    "hasil_model": ringkasan_model,
    "perbandingan_threshold_logistic": hasil_threshold,
}

lokasi_laporan = reports_dir / "baseline_validation.json"

with lokasi_laporan.open("w", encoding="utf-8") as file:
    json.dump(
        laporan,
        file,
        indent=2,
        allow_nan=False,
    )

print(f"\nModel tersimpan: {lokasi_model}")
print(f"Laporan tersimpan: {lokasi_laporan}")
print("\nSeluruh proses selesai.")