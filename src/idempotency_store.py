import hashlib
import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from decision_store import DecisionStore


class IdempotencyConflict(ValueError):
    """Kunci yang sama digunakan untuk input yang berbeda."""


class IdempotencyStore(DecisionStore):
    def __init__(self, db_path):
        # Siapkan tabel decisions dari modul sebelumnya.
        super().__init__(db_path)

        # Tambahkan tabel penghubung kunci dengan keputusan.
        with closing(self._connect_idempotency()) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS idempotency_keys (
                        idempotency_key TEXT PRIMARY KEY NOT NULL,
                        input_hash TEXT NOT NULL,
                        original_request_id TEXT NOT NULL,
                        FOREIGN KEY (original_request_id)
                            REFERENCES decisions(request_id)
                    )
                    """
                )

    def _connect_idempotency(self):
        # Transaksi akan dimulai secara eksplisit saat diperlukan.
        connection = sqlite3.connect(
            self.db_path,
            timeout=10,
            autocommit=sqlite3.LEGACY_TRANSACTION_CONTROL,
            isolation_level="DEFERRED",
        )

        connection.execute("PRAGMA foreign_keys = ON")

        return connection

    def proses(
        self,
        idempotency_key,
        request_id,
        transaksi,
        buat_hasil,
    ):
        """
        transaksi harus sudah lolos validasi input API.
        buat_hasil adalah fungsi tanpa argumen yang menghasilkan
        dictionary hasil prediksi yang sudah divalidasi.
        """
        if (
            not isinstance(idempotency_key, str)
            or re.fullmatch(
                r"[A-Za-z0-9._:-]{1,128}",
                idempotency_key,
            ) is None
        ):
            raise ValueError(
                "Kunci harus berisi 1–128 karakter: "
                "huruf, angka, titik, garis bawah, titik dua, "
                "atau tanda minus."
            )

        if not isinstance(request_id, str) or not request_id.strip():
            raise ValueError("request_id harus terisi.")

        # Input API sudah menormalkan tipe angka dan waktu.
        # sort_keys membuat urutan nama kolom tidak memengaruhi hash.
        transaksi_json = json.dumps(
            transaksi,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

        input_hash = hashlib.sha256(
            transaksi_json.encode("utf-8")
        ).hexdigest()

        with closing(self._connect_idempotency()) as connection:
            with connection:
                # Ambil giliran menulis sebelum memeriksa kunci.
                connection.execute("BEGIN IMMEDIATE")

                tersimpan = connection.execute(
                    """
                    SELECT
                        k.input_hash,
                        k.original_request_id,
                        d.result_json
                    FROM idempotency_keys AS k
                    JOIN decisions AS d
                        ON d.request_id = k.original_request_id
                    WHERE k.idempotency_key = ?
                    """,
                    (idempotency_key,),
                ).fetchone()

                if tersimpan is not None:
                    if tersimpan[0] != input_hash:
                        raise IdempotencyConflict(
                            "Kunci sudah digunakan untuk input berbeda."
                        )

                    return {
                        "hasil": json.loads(tersimpan[2]),
                        "replayed": True,
                        "original_request_id": tersimpan[1],
                    }

                # Fungsi ini hanya dipanggil untuk kunci baru.
                hasil = buat_hasil()

                if hasil["transaction_id"] != transaksi["TRANSACTION_ID"]:
                    raise ValueError(
                        "ID transaksi input dan hasil tidak cocok."
                    )

                hasil_json = json.dumps(
                    hasil,
                    ensure_ascii=False,
                    allow_nan=False,
                )

                waktu_simpan = datetime.now(
                    timezone.utc
                ).isoformat()

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

                connection.execute(
                    """
                    INSERT INTO idempotency_keys (
                        idempotency_key,
                        input_hash,
                        original_request_id
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        idempotency_key,
                        input_hash,
                        request_id,
                    ),
                )

                return {
                    "hasil": hasil,
                    "replayed": False,
                    "original_request_id": request_id,
                }