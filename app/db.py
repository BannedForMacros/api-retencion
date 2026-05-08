from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

import pyodbc

from .config import build_connection_string, settings


@contextmanager
def transaction() -> Iterator[pyodbc.Connection]:
    """Abre conexión, hace commit al salir sin error, rollback ante excepción."""
    cnx = pyodbc.connect(
        build_connection_string(),
        autocommit=False,
        timeout=settings.db_login_timeout,
    )
    cnx.timeout = settings.db_query_timeout
    try:
        yield cnx
        cnx.commit()
    except Exception:
        cnx.rollback()
        raise
    finally:
        cnx.close()


def call_sp(cursor: pyodbc.Cursor, name: str, params: Sequence[Any]) -> None:
    """Ejecuta un stored procedure con parámetros posicionales (estilo {CALL ...})."""
    placeholders = ", ".join(["?"] * len(params))
    cursor.execute(f"{{CALL {name}({placeholders})}}", tuple(params))


def rows_to_dicts(cursor: pyodbc.Cursor) -> list[dict[str, Any]]:
    """Convierte el resultset actual del cursor en lista de dicts."""
    if cursor.description is None:
        return []
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, row, strict=True)) for row in cursor.fetchall()]


def row_to_dict(cursor: pyodbc.Cursor) -> dict[str, Any] | None:
    if cursor.description is None:
        return None
    cols = [c[0] for c in cursor.description]
    row = cursor.fetchone()
    return dict(zip(cols, row, strict=True)) if row is not None else None
