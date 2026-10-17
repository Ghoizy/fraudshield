import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from fastapi.testclient import TestClient


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from api import create_app


class TestAPILogging(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Database sementara khusus kelompok tes ini.
        folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(folder.cleanup)

        db_path = Path(folder.name) / "test.db"

        cls.app = create_app(db_path=db_path)

        cls.client = cls.enterClassContext(
            TestClient(cls.app)
        )

        cls.engine = cls.app.state.engine

    def setUp(self):
        self.transaksi = {
            "TRANSACTION_ID": 100,
            "TX_DATETIME": "2018-05-01T10:00:00",
            "TX_AMOUNT": 75.0,
        }

    def test_header_dan_log_saling_cocok(self):
        # Tangkap catatan yang ditulis aplikasi.
        with self.assertLogs(
            "uvicorn.error",
            level="INFO",
        ) as rekaman:
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

        # Pastikan ID memiliki format UUID yang benar.
        self.assertEqual(
            str(UUID(request_id)),
            request_id,
        )

        waktu_header = float(
            response.headers["X-Process-Time-Ms"]
        )

        self.assertGreaterEqual(waktu_header, 0)

        catatan_request = []

        for record in rekaman.records:
            try:
                isi = json.loads(record.getMessage())
            except json.JSONDecodeError:
                continue

            if (
                isinstance(isi, dict)
                and isi.get("event") == "request_completed"
            ):
                catatan_request.append(isi)

        self.assertEqual(len(catatan_request), 1)

        catatan = catatan_request[0]

        self.assertEqual(
            catatan["request_id"],
            request_id,
        )

        self.assertEqual(catatan["status_code"], 200)
        self.assertEqual(catatan["endpoint"], "/predict")

        self.assertEqual(
            catatan["duration_ms"],
            waktu_header,
        )

    def test_setiap_request_memiliki_id_berbeda(self):
        pertama = self.client.get("/health")
        kedua = self.client.get("/health")

        self.assertEqual(pertama.status_code, 200)
        self.assertEqual(kedua.status_code, 200)

        self.assertNotEqual(
            pertama.headers["X-Request-ID"],
            kedua.headers["X-Request-ID"],
        )

    def test_input_ditolak_tetap_memiliki_request_id(self):
        transaksi = {
            **self.transaksi,
            "TX_AMOUNT": -10.0,
        }

        response = self.client.post(
            "/predict",
            json=transaksi,
        )

        self.assertEqual(
            response.status_code,
            422,
            response.text,
        )

        self.assertIn(
            "X-Request-ID",
            response.headers,
        )

    def test_error_tak_terduga_tetap_bisa_dilacak(self):
        with patch.object(
            self.engine,
            "score",
            side_effect=RuntimeError(
                "detail internal simulasi"
            ),
        ):
            with self.assertLogs(
                "uvicorn.error",
                level="ERROR",
            ) as rekaman:
                response = self.client.post(
                    "/predict",
                    json=self.transaksi,
                )

        self.assertEqual(
            response.status_code,
            500,
            response.text,
        )

        self.assertIn(
            "X-Request-ID",
            response.headers,
        )

        # Pengguna mendapat pesan umum, bukan detail internal.
        self.assertEqual(
            response.json(),
            {
                "detail": (
                    "Terjadi kesalahan internal pada layanan."
                )
            },
        )

        catatan = json.loads(
            rekaman.records[-1].getMessage()
        )

        self.assertEqual(
            catatan["request_id"],
            response.headers["X-Request-ID"],
        )

        self.assertEqual(catatan["status_code"], 500)

        self.assertEqual(
            catatan["error_type"],
            "RuntimeError",
        )


if __name__ == "__main__":
    unittest.main()