import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import (
    FastAPI,
    Header,
    HTTPException,
    Request,
    Response,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator

from idempotency_store import (
    IdempotencyConflict,
    IdempotencyStore,
)
from request_logging import pasang_pencatatan_request
from risk_engine import RiskEngine


project_root = Path(__file__).resolve().parent.parent

DEFAULT_DB_PATH = (
    project_root / "data" / "runtime" / "fraudshield.db"
)


class TransactionRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    TRANSACTION_ID: int = Field(ge=0)

    TX_DATETIME: str = Field(
        examples=["2018-05-01T10:00:00"]
    )

    TX_AMOUNT: float = Field(
        ge=0,
        allow_inf_nan=False,
    )

    @field_validator("TX_DATETIME")
    @classmethod
    def periksa_waktu(cls, nilai):
        try:
            waktu = datetime.fromisoformat(nilai)
        except ValueError:
            raise ValueError(
                "Gunakan waktu berformat ISO, "
                "contohnya 2018-05-01T10:00:00."
            ) from None

        if waktu.tzinfo is not None:
            raise ValueError(
                "Versi ini memakai waktu tanpa zona waktu, "
                "sesuai format dataset."
            )

        return waktu.isoformat()


class PredictionResponse(BaseModel):
    transaction_id: int = Field(ge=0)

    risk_score: float = Field(
        ge=0,
        le=1,
        allow_inf_nan=False,
    )

    threshold: float = Field(
        ge=0,
        le=1,
        allow_inf_nan=False,
    )

    decision: Literal["ALLOW", "REVIEW"]
    reason: str
    model_version: str
    policy_version: str


def create_app(db_path=None):
    lokasi_database = (
        Path(db_path)
        if db_path is not None
        else DEFAULT_DB_PATH
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        engine = RiskEngine()
        store = IdempotencyStore(lokasi_database)

        application.state.engine = engine
        application.state.store = store

        try:
            yield
        finally:
            del application.state.engine
            del application.state.store

    application = FastAPI(
        title="FraudShield API",
        description="API penilaian risiko transaksi.",
        version="0.3.0",
        lifespan=lifespan,
    )

    pasang_pencatatan_request(application)

    @application.get("/health")
    def health(request: Request):
        engine = request.app.state.engine

        return {
            "status": "ready",
            "model_version": engine.model_version,
            "policy_version": engine.policy_version,
        }

    @application.post(
        "/predict",
        response_model=PredictionResponse,
        responses={
            409: {
                "description": (
                    "Kunci idempotency sudah dipakai "
                    "untuk input berbeda."
                )
            },
            500: {
                "description": "Penilaian gagal diproses."
            },
            503: {
                "description": "Penyimpanan tidak tersedia."
            },
        },
    )
    def predict(
        transaksi: TransactionRequest,
        request: Request,
        response: Response,
        idempotency_key: Annotated[
            str | None,
            Header(
                alias="Idempotency-Key",
                min_length=1,
                max_length=128,
                pattern=r"^[A-Za-z0-9._:-]+$",
                description=(
                    "Gunakan kunci yang sama saat mengulang "
                    "permintaan dengan input yang sama."
                ),
            ),
        ] = None,
    ):
        engine = request.app.state.engine
        store = request.app.state.store

        request_id = request.state.request_id
        data_transaksi = transaksi.model_dump()

        # Samakan representasi -0.0 dan 0.0.
        if data_transaksi["TX_AMOUNT"] == 0:
            data_transaksi["TX_AMOUNT"] = 0.0

        def buat_hasil():
            hasil_engine = engine.score(data_transaksi)

            return PredictionResponse.model_validate(
                hasil_engine
            ).model_dump()

        try:
            if idempotency_key is None:
                # Perilaku sebelumnya: setiap request dinilai.
                hasil = buat_hasil()

                store.simpan(
                    request_id=request_id,
                    transaksi=data_transaksi,
                    hasil=hasil,
                )

                replayed = False
                original_request_id = request_id

            else:
                # Model hanya dijalankan jika kuncinya baru.
                proses = store.proses(
                    idempotency_key=idempotency_key,
                    request_id=request_id,
                    transaksi=data_transaksi,
                    buat_hasil=buat_hasil,
                )

                hasil = proses["hasil"]
                replayed = proses["replayed"]
                original_request_id = proses["original_request_id"]

        except IdempotencyConflict:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Idempotency-Key sudah digunakan "
                    "untuk input transaksi yang berbeda."
                ),
            ) from None

        except (sqlite3.Error, OSError):
            raise HTTPException(
                status_code=503,
                detail=(
                    "Hasil penilaian gagal disimpan. "
                    "Layanan sementara tidak dapat "
                    "menyelesaikan permintaan."
                ),
            ) from None

        except ValueError:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Engine gagal menghasilkan penilaian yang valid."
                ),
            ) from None

        response.headers["X-Idempotent-Replay"] = (
            "true" if replayed else "false"
        )

        response.headers["X-Original-Request-ID"] = (
            original_request_id
        )

        return hasil

    return application


app = create_app()