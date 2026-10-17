import json
import logging
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


logger = logging.getLogger("uvicorn.error")


def pasang_pencatatan_request(app: FastAPI):
    @app.middleware("http")
    async def catat_request(request: Request, call_next):
        # Setiap permintaan mendapat ID baru dari server.
        request_id = str(uuid4())
        request.state.request_id = request_id

        mulai = perf_counter()
        jenis_error = None

        try:
            # Teruskan permintaan ke endpoint yang sesuai.
            response = await call_next(request)

        except Exception as error:
            # Tangani kegagalan tak terduga.
            # Detail internal tidak dikirim ke pemanggil API.
            jenis_error = type(error).__name__

            response = JSONResponse(
                status_code=500,
                content={
                    "detail": "Terjadi kesalahan internal pada layanan."
                },
            )

        durasi_ms = (perf_counter() - mulai) * 1000

        # Header adalah informasi tambahan di luar isi JSON.
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = f"{durasi_ms:.3f}"

        route = request.scope.get("route")
        nama_endpoint = getattr(route, "path", "<unmatched>")

        catatan = {
            "event": "request_completed",
            "timestamp_utc": datetime.now(
                timezone.utc
            ).isoformat(),
            "request_id": request_id,
            "method": request.method,
            "endpoint": nama_endpoint,
            "status_code": response.status_code,
            "duration_ms": round(durasi_ms, 3),
        }

        if jenis_error is not None:
            catatan["error_type"] = jenis_error

        level = (
            logging.ERROR
            if response.status_code >= 500
            else logging.INFO
        )

        logger.log(
            level,
            json.dumps(catatan, ensure_ascii=False),
        )

        return response