FEATURE_COLUMNS = [
    "TX_AMOUNT",
    "TX_HOUR",
    "TX_IS_WEEKEND",
]


def buat_fitur(tabel):
    fitur = tabel[["TX_AMOUNT"]].copy()

    fitur["TX_HOUR"] = (
        tabel["TX_DATETIME"].dt.hour
    )

    fitur["TX_IS_WEEKEND"] = (
        tabel["TX_DATETIME"].dt.dayofweek >= 5
    ).astype("int64")

    return fitur[FEATURE_COLUMNS]