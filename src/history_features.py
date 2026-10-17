from datetime import timedelta

import pandas as pd
from bisect import bisect_left


def hitung_transaksi_24h(data, customer_id, waktu_transaksi):
    waktu_sekarang = pd.Timestamp(
        waktu_transaksi
    ).to_pydatetime()

    batas_awal = waktu_sekarang - timedelta(hours=24)

    riwayat = data.loc[
        (data["CUSTOMER_ID"] == customer_id)
        & (data["TX_DATETIME"] >= batas_awal)
        & (data["TX_DATETIME"] < waktu_sekarang)
    ]

    return len(riwayat)
def tambah_fitur_riwayat_24h(data):
    hasil = data.copy().reset_index(drop=True)

    hasil["TX_DATETIME"] = pd.to_datetime(
        hasil["TX_DATETIME"],
        errors="raise",
    )

    kolom_wajib = [
        "CUSTOMER_ID",
        "TX_DATETIME",
        "TX_AMOUNT",
    ]

    if hasil[kolom_wajib].isna().any().any():
        raise ValueError(
            "Customer ID, waktu, dan nominal tidak boleh kosong."
        )

    # Menyiapkan tiga kolom fitur.
    hasil["CUSTOMER_TX_COUNT_24H"] = 0
    hasil["CUSTOMER_AMOUNT_MEAN_24H"] = 0.0
    hasil["CUSTOMER_NO_HISTORY_24H"] = 0

    for customer_id, kelompok in hasil.groupby("CUSTOMER_ID"):
        kelompok = kelompok.sort_values(
            ["TX_DATETIME", "TRANSACTION_ID"]
        )

        daftar_waktu = [
            waktu.to_pydatetime()
            for waktu in kelompok["TX_DATETIME"]
        ]

        # Menyimpan total nominal secara bertahap.
        jumlah_kumulatif = [0.0]

        for nominal in kelompok["TX_AMOUNT"]:
            jumlah_kumulatif.append(
                jumlah_kumulatif[-1] + float(nominal)
            )

        daftar_jumlah = []
        daftar_rata_rata = []
        daftar_tanpa_riwayat = []

        for waktu_sekarang in daftar_waktu:
            batas_awal = waktu_sekarang - timedelta(hours=24)

            posisi_awal = bisect_left(
                daftar_waktu,
                batas_awal,
            )

            posisi_akhir = bisect_left(
                daftar_waktu,
                waktu_sekarang,
            )

            jumlah = posisi_akhir - posisi_awal

            total_nominal = (
                jumlah_kumulatif[posisi_akhir]
                - jumlah_kumulatif[posisi_awal]
            )

            if jumlah > 0:
                rata_rata = total_nominal / jumlah
                tanpa_riwayat = 0
            else:
                rata_rata = 0.0
                tanpa_riwayat = 1

            daftar_jumlah.append(jumlah)
            daftar_rata_rata.append(rata_rata)
            daftar_tanpa_riwayat.append(tanpa_riwayat)

        hasil.loc[
            kelompok.index,
            "CUSTOMER_TX_COUNT_24H",
        ] = daftar_jumlah

        hasil.loc[
            kelompok.index,
            "CUSTOMER_AMOUNT_MEAN_24H",
        ] = daftar_rata_rata

        hasil.loc[
            kelompok.index,
            "CUSTOMER_NO_HISTORY_24H",
        ] = daftar_tanpa_riwayat

    return hasil

def tambah_rasio_nominal_24h(data):
    hasil = data.copy()

    kolom_rata_rata = "CUSTOMER_AMOUNT_MEAN_24H"
    kolom_jumlah = "CUSTOMER_TX_COUNT_24H"

    # Nilai pengganti jika rasio belum bisa dihitung.
    hasil["CUSTOMER_AMOUNT_RATIO_24H"] = 0.0

    # Rasio hanya dihitung jika rata-rata lebih besar dari nol.
    bisa_dihitung = hasil[kolom_rata_rata] > 0

    hasil.loc[
        bisa_dihitung,
        "CUSTOMER_AMOUNT_RATIO_24H",
    ] = (
        hasil.loc[bisa_dihitung, "TX_AMOUNT"]
        / hasil.loc[bisa_dihitung, kolom_rata_rata]
    )

    # Penanda: ada riwayat, tetapi rata-rata nominalnya nol.
    hasil["CUSTOMER_ZERO_MEAN_24H"] = (
        (hasil[kolom_jumlah] > 0)
        & (hasil[kolom_rata_rata] == 0)
    ).astype("int64")

    return hasil
def tambah_riwayat_terminal_24h(data):
    hasil = data.copy().reset_index(drop=True)

    hasil["TX_DATETIME"] = pd.to_datetime(
        hasil["TX_DATETIME"],
        errors="raise",
    )

    if hasil[["TERMINAL_ID", "TX_DATETIME"]].isna().any().any():
        raise ValueError(
            "Terminal ID dan waktu transaksi tidak boleh kosong."
        )

    hasil["TERMINAL_TX_COUNT_24H"] = 0

    for terminal_id, kelompok in hasil.groupby("TERMINAL_ID"):
        kelompok = kelompok.sort_values(
            ["TX_DATETIME", "TRANSACTION_ID"]
        )

        daftar_waktu = [
            waktu.to_pydatetime()
            for waktu in kelompok["TX_DATETIME"]
        ]

        daftar_jumlah = []

        for waktu_sekarang in daftar_waktu:
            batas_awal = waktu_sekarang - timedelta(hours=24)

            posisi_awal = bisect_left(
                daftar_waktu,
                batas_awal,
            )

            posisi_akhir = bisect_left(
                daftar_waktu,
                waktu_sekarang,
            )

            daftar_jumlah.append(
                posisi_akhir - posisi_awal
            )

        hasil.loc[
            kelompok.index,
            "TERMINAL_TX_COUNT_24H",
        ] = daftar_jumlah

    return hasil