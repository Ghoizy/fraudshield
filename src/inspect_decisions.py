import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path


project_root = Path(__file__).resolve().parent.parent

db_path = (
    project_root / "data" / "runtime" / "fraudshield.db"
)


def main():
    parser = argparse.ArgumentParser(
        description="Membaca riwayat keputusan FraudShield."
    )

    parser.add_argument(
        "--request-id",
        help="ID permintaan tertentu yang ingin diperiksa.",
    )

    args = parser.parse_args()

    if not db_path.is_file():
        raise SystemExit(
            "Database belum tersedia. "
            "Jalankan server API terlebih dahulu."
        )

    # Buka dalam mode baca saja.
    # Script ini tidak membuat atau mengubah catatan.
    database_uri = db_path.resolve().as_uri() + "?mode=ro"

    with closing(
        sqlite3.connect(database_uri, uri=True)
    ) as connection:
        connection.row_factory = sqlite3.Row

        jumlah_catatan = connection.execute(
            "SELECT COUNT(*) FROM decisions"
        ).fetchone()[0]

        if args.request_id:
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
                (args.request_id,),
            ).fetchall()

        else:
            baris = connection.execute(
                """
                SELECT
                    request_id,
                    created_at_utc,
                    transaction_json,
                    result_json
                FROM decisions
                ORDER BY created_at_utc DESC, request_id DESC
                LIMIT 5
                """
            ).fetchall()

    print(f"Database: {db_path}")
    print(f"Jumlah seluruh catatan: {jumlah_catatan}")

    if not baris:
        print("\nTidak ada catatan yang cocok.")
        return

    print(f"\nMenampilkan {len(baris)} catatan:")

    for nomor, item in enumerate(baris, start=1):
        catatan = {
            "request_id": item["request_id"],
            "created_at_utc": item["created_at_utc"],
            "transaksi": json.loads(
                item["transaction_json"]
            ),
            "hasil": json.loads(
                item["result_json"]
            ),
        }

        print(f"\nCATATAN {nomor}")
        print(
            json.dumps(
                catatan,
                indent=2,
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()