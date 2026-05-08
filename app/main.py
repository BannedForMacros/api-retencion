import logging

import pyodbc
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import parse_cors_origins, settings
from .errors import parse as parse_sql_error
from .routers import proveedores, retenciones

logger = logging.getLogger("retenciones-datamarket")

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=(
        "API de replicación de retenciones SUNAT al datamarket SQL Server. "
        "Cada endpoint mapea 1:1 a un stored procedure equivalente al de la base origen."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(pyodbc.Error)
def pyodbc_exception_handler(_: Request, exc: pyodbc.Error) -> JSONResponse:
    """Mapea errores del SP a HTTP correctos.

    - THROW 5000x → 4xx (validación / no encontrado / conflicto)
    - Cualquier otro → 500
    """
    parsed = parse_sql_error(exc)

    if parsed.http_status >= 500:
        logger.exception("Error pyodbc no mapeado: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Error de base de datos", "message": parsed.message},
        )

    logger.warning("SP error %s → HTTP %s: %s", parsed.code, parsed.http_status, parsed.message)
    return JSONResponse(
        status_code=parsed.http_status,
        content={"detail": parsed.message, "sql_error_code": parsed.code},
    )


@app.get("/health", tags=["health"], summary="Health check")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(retenciones.router)
app.include_router(proveedores.router)
