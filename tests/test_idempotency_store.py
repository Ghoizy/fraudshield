import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import Mock

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from idempotency_store import (
    IdempotencyConflict,
    IdempotencyStore,
)


class TestIdempotencyStore(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)

        self.db_path = Path(folder.name) / "test.db"
        self.store = IdempotencyStore(self.db_path)

        self.transaksi = {
            "TRANSACTION_ID": 2001,
            "TX_DATETIME": "2018-05-01T10:00:00",
            "TX_AMOUNT": 75.0,
        }

        # Contoh hasil khusus pengujian penyimpanan.
        self.hasil = {
            "transaction_id": 2001,
            "risk_score": 0.02,
            "threshold": 0.05,
            "decision": "ALLOW",
            "reason": "SCORE_BELOW_THRESHOLD",
            "model_version": "fraudshield-v1",
            "policy_version": "review-policy-v1",
        }

    def test_pengulangan_memakai_hasil_tersimpan(self):
        pembuat = Mock(return_value=self.hasil)

        pertama = self.store.proses(
            "transaksi-2001",
            "request-001",
            self.transaksi,
            pembuat,
        )

        # Buka ulang database untuk memastikan hasilnya persisten.
        store_baru = IdempotencyStore(self.db_path)

        kedua = store_baru.proses(
            "transaksi-2001",
            "request-002",
            self.transaksi,
            pembuat,
        )

        pembuat.assert_called_once_with()

        self.assertFalse(pertama["replayed"])
        self.assertTrue(kedua["replayed"])

        self.assertEqual(
            pertama["hasil"],
            kedua["hasil"],
        )

        self.assertEqual(
            kedua["original_request_id"],
            "request-001",
        )

        # Pengulangan tidak membuat catatan keputusan baru.
        self.assertIsNone(
            self.store.cari("request-002")
        )

    def test_input_berbeda_dengan_kunci_sama_ditolak(self):
        pembuat = Mock(return_value=self.hasil)

        self.store.proses(
            "transaksi-2001",
            "request-001",
            self.transaksi,
            pembuat,
        )

        transaksi_berbeda = {
            **self.transaksi,
            "TX_AMOUNT": 999.0,
        }

        with self.assertRaises(IdempotencyConflict):
            self.store.proses(
                "transaksi-2001",
                "request-002",
                transaksi_berbeda,
                pembuat,
            )

        pembuat.assert_called_once_with()

        self.assertIsNone(
            self.store.cari("request-002")
        )

    def test_kegagalan_tidak_mengunci_kunci_selamanya(self):
        pembuat_gagal = Mock(
            side_effect=RuntimeError("simulasi kegagalan")
        )

        with self.assertRaises(RuntimeError):
            self.store.proses(
                "transaksi-2001",
                "request-001",
                self.transaksi,
                pembuat_gagal,
            )

        self.assertIsNone(
            self.store.cari("request-001")
        )

        pembuat_berhasil = Mock(return_value=self.hasil)

        hasil = self.store.proses(
            "transaksi-2001",
            "request-002",
            self.transaksi,
            pembuat_berhasil,
        )

        pembuat_berhasil.assert_called_once_with()
        self.assertFalse(hasil["replayed"])

    def test_dua_request_bersamaan_hanya_membuat_satu_hasil(self):
        pembuat = Mock(return_value=self.hasil)
        gerbang = Barrier(2)

        def kirim(request_id):
            # Kedua pekerja mulai mencoba hampir bersamaan.
            gerbang.wait(timeout=10)

            return self.store.proses(
                "transaksi-2001",
                request_id,
                self.transaksi,
                pembuat,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            hasil = list(
                executor.map(
                    kirim,
                    ["request-001", "request-002"],
                )
            )

        pembuat.assert_called_once_with()

        self.assertEqual(
            sorted(item["replayed"] for item in hasil),
            [False, True],
        )

        self.assertEqual(
            hasil[0]["original_request_id"],
            hasil[1]["original_request_id"],
        )

        jumlah_catatan = sum(
            self.store.cari(request_id) is not None
            for request_id in [
                "request-001",
                "request-002",
            ]
        )

        self.assertEqual(jumlah_catatan, 1)


if __name__ == "__main__":
    unittest.main()