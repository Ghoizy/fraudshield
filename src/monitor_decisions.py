import json
import sqlite3
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def main():
    project_root = Path(__file__).resolve().parent.parent
    db_path = project_root / "data" / "runtime" / "fraudshield.db"

    if not db_path.is_file():
        raise SystemExit(
            f"Database belum ditemukan: {db_path}\n"
            "Pastikan API pernah menyimpan hasil penilaian."
        )

    # Buka database dalam mode hanya-baca.
    database_uri = db_path.resolve().as_uri() + "?mode=ro"

    with closing(
        sqlite3.connect(database_uri, uri=True, timeout=10)
    ) as connection:
        connection.row_factory = sqlite3.Row

        catatan = connection.execute(
            """
            SELECT
                request_id,
                transaction_id,
                created_at_utc,
                result_json
            FROM decisions
            ORDER BY created_at_utc, request_id
            """
        ).fetchall()

    print("MONITORING KEPUTUSAN FRAUDSHIELD")
    print(f"Database: {db_path}")
    print("Cakupan: seluruh catatan keputusan yang tersimpan")

    if not catatan:
        print("\nBelum ada catatan keputusan.")
        return

    jumlah_keputusan = Counter()
    ringkasan_harian = defaultdict(Counter)
    id_transaksi_unik = set()

    for baris in catatan:
        hasil = json.loads(baris["result_json"])
        keputusan = hasil.get("decision")

        if keputusan not in {"ALLOW", "REVIEW"}:
            raise ValueError(
                f"Keputusan tidak dikenali pada request "
                f"{baris['request_id']}: {keputusan!r}"
            )

        waktu = datetime.fromisoformat(baris["created_at_utc"])

        if waktu.tzinfo is None:
            raise ValueError(
                f"Waktu penyimpanan tidak memiliki zona waktu "
                f"pada request {baris['request_id']}"
            )

        tanggal = waktu.astimezone(timezone.utc).date().isoformat()

        jumlah_keputusan[keputusan] += 1
        ringkasan_harian[tanggal][keputusan] += 1
        id_transaksi_unik.add(baris["transaction_id"])

    total = len(catatan)
    jumlah_allow = jumlah_keputusan["ALLOW"]
    jumlah_review = jumlah_keputusan["REVIEW"]
    persentase_review = jumlah_review / total * 100

    print("\nRINGKASAN KESELURUHAN")
    print(f"Jumlah catatan keputusan: {total}")
    print(f"Jumlah ID transaksi unik: {len(id_transaksi_unik)}")
    print(f"Jumlah ALLOW: {jumlah_allow}")
    print(f"Jumlah REVIEW: {jumlah_review}")
    print(f"Persentase REVIEW: {persentase_review:.2f}%")

    print("\nRINCIAN BERDASARKAN TANGGAL PENYIMPANAN (UTC)")
    print(f"{'Tanggal':<12} {'Total':>8} {'ALLOW':>8} {'REVIEW':>8}")

    for tanggal, hitungan in sorted(ringkasan_harian.items()):
        allow = hitungan["ALLOW"]
        review = hitungan["REVIEW"]
        total_harian = allow + review

        print(
            f"{tanggal:<12} "
            f"{total_harian:>8} "
            f"{allow:>8} "
            f"{review:>8}"
        )


if __name__ == "__main__":
    main()