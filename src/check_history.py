import pandas as pd

from history_features import hitung_transaksi_24h

from math import isclose

from history_features import tambah_rasio_nominal_24h

from history_features import tambah_riwayat_terminal_24h

waktu_sekarang = "2018-04-03 10:00:00"

# Isi setiap kasus:
# nama kasus, customer ID, waktu transaksi, hasil yang diharapkan
kasus_uji = [
    (
        "Lebih lama dari 24 jam",
        149,
        "2018-04-02 09:59:59",
        0,
    ),
    (
        "Tepat 24 jam sebelumnya",
        149,
        "2018-04-02 10:00:00",
        1,
    ),
    (
        "Satu detik sebelumnya",
        149,
        "2018-04-03 09:59:59",
        1,
    ),
    (
        "Waktu persis sama",
        149,
        "2018-04-03 10:00:00",
        0,
    ),
    (
        "Transaksi masa depan",
        149,
        "2018-04-03 10:00:01",
        0,
    ),
    (
        "Pelanggan berbeda",
        999,
        "2018-04-03 09:00:00",
        0,
    ),
]


for nama, customer_id, waktu, expected in kasus_uji:
    data_uji = pd.DataFrame({
        "CUSTOMER_ID": [customer_id],
        "TX_DATETIME": pd.to_datetime([waktu]),
    })

    hasil = hitung_transaksi_24h(
        data=data_uji,
        customer_id=149,
        waktu_transaksi=waktu_sekarang,
    )

    if hasil != expected:
        raise AssertionError(
            f"{nama}: seharusnya {expected}, tetapi hasilnya {hasil}"
        )

    print(f"LULUS: {nama} | hasil={hasil}")


print("\nSEMUA 6 KASUS LULUS")

data_rasio = pd.DataFrame({
    "TX_AMOUNT": [100.0, 50.0, 25.0, 100.0, 100.0, 0.0],
    "CUSTOMER_TX_COUNT_24H": [2, 2, 2, 0, 2, 2],
    "CUSTOMER_AMOUNT_MEAN_24H": [50.0, 50.0, 50.0, 0.0, 0.0, 50.0],
    "CUSTOMER_NO_HISTORY_24H": [0, 0, 0, 1, 0, 0],
})

hasil_rasio = tambah_rasio_nominal_24h(data_rasio)

rasio_expected = [2.0, 1.0, 0.5, 0.0, 0.0, 0.0]
zero_mean_expected = [0, 0, 0, 0, 1, 0]

for posisi, expected in enumerate(rasio_expected):
    aktual = hasil_rasio.loc[
        posisi,
        "CUSTOMER_AMOUNT_RATIO_24H",
    ]

    if not isclose(aktual, expected, rel_tol=1e-9, abs_tol=1e-8):
        raise AssertionError(
            f"Rasio baris {posisi}: "
            f"seharusnya {expected}, hasilnya {aktual}"
        )

    penanda = hasil_rasio.loc[
        posisi,
        "CUSTOMER_ZERO_MEAN_24H",
    ]

    if penanda != zero_mean_expected[posisi]:
        raise AssertionError(
            f"Penanda rata-rata nol salah pada baris {posisi}"
        )

print("\nPEMERIKSAAN RASIO: SEMUA 6 KASUS LULUS")

data_terminal = pd.DataFrame({
    "TRANSACTION_ID": [1, 2, 3, 4, 5, 6, 7],
    "CUSTOMER_ID": [101, 102, 103, 104, 105, 106, 107],
    "TERMINAL_ID": [10, 10, 10, 20, 10, 10, 10],
    "TX_DATETIME": pd.to_datetime([
        "2018-04-02 09:59:59",
        "2018-04-02 10:00:00",
        "2018-04-03 09:00:00",
        "2018-04-03 09:30:00",
        "2018-04-03 10:00:00",
        "2018-04-03 10:00:00",
        "2018-04-03 10:01:00",
    ]),
})

hasil_terminal = tambah_riwayat_terminal_24h(data_terminal)

expected_terminal = [0, 1, 2, 0, 2, 2, 3]

for posisi, expected in enumerate(expected_terminal):
    aktual = hasil_terminal.loc[
        posisi,
        "TERMINAL_TX_COUNT_24H",
    ]

    if aktual != expected:
        transaction_id = hasil_terminal.loc[
            posisi,
            "TRANSACTION_ID",
        ]

        raise AssertionError(
            f"Transaksi {transaction_id}: "
            f"seharusnya {expected}, hasilnya {aktual}"
        )

print("\nPEMERIKSAAN TERMINAL: SEMUA 7 BARIS LULUS")