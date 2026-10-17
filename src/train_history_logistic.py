import json
import warnings
from pathlib import Path

import pandas as pd
import sklearn

from sklearn.compose import ColumnTransformer
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


# =========================================================
# 1. LOKASI DATA DAN HASIL
# =========================================================

project_root = Path(__file__).resolve().parent.parent

data_dir = project_root / "data" / "processed" / "history_v1"
model_dir = project_root / "models" / "history_v1"
report_dir = project_root / "reports" / "history_v1"


# =========================================================
# 2. MEMBACA TRAIN DAN VALIDATION
# =========================================================

train = pd.read_pickle(data_dir / "train.pkl")
validation = pd.read_pickle(data_dir / "validation.pkl")

X_train = train["X"]
y_train = train["y"]

X_val = validation["X"]
y_val = validation["y"]

metadata_val = validation["metadata"]

for nama, bagian in [
    ("train", train),
    ("validation", validation),
]:
    if not (
        len(bagian["X"])
        == len(bagian["y"])
        == len(bagian["metadata"])
    ):
        raise ValueError(f"Jumlah baris tidak cocok pada {nama}.")

    if set(bagian["y"].unique()) != {0, 1}:
        raise ValueError(
            f"Bagian {nama} harus memiliki label normal dan fraud."
        )

if (
    train["metadata"]["TX_DATETIME"].max()
    >= metadata_val["TX_DATETIME"].min()
):
    raise ValueError("Periode train dan validation tidak terpisah.")

print(f"Jumlah transaksi train: {len(X_train)}")
print(f"Jumlah transaksi validation: {len(X_val)}")


# =========================================================
# 3. MENENTUKAN DUA KELOMPOK FITUR
# =========================================================

fitur_dasar = [
    "TX_AMOUNT",
    "TX_HOUR",
    "TX_IS_WEEKEND",
]

fitur_riwayat = fitur_dasar + [
    "CUSTOMER_TX_COUNT_24H",
    "CUSTOMER_AMOUNT_MEAN_24H",
    "CUSTOMER_AMOUNT_RATIO_24H",
    "CUSTOMER_NO_HISTORY_24H",
    "CUSTOMER_ZERO_MEAN_24H",
    "TERMINAL_TX_COUNT_24H",
]

eksperimen = {
    "basic": fitur_dasar,
    "history": fitur_riwayat,
}

fitur_penanda = [
    "TX_IS_WEEKEND",
    "CUSTOMER_NO_HISTORY_24H",
    "CUSTOMER_ZERO_MEAN_24H",
]

# Batas pembanding awal, belum threshold final.
threshold = 0.05

hasil_perbandingan = []
model_terlatih = {}

skor_validation = metadata_val.reset_index(drop=True).copy()
skor_validation["TX_FRAUD"] = y_val.to_numpy()


# =========================================================
# 4. MELATIH DAN MENGEVALUASI SETIAP EKSPERIMEN
# =========================================================

for nama, daftar_fitur in eksperimen.items():
    print(f"\nMelatih Logistic Regression: {nama}...")

    kolom_penanda = [
        kolom
        for kolom in daftar_fitur
        if kolom in fitur_penanda
    ]

    kolom_numerik = [
        kolom
        for kolom in daftar_fitur
        if kolom != "TX_HOUR"
        and kolom not in kolom_penanda
    ]

    preprocessing = ColumnTransformer(
        transformers=[
            (
                "numerik",
                StandardScaler(),
                kolom_numerik,
            ),
            (
                "jam",
                OneHotEncoder(
                    categories=[list(range(24))],
                    handle_unknown="error",
                    sparse_output=False,
                ),
                ["TX_HOUR"],
            ),
            (
                "penanda",
                "passthrough",
                kolom_penanda,
            ),
        ],
        remainder="drop",
    )

    model = Pipeline(
        steps=[
            ("preprocessing", preprocessing),
            (
                "classifier",
                LogisticRegression(
                    solver="lbfgs",
                    max_iter=2000,
                    random_state=42,
                ),
            ),
        ]
    )

    # Berhenti jika optimasi belum konvergen.
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)

        model.fit(
            X_train[daftar_fitur],
            y_train,
        )

    skor_train = model.predict_proba(
        X_train[daftar_fitur]
    )[:, 1]

    skor_val = model.predict_proba(
        X_val[daftar_fitur]
    )[:, 1]

    prediksi_val = (skor_val >= threshold).astype("int64")

    tn, fp, fn, tp = confusion_matrix(
        y_val,
        prediksi_val,
        labels=[0, 1],
    ).ravel()

    review_harian = pd.DataFrame({
        "tanggal": metadata_val["TX_DATETIME"].dt.date.to_numpy(),
        "review": prediksi_val,
    }).groupby("tanggal")["review"].sum()

    hasil_perbandingan.append({
        "model": nama,
        "jumlah_fitur": len(daftar_fitur),
        "ap_train": float(
            average_precision_score(y_train, skor_train)
        ),
        "ap_validation": float(
            average_precision_score(y_val, skor_val)
        ),
        "threshold": threshold,
        "precision": float(
            precision_score(
                y_val,
                prediksi_val,
                zero_division=0,
            )
        ),
        "recall": float(
            recall_score(
                y_val,
                prediksi_val,
                zero_division=0,
            )
        ),
        "tp": int(tp),
        "fp": int(fp),
        "fn": int(fn),
        "tn": int(tn),
        "total_review": int(prediksi_val.sum()),
        "max_review_harian": int(review_harian.max()),
        "hari_melebihi_100": int((review_harian > 100).sum()),
    })

    model_terlatih[nama] = {
        "pipeline": model,
        "features": daftar_fitur,
        "decision_threshold": None,
        "sklearn_version": sklearn.__version__,
        "train_start": str(
            train["metadata"]["TX_DATETIME"].min()
        ),
        "train_end": str(
            train["metadata"]["TX_DATETIME"].max()
        ),
    }

    skor_validation[f"score_{nama}"] = skor_val


# =========================================================
# 5. MENAMPILKAN HASIL
# =========================================================

tabel_hasil = pd.DataFrame(hasil_perbandingan)

print("\nHASIL PERBANDINGAN LOGISTIC REGRESSION")
print(
    tabel_hasil.to_string(
        index=False,
        float_format=lambda nilai: f"{nilai:.4f}",
    )
)


# =========================================================
# 6. MENYIMPAN MODEL, LAPORAN, DAN SKOR VALIDATION
# =========================================================

model_dir.mkdir(parents=True, exist_ok=True)
report_dir.mkdir(parents=True, exist_ok=True)

for nama, artefak in model_terlatih.items():
    lokasi_model = model_dir / f"logistic_{nama}.pkl"
    pd.to_pickle(artefak, lokasi_model)
    print(f"\nModel tersimpan: {lokasi_model}")

laporan = {
    "evaluation_split": "validation",
    "comparison_threshold": threshold,
    "review_capacity_assumption": 100,
    "sklearn_version": sklearn.__version__,
    "pandas_version": pd.__version__,
    "results": hasil_perbandingan,
}

lokasi_laporan = report_dir / "logistic_comparison_validation.json"

with lokasi_laporan.open("w", encoding="utf-8") as file:
    json.dump(
        laporan,
        file,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
    )

lokasi_skor = data_dir / "logistic_validation_scores.pkl"
skor_validation.to_pickle(lokasi_skor)

print(f"\nLaporan tersimpan: {lokasi_laporan}")
print(f"Skor validation tersimpan: {lokasi_skor}")
print("\nEKSPERIMEN LOGISTIC SELESAI")