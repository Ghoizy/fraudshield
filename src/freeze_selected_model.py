import hashlib
import json
import platform
from datetime import datetime, timezone
from math import isclose
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn

from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_score,
    recall_score,
)


# =========================================================
# 1. LOKASI FILE
# =========================================================

project_root = Path(__file__).resolve().parent.parent

data_dir = project_root / "data" / "processed" / "history_v1"
model_dir = project_root / "models" / "history_v1"
report_dir = project_root / "reports" / "history_v1"

comparison_path = report_dir / "model_comparison_validation.json"

frozen_dir = project_root / "models" / "frozen_v1"

if frozen_dir.exists():
    raise SystemExit(
        "Folder models/frozen_v1 sudah ada. "
        "Script berhenti agar versi yang sudah disimpan tidak tertimpa."
    )


def hitung_hash(lokasi_file):
    """Membuat sidik jari dari isi file."""
    pemeriksa = hashlib.sha256()

    with lokasi_file.open("rb") as file:
        for potongan in iter(lambda: file.read(1024 * 1024), b""):
            pemeriksa.update(potongan)

    return pemeriksa.hexdigest()


# =========================================================
# 2. MEMBACA REKOMENDASI YANG SUDAH DITINJAU
# =========================================================

with comparison_path.open("r", encoding="utf-8") as file:
    laporan = json.load(file)

pilihan = laporan["recommendation"]

if pilihan is None:
    raise ValueError("Belum ada rekomendasi model.")

candidate = pilihan["candidate"]
threshold = float(pilihan["threshold"])

# Sesuai hasil yang sudah kita tinjau bersama.
if candidate != "logistic_basic" or threshold != 0.05:
    raise ValueError(
        "Rekomendasi berubah dari logistic_basic / 0.05. "
        "Periksa hasil perbandingan sebelum membuat versi tetap."
    )

if laporan["evaluation_split"] != "validation":
    raise ValueError("Rekomendasi harus berasal dari validation.")

if laporan["daily_review_capacity"] != 100:
    raise ValueError("Asumsi kapasitas review berubah.")

source_model_path = model_dir / "logistic_basic.pkl"
artefak = pd.read_pickle(source_model_path)

if artefak["sklearn_version"] != sklearn.__version__:
    raise ValueError(
        "Versi scikit-learn berbeda dari versi pelatihan."
    )

features = artefak["features"]

if features != ["TX_AMOUNT", "TX_HOUR", "TX_IS_WEEKEND"]:
    raise ValueError("Daftar fitur model tidak sesuai.")

model = artefak["pipeline"]


# =========================================================
# 3. MEMERIKSA ULANG MODEL PADA VALIDATION
# =========================================================

validation = pd.read_pickle(data_dir / "validation.pkl")

X_val = validation["X"]
y_val = validation["y"]
metadata = validation["metadata"]

if not (len(X_val) == len(y_val) == len(metadata)):
    raise ValueError("Jumlah baris validation tidak sesuai.")

if set(y_val.unique()) != {0, 1}:
    raise ValueError("Label validation tidak sesuai.")

waktu = pd.to_datetime(metadata["TX_DATETIME"])

if not (
    (waktu >= pd.Timestamp("2018-04-19"))
    & (waktu < pd.Timestamp("2018-04-25"))
).all():
    raise ValueError("Periode validation tidak sesuai.")

# Tidak ada pelatihan ulang di sini.
skor = model.predict_proba(X_val[features])[:, 1]

if not np.isfinite(skor).all():
    raise ValueError("Model menghasilkan skor tidak valid.")

prediksi = (skor >= threshold).astype("int64")

tn, fp, fn, tp = confusion_matrix(
    y_val,
    prediksi,
    labels=[0, 1],
).ravel()

review_harian = (
    pd.DataFrame({
        "tanggal": waktu.dt.normalize().to_numpy(),
        "review": prediksi,
    })
    .groupby("tanggal")["review"]
    .sum()
    .reindex(
        pd.date_range("2018-04-19", "2018-04-24"),
        fill_value=0,
    )
)

hasil_ulang = {
    "tp": int(tp),
    "fp": int(fp),
    "fn": int(fn),
    "total_review": int(prediksi.sum()),
    "max_review_harian": int(review_harian.max()),
    "hari_melebihi_100": int((review_harian > 100).sum()),
    "precision": float(
        precision_score(y_val, prediksi, zero_division=0)
    ),
    "recall": float(
        recall_score(y_val, prediksi, zero_division=0)
    ),
    "ap_validation": float(
        average_precision_score(y_val, skor)
    ),
}

kolom_bilangan_bulat = [
    "tp",
    "fp",
    "fn",
    "total_review",
    "max_review_harian",
    "hari_melebihi_100",
]

for nama in kolom_bilangan_bulat:
    if hasil_ulang[nama] != pilihan[nama]:
        raise ValueError(
            f"Hasil {nama} berbeda dari laporan: "
            f"sekarang={hasil_ulang[nama]}, "
            f"laporan={pilihan[nama]}"
        )

for nama in ["precision", "recall", "ap_validation"]:
    if not isclose(
        hasil_ulang[nama],
        pilihan[nama],
        rel_tol=1e-9,
        abs_tol=1e-12,
    ):
        raise ValueError(
            f"Hasil {nama} berbeda dari laporan."
        )

if hasil_ulang["hari_melebihi_100"] != 0:
    raise ValueError("Kandidat melampaui kapasitas validation.")

print("PEMERIKSAAN VALIDATION COCOK")


# =========================================================
# 4. MENCATAT SIDIK JARI DATA DAN LAPORAN
# =========================================================

file_acuan = [
    data_dir / "train.pkl",
    data_dir / "validation.pkl",
    data_dir / "test.pkl",
    comparison_path,
    source_model_path,
]

hash_file_acuan = {
    lokasi.relative_to(project_root).as_posix(): hitung_hash(lokasi)
    for lokasi in file_acuan
}


# =========================================================
# 5. MENYIMPAN SALINAN MODEL DAN KONFIGURASI
# =========================================================

frozen_dir.mkdir(parents=True, exist_ok=False)

frozen_model_path = frozen_dir / "model.pkl"
selection_path = frozen_dir / "selection.json"

artefak_beku = artefak.copy()
artefak_beku["decision_threshold"] = threshold
artefak_beku["model_version"] = "fraudshield-v1"
artefak_beku["candidate"] = candidate

pd.to_pickle(artefak_beku, frozen_model_path)

konfigurasi = {
    "model_version": "fraudshield-v1",
    "candidate": candidate,
    "threshold": threshold,
    "features": features,
    "selection_split": "validation",
    "daily_review_capacity_assumption": 100,
    "validation_metrics": hasil_ulang,
    "test_start": "2018-04-25",
    "test_end_exclusive": "2018-05-01",
    "model_path": frozen_model_path.relative_to(
        project_root
    ).as_posix(),
    "model_sha256": hitung_hash(frozen_model_path),
    "reference_file_hashes": hash_file_acuan,
    "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
    "environment": {
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "scikit_learn": sklearn.__version__,
    },
}

with selection_path.open("x", encoding="utf-8") as file:
    json.dump(
        konfigurasi,
        file,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
    )

print("\nMODEL DAN THRESHOLD TERSIMPAN")
print(f"Versi: {konfigurasi['model_version']}")
print(f"Kandidat: {candidate}")
print(f"Threshold: {threshold}")
print(f"Fitur: {features}")
print(f"Model: {frozen_model_path}")
print(f"Konfigurasi: {selection_path}")
print("\nCHECKPOINT 8A SELESAI")