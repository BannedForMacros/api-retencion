from fastapi import APIRouter, HTTPException, Query, status

from ..db import call_sp, rows_to_dicts, transaction
from ..models import (
    FacturaProveedorListResponse,
    FacturaProveedorRow,
    ProveedorListResponse,
    ProveedorRow,
    SetAfectoRetencionInput,
    SetAfectoRetencionResponse,
)

router = APIRouter(prefix="/proveedores", tags=["proveedores"])


@router.get(
    "",
    response_model=ProveedorListResponse,
    summary="Buscar proveedores activos (paginado)",
    description=(
        "Lista proveedores activos de MaestroProveedores filtrados por RUC o "
        "razón social. Devuelve items + total."
    ),
)
def buscar_proveedores(
    search: str | None = Query(None, max_length=100),
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> ProveedorListResponse:
    with transaction() as cnx:
        cur = cnx.cursor()
        call_sp(cur, "dbo.SP_PROVEEDORES_BUSCAR", (search, limit, offset))
        items = rows_to_dicts(cur)

        total = 0
        if cur.nextset():
            total_row = cur.fetchone()
            if total_row is not None:
                total = int(total_row[0])

    return ProveedorListResponse(
        items=[ProveedorRow.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{ruc}/facturas",
    response_model=FacturaProveedorListResponse,
    summary="Facturas de un proveedor (con flag ya_retenida)",
    description=(
        "Devuelve las facturas / NC / ND del proveedor (SUNAT cat. 01: '01','07','08') "
        "que están pendientes de pago, junto con el flag `ya_retenida` indicando si "
        "ya fueron incluidas en una retención no anulada de la empresa que consulta."
    ),
)
def facturas_de_proveedor(
    ruc: str,
    rucempresa: str = Query(..., min_length=11, max_length=11, pattern=r"^\d{11}$"),
    search: str | None = Query(None, max_length=50),
    solo_disponibles: bool = Query(False, description="Si es true, oculta las ya retenidas"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> FacturaProveedorListResponse:
    with transaction() as cnx:
        cur = cnx.cursor()
        call_sp(
            cur,
            "dbo.SP_FACTURAS_PROVEEDOR_BUSCAR",
            (rucempresa, ruc, search, 1 if solo_disponibles else 0, limit, offset),
        )
        items = rows_to_dicts(cur)

        total = 0
        if cur.nextset():
            total_row = cur.fetchone()
            if total_row is not None:
                total = int(total_row[0])

    return FacturaProveedorListResponse(
        items=[FacturaProveedorRow.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/{ruc}/afecto-retencion",
    response_model=SetAfectoRetencionResponse,
    summary="Marcar / desmarcar a un proveedor como afecto a retencion",
    description=(
        "Actualiza la columna AfectoRetencion de MaestroProveedores. SQL inline "
        "(no usa SP). Si el RUC no existe responde 404."
    ),
)
def set_afecto_retencion(
    ruc: str,
    payload: SetAfectoRetencionInput,
) -> SetAfectoRetencionResponse:
    sql_update = """
        UPDATE dbo.MaestroProveedores
           SET AfectoRetencion    = ?,
               UsuarioModificador = ?,
               FechaModificacion  = GETDATE()
         WHERE LTRIM(RTRIM(RUC)) = ?;
    """
    # UsuarioModificador es varchar(15) en la tabla, truncamos por las dudas.
    usuario = payload.usuariomodificador[:15]
    with transaction() as cnx:
        cur = cnx.cursor()
        cur.execute(sql_update, (1 if payload.afecto else 0, usuario, ruc))
        if cur.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Proveedor {ruc} no encontrado",
            )

    return SetAfectoRetencionResponse(ruc=ruc, afecto_retencion=payload.afecto)
