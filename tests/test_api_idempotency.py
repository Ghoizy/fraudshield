import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from api import create_app


class TestAPIIdempotency(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)

        db_path = Path(folder.name) / "test.db"

        self.app = create_app(db_path=db_path)

        self.client = self.enterContext(
            TestClient(self.app)
        )

        self.engine = self.app.state.engine
        self.store = self.app.state.store

        self.transaksi = {
            "TRANSACTION_ID": 3001,
            "TX_DATETIME": "2018-05-01T10:00:00",
            "TX_AMOUNT": 75.0,
        }

        self.headers = {
            "Idempotency-Key": "transaksi-3001-v1",
        }

    def test_pengulangan_tidak_menjalankan_model_lagi(self):
        with patch.object(
            self.engine,
            "score",
            wraps=self.engine.score,
        ) as mock_score:
            pertama = self.client.post(
                "/predict",
                json=self.transaksi,
                headers=self.headers,
            )

            kedua = self.client.post(
                "/predict",
                json=self.transaksi,
                headers=self.headers,
            )

        self.assertEqual(
            pertama.status_code,
            200,
            pertama.text,
        )

        self.assertEqual(
            kedua.status_code,
            200,
            kedua.text,
        )

        mock_score.assert_called_once_with(self.transaksi)

        self.assertEqual(
            pertama.json(),
            kedua.json(),
        )

        self.assertEqual(
            pertama.headers["X-Idempotent-Replay"],
            "false",
        )

        self.assertEqual(
            kedua.headers["X-Idempotent-Replay"],
            "true",
        )

        id_pertama = pertama.headers["X-Request-ID"]
        id_kedua = kedua.headers["X-Request-ID"]

        self.assertNotEqual(id_pertama, id_kedua)

        self.assertEqual(
            kedua.headers["X-Original-Request-ID"],
            id_pertama,
        )

        self.assertIsNotNone(self.store.cari(id_pertama))
        self.assertIsNone(self.store.cari(id_kedua))

    def test_kunci_sama_input_berbeda_menghasilkan_409(self):
        pertama = self.client.post(
            "/predict",
            json=self.transaksi,
            headers=self.headers,
        )

        self.assertEqual(
            pertama.status_code,
            200,
            pertama.text,
        )

        transaksi_berbeda = {
            **self.transaksi,
            "TX_AMOUNT": 999.0,
        }

        with patch.object(
            self.engine,
            "score",
        ) as mock_score:
            kedua = self.client.post(
                "/predict",
                json=transaksi_berbeda,
                headers=self.headers,
            )

        self.assertEqual(
            kedua.status_code,
            409,
            kedua.text,
        )

        mock_score.assert_not_called()

        self.assertIsNone(
            self.store.cari(
                kedua.headers["X-Request-ID"]
            )
        )

    def test_format_kunci_salah_ditolak(self):
        with patch.object(
            self.engine,
            "score",
        ) as mock_score:
            response = self.client.post(
                "/predict",
                json=self.transaksi,
                headers={
                    "Idempotency-Key": "kunci pakai spasi",
                },
            )

        self.assertEqual(
            response.status_code,
            422,
            response.text,
        )

        mock_score.assert_not_called()

    def test_kunci_berbeda_membuat_penilaian_baru(self):
        pertama = self.client.post(
            "/predict",
            json=self.transaksi,
            headers={
                "Idempotency-Key": "operasi-pertama",
            },
        )

        kedua = self.client.post(
            "/predict",
            json=self.transaksi,
            headers={
                "Idempotency-Key": "operasi-kedua",
            },
        )

        for response in [pertama, kedua]:
            self.assertEqual(
                response.status_code,
                200,
                response.text,
            )

            self.assertEqual(
                response.headers["X-Idempotent-Replay"],
                "false",
            )

            self.assertIsNotNone(
                self.store.cari(
                    response.headers["X-Request-ID"]
                )
            )

        self.assertNotEqual(
            pertama.headers["X-Original-Request-ID"],
            kedua.headers["X-Original-Request-ID"],
        )


if __name__ == "__main__":
    unittest.main()