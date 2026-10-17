import hashlib
import json
from datetime import datetime
from math import isfinite
from numbers import Integral
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn


class RiskEngine:
    def __init__(self):
        project_root = Path(__file__).resolve().parent.parent

        selection_path = (
            project_root
            / "models"
            / "frozen_v1"
            / "selection.json"
        )

        with selection_path.open("r", encoding="utf-8") as file:
            konfigurasi = json.load(file)

        # Engine versi ini khusus untuk model dasar terpilih.
        fitur_diharapkan = [
            "TX_AMOUNT",
            "TX_HOUR",
            "TX_IS_WEEKEND",
        ]

        if konfigurasi["features"] != fitur_diharapkan:
            raise ValueError(
                "Engine ini membutuhkan model dengan fitur dasar."
            )

        versi_sekarang = {
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
        }

        for nama, versi in versi_sekarang.items():
            if konfigurasi["environment"][nama] != versi:
                raise ValueError(
                    f"Versi {nama} berbeda dari konfigurasi freeze."
                )

        model_path = project_root / konfigurasi["model_path"]

        hash_model = hashlib.sha256(
            model_path.read_bytes()
        ).hexdigest()

        if hash_model != konfigurasi["model_sha256"]:
            raise ValueError("File model berubah setelah freeze.")

        artefak = pd.read_pickle(model_path)

        if artefak["features"] != konfigurasi["features"]:
            raise ValueError("Daftar fitur model tidak sesuai.")

        if (
            artefak["decision_threshold"]
            != konfigurasi["threshold"]
        ):
            raise ValueError("Threshold model tidak sesuai.")

        self.model = artefak["pipeline"]
        self.features = konfigurasi["features"]
        self.threshold = float(konfigurasi["threshold"])
        self.model_version = konfigurasi["model_version"]
        self.policy_version = "review-policy-v1"

        if not isfinite(self.threshold) or not 0 <= self.threshold <= 1:
            raise ValueError("Threshold tidak valid.")

    def score(self, transaksi):
        # 1. Memeriksa bentuk input.
        if not isinstance(transaksi, dict):
            raise ValueError("Input transaksi harus berupa dictionary.")

        kolom_wajib = {
            "TRANSACTION_ID",
            "TX_DATETIME",
            "TX_AMOUNT",
        }

        kolom_hilang = kolom_wajib - set(transaksi)

        if kolom_hilang:
            raise ValueError(
                f"Input belum lengkap: {sorted(kolom_hilang)}"
            )

        if {"TX_FRAUD", "TX_FRAUD_SCENARIO"} & set(transaksi):
            raise ValueError(
                "Input prediksi tidak boleh menyertakan label fraud."
            )

        # 2. Memeriksa ID transaksi.
        transaction_id = transaksi["TRANSACTION_ID"]

        if (
            isinstance(transaction_id, bool)
            or not isinstance(transaction_id, Integral)
            or transaction_id < 0
        ):
            raise ValueError(
                "TRANSACTION_ID harus berupa bilangan bulat nonnegatif."
            )

        # 3. Memeriksa nominal.
        nominal_input = transaksi["TX_AMOUNT"]

        if isinstance(nominal_input, bool):
            raise ValueError("TX_AMOUNT harus berupa nominal.")

        try:
            nominal = float(nominal_input)
        except (TypeError, ValueError):
            raise ValueError("TX_AMOUNT tidak dapat dibaca sebagai angka.")

        if not isfinite(nominal) or nominal < 0:
            raise ValueError(
                "TX_AMOUNT harus berupa angka terbatas dan tidak negatif."
            )

        # 4. Memeriksa waktu transaksi.
        waktu_input = transaksi["TX_DATETIME"]

        if not isinstance(waktu_input, (str, datetime)):
            raise ValueError(
                "TX_DATETIME harus berupa teks tanggal atau datetime."
            )

        try:
            waktu = pd.Timestamp(waktu_input)
        except (TypeError, ValueError):
            raise ValueError("TX_DATETIME tidak dapat dibaca.")

        if pd.isna(waktu):
            raise ValueError("TX_DATETIME tidak boleh kosong.")

        if waktu.tzinfo is not None:
            raise ValueError(
                "Demo ini memakai waktu tanpa zona waktu, "
                "sesuai dataset pelatihan."
            )

        # 5. Membentuk fitur dengan aturan yang sama saat pelatihan.
        fitur = pd.DataFrame([{
            "TX_AMOUNT": nominal,
            "TX_HOUR": waktu.hour,
            "TX_IS_WEEKEND": int(waktu.dayofweek >= 5),
        }])

        fitur = fitur[self.features].astype("float64")

        # 6. Menghasilkan skor.
        skor = float(
            self.model.predict_proba(fitur)[0, 1]
        )

        if not isfinite(skor) or not 0 <= skor <= 1:
            raise ValueError("Model menghasilkan skor tidak valid.")

        # 7. Menerapkan kebijakan keputusan.
        if skor >= self.threshold:
            keputusan = "REVIEW"
            alasan = "SCORE_AT_OR_ABOVE_THRESHOLD"
        else:
            keputusan = "ALLOW"
            alasan = "SCORE_BELOW_THRESHOLD"

        return {
            "transaction_id": int(transaction_id),
            "risk_score": skor,
            "threshold": self.threshold,
            "decision": keputusan,
            "reason": alasan,
            "model_version": self.model_version,
            "policy_version": self.policy_version,
        }