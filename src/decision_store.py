import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


class DecisionStore:
    def __init__(self, db_path):
        self.db_path = Path(db_path)

        # Buat folder penyimpanan jika belum tersedia.
        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # Buat tabel jika database belum memiliki tabel tersebut.
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS decisions (
                        request_id TEXT PRIMARY KEY NOT NULL,
                        transaction_id TEXT NOT NULL,
                        created_at_utc TEXT NOT NULL,
                        transaction_json TEXT NOT NULL,
                        result_json TEXT NOT NULL
                    )
                    """
                )

    def _connect(self):
        # Setiap operasi menggunakan koneksinya sendiri.
        return sqlite3.connect(
            self.db_path,
            timeout=10,
            autocommit=False,
        )

    def simpan(self, request_id, transaksi, hasil):
        if not isinstance(request_id, str) or not request_id.strip():
            raise ValueError("request_id harus berupa teks yang terisi.")

        if transaksi["TRANSACTION_ID"] != hasil["transaction_id"]:
            raise ValueError(
                "ID transaksi pada input dan hasil tidak cocok."
            )

        waktu_simpan = datetime.now(
            timezone.utc
        ).isoformat()

        # Ubah dictionary menjadi teks JSON untuk disimpan.
        transaksi_json = json.dumps(
            transaksi,
            ensure_ascii=False,
            allow_nan=False,
        )

        hasil_json = json.dumps(
            hasil,
            ensure_ascii=False,
            allow_nan=False,
        )

        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO decisions (
                        request_id,
                        transaction_id,
                        created_at_utc,
                        transaction_json,
                        result_json
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        request_id,
                        str(transaksi["TRANSACTION_ID"]),
                        waktu_simpan,
                        transaksi_json,
                        hasil_json,
                    ),
                )

    def cari(self, request_id):
        with closing(self._connect()) as connection:
            baris = connection.execute(
                """
                SELECT
                    request_id,
                    created_at_utc,
                    transaction_json,
                    result_json
                FROM decisions
                WHERE request_id = ?
                """,
                (request_id,),
            ).fetchone()

        if baris is None:
            return None

        return {
            "request_id": baris[0],
            "created_at_utc": baris[1],
            "transaksi": json.loads(baris[2]),
            "hasil": json.loads(baris[3]),
        }