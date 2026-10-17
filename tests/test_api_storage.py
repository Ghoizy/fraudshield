import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from api import create_app
from decision_store import DecisionStore


class TestAPIStorage(unittest.TestCase):
    def setUp(self):
        # Setiap tes menggunakan database sementara.
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)

        self.db_path = Path(folder.name) / "test.db"

        self.app = create_app(db_path=self.db_path)

        self.client = self.enterContext(
            TestClient(self.app)
        )

        self.store = self.app.state.store

        self.transaksi = {
            "TRANSACTION_ID": 100,
            "TX_DATETIME": "2018-05-01T10:00:00",
            "TX_AMOUNT": 75.0,
        }

    def test_hasil_api_tersimpan_di_database(self):
        response = self.client.post(
            "/predict",
            json=self.transaksi,
        )

        self.assertEqual(
            response.status_code,
            200,
            response.text,
        )

        request_id = response.headers["X-Request-ID"]

        # Baca hasil melalui koneksi database yang baru.
        pembaca = DecisionStore(self.db_path)
        catatan = pembaca.cari(request_id)

        self.assertIsNotNone(catatan)

        self.assertEqual(
            catatan["request_id"],
            request_id,
        )

        self.assertEqual(
            catatan["transaksi"],
            self.transaksi,
        )

        self.assertEqual(
            catatan["hasil"],
            response.json(),
        )

    def test_input_salah_tidak_disimpan(self):
        transaksi = {
            **self.transaksi,
            "TX_AMOUNT": -10.0,
        }

        with patch.object(
            self.store,
            "simpan",
        ) as mock_simpan:
            response = self.client.post(
                "/predict",
                json=transaksi,
            )

            self.assertEqual(
                response.status_code,
                422,
                response.text,
            )

            # Pastikan fungsi penyimpanan tidak dipanggil.
            mock_simpan.assert_not_called()

        request_id = response.headers["X-Request-ID"]

        self.assertIsNone(
            self.store.cari(request_id)
        )

    def test_database_gagal_menghasilkan_503(self):
        # Simulasikan kegagalan database.
        with patch.object(
            self.store,
            "simpan",
            side_effect=sqlite3.OperationalError(
                "simulasi database tidak tersedia"
            ),
        ):
            response = self.client.post(
                "/predict",
                json=self.transaksi,
            )

        self.assertEqual(
            response.status_code,
            503,
            response.text,
        )

        self.assertEqual(
            response.json(),
            {
                "detail": (
                    "Hasil penilaian gagal disimpan. "
                    "Layanan sementara tidak dapat "
                    "menyelesaikan permintaan."
                )
            },
        )

        request_id = response.headers["X-Request-ID"]

        self.assertIsNone(
            self.store.cari(request_id)
        )


if __name__ == "__main__":
    unittest.main()