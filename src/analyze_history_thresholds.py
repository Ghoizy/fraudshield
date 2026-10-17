import json
from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_score,
    recall_score,
)


# =========================================================
# 1. LOKASI INPUT DAN LAPORAN
# =========================================================

project_root = Path(__file__).resolve().parent.parent

input_path = (
    project_root
    / "data"
    / "processed"
    / "history_v1"
    / "logistic_validation_scores.pkl"
)

report_dir = project_root / "reports" / "history_v1"

if not input_path.is_file():
    raise FileNotFoundError(
        "Skor validation belum tersedia. "
        "Jalankan src/train_history_logistic.py sampai selesai."
    )

df = pd.read_pickle(input_path)


# =========================================================
# 2. MEMERIKSA DATA SKOR
# =========================================================

kolom_wajib = [
    "TRANSACTION_ID",
    "TX_DATETIME",
    "TX_FRAUD",
    "score_basic",
    "score_history",
]

kolom_hilang = set(kolom_wajib) - set(df.columns)

if kolom_hilang:
    raise ValueError(
        f"Kolom belum tersedia: {sorted(kolom_hilang)}"
    )

if df.empty:
    raise ValueError("Data skor kosong.")

if df[kolom_wajib].isna().any().any():
    raise ValueError("Ada nilai kosong pada data skor.")

if df["TRANSACTION_ID"].duplicated().any():
    raise ValueError("Ada ID transaksi yang berulang.")

if set(df["TX_FRAUD"].unique()) != {0, 1}:
    raise ValueError(
        "Validation harus memiliki label normal dan fraud."
    )

df["TX_DATETIME"] = pd.to_datetime(
    df["TX_DATETIME"],
    errors="raise",
)

dalam_validation = (
    (df["TX_DATETIME"] >= pd.Timestamp("2018-04-19"))
    & (df["TX_DATETIME"] < pd.Timestamp("2018-04-25"))
)

if not dalam_validation.all():
    raise ValueError("Ada transaksi di luar periode validation.")

for kolom in ["score_basic", "score_history"]:
    skor = df[kolom].to_numpy(dtype=float)

    if not np.isfinite(skor).all():
        raise ValueError(f"Ada skor tidak valid pada {kolom}.")

    if not df[kolom].between(0, 1).all():
        raise ValueError(f"Skor pada {kolom} harus berada di 0–1.")


# =========================================================
# 3. MENETAPKAN THRESHOLD DAN KAPASITAS
# =========================================================

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
    start="2018-04-19",
    end="2018-04-24",
    freq="D",
)

y_true = df["TX_FRAUD"]
hasil_threshold = []


# =========================================================
# 4. MEMERIKSA SETIAP MODEL DAN THRESHOLD
# =========================================================

for nama_model in ["basic", "history"]:
    skor = df[f"score_{nama_model}"]

    ap_validation = float(
        average_precision_score(y_true, skor)
    )

    for threshold in daftar_threshold:
        prediksi = (skor >= threshold).astype("int64")

        tn, fp, fn, tp = confusion_matrix(
            y_true,
            prediksi,
            labels=[0, 1],
        ).ravel()

        tabel_review = pd.DataFrame({
            "tanggal": df["TX_DATETIME"].dt.normalize().to_numpy(),
            "review": prediksi.to_numpy(),
        })

        review_harian = (
            tabel_review
            .groupby("tanggal")["review"]
            .sum()
            .reindex(daftar_hari, fill_value=0)
        )

        max_review = int(review_harian.max())

        hari_melebihi = int(
            (review_harian > kapasitas_harian).sum()
        )

        hasil_threshold.append({
            "model": nama_model,
            "threshold": float(threshold),
            "ap_validation": ap_validation,
            "precision": float(
                precision_score(
                    y_true,
                    prediksi,
                    zero_division=0,
                )
            ),
            "recall": float(
                recall_score(
                    y_true,
                    prediksi,
                    zero_division=0,
                )
            ),
            "tp": int(tp),
            "fp": int(fp),
            "fn": int(fn),
            "total_review": int(prediksi.sum()),
            "max_review_harian": max_review,
            "hari_melebihi_100": hari_melebihi,
            "memenuhi_kapasitas": hari_melebihi == 0,
        })


# =========================================================
# 5. MENAMPILKAN SELURUH HASIL
# =========================================================

tabel_hasil = pd.DataFrame(hasil_threshold)

print("\nPERBANDINGAN THRESHOLD PADA VALIDATION")
print(
    tabel_hasil.to_string(
        index=False,
        float_format=lambda angka: f"{angka:.4f}",
    )
)


# =========================================================
# 6. MENCARI KANDIDAT UNTUK SETIAP MODEL
# =========================================================

kandidat_per_model = []

for nama_model in ["basic", "history"]:
    pilihan = [
        baris
        for baris in hasil_threshold
        if baris["model"] == nama_model
        and baris["memenuhi_kapasitas"]
    ]

    if not pilihan:
        print(
            f"\nModel {nama_model}: tidak ada threshold "
            "yang memenuhi kapasitas dalam daftar percobaan."
        )
        continue

    # Prioritas:
    # 1. Recall tertinggi.
    # 2. False positive paling sedikit.
    # 3. Threshold tertinggi jika hasilnya masih sama.
    pilihan.sort(
        key=lambda baris: (
            -baris["recall"],
            baris["fp"],
            -baris["threshold"],
        )
    )

    kandidat_per_model.append(pilihan[0])


print("\nKANDIDAT THRESHOLD PER MODEL")

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
# 7. MENYIMPAN LAPORAN
# =========================================================

report_dir.mkdir(parents=True, exist_ok=True)

laporan = {
    "evaluation_split": "validation",
    "validation_start": "2018-04-19",
    "validation_end_exclusive": "2018-04-25",
    "daily_review_capacity": kapasitas_harian,
    "thresholds_tested": daftar_threshold,
    "results": hasil_threshold,
    "candidates_per_model": kandidat_per_model,
}

output_path = (
    report_dir
    / "logistic_thresholds_validation.json"
)

with output_path.open("w", encoding="utf-8") as file:
    json.dump(
        laporan,
        file,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
    )

print(f"\nLaporan tersimpan: {output_path}")
print("\nANALISIS THRESHOLD SELESAI")