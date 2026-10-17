import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from decision_store import DecisionStore


class TestDecisionStore(unittest.TestCase):
    def setUp(self):
        # Setiap tes memakai folder dan database sementara.
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)

        self.db_path = Path(folder.name) / "test.db"
        self.store = DecisionStore(self.db_path)

        self.transaksi = {
            "TRANSACTION_ID": 100,
            "TX_DATETIME": "2018-05-01T10:00:00",
            "TX_AMOUNT": 75.0,
        }

        # Contoh hasil untuk menguji penyimpanan.
        # Angka ini bukan hasil evaluasi model.
        self.hasil = {
            "transaction_id": 100,
            "risk_score": 0.02,
            "threshold": 0.05,
            "decision": "ALLOW",
            "reason": "SCORE_BELOW_THRESHOLD",
            "model_version": "fraudshield-v1",
            "policy_version": "review-policy-v1",
        }

    def test_data_tetap_ada_setelah_dibuka_ulang(self):
        self.store.simpan(
            "request-001",
            self.transaksi,
            self.hasil,
        )

        # Buat objek baru yang membuka file database yang sama.
        store_baru = DecisionStore(self.db_path)
        catatan = store_baru.cari("request-001")

        self.assertIsNotNone(catatan)
        self.assertEqual(
            catatan["request_id"],
            "request-001",
        )
        self.assertEqual(
            catatan["transaksi"],
            self.transaksi,
        )
        self.assertEqual(
            catatan["hasil"],
            self.hasil,
        )
        self.assertTrue(catatan["created_at_utc"])

    def test_request_id_sama_tidak_menimpa_catatan(self):
        self.store.simpan(
            "request-001",
            self.transaksi,
            self.hasil,
        )

        hasil_berbeda = {
            **self.hasil,
            "risk_score": 0.80,
            "decision": "REVIEW",
            "reason": "SCORE_AT_OR_ABOVE_THRESHOLD",
        }

        with self.assertRaises(sqlite3.IntegrityError):
            self.store.simpan(
                "request-001",
                self.transaksi,
                hasil_berbeda,
            )

        catatan = self.store.cari("request-001")

        # Catatan pertama harus tetap utuh.
        self.assertEqual(catatan["hasil"], self.hasil)

    def test_id_transaksi_tidak_cocok_ditolak(self):
        hasil_salah = {
            **self.hasil,
            "transaction_id": 999,
        }

        with self.assertRaises(ValueError):
            self.store.simpan(
                "request-001",
                self.transaksi,
                hasil_salah,
            )

        self.assertIsNone(
            self.store.cari("request-001")
        )

    def test_request_tidak_ditemukan(self):
        catatan = self.store.cari("belum-pernah-disimpan")

        self.assertIsNone(catatan)


if __name__ == "__main__":
    unittest.main()