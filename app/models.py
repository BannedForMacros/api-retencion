from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

# ─── Tipos compartidos (longitudes alineadas con DDL y firmas de SP) ─────────

RUC = Annotated[
    str,
    Field(min_length=11, max_length=11, pattern=r"^\d{11}$", description="RUC de 11 dígitos"),
]
SerieNumero = Annotated[
    str,
    Field(min_length=3, max_length=15, description="Serie-Número, ej. 'R001-00000123'"),
]
Cat01 = Annotated[
    str,
    Field(min_length=2, max_length=2, description="Código de 2 dígitos (catálogo SUNAT)"),
]
Moneda = Annotated[
    str,
    Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$", description="ISO 4217 (PEN, USD)"),
]
FechaISO = Annotated[
    str,
    Field(
        min_length=10,
        max_length=10,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Fecha YYYY-MM-DD",
    ),
]
ImporteStr = Annotated[
    str,
    Field(
        min_length=1,
        max_length=15,
        pattern=r"^-?\d+(\.\d+)?$",
        description="Importe como string decimal, ej. '1234.56'",
    ),
]
NumeroPago = Annotated[str, Field(min_length=1, max_length=3, pattern=r"^\d{1,3}$")]
Usuario = Annotated[str, Field(min_length=1, max_length=30)]
TasaStr = Annotated[str, Field(min_length=1, max_length=4)]


# ─── INPUT: crear retención (cabecera + lista de detalles, transaccional) ────


class DetalleRetencionInput(BaseModel):
    """Línea de detalle. Mapea 1:1 a SP_DETALLERETENCION_INSERT."""

    tipodocrelacionado: Cat01 = Field(..., description="01 Factura, 07 NC, 08 ND")
    serienumerorelacionado: SerieNumero
    fechaemisiondocrelacionado: FechaISO
    importetotaldocrela: ImporteStr
    monedaimportedocrela: Moneda
    fechapago: FechaISO
    numeropago: NumeroPago
    importepagosinretencion: ImporteStr
    monedapago: Moneda
    importeretenido: ImporteStr
    monedaimporteretenido: Moneda = "PEN"
    fecharetencion: FechaISO
    montonetopagar: ImporteStr
    monedamontonetopagar: Moneda = "PEN"


class RetencionCreate(BaseModel):
    """Cabecera + lista de detalles. La operación es transaccional."""

    rucempresa: RUC
    serienumero: SerieNumero
    versionubl: Annotated[str, Field(max_length=3)] = "2.0"
    versionestructura: Annotated[str, Field(max_length=3)] = "1.0"
    fechaemision: FechaISO
    numdocproveedor: RUC
    tipodocproveedor: Cat01 = "06"
    direccionproveedor: Annotated[str, Field(max_length=150)] | None = None
    razonsocialproveedor: Annotated[str, Field(min_length=1, max_length=150)]
    regimenretencion: Cat01 = "01"
    tasaretencion: TasaStr = "3.00"
    observacion: Annotated[str, Field(max_length=250)] | None = None
    importetotalretenido: ImporteStr
    monedaimportetotalretenido: Moneda = "PEN"
    importetotalpagado: ImporteStr
    monedaimportetotalpagado: Moneda = "PEN"
    usuariocreador: Usuario
    detalles: Annotated[list[DetalleRetencionInput], Field(min_length=1)]


# ─── INPUTS: actualizaciones puntuales ───────────────────────────────────────


class ActualizarEstadoInput(BaseModel):
    estadosunat: Cat01 | None = None
    estadoproceso: Cat01 | None = None
    estadodocumento: Cat01 | None = None
    tramacdr: str | None = None
    usuariomodificador: Usuario


class ActualizarTramaInput(BaseModel):
    tramajson: str | None = None
    xmlfirmado: str | None = None
    usuariomodificador: Usuario


class AnularInput(BaseModel):
    motivo: Annotated[str, Field(min_length=1, max_length=250)]
    usuariomodificador: Usuario


# ─── OUTPUT: filas tal como las devuelven los SP de lectura ──────────────────


class RetencionRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rucempresa: str
    serienumero: str
    versionubl: str | None = None
    versionestructura: str | None = None
    fechaemision: str | None = None
    numdocproveedor: str | None = None
    tipodocproveedor: str | None = None
    direccionproveedor: str | None = None
    razonsocialproveedor: str | None = None
    regimenretencion: str | None = None
    tasaretencion: str | None = None
    observacion: str | None = None
    importetotalretenido: str | None = None
    monedaimportetotalretenido: str | None = None
    importetotalpagado: str | None = None
    monedaimportetotalpagado: str | None = None
    estadosunat: str | None = None
    estadoproceso: str | None = None
    estadodocumento: str | None = None
    # Respuesta de DB Peru / SUNAT (nullable hasta que se envia)
    codigohash: str | None = None
    codigoqr: str | None = None
    pdf417: str | None = None
    mensaje_error: str | None = None
    respuesta_envio: str | None = None
    usuariocreador: str | None = None
    fechacreacion: datetime | None = None
    usuariomodificador: str | None = None
    fechamodificacion: datetime | None = None
    anio: int | None = None
    mes: int | None = None
    dia: int | None = None


class ActualizarEnvioSunatInput(BaseModel):
    """Resultado del envio a DB Peru / SUNAT, persistido en datamarket."""

    estadosunat: str | None = None       # 'A' tras Aceptado SUNAT, NULL si no enviado
    estadoproceso: str = "F"             # 'C' Completado | 'F' Fallido | 'P' Pendiente
    estadodocumento: str | None = None   # '1' enviado/firmado, NULL en otros casos
    codigohash: str | None = None
    codigoqr: str | None = None
    pdf417: str | None = None
    mensaje_error: str | None = None
    respuesta_envio: str | None = None
    usuariomodificador: Usuario


class DetalleRetencionRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rucempresa: str
    serienumero: str
    tipodocrelacionado: str
    serienumerorelacionado: str
    fechaemisiondocrelacionado: str | None = None
    importetotaldocrela: str | None = None
    monedaimportedocrela: str | None = None
    fechapago: str | None = None
    numeropago: str
    importepagosinretencion: str | None = None
    monedapago: str | None = None
    importeretenido: str | None = None
    monedaimporteretenido: str | None = None
    fecharetencion: str | None = None
    montonetopagar: str | None = None
    monedamontonetopagar: str | None = None
    usuariocreador: str | None = None
    fechacreacion: datetime | None = None


# ─── OUTPUTS: respuestas estructuradas ───────────────────────────────────────


class RetencionCreatedResponse(BaseModel):
    rucempresa: str
    serienumero: str
    detalles_insertados: int
    mensaje: str = "Retención registrada correctamente."


class ExisteResponse(BaseModel):
    existe: bool


class RetencionListResponse(BaseModel):
    """Respuesta paginada de SP_RETENCION_LISTAR (combina los 2 resultsets)."""

    items: list[RetencionRow]
    total: int
    limit: int
    offset: int


class SiguienteNumeroResponse(BaseModel):
    siguiente_numero: str = Field(..., min_length=8, max_length=8, pattern=r"^\d{8}$")


class ReportePeriodoRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    numdocproveedor: str
    razonsocialproveedor: str
    total_comprobantes: int
    total_pagado: Decimal | None = None
    total_retenido: Decimal | None = None
    aceptadas: int
    rechazadas: int
    anuladas: int


class TotalesDashboardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_retenciones: int
    proveedores_distintos: int
    total_retenido: Decimal | None = None
    total_pagado: Decimal | None = None
    aceptadas: int
    rechazadas: int
    pendientes: int
    anuladas: int


# ─── Proveedores ─────────────────────────────────────────────────────────────


class ProveedorRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cod_proveedor: int
    ruc: str
    razon_social: str
    direccion: str = ""


class ProveedorListResponse(BaseModel):
    items: list[ProveedorRow]
    total: int
    limit: int
    offset: int


# ─── Facturas de proveedor (para el selector de retencion) ───────────────────


class FacturaProveedorRow(BaseModel):
    """Una factura/NC/ND de proveedor con flag de si ya fue retenida."""

    model_config = ConfigDict(from_attributes=True)

    tipo_doc: str = Field(..., description="SUNAT cat. 01: '01','07','08'")
    serie_numero: str = Field(..., description="Formato 'F001-00000123'")
    fecha_emision: str
    moneda: Moneda
    valor_neto: Decimal
    igv: Decimal
    importe_total: Decimal
    estado_pago: str
    proveedor_ruc: str
    proveedor_nombre: str
    ya_retenida: bool
    retencion_serienumero: str | None = None
    retencion_fecha: str | None = None


class FacturaProveedorListResponse(BaseModel):
    items: list[FacturaProveedorRow]
    total: int
    limit: int
    offset: int
