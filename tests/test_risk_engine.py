import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np


# Agar pengujian dapat mengimpor risk_engine dari folder src.
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from risk_engine import RiskEngine


class TestRiskEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Membaca model sekali untuk seluruh kelompok pengujian.
        cls.engine = RiskEngine()

    def setUp(self):
        # Menyiapkan input baru untuk setiap metode pengujian.
        self.transaksi = {
            "TRANSACTION_ID": 100,
            "TX_DATETIME": "2018-05-01 10:00:00",
            "TX_AMOUNT": 75.0,
        }

    def test_transaksi_valid(self):
        hasil = self.engine.score(self.transaksi)

        self.assertEqual(
            hasil["transaction_id"],
            self.transaksi["TRANSACTION_ID"],
        )

        self.assertGreaterEqual(hasil["risk_score"], 0.0)
        self.assertLessEqual(hasil["risk_score"], 1.0)

        self.assertIn(
            hasil["decision"],
            ["ALLOW", "REVIEW"],
        )

        self.assertEqual(
            hasil["threshold"],
            self.engine.threshold,
        )

        self.assertEqual(
            hasil["model_version"],
            self.engine.model_version,
        )

    def test_nominal_nol_diterima(self):
        transaksi = {
            **self.transaksi,
            "TX_AMOUNT": 0.0,
        }

        hasil = self.engine.score(transaksi)

        self.assertGreaterEqual(hasil["risk_score"], 0.0)
        self.assertLessEqual(hasil["risk_score"], 1.0)

    def test_input_tidak_valid_ditolak(self):
        kasus = [
            ("input bukan dictionary", []),
            (
                "nominal negatif",
                {**self.transaksi, "TX_AMOUNT": -10.0},
            ),
            (
                "nominal bukan angka",
                {**self.transaksi, "TX_AMOUNT": "abc"},
            ),
            (
                "nominal kosong",
                {**self.transaksi, "TX_AMOUNT": None},
            ),
            (
                "nominal NaN",
                {**self.transaksi, "TX_AMOUNT": float("nan")},
            ),
            (
                "nominal tak hingga",
                {**self.transaksi, "TX_AMOUNT": float("inf")},
            ),
            (
                "nominal boolean",
                {**self.transaksi, "TX_AMOUNT": True},
            ),
            (
                "ID negatif",
                {**self.transaksi, "TRANSACTION_ID": -1},
            ),
            (
                "ID pecahan",
                {**self.transaksi, "TRANSACTION_ID": 1.5},
            ),
            (
                "ID boolean",
                {**self.transaksi, "TRANSACTION_ID": True},
            ),
            (
                "waktu tidak terbaca",
                {**self.transaksi, "TX_DATETIME": "bukan-tanggal"},
            ),
            (
                "waktu kosong",
                {**self.transaksi, "TX_DATETIME": None},
            ),
            (
                "waktu NaT",
                {**self.transaksi, "TX_DATETIME": "NaT"},
            ),
            (
                "zona waktu belum didukung",
                {
                    **self.transaksi,
                    "TX_DATETIME": "2018-05-01T10:00:00+07:00",
                },
            ),
            (
                "input membawa label fraud",
                {**self.transaksi, "TX_FRAUD": 1},
            ),
            (
                "input membawa skenario fraud",
                {**self.transaksi, "TX_FRAUD_SCENARIO": 2},
            ),
        ]

        # Memeriksa setiap kolom wajib yang tidak diberikan.
        for kolom in self.transaksi:
            tidak_lengkap = self.transaksi.copy()
            del tidak_lengkap[kolom]

            kasus.append(
                (f"kolom {kolom} hilang", tidak_lengkap)
            )

        for nama, transaksi in kasus:
            with self.subTest(kasus=nama):
                with patch.object(
                    self.engine.model,
                    "predict_proba",
                ) as prediksi_model:
                    with self.assertRaises(ValueError):
                        self.engine.score(transaksi)

                    # Input salah harus ditolak sebelum model dipanggil.
                    prediksi_model.assert_not_called()

    def test_keputusan_di_sekitar_threshold(self):
        threshold = self.engine.threshold

        kasus = [
            (
                threshold - 0.001,
                "ALLOW",
                "SCORE_BELOW_THRESHOLD",
            ),
            (
                threshold,
                "REVIEW",
                "SCORE_AT_OR_ABOVE_THRESHOLD",
            ),
            (
                threshold + 0.001,
                "REVIEW",
                "SCORE_AT_OR_ABOVE_THRESHOLD",
            ),
        ]

        for skor, keputusan, alasan in kasus:
            with self.subTest(skor=skor):
                skor_buatan = np.array([[1.0 - skor, skor]])

                with patch.object(
                    self.engine.model,
                    "predict_proba",
                    return_value=skor_buatan,
                ):
                    hasil = self.engine.score(self.transaksi)

                self.assertEqual(hasil["decision"], keputusan)
                self.assertEqual(hasil["reason"], alasan)

    def test_skor_model_tidak_valid_ditolak(self):
        for skor in [
            float("nan"),
            float("inf"),
            -0.1,
            1.1,
        ]:
            with self.subTest(skor=skor):
                skor_buatan = np.array([[0.0, skor]])

                with patch.object(
                    self.engine.model,
                    "predict_proba",
                    return_value=skor_buatan,
                ):
                    with self.assertRaises(ValueError):
                        self.engine.score(self.transaksi)


if __name__ == "__main__":
    unittest.main()