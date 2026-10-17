import json
from math import isfinite
from pathlib import Path

import pandas as pd


# =========================================================
# 1. LOKASI LAPORAN
# =========================================================

project_root = Path(__file__).resolve().parent.parent
report_dir = project_root / "reports" / "history_v1"

sumber_laporan = {
    "logistic": report_dir / "logistic_thresholds_validation.json",
    "tree": report_dir / "tree_thresholds_validation.json",
}

kapasitas_harian = 100
threshold_diharapkan = {
    0.5,
    0.2,
    0.1,
    0.05,
    0.02,
    0.01,
    0.005,
}

semua_hasil = []


# =========================================================
# 2. MEMBACA DAN MEMERIKSA LAPORAN
# =========================================================

for algoritma, lokasi_file in sumber_laporan.items():
    if not lokasi_file.is_file():
        raise FileNotFoundError(
            f"Laporan belum tersedia: {lokasi_file}"
        )

    with lokasi_file.open("r", encoding="utf-8") as file:
        laporan = json.load(file)

    if laporan["evaluation_split"] != "validation":
        raise ValueError(
            f"Laporan {algoritma} bukan evaluasi validation."
        )

    if (
        laporan["validation_start"] != "2018-04-19"
        or laporan["validation_end_exclusive"] != "2018-04-25"
    ):
        raise ValueError(
            f"Periode validation {algoritma} tidak sesuai."
        )

    if laporan["daily_review_capacity"] != kapasitas_harian:
        raise ValueError(
            f"Asumsi kapasitas {algoritma} berbeda."
        )

    pasangan_ditemukan = set()

    for baris in laporan["results"]:
        nama_fitur = baris["model"]
        threshold = float(baris["threshold"])

        pasangan = (nama_fitur, threshold)

        if pasangan in pasangan_ditemukan:
            raise ValueError(
                f"Hasil berulang pada {algoritma}: {pasangan}"
            )

        pasangan_ditemukan.add(pasangan)

        for metrik in ["precision", "recall", "ap_validation"]:
            nilai = float(baris[metrik])

            if not isfinite(nilai) or not 0 <= nilai <= 1:
                raise ValueError(
                    f"Metrik {metrik} tidak valid pada {algoritma}."
                )

        memenuhi_kapasitas = (
            int(baris["max_review_harian"]) <= kapasitas_harian
            and int(baris["hari_melebihi_100"]) == 0
        )

        semua_hasil.append({
            "candidate": f"{algoritma}_{nama_fitur}",
            "algorithm": algoritma,
            "feature_set": nama_fitur,
            "threshold": threshold,
            "ap_validation": float(baris["ap_validation"]),
            "precision": float(baris["precision"]),
            "recall": float(baris["recall"]),
            "tp": int(baris["tp"]),
            "fp": int(baris["fp"]),
            "fn": int(baris["fn"]),
            "total_review": int(baris["total_review"]),
            "max_review_harian": int(baris["max_review_harian"]),
            "hari_melebihi_100": int(baris["hari_melebihi_100"]),
            "memenuhi_kapasitas": memenuhi_kapasitas,
        })

    pasangan_diharapkan = {
        (nama_fitur, threshold)
        for nama_fitur in ["basic", "history"]
        for threshold in threshold_diharapkan
    }

    if pasangan_ditemukan != pasangan_diharapkan:
        raise ValueError(
            f"Daftar model atau threshold {algoritma} tidak lengkap."
        )


# Memeriksa kesamaan jumlah fraud sebagai pemeriksaan dasar.
jumlah_fraud = {
    baris["tp"] + baris["fn"]
    for baris in semua_hasil
}

if len(jumlah_fraud) != 1:
    raise ValueError(
        "Jumlah fraud berbeda antarhasil. "
        "Periksa apakah eksperimen memakai validation yang sama."
    )


# =========================================================
# 3. MENYARING DAN MENGURUTKAN PILIHAN
# =========================================================

pilihan_lolos = [
    baris
    for baris in semua_hasil
    if baris["memenuhi_kapasitas"]
]

pilihan_lolos.sort(
    key=lambda baris: (
        -baris["recall"],
        baris["fp"],
        -baris["ap_validation"],
        baris["candidate"],
        -baris["threshold"],
    )
)


# =========================================================
# 4. MENGAMBIL THRESHOLD TERBAIK PER KANDIDAT
# =========================================================

terbaik_per_kandidat = {}

for baris in pilihan_lolos:
    nama = baris["candidate"]

    if nama not in terbaik_per_kandidat:
        terbaik_per_kandidat[nama] = baris

ringkasan = list(terbaik_per_kandidat.values())

print("\nTHRESHOLD TERBAIK PER KANDIDAT")
print("Syarat: setiap hari validation maksimal 100 review.")

if ringkasan:
    kolom_tampil = [
        "candidate",
        "threshold",
        "ap_validation",
        "precision",
        "recall",
        "tp",
        "fp",
        "fn",
        "max_review_harian",
    ]

    print(
        pd.DataFrame(ringkasan)[kolom_tampil].to_string(
            index=False,
            float_format=lambda angka: f"{angka:.4f}",
        )
    )
else:
    print("Tidak ada kandidat yang memenuhi kapasitas.")

semua_nama = sorted({
    baris["candidate"]
    for baris in semua_hasil
})

for nama in semua_nama:
    if nama not in terbaik_per_kandidat:
        print(
            f"\n{nama}: tidak memiliki threshold "
            "yang memenuhi kapasitas dalam daftar percobaan."
        )


# =========================================================
# 5. MENAMPILKAN REKOMENDASI
# =========================================================

rekomendasi = pilihan_lolos[0] if pilihan_lolos else None

print("\nREKOMENDASI BERDASARKAN VALIDATION")

if rekomendasi is None:
    print("Belum tersedia. Jangan lanjut ke evaluasi test.")
else:
    print(f"Kandidat: {rekomendasi['candidate']}")
    print(f"Threshold: {rekomendasi['threshold']}")
    print(f"Recall: {rekomendasi['recall']:.4f}")
    print(f"Precision: {rekomendasi['precision']:.4f}")
    print(f"Fraud tertangkap: {rekomendasi['tp']}")
    print(f"Transaksi normal ikut ditandai: {rekomendasi['fp']}")
    print(f"Fraud belum tertangkap: {rekomendasi['fn']}")
    print(
        "Review harian tertinggi: "
        f"{rekomendasi['max_review_harian']}"
    )

    if rekomendasi["tp"] == 0:
        print(
            "CATATAN: kandidat ini belum menangkap fraud "
            "pada threshold yang memenuhi kapasitas."
        )


# =========================================================
# 6. MENYIMPAN LAPORAN PERBANDINGAN
# =========================================================

output = {
    "status": "recommendation_only",
    "evaluation_split": "validation",
    "validation_start": "2018-04-19",
    "validation_end_exclusive": "2018-04-25",
    "daily_review_capacity": kapasitas_harian,
    "selection_order": [
        "Meet daily review capacity",
        "Highest recall",
        "Lowest false positives",
        "Highest validation average precision",
        "Candidate name ascending",
        "Highest threshold",
    ],
    "all_results": semua_hasil,
    "best_per_candidate": ringkasan,
    "recommendation": rekomendasi,
}

report_dir.mkdir(parents=True, exist_ok=True)

output_path = report_dir / "model_comparison_validation.json"

with output_path.open("w", encoding="utf-8") as file:
    json.dump(
        output,
        file,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
    )

print(f"\nLaporan tersimpan: {output_path}")
print("\nPERBANDINGAN MODEL SELESAI")