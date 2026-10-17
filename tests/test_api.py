import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from api import create_app


class TestFraudShieldAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Database sementara khusus kelompok tes ini.
        folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(folder.cleanup)

        db_path = Path(folder.name) / "test.db"

        cls.app = create_app(db_path=db_path)

        # Memulai aplikasi beserta engine dan penyimpanannya.
        cls.client = cls.enterClassContext(
            TestClient(cls.app)
        )

        cls.engine = cls.app.state.engine

    def setUp(self):
        # Setiap tes mendapat contoh transaksi baru.
        self.transaksi = {
            "TRANSACTION_ID": 100,
            "TX_DATETIME": "2018-05-01T10:00:00",
            "TX_AMOUNT": 75.0,
        }

    def periksa_penolakan(self, transaksi, nama_kolom):
        # Input salah harus ditolak sebelum engine dipanggil.
        with patch.object(self.engine, "score") as mock_score:
            response = self.client.post(
                "/predict",
                json=transaksi,
            )

            self.assertEqual(
                response.status_code,
                422,
                response.text,
            )

            mock_score.assert_not_called()

        lokasi_error = [
            item["loc"]
            for item in response.json()["detail"]
        ]

        self.assertIn(
            ["body", nama_kolom],
            lokasi_error,
        )

    def test_health(self):
        response = self.client.get("/health")

        self.assertEqual(
            response.status_code,
            200,
            response.text,
        )

        hasil = response.json()

        self.assertEqual(hasil["status"], "ready")

        self.assertEqual(
            hasil["model_version"],
            self.engine.model_version,
        )

        self.assertEqual(
            hasil["policy_version"],
            self.engine.policy_version,
        )

    def test_prediksi_sesuai_engine(self):
        # Bandingkan hasil API dengan engine langsung.
        acuan = self.engine.score(self.transaksi)

        response = self.client.post(
            "/predict",
            json=self.transaksi,
        )

        self.assertEqual(
            response.status_code,
            200,
            response.text,
        )

        self.assertEqual(response.json(), acuan)

    def test_nominal_nol_diterima(self):
        transaksi = {
            **self.transaksi,
            "TX_AMOUNT": 0.0,
        }

        response = self.client.post(
            "/predict",
            json=transaksi,
        )

        self.assertEqual(
            response.status_code,
            200,
            response.text,
        )

        hasil = response.json()

        self.assertGreaterEqual(hasil["risk_score"], 0)
        self.assertLessEqual(hasil["risk_score"], 1)

        self.assertIn(
            hasil["decision"],
            ["ALLOW", "REVIEW"],
        )

    def test_nilai_dan_tipe_salah_ditolak(self):
        kasus = [
            ("TX_AMOUNT", -10.0),
            ("TX_AMOUNT", "75.0"),
            ("TX_AMOUNT", True),
            ("TX_AMOUNT", None),
            ("TRANSACTION_ID", -1),
            ("TRANSACTION_ID", 1.5),
            ("TRANSACTION_ID", "100"),
            ("TRANSACTION_ID", True),
            ("TRANSACTION_ID", None),
        ]

        for kolom, nilai in kasus:
            with self.subTest(kolom=kolom, nilai=nilai):
                transaksi = {
                    **self.transaksi,
                    kolom: nilai,
                }

                self.periksa_penolakan(
                    transaksi,
                    kolom,
                )

    def test_kolom_wajib_hilang_ditolak(self):
        for kolom in self.transaksi:
            with self.subTest(kolom=kolom):
                transaksi = self.transaksi.copy()
                del transaksi[kolom]

                self.periksa_penolakan(
                    transaksi,
                    kolom,
                )

    def test_kolom_tambahan_ditolak(self):
        kasus = [
            "TX_FRAUD",
            "TX_FRAUD_SCENARIO",
            "KOLOM_TIDAK_DIKENAL",
        ]

        for kolom in kasus:
            with self.subTest(kolom=kolom):
                transaksi = {
                    **self.transaksi,
                    kolom: 1,
                }

                self.periksa_penolakan(
                    transaksi,
                    kolom,
                )

    def test_waktu_tidak_valid_ditolak(self):
        kasus = [
            "bukan-tanggal",
            "2018-02-30T10:00:00",
            "2018-05-01T10:00:00+07:00",
            "",
            None,
            123,
        ]

        for nilai in kasus:
            with self.subTest(waktu=nilai):
                transaksi = {
                    **self.transaksi,
                    "TX_DATETIME": nilai,
                }

                self.periksa_penolakan(
                    transaksi,
                    "TX_DATETIME",
                )

    def test_kegagalan_engine_menghasilkan_500(self):
        # Simulasi kegagalan hanya berlaku dalam blok with.
        with patch.object(
            self.engine,
            "score",
            side_effect=ValueError("simulasi kegagalan"),
        ):
            response = self.client.post(
                "/predict",
                json=self.transaksi,
            )

        self.assertEqual(
            response.status_code,
            500,
            response.text,
        )

        self.assertEqual(
            response.json(),
            {
                "detail": (
                    "Engine gagal menghasilkan penilaian yang valid."
                )
            },
        )


if __name__ == "__main__":
    unittest.main()