import json
from pathlib import Path

import pandas as pd
import sklearn

from sklearn.compose import ColumnTransformer
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier


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

X_train = train["X"]
y_train = train["y"]

X_val = validation["X"]
y_val = validation["y"]
metadata_val = validation["metadata"]

if (
    train["metadata"]["TX_DATETIME"].max()
    >= metadata_val["TX_DATETIME"].min()
):
    raise ValueError("Periode train dan validation tidak terpisah.")

dalam_validation = (
    (metadata_val["TX_DATETIME"] >= pd.Timestamp("2018-04-19"))
    & (metadata_val["TX_DATETIME"] < pd.Timestamp("2018-04-25"))
)

if not dalam_validation.all():
    raise ValueError("Tanggal validation tidak sesuai.")

print(f"Jumlah transaksi train: {len(X_train)}")
print(f"Jumlah transaksi validation: {len(X_val)}")


# =========================================================
# 3. FITUR DAN PENGATURAN EKSPERIMEN
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

daftar_threshold = [
    0.5,
    0.2,
    0.1,
    0.05,
    0.02,
    0.01,
    0.005,
]

kapasitas_harian = 100

daftar_hari = pd.date_range(
    "2018-04-19",
    "2018-04-24",
    freq="D",
)

hasil_threshold = []
model_terlatih = {}

skor_validation = metadata_val.reset_index(drop=True).copy()
skor_validation["TX_FRAUD"] = y_val.to_numpy()


# =========================================================
# 4. MELATIH DUA MODEL DECISION TREE
# =========================================================

for nama, daftar_fitur in eksperimen.items():
    print(f"\nMelatih Decision Tree: {nama}...")

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

    # Susunan preprocessing sama dengan eksperimen Logistic.
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
                DecisionTreeClassifier(
                    max_depth=5,
                    min_samples_leaf=50,
                    random_state=42,
                ),
            ),
        ]
    )

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

    ap_train = float(
        average_precision_score(y_train, skor_train)
    )

    ap_validation = float(
        average_precision_score(y_val, skor_val)
    )

    skor_validation[f"score_{nama}"] = skor_val

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

    # Memeriksa tujuh threshold tanpa melatih ulang model.
    for threshold in daftar_threshold:
        prediksi = (skor_val >= threshold).astype("int64")

        tn, fp, fn, tp = confusion_matrix(
            y_val,
            prediksi,
            labels=[0, 1],
        ).ravel()

        review_harian = (
            pd.DataFrame({
                "tanggal": (
                    metadata_val["TX_DATETIME"]
                    .dt.normalize()
                    .to_numpy()
                ),
                "review": prediksi,
            })
            .groupby("tanggal")["review"]
            .sum()
            .reindex(daftar_hari, fill_value=0)
        )

        hari_melebihi = int(
            (review_harian > kapasitas_harian).sum()
        )

        hasil_threshold.append({
            "model": nama,
            "jumlah_fitur": len(daftar_fitur),
            "ap_train": ap_train,
            "ap_validation": ap_validation,
            "threshold": float(threshold),
            "precision": float(
                precision_score(
                    y_val,
                    prediksi,
                    zero_division=0,
                )
            ),
            "recall": float(
                recall_score(
                    y_val,
                    prediksi,
                    zero_division=0,
                )
            ),
            "tp": int(tp),
            "fp": int(fp),
            "fn": int(fn),
            "total_review": int(prediksi.sum()),
            "max_review_harian": int(review_harian.max()),
            "hari_melebihi_100": hari_melebihi,
            "memenuhi_kapasitas": hari_melebihi == 0,
        })


# =========================================================
# 5. MENAMPILKAN HASIL DAN KANDIDAT PER MODEL
# =========================================================

tabel_hasil = pd.DataFrame(hasil_threshold)

print("\nHASIL DECISION TREE PADA VALIDATION")
print(
    tabel_hasil.to_string(
        index=False,
        float_format=lambda angka: f"{angka:.4f}",
    )
)

kandidat_per_model = []

for nama in eksperimen:
    pilihan = [
        baris
        for baris in hasil_threshold
        if baris["model"] == nama
        and baris["memenuhi_kapasitas"]
    ]

    if not pilihan:
        print(
            f"\nTree {nama}: belum ada threshold "
            "yang memenuhi kapasitas dalam daftar percobaan."
        )
        continue

    pilihan.sort(
        key=lambda baris: (
            -baris["recall"],
            baris["fp"],
            -baris["threshold"],
        )
    )

    kandidat_per_model.append(pilihan[0])

print("\nKANDIDAT THRESHOLD DECISION TREE")

if kandidat_per_model:
    print(
        pd.DataFrame(kandidat_per_model).to_string(
            index=False,
            float_format=lambda angka: f"{angka:.4f}",
        )
    )
else:
    print("Belum ada kandidat yang memenuhi kapasitas.")


# =========================================================
# 6. MENYIMPAN HASIL EKSPERIMEN
# =========================================================

model_dir.mkdir(parents=True, exist_ok=True)
report_dir.mkdir(parents=True, exist_ok=True)

for nama, artefak in model_terlatih.items():
    lokasi_model = model_dir / f"tree_{nama}.pkl"
    pd.to_pickle(artefak, lokasi_model)
    print(f"\nModel tersimpan: {lokasi_model}")

laporan = {
    "algorithm": "DecisionTreeClassifier",
    "model_parameters": {
        "max_depth": 5,
        "min_samples_leaf": 50,
        "random_state": 42,
    },
    "evaluation_split": "validation",
    "validation_start": "2018-04-19",
    "validation_end_exclusive": "2018-04-25",
    "daily_review_capacity": kapasitas_harian,
    "thresholds_tested": daftar_threshold,
    "sklearn_version": sklearn.__version__,
    "pandas_version": pd.__version__,
    "results": hasil_threshold,
    "candidates_per_model": kandidat_per_model,
}

lokasi_laporan = report_dir / "tree_thresholds_validation.json"

with lokasi_laporan.open("w", encoding="utf-8") as file:
    json.dump(
        laporan,
        file,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
    )

lokasi_skor = data_dir / "tree_validation_scores.pkl"
skor_validation.to_pickle(lokasi_skor)

print(f"\nLaporan tersimpan: {lokasi_laporan}")
print(f"Skor validation tersimpan: {lokasi_skor}")
print("\nEKSPERIMEN TREE SELESAI")