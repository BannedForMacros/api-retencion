"""Endpoints de configuracion / maestros sobre db_fsm_emmel.

Todas las consultas usan SQL inline parametrizado (sin SPs).
"""

import pyodbc
from fastapi import APIRouter, HTTPException, Query, status

from ..db import row_to_dict, rows_to_dicts, transaction
from ..models import (
    SerieCreateRequest,
    SerieListResponse,
    SerieRow,
    SiguienteNumeroSerieResponse,
)

router = APIRouter(prefix="/maestros", tags=["maestros"])


# ─── Series (MaestroDocumentoSerie) ─────────────────────────────────────────

# Para SQL Server pyodbc, codigo de violacion de PK / unique:
_PK_VIOLATION_CODES = ("23000",)
_PK_NUMBERS = (2627, 2601)  # PK / unique key


@router.get(
    "/series",
    response_model=SerieListResponse,
    summary="Listar series habilitadas para un tipo de documento",
    description=(
        "Devuelve las filas de MaestroDocumentoSerie joineadas con MaestroDocumento "
        "para el tipo indicado, con la serie ya formateada (PrefijoSerie + 3 digitos)."
    ),
)
def listar_series(
    tipo_documento: int = Query(..., ge=1, le=255),
) -> SerieListResponse:
    sql = """
        SELECT
            s.TipoDocumento                                             AS tipo_documento,
            s.NumSerie                                                  AS num_serie,
            LTRIM(RTRIM(ISNULL(md.PrefijoSerie, '')))                   AS prefijo,
            LTRIM(RTRIM(ISNULL(md.PrefijoSerie, '')))
                + RIGHT('000' + CAST(s.NumSerie AS VARCHAR(3)), 3)      AS serie_formateada,
            ISNULL(s.UltimoValor, 0)                                    AS ultimo_valor,
            ISNULL(s.UltimoValorMarket, 0)                              AS ultimo_valor_market,
            s.CtrResp                                                   AS ctr_resp,
            LTRIM(RTRIM(md.Descripcion))                                AS descripcion
        FROM dbo.MaestroDocumentoSerie s
        INNER JOIN dbo.MaestroDocumento md
                ON md.TipoDocumento = s.TipoDocumento
        WHERE s.TipoDocumento = ?
        ORDER BY s.NumSerie;
    """
    with transaction() as cnx:
        cur = cnx.cursor()
        cur.execute(sql, (tipo_documento,))
        rows = rows_to_dicts(cur)

    return SerieListResponse(
        items=[SerieRow.model_validate(r) for r in rows],
        tipo_documento=tipo_documento,
    )


@router.post(
    "/series",
    status_code=status.HTTP_201_CREATED,
    response_model=SerieRow,
    summary="Crear serie nueva (UltimoValor = 0)",
    description=(
        "Inserta una fila en MaestroDocumentoSerie. Falla con 404 si el tipo de "
        "documento no existe en MaestroDocumento, y con 409 si la serie ya existe."
    ),
)
def crear_serie(payload: SerieCreateRequest) -> SerieRow:
    sql_md_existe = """
        SELECT
            LTRIM(RTRIM(ISNULL(PrefijoSerie, '')))  AS prefijo,
            LTRIM(RTRIM(Descripcion))               AS descripcion
        FROM dbo.MaestroDocumento
        WHERE TipoDocumento = ?
    """
    sql_insert = """
        INSERT INTO dbo.MaestroDocumentoSerie
            (TipoDocumento, NumSerie, UltimoValor, UltimoValorMarket, CtrResp)
        VALUES (?, ?, 0, 0, ?);
    """
    with transaction() as cnx:
        cur = cnx.cursor()
        cur.execute(sql_md_existe, (payload.tipo_documento,))
        md = row_to_dict(cur)
        if md is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"TipoDocumento {payload.tipo_documento} no existe en MaestroDocumento",
            )

        try:
            cur.execute(
                sql_insert,
                (payload.tipo_documento, payload.num_serie, payload.ctr_resp),
            )
        except pyodbc.IntegrityError as e:
            sqlstate = e.args[0] if e.args else ""
            number = getattr(e, "args", [None, None])[1] if len(e.args) > 1 else None
            # SQL Server: 2627 PK violation, 2601 unique index violation
            if sqlstate in _PK_VIOLATION_CODES or any(
                str(code) in str(e) for code in _PK_NUMBERS
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"La serie {payload.num_serie} ya existe para "
                        f"TipoDocumento {payload.tipo_documento}"
                    ),
                ) from e
            raise

    prefijo = md["prefijo"]
    serie_fmt = f"{prefijo}{payload.num_serie:03d}"
    return SerieRow(
        tipo_documento=payload.tipo_documento,
        num_serie=payload.num_serie,
        prefijo=prefijo,
        serie_formateada=serie_fmt,
        ultimo_valor=0,
        ultimo_valor_market=0,
        ctr_resp=payload.ctr_resp,
        descripcion=md["descripcion"],
    )


@router.get(
    "/series/siguiente-numero",
    response_model=SiguienteNumeroSerieResponse,
    summary="Siguiente correlativo de una serie (UltimoValor + 1, padded a 8)",
    description=(
        "Devuelve el siguiente numero a emitir para la combinacion (tipo_documento, "
        "num_serie). NO incrementa UltimoValor; el incremento sucede al insertar la "
        "retencion / documento. Si la serie no existe responde 404."
    ),
)
def siguiente_numero_serie(
    tipo_documento: int = Query(..., ge=1, le=255),
    num_serie: int = Query(..., ge=1, le=9999),
) -> SiguienteNumeroSerieResponse:
    sql = """
        SELECT
            s.TipoDocumento                                             AS tipo_documento,
            s.NumSerie                                                  AS num_serie,
            LTRIM(RTRIM(ISNULL(md.PrefijoSerie, '')))
                + RIGHT('000' + CAST(s.NumSerie AS VARCHAR(3)), 3)      AS serie_formateada,
            ISNULL(s.UltimoValor, 0)                                    AS ultimo_valor,
            RIGHT('00000000'
                + CAST(ISNULL(s.UltimoValor, 0) + 1 AS VARCHAR(10)), 8) AS siguiente_numero
        FROM dbo.MaestroDocumentoSerie s
        INNER JOIN dbo.MaestroDocumento md
                ON md.TipoDocumento = s.TipoDocumento
        WHERE s.TipoDocumento = ? AND s.NumSerie = ?;
    """
    with transaction() as cnx:
        cur = cnx.cursor()
        cur.execute(sql, (tipo_documento, num_serie))
        row = row_to_dict(cur)

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Serie ({tipo_documento}, {num_serie}) no existe",
        )
    return SiguienteNumeroSerieResponse.model_validate(row)
