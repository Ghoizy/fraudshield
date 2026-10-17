import hashlib
import json
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

selection_path = (
    project_root / "models" / "frozen_v1" / "selection.json"
)

report_dir = project_root / "reports" / "frozen_v1"
report_path = report_dir / "test_evaluation.json"

prediction_dir = project_root / "data" / "processed" / "frozen_v1"
prediction_path = prediction_dir / "test_predictions.pkl"


def hitung_hash(lokasi_file):
    pemeriksa = hashlib.sha256()

    with lokasi_file.open("rb") as file:
        for potongan in iter(lambda: file.read(1024 * 1024), b""):
            pemeriksa.update(potongan)

    return pemeriksa.hexdigest()


# =========================================================
# 2. MEMBACA PILIHAN MODEL DAN MEMERIKSA FILE
# =========================================================

with selection_path.open("r", encoding="utf-8") as file:
    konfigurasi = json.load(file)

model_path = project_root / konfigurasi["model_path"]

if hitung_hash(model_path) != konfigurasi["model_sha256"]:
    raise ValueError("Isi model berbeda dari model yang dibekukan.")

for path_relatif, hash_acuan in konfigurasi[
    "reference_file_hashes"
].items():
    lokasi_file = project_root / path_relatif

    if hitung_hash(lokasi_file) != hash_acuan:
        raise ValueError(
            f"File berubah setelah freeze: {path_relatif}"
        )

versi_sekarang = {
    "pandas": pd.__version__,
    "numpy": np.__version__,
    "scikit_learn": sklearn.__version__,
}

for nama, versi in versi_sekarang.items():
    if konfigurasi["environment"][nama] != versi:
        raise ValueError(
            f"Versi {nama} berubah setelah freeze."
        )

selection_hash = hitung_hash(selection_path)


# =========================================================
# 3. MENAMPILKAN HASIL LAMA JIKA SUDAH PERNAH DIEVALUASI
# =========================================================

if report_path.exists():
    with report_path.open("r", encoding="utf-8") as file:
        laporan_lama = json.load(file)

    if laporan_lama["selection_sha256"] != selection_hash:
        raise ValueError(
            "Konfigurasi berbeda dari evaluasi test sebelumnya."
        )

    if (
        not prediction_path.is_file()
        or hitung_hash(prediction_path)
        != laporan_lama["predictions_sha256"]
    ):
        raise ValueError(
            "File prediksi test hilang atau berubah."
        )

    print("Evaluasi test sudah pernah dilakukan.")
    print("Menampilkan hasil yang tersimpan:")
    print(
        json.dumps(
            laporan_lama["test_metrics"],
            indent=2,
            ensure_ascii=False,
        )
    )

    raise SystemExit(0)


# =========================================================
# 4. MEMBACA MODEL DAN DATA TEST
# =========================================================

artefak = pd.read_pickle(model_path)

model = artefak["pipeline"]
features = konfigurasi["features"]
threshold = float(konfigurasi["threshold"])

if artefak["features"] != features:
    raise ValueError("Daftar fitur model dan konfigurasi berbeda.")

if artefak["decision_threshold"] != threshold:
    raise ValueError("Threshold model dan konfigurasi berbeda.")

test_path = (
    project_root
    / "data"
    / "processed"
    / "history_v1"
    / "test.pkl"
)

test = pd.read_pickle(test_path)

X_test = test["X"]
y_test = test["y"]
metadata = test["metadata"]

if not (len(X_test) == len(y_test) == len(metadata)):
    raise ValueError("Jumlah baris test tidak sesuai.")

if len(X_test) == 0:
    raise ValueError("Data test kosong.")

if metadata["TRANSACTION_ID"].duplicated().any():
    raise ValueError("Ada ID transaksi test yang berulang.")

if set(y_test.unique()) != {0, 1}:
    raise ValueError(
        "Periksa label test: script ini membutuhkan "
        "transaksi normal dan fraud untuk evaluasi."
    )

waktu = pd.to_datetime(metadata["TX_DATETIME"], errors="raise")

dalam_test = (
    (waktu >= pd.Timestamp(konfigurasi["test_start"]))
    & (waktu < pd.Timestamp(konfigurasi["test_end_exclusive"]))
)

if not dalam_test.all():
    raise ValueError("Periode data test tidak sesuai.")

if not np.isfinite(
    X_test[features].to_numpy(dtype=float)
).all():
    raise ValueError("Ada nilai fitur test yang tidak valid.")


# =========================================================
# 5. MENGHASILKAN SKOR TANPA PELATIHAN ULANG
# =========================================================

print("Mengevaluasi model tetap pada data test...")

skor = model.predict_proba(X_test[features])[:, 1]

if not np.isfinite(skor).all():
    raise ValueError("Model menghasilkan skor tidak valid.")

prediksi = (skor >= threshold).astype("int64")

tn, fp, fn, tp = confusion_matrix(
    y_test,
    prediksi,
    labels=[0, 1],
).ravel()


# =========================================================
# 6. MENGHITUNG BEBAN REVIEW HARIAN
# =========================================================

hasil_prediksi = metadata.reset_index(drop=True).copy()

hasil_prediksi["TX_FRAUD"] = y_test.to_numpy()
hasil_prediksi["risk_score"] = skor
hasil_prediksi["review_flag"] = prediksi

hasil_prediksi["decision"] = np.where(
    prediksi == 1,
    "REVIEW",
    "ALLOW",
)

tanggal = waktu.dt.strftime("%Y-%m-%d").to_numpy()

review_harian = (
    pd.DataFrame({
        "tanggal": tanggal,
        "jumlah_review": prediksi,
    })
    .groupby("tanggal")["jumlah_review"]
    .sum()
    .reindex(
        pd.date_range(
            "2018-04-25",
            "2018-04-30",
        ).strftime("%Y-%m-%d"),
        fill_value=0,
    )
)

review_harian.index.name = "tanggal"

kapasitas = konfigurasi["daily_review_capacity_assumption"]

metrik_test = {
    "jumlah_transaksi": len(X_test),
    "jumlah_fraud": int(y_test.sum()),
    "threshold": threshold,
    "average_precision": float(
        average_precision_score(y_test, skor)
    ),
    "precision": float(
        precision_score(y_test, prediksi, zero_division=0)
    ),
    "recall": float(
        recall_score(y_test, prediksi, zero_division=0)
    ),
    "tp": int(tp),
    "fp": int(fp),
    "fn": int(fn),
    "tn": int(tn),
    "total_review": int(prediksi.sum()),
    "max_review_harian": int(review_harian.max()),
    "hari_melebihi_kapasitas": int(
        (review_harian > kapasitas).sum()
    ),
}


# =========================================================
# 7. MENAMPILKAN HASIL
# =========================================================

print("\nHASIL EVALUASI TEST")
print(f"Kandidat: {konfigurasi['candidate']}")

for nama, nilai in metrik_test.items():
    if isinstance(nilai, float):
        print(f"{nama}: {nilai:.4f}")
    else:
        print(f"{nama}: {nilai}")

print("\nJUMLAH REVIEW PER HARI")
print(review_harian.to_string())

if metrik_test["hari_melebihi_kapasitas"] > 0:
    print(
        "\nKapasitas review terlampaui pada sebagian hari test."
        "\nHasil dicatat apa adanya; threshold tidak diubah."
    )


# =========================================================
# 8. MENYIMPAN PREDIKSI DAN LAPORAN
# =========================================================

prediction_dir.mkdir(parents=True, exist_ok=True)
report_dir.mkdir(parents=True, exist_ok=True)

hasil_prediksi.to_pickle(prediction_path)

laporan = {
    "evaluation_split": "test",
    "evaluation_scope": "internal_april_2018",
    "model_version": konfigurasi["model_version"],
    "candidate": konfigurasi["candidate"],
    "threshold": threshold,
    "test_start": konfigurasi["test_start"],
    "test_end_exclusive": konfigurasi["test_end_exclusive"],
    "daily_review_capacity_assumption": kapasitas,
    "selection_sha256": selection_hash,
    "model_sha256": konfigurasi["model_sha256"],
    "test_data_sha256": hitung_hash(test_path),
    "predictions_sha256": hitung_hash(prediction_path),
    "validation_metrics": konfigurasi["validation_metrics"],
    "test_metrics": metrik_test,
    "daily_reviews": (
        review_harian
        .reset_index()
        .to_dict(orient="records")
    ),
}

with report_path.open("x", encoding="utf-8") as file:
    json.dump(
        laporan,
        file,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
    )

print(f"\nPrediksi tersimpan: {prediction_path}")
print(f"Laporan tersimpan: {report_path}")
print("\nCHECKPOINT 8B SELESAI")