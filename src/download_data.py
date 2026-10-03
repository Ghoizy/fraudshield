from datetime import date, timedelta
from pathlib import Path
from urllib.request import urlopen

project_root = Path(__file__).resolve().parent.parent
raw_dir = project_root / "data" / "raw"
raw_dir.mkdir(parents=True, exist_ok=True)

dataset_version = "6e67dbd0a3bfe0d7ec33abc4bce5f37cd4ff0d6a"
base_url = (
    "https://raw.githubusercontent.com/"
    "Fraud-Detection-Handbook/simulated-data-raw/"
    f"{dataset_version}/data"
)

tanggal_awal = date(2018, 4, 1)
jumlah_hari = 30

for urutan in range(jumlah_hari):
    tanggal = tanggal_awal + timedelta(days=urutan)
    nama_file = f"{tanggal}.pkl"
    lokasi_file = raw_dir / nama_file

    if lokasi_file.exists() and lokasi_file.stat().st_size > 0:
        print(f"SUDAH ADA: {nama_file}")
        continue

    url = f"{base_url}/{nama_file}"
    print(f"MENGUNDUH: {nama_file}", flush=True)

    with urlopen(url, timeout=60) as respons:
        isi_file = respons.read()

    lokasi_file.write_bytes(isi_file)
    print(f"TERSIMPAN: {nama_file}")

print("\nSelesai menyiapkan file untuk 1–30 April 2018.")