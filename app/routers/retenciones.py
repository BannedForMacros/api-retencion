from fastapi import APIRouter, HTTPException, Query, status

from ..db import call_sp, row_to_dict, rows_to_dicts, transaction
from ..models import (
    ActualizarEnvioSunatInput,
    ActualizarEstadoInput,
    ActualizarTramaInput,
    AnularInput,
    DetalleRetencionRow,
    ExisteResponse,
    ReportePeriodoRow,
    RetencionCreate,
    RetencionCreatedResponse,
    RetencionListResponse,
    RetencionRow,
    SiguienteNumeroResponse,
    TotalesDashboardResponse,
)

router = APIRouter(prefix="/retenciones", tags=["retenciones"])


# ─── Crear retención (cabecera + detalles, transaccional) ────────────────────


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=RetencionCreatedResponse,
    summary="Crear retención",
    description=(
        "Inserta la cabecera (SP_RETENCION_INSERT) y todos los detalles "
        "(SP_DETALLERETENCION_INSERT) en una sola transacción."
    ),
)
def crear_retencion(payload: RetencionCreate) -> RetencionCreatedResponse:
    with transaction() as cnx:
        cur = cnx.cursor()

        call_sp(
            cur,
            "dbo.SP_RETENCION_INSERT",
            (
                payload.rucempresa,
                payload.serienumero,
                payload.versionubl,
                payload.versionestructura,
                payload.fechaemision,
                payload.numdocproveedor,
                payload.tipodocproveedor,
                payload.direccionproveedor,
                payload.razonsocialproveedor,
                payload.regimenretencion,
                payload.tasaretencion,
                payload.observacion,
                payload.importetotalretenido,
                payload.monedaimportetotalretenido,
                payload.importetotalpagado,
                payload.monedaimportetotalpagado,
                payload.usuariocreador,
            ),
        )

        for d in payload.detalles:
            call_sp(
                cur,
                "dbo.SP_DETALLERETENCION_INSERT",
                (
                    payload.rucempresa,
                    payload.serienumero,
                    d.tipodocrelacionado,
                    d.serienumerorelacionado,
                    d.fechaemisiondocrelacionado,
                    d.importetotaldocrela,
                    d.monedaimportedocrela,
                    d.fechapago,
                    d.numeropago,
                    d.importepagosinretencion,
                    d.monedapago,
                    d.importeretenido,
                    d.monedaimporteretenido,
                    d.fecharetencion,
                    d.montonetopagar,
                    d.monedamontonetopagar,
                    payload.usuariocreador,
                ),
            )

    return RetencionCreatedResponse(
        rucempresa=payload.rucempresa,
        serienumero=payload.serienumero,
        detalles_insertados=len(payload.detalles),
    )


# ─── Listar / consultar ──────────────────────────────────────────────────────


@router.get(
    "",
    response_model=RetencionListResponse,
    summary="Listar retenciones (paginado)",
    description="Devuelve items + total. Total proviene del segundo resultset del SP.",
)
def listar_retenciones(
    rucempresa: str = Query(..., min_length=11, max_length=11, pattern=r"^\d{11}$"),
    fecha_desde: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    fecha_hasta: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    numdocproveedor: str | None = Query(None, max_length=11),
    estadosunat: str | None = Query(None, max_length=2),
    search: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> RetencionListResponse:
    with transaction() as cnx:
        cur = cnx.cursor()
        call_sp(
            cur,
            "dbo.SP_RETENCION_LISTAR",
            (
                rucempresa,
                fecha_desde,
                fecha_hasta,
                numdocproveedor,
                estadosunat,
                search,
                limit,
                offset,
            ),
        )
        items = rows_to_dicts(cur)

        total = 0
        if cur.nextset():
            total_row = cur.fetchone()
            if total_row is not None:
                total = int(total_row[0])

    return RetencionListResponse(
        items=[RetencionRow.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/dashboard/totales",
    response_model=TotalesDashboardResponse,
    summary="KPIs del dashboard (totales agregados)",
)
def dashboard_totales(
    rucempresa: str = Query(..., min_length=11, max_length=11, pattern=r"^\d{11}$"),
    fecha_desde: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    fecha_hasta: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
) -> TotalesDashboardResponse:
    with transaction() as cnx:
        cur = cnx.cursor()
        call_sp(
            cur,
            "dbo.SP_RETENCION_TOTALES_DASHBOARD",
            (rucempresa, fecha_desde, fecha_hasta),
        )
        row = row_to_dict(cur)
    if row is None:
        # SP siempre debería retornar 1 fila; si no, devolvemos ceros.
        return TotalesDashboardResponse(
            total_retenciones=0,
            proveedores_distintos=0,
            aceptadas=0,
            rechazadas=0,
            pendientes=0,
            anuladas=0,
        )
    return TotalesDashboardResponse.model_validate(row)


@router.get(
    "/reporte/periodo",
    response_model=list[ReportePeriodoRow],
    summary="Reporte por proveedor en un período (anio/mes)",
)
def reporte_periodo(
    rucempresa: str = Query(..., min_length=11, max_length=11, pattern=r"^\d{11}$"),
    anio: int = Query(..., ge=2000, le=2100),
    mes: int | None = Query(None, ge=1, le=12),
) -> list[ReportePeriodoRow]:
    with transaction() as cnx:
        cur = cnx.cursor()
        call_sp(cur, "dbo.SP_RETENCION_REPORTE_PERIODO", (rucempresa, anio, mes))
        rows = rows_to_dicts(cur)
    return [ReportePeriodoRow.model_validate(r) for r in rows]


@router.get(
    "/siguiente-numero",
    response_model=SiguienteNumeroResponse,
    summary="Siguiente correlativo (8 dígitos) para una serie",
)
def siguiente_numero(
    rucempresa: str = Query(..., min_length=11, max_length=11, pattern=r"^\d{11}$"),
    serie: str = Query(..., min_length=1, max_length=4, pattern=r"^[A-Za-z0-9]{1,4}$"),
) -> SiguienteNumeroResponse:
    with transaction() as cnx:
        cur = cnx.cursor()
        call_sp(cur, "dbo.SP_RETENCION_SIGUIENTE_NUMERO", (rucempresa, serie))
        row = row_to_dict(cur)
    if row is None or "siguiente_numero" not in row:
        raise HTTPException(status_code=500, detail="SP no devolvió siguiente_numero")
    return SiguienteNumeroResponse(siguiente_numero=row["siguiente_numero"])


@router.get(
    "/{rucempresa}/{serienumero}",
    response_model=RetencionRow,
    summary="Obtener cabecera de una retención",
)
def obtener_retencion(rucempresa: str, serienumero: str) -> RetencionRow:
    with transaction() as cnx:
        cur = cnx.cursor()
        call_sp(cur, "dbo.SP_RETENCION_OBTENER", (rucempresa, serienumero))
        row = row_to_dict(cur)
    if row is None:
        raise HTTPException(status_code=404, detail="Retención no encontrada")
    return RetencionRow.model_validate(row)


@router.get(
    "/{rucempresa}/{serienumero}/detalles",
    response_model=list[DetalleRetencionRow],
    summary="Obtener detalles de una retención",
)
def obtener_detalles(rucempresa: str, serienumero: str) -> list[DetalleRetencionRow]:
    with transaction() as cnx:
        cur = cnx.cursor()
        call_sp(cur, "dbo.SP_RETENCION_OBTENER_DETALLES", (rucempresa, serienumero))
        rows = rows_to_dicts(cur)
    return [DetalleRetencionRow.model_validate(r) for r in rows]


@router.get(
    "/{rucempresa}/{serienumero}/existe",
    response_model=ExisteResponse,
    summary="Verificar existencia",
)
def existe_retencion(rucempresa: str, serienumero: str) -> ExisteResponse:
    with transaction() as cnx:
        cur = cnx.cursor()
        call_sp(cur, "dbo.SP_RETENCION_EXISTE", (rucempresa, serienumero))
        row = cur.fetchone()
    existe = bool(row[0]) if row is not None else False
    return ExisteResponse(existe=existe)


# ─── Mutaciones de estado / trama / anulación ────────────────────────────────


@router.patch(
    "/{rucempresa}/{serienumero}/estado",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Actualizar estados (SUNAT / proceso / documento) y CDR",
)
def actualizar_estado(rucempresa: str, serienumero: str, payload: ActualizarEstadoInput) -> None:
    with transaction() as cnx:
        cur = cnx.cursor()
        call_sp(
            cur,
            "dbo.SP_RETENCION_ACTUALIZAR_ESTADO",
            (
                rucempresa,
                serienumero,
                payload.estadosunat,
                payload.estadoproceso,
                payload.estadodocumento,
                payload.tramacdr,
                payload.usuariomodificador,
            ),
        )


@router.patch(
    "/{rucempresa}/{serienumero}/trama",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Actualizar trama JSON / XML firmado",
)
def actualizar_trama(rucempresa: str, serienumero: str, payload: ActualizarTramaInput) -> None:
    with transaction() as cnx:
        cur = cnx.cursor()
        call_sp(
            cur,
            "dbo.SP_RETENCION_ACTUALIZAR_TRAMA",
            (
                rucempresa,
                serienumero,
                payload.tramajson,
                payload.xmlfirmado,
                payload.usuariomodificador,
            ),
        )


@router.patch(
    "/{rucempresa}/{serienumero}/envio-sunat",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Persistir resultado del envío a DB Perú / SUNAT (CodigoHash, QR, pdf417...)",
)
def actualizar_envio_sunat(
    rucempresa: str, serienumero: str, payload: ActualizarEnvioSunatInput
) -> None:
    with transaction() as cnx:
        cur = cnx.cursor()
        call_sp(
            cur,
            "dbo.SP_RETENCION_ACTUALIZAR_ENVIO_SUNAT",
            (
                rucempresa,
                serienumero,
                payload.estadosunat,
                payload.estadoproceso,
                payload.estadodocumento,
                payload.codigohash,
                payload.codigoqr,
                payload.pdf417,
                payload.mensaje_error,
                payload.respuesta_envio,
                payload.usuariomodificador,
            ),
        )


@router.post(
    "/{rucempresa}/{serienumero}/anular",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Anular retención",
)
def anular_retencion(rucempresa: str, serienumero: str, payload: AnularInput) -> None:
    with transaction() as cnx:
        cur = cnx.cursor()
        call_sp(
            cur,
            "dbo.SP_RETENCION_ANULAR",
            (rucempresa, serienumero, payload.motivo, payload.usuariomodificador),
        )
