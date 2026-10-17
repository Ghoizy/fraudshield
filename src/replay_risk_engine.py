import hashlib
import json
from datetime import datetime, timezone
from math import isclose, isfinite
from pathlib import Path
from time import perf_counter

import pandas as pd

from risk_engine import RiskEngine


project_root = Path(__file__).resolve().parent.parent

test_path = project_root / "data/processed/history_v1/test.pkl"
predictions_path = (
    project_root / "data/processed/frozen_v1/test_predictions.pkl"
)
evaluation_path = (
    project_root / "reports/frozen_v1/test_evaluation.json"
)
selection_path = project_root / "models/frozen_v1/selection.json"

output_path = (
    project_root / "reports/frozen_v1/risk_engine_replay.json"
)


def hitung_hash(lokasi_file):
    """Membuat sidik jari isi file."""
    pemeriksa = hashlib.sha256()

    with lokasi_file.open("rb") as file:
        for potongan in iter(lambda: file.read(1024 * 1024), b""):
            pemeriksa.update(potongan)

    return pemeriksa.hexdigest()


def main():
    # 1. Pastikan semua file yang diperlukan tersedia.
    for lokasi in [
        test_path,
        predictions_path,
        evaluation_path,
        selection_path,
    ]:
        if not lokasi.is_file():
            raise FileNotFoundError(
                f"File belum tersedia: {lokasi}"
            )

    with evaluation_path.open("r", encoding="utf-8") as file:
        laporan_evaluasi = json.load(file)

    # 2. Pastikan file masih sama dengan saat evaluasi.
    pemeriksaan_file = [
        (test_path, "test_data_sha256"),
        (predictions_path, "predictions_sha256"),
        (selection_path, "selection_sha256"),
    ]

    for lokasi, nama_hash in pemeriksaan_file:
        hash_sekarang = hitung_hash(lokasi)
        hash_acuan = laporan_evaluasi[nama_hash]

        if hash_sekarang != hash_acuan:
            raise ValueError(
                f"Isi file berubah sejak evaluasi: {lokasi.name}"
            )

    # 3. Baca data test dan prediksi acuan.
    data_test = pd.read_pickle(test_path)

    X_test = data_test["X"].reset_index(drop=True)
    metadata = data_test["metadata"].reset_index(drop=True)

    prediksi_acuan = pd.read_pickle(predictions_path)

    jumlah_transaksi = len(metadata)

    if jumlah_transaksi == 0:
        raise ValueError("Data test kosong.")

    if not (
        len(X_test)
        == jumlah_transaksi
        == len(prediksi_acuan)
    ):
        raise ValueError(
            "Jumlah baris data test dan prediksi acuan berbeda."
        )

    if metadata["TRANSACTION_ID"].duplicated().any():
        raise ValueError("Ada ID transaksi berulang pada data test.")

    if prediksi_acuan["TRANSACTION_ID"].duplicated().any():
        raise ValueError("Ada ID berulang pada prediksi acuan.")

    id_test = set(metadata["TRANSACTION_ID"])
    id_acuan = set(prediksi_acuan["TRANSACTION_ID"])

    if id_test != id_acuan:
        raise ValueError(
            "ID transaksi data test dan prediksi acuan berbeda."
        )

    # Gunakan ID untuk memasangkan transaksi dengan hasil acuan.
    acuan_per_id = prediksi_acuan.set_index("TRANSACTION_ID")

    # Model dimuat sekali, kemudian digunakan berulang.
    engine = RiskEngine()

    jumlah_skor_berbeda = 0
    jumlah_keputusan_berbeda = 0
    selisih_skor_terbesar = 0.0
    contoh_perbedaan = []

    waktu_mulai = perf_counter()

    print(f"Memeriksa {jumlah_transaksi:,} transaksi...")
    print("Model dimuat sekali. Transaksi diproses satu per satu.")

    # 4. Jalankan seluruh transaksi melalui RiskEngine.
    for posisi in range(jumlah_transaksi):
        baris_metadata = metadata.iloc[posisi]
        baris_fitur = X_test.iloc[posisi]

        transaksi = {
            "TRANSACTION_ID": int(
                baris_metadata["TRANSACTION_ID"]
            ),
            "TX_DATETIME": pd.Timestamp(
                baris_metadata["TX_DATETIME"]
            ).isoformat(),
            "TX_AMOUNT": float(baris_fitur["TX_AMOUNT"]),
        }

        hasil = engine.score(transaksi)

        transaction_id = transaksi["TRANSACTION_ID"]
        acuan = acuan_per_id.loc[transaction_id]

        skor_engine = float(hasil["risk_score"])
        skor_acuan = float(acuan["risk_score"])

        if not (
            isfinite(skor_engine)
            and isfinite(skor_acuan)
            and 0 <= skor_engine <= 1
            and 0 <= skor_acuan <= 1
        ):
            raise ValueError(
                f"Skor tidak valid untuk transaksi {transaction_id}."
            )

        if hasil["transaction_id"] != transaction_id:
            raise ValueError(
                f"Engine mengembalikan ID yang salah: {transaction_id}"
            )

        skor_cocok = isclose(
            skor_engine,
            skor_acuan,
            rel_tol=1e-10,
            abs_tol=1e-12,
        )

        keputusan_cocok = (
            hasil["decision"] == acuan["decision"]
        )

        selisih = abs(skor_engine - skor_acuan)
        selisih_skor_terbesar = max(
            selisih_skor_terbesar,
            selisih,
        )

        if not skor_cocok:
            jumlah_skor_berbeda += 1

        if not keputusan_cocok:
            jumlah_keputusan_berbeda += 1

        if (
            not skor_cocok or not keputusan_cocok
        ) and len(contoh_perbedaan) < 5:
            contoh_perbedaan.append({
                "transaction_id": transaction_id,
                "skor_engine": skor_engine,
                "skor_acuan": skor_acuan,
                "keputusan_engine": hasil["decision"],
                "keputusan_acuan": str(acuan["decision"]),
            })

        sudah_diperiksa = posisi + 1

        if (
            sudah_diperiksa % 1000 == 0
            or sudah_diperiksa == jumlah_transaksi
        ):
            print(
                f"Progres: {sudah_diperiksa:,}"
                f"/{jumlah_transaksi:,} transaksi"
            )

    # 5. Simpan ringkasan, termasuk jika ditemukan perbedaan.
    durasi = perf_counter() - waktu_mulai

    lulus = (
        jumlah_skor_berbeda == 0
        and jumlah_keputusan_berbeda == 0
    )

    laporan = {
        "status": "PASS" if lulus else "FAIL",
        "checked_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "model_version": engine.model_version,
        "policy_version": engine.policy_version,
        "threshold": engine.threshold,
        "jumlah_transaksi": jumlah_transaksi,
        "jumlah_skor_berbeda": jumlah_skor_berbeda,
        "jumlah_keputusan_berbeda": jumlah_keputusan_berbeda,
        "selisih_skor_terbesar": selisih_skor_terbesar,
        "durasi_detik": round(durasi, 3),
        "score_tolerance": {
            "relative": 1e-10,
            "absolute": 1e-12,
        },
        "test_data_sha256": hitung_hash(test_path),
        "predictions_sha256": hitung_hash(predictions_path),
        "selection_sha256": hitung_hash(selection_path),
        "risk_engine_code_sha256": hitung_hash(
            project_root / "src/risk_engine.py"
        ),
        "contoh_perbedaan": contoh_perbedaan,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            laporan,
            file,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )

    print("\nHASIL PEMERIKSAAN KONSISTENSI")
    print(f"Jumlah transaksi: {jumlah_transaksi:,}")
    print(f"Skor berbeda: {jumlah_skor_berbeda}")
    print(f"Keputusan berbeda: {jumlah_keputusan_berbeda}")
    print(f"Selisih skor terbesar: {selisih_skor_terbesar:.12g}")
    print(f"Durasi: {durasi:.2f} detik")
    print(f"Laporan disimpan: {output_path}")

    if not lulus:
        print("\nCONTOH PERBEDAAN")
        print(json.dumps(contoh_perbedaan, indent=2))

        raise SystemExit(
            "PEMERIKSAAN GAGAL: ada hasil yang berbeda."
        )

    print("\nPEMERIKSAAN LULUS: seluruh hasil konsisten.")


if __name__ == "__main__":
    main()