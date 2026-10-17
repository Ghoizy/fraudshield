import hashlib
import json
from math import isclose
from pathlib import Path

import pandas as pd

from risk_engine import RiskEngine


project_root = Path(__file__).resolve().parent.parent

test_path = (
    project_root
    / "data"
    / "processed"
    / "history_v1"
    / "test.pkl"
)

prediction_path = (
    project_root
    / "data"
    / "processed"
    / "frozen_v1"
    / "test_predictions.pkl"
)

report_path = (
    project_root
    / "reports"
    / "frozen_v1"
    / "test_evaluation.json"
)

selection_path = (
    project_root
    / "models"
    / "frozen_v1"
    / "selection.json"
)


def hitung_hash(lokasi):
    return hashlib.sha256(lokasi.read_bytes()).hexdigest()


# Memastikan data dan konfigurasi sama dengan evaluasi test.
with report_path.open("r", encoding="utf-8") as file:
    laporan_test = json.load(file)

if hitung_hash(test_path) != laporan_test["test_data_sha256"]:
    raise ValueError("Data test berubah sejak evaluasi.")

if (
    hitung_hash(prediction_path)
    != laporan_test["predictions_sha256"]
):
    raise ValueError("File prediksi test berubah.")

if (
    hitung_hash(selection_path)
    != laporan_test["selection_sha256"]
):
    raise ValueError("Konfigurasi model berubah.")


test = pd.read_pickle(test_path)

prediksi_acuan = pd.read_pickle(
    prediction_path
).set_index("TRANSACTION_ID")

engine = RiskEngine()

jumlah_contoh = min(5, len(test["X"]))

if jumlah_contoh == 0:
    raise ValueError("Tidak ada transaksi untuk demo.")

for posisi in range(jumlah_contoh):
    metadata = test["metadata"].iloc[posisi]
    fitur = test["X"].iloc[posisi]

    # Hanya informasi transaksi yang diberikan kepada engine.
    transaksi = {
        "TRANSACTION_ID": int(metadata["TRANSACTION_ID"]),
        "TX_DATETIME": metadata["TX_DATETIME"].isoformat(),
        "TX_AMOUNT": float(fitur["TX_AMOUNT"]),
    }

    hasil = engine.score(transaksi)

    acuan = prediksi_acuan.loc[
        transaksi["TRANSACTION_ID"]
    ]

    if not isclose(
        hasil["risk_score"],
        float(acuan["risk_score"]),
        rel_tol=1e-10,
        abs_tol=1e-12,
    ):
        raise AssertionError(
            f"Skor berbeda pada transaksi "
            f"{transaksi['TRANSACTION_ID']}"
        )

    if hasil["decision"] != acuan["decision"]:
        raise AssertionError(
            f"Keputusan berbeda pada transaksi "
            f"{transaksi['TRANSACTION_ID']}"
        )

    print("\nINPUT:")
    print(json.dumps(transaksi, indent=2))

    print("OUTPUT:")
    print(json.dumps(hasil, indent=2))

print(
    f"\nDEMO LULUS: {jumlah_contoh} transaksi "
    "memiliki skor dan keputusan yang sesuai evaluasi test."
)