"""Mapeo de errores de SQL Server (THROW) a respuestas HTTP estructuradas.

Los SPs lanzan errores con códigos 50001-50031 vía `THROW`. pyodbc los expone
en `Error.args[1]` como un string del estilo:
    [42000] [Microsoft][ODBC Driver 18][SQL Server]<mensaje> (50003) (SQLExecDirectW)

Aquí extraemos el número y el mensaje limpio para devolver 4xx adecuados.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pyodbc

# Códigos definidos en los SPs. Ver retenciones_sqlserver.sql.
ERROR_HTTP_MAP: dict[int, int] = {
    50001: 400,  # rucempresa invalido
    50002: 400,  # serienumero obligatorio
    50003: 409,  # retencion ya existe
    50010: 404,  # no existe cabecera (al insertar detalle)
    50020: 404,  # no existe retencion (actualizar trama)
    50021: 404,  # no existe retencion (actualizar estado)
    50030: 404,  # no existe retencion (anular)
    50031: 409,  # retencion ya esta anulada
    50040: 404,  # no existe retencion (actualizar envio SUNAT)
}

_BRACKET_PREFIX_RE = re.compile(r"^(?:\[[^\]]+\]\s*)+")
_TRAILING_NOISE_RE = re.compile(r"\s*\(\d+\)\s*\(SQLExecDirectW\)\s*$")
_TRAILING_CODE_RE = re.compile(r"\s*\(\d+\)\s*$")
_ANY_CODE_RE = re.compile(r"\((\d{4,6})\)")


@dataclass(frozen=True)
class ParsedSqlError:
    code: int | None
    message: str
    http_status: int


def parse(exc: pyodbc.Error) -> ParsedSqlError:
    """Extrae código y mensaje limpio de una excepción de pyodbc."""
    raw = str(exc.args[1]) if len(exc.args) > 1 else str(exc)

    # El número de error suele aparecer al final entre paréntesis.
    matches = _ANY_CODE_RE.findall(raw)
    code: int | None = int(matches[-1]) if matches else None

    cleaned = _BRACKET_PREFIX_RE.sub("", raw).strip()
    cleaned = _TRAILING_NOISE_RE.sub("", cleaned).strip()
    cleaned = _TRAILING_CODE_RE.sub("", cleaned).strip()
    if not cleaned:
        cleaned = raw

    http_status = ERROR_HTTP_MAP.get(code, 500) if code is not None else 500
    return ParsedSqlError(code=code, message=cleaned, http_status=http_status)
