from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


# Choices para el formato de billetes Bs (denominaciones individuales)
class FormatoBilletesChoices(models.TextChoices):
    DEFAULT = "10-20-50-100-200-500", "10-20-50-100-200-500 (default)"
    SOLO_100 = "100-200-500", "100-200-500"
    SOLO_10_50 = "10-50", "10-50"
    PERSONALIZADO = "personalizado", "Personalizado"


class Departamento(models.Model):
    """Área de la empresa que opera una o varias cajas."""

    nombre = models.CharField(max_length=60, unique=True, verbose_name="Nombre")
    slug = models.SlugField(max_length=60, unique=True, verbose_name="Identificador")
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden")
    activo = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        ordering = ["orden", "nombre"]
        verbose_name = "Departamento"
        verbose_name_plural = "Departamentos"

    def __str__(self):
        return self.nombre


class Caja(models.Model):
    """Caja registradora perteneciente a un departamento."""

    departamento = models.ForeignKey(
        Departamento,
        on_delete=models.CASCADE,
        related_name="cajas",
        verbose_name="Departamento",
    )
    nombre = models.CharField(max_length=60, verbose_name="Nombre")
    numero = models.PositiveIntegerField(verbose_name="Número")
    activo = models.BooleanField(default=True, verbose_name="Activa")

    class Meta:
        ordering = ["departamento__orden", "numero"]
        verbose_name = "Caja"
        verbose_name_plural = "Cajas"
        constraints = [
            models.UniqueConstraint(
                fields=["departamento", "numero"],
                name="unique_caja_por_departamento",
            )
        ]

    def __str__(self):
        return f"{self.departamento.nombre} - {self.nombre}"


class TurnoChoices(models.TextChoices):
    AM = "AM", "AM"
    PM = "PM", "PM"


class MetodoPagoChoices(models.TextChoices):
    EFECTIVO_BS = "EFECTIVO_BS", "Efectivo Bs"
    EFECTIVO_USD = "EFECTIVO_USD", "Efectivo USD"
    PUNTO_VENTA = "PUNTO_VENTA", "Punto de venta"
    PAGO_MOVIL = "PAGO_MOVIL", "Pago móvil"
    ZELLE = "ZELLE", "Zelle"
    BIO_PAGO = "BIO_PAGO", "Bio pago"
    TRANSFERENCIA = "TRANSFERENCIA", "Transferencia"
    OTRO = "OTRO", "Otro"


MONEDA_BS = "BS"
MONEDA_USD = "USD"

# Moneda con la que opera cada método de pago.
MONEDA_POR_METODO = {
    MetodoPagoChoices.EFECTIVO_BS.value: MONEDA_BS,
    MetodoPagoChoices.EFECTIVO_USD.value: MONEDA_USD,
    MetodoPagoChoices.PUNTO_VENTA.value: MONEDA_BS,
    MetodoPagoChoices.PAGO_MOVIL.value: MONEDA_BS,
    MetodoPagoChoices.ZELLE.value: MONEDA_USD,
    MetodoPagoChoices.BIO_PAGO.value: MONEDA_BS,
    MetodoPagoChoices.TRANSFERENCIA.value: MONEDA_BS,
    MetodoPagoChoices.OTRO.value: MONEDA_BS,
}


class CierreCaja(models.Model):
    """Cierre diario de una caja, por turno y cajera."""

    caja = models.ForeignKey(
        Caja,
        on_delete=models.PROTECT,
        related_name="cierres",
        verbose_name="Caja",
    )
    fecha = models.DateField(default=timezone.localdate, verbose_name="Fecha")
    turno = models.CharField(
        max_length=2,
        choices=TurnoChoices.choices,
        verbose_name="Turno",
    )
    nombre_cajera = models.CharField(max_length=100, verbose_name="Nombre de la cajera")
    tasa = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=0,
        verbose_name="Tasa del día (Bs/USD)",
    )
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    total_bs = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        verbose_name="Total en Bs",
    )
    total_usd = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        verbose_name="Total en USD",
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Registrado por",
    )
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de registro")

    class Meta:
        ordering = ["-fecha", "-fecha_registro"]
        verbose_name = "Cierre de caja"
        verbose_name_plural = "Cierres de caja"
        constraints = [
            models.UniqueConstraint(
                fields=["caja", "fecha", "turno"],
                name="unique_cierre_por_caja_fecha_turno",
            )
        ]

    def __str__(self):
        return f"{self.caja} - {self.fecha:%d/%m/%Y} - {self.turno} - {self.nombre_cajera}"

    @property
    def total_equivalente_bs(self):
        if self.tasa:
            return _redondear(self.total_bs + (self.total_usd * self.tasa))
        return _redondear(self.total_bs)

    @property
    def total_equivalente_usd(self):
        if self.tasa:
            return _redondear(self.total_usd + (self.total_bs / self.tasa))
        return _redondear(self.total_usd)


def _redondear(valor):
    if valor is None:
        return Decimal("0.00")
    return Decimal(valor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class DetalleCierre(models.Model):
    """Monto realizado durante el día para cada método de pago."""

    cierre = models.ForeignKey(
        CierreCaja,
        on_delete=models.CASCADE,
        related_name="detalles",
        verbose_name="Cierre",
    )
    metodo_pago = models.CharField(
        max_length=20,
        choices=MetodoPagoChoices.choices,
        verbose_name="Método de pago",
    )
    monto_bs = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        verbose_name="Monto en Bs",
    )
    monto_usd = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        verbose_name="Monto en USD",
    )

    class Meta:
        ordering = ["id"]
        verbose_name = "Detalle de cierre"
        verbose_name_plural = "Detalles de cierre"
        constraints = [
            models.UniqueConstraint(
                fields=["cierre", "metodo_pago"],
                name="unique_metodo_por_cierre",
            )
        ]

    def __str__(self):
        return f"{self.get_metodo_pago_display()} - {self.cierre}"


class TipoSalidaChoices(models.TextChoices):
    EGRESO = "EGRESO", "Egreso"
    DEVOLUCION = "DEVOLUCION", "Devolución"


class EgresoCierre(models.Model):
    """Egreso o devolución registrado durante el día (informativo)."""

    cierre = models.ForeignKey(
        CierreCaja,
        on_delete=models.CASCADE,
        related_name="egresos",
        verbose_name="Cierre",
    )
    tipo = models.CharField(
        max_length=12,
        choices=TipoSalidaChoices.choices,
        default=TipoSalidaChoices.EGRESO,
        verbose_name="Tipo",
    )
    cedula = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="Cédula",
    )
    telefono = models.CharField(
        max_length=30,
        blank=True,
        default="",
        verbose_name="Teléfono",
    )
    banco = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Banco",
    )
    moneda = models.CharField(
        max_length=3,
        choices=[(MONEDA_BS, "Bolívares"), (MONEDA_USD, "Dólares")],
        default=MONEDA_BS,
        verbose_name="Moneda",
    )
    monto = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        verbose_name="Monto",
    )
    referencia = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Referencia",
    )

    class Meta:
        ordering = ["id"]
        verbose_name = "Egreso o devolución"
        verbose_name_plural = "Egresos y devoluciones"

    def __str__(self):
        identificacion = self.cedula or self.get_tipo_display()
        return f"{identificacion} - {self.monto}"

    @property
    def monto_bs(self):
        return self.monto if self.moneda == MONEDA_BS else Decimal("0.00")

    @property
    def monto_usd(self):
        return self.monto if self.moneda == MONEDA_USD else Decimal("0.00")


class CierreTransaccion(models.Model):
    """Transacción individual dentro de un cierre por método de pago."""

    cierre = models.ForeignKey(
        CierreCaja,
        on_delete=models.CASCADE,
        related_name="transacciones",
        verbose_name="Cierre",
    )
    metodo_pago = models.CharField(
        max_length=20,
        choices=MetodoPagoChoices.choices,
        verbose_name="Método de pago",
    )
    banco = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Banco o entidad",
    )
    monto = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        verbose_name="Monto",
    )
    ref = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Referencia",
    )
    notas = models.TextField(
        blank=True, verbose_name="Notas adicionales"
    )
    formato_billetes_bs = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Formato de billetes Bs",
        help_text="Denominaciones de billetes (ej: 10, 20, 50, 100, 200, 500)",
    )

    class Meta:
        ordering = ["id"]
        verbose_name = "Transacción de cierre"
        verbose_name_plural = "Transacciones de cierre"

    def __str__(self):
        return f"{self.get_metodo_pago_display()} - {self.banco} - {self.monto}"

    @property
    def monto_bs(self):
        return self.monto if MONEDA_POR_METODO.get(self.metodo_pago) == MONEDA_BS else Decimal("0.00")

    @property
    def monto_usd(self):
        return self.monto if MONEDA_POR_METODO.get(self.metodo_pago) == MONEDA_USD else Decimal("0.00")


class ImagenCierre(models.Model):
    """Imagen adjunta a un cierre (máximo 5 por cierre)."""

    cierre = models.ForeignKey(
        CierreCaja,
        on_delete=models.CASCADE,
        related_name="imagenes",
        verbose_name="Cierre",
    )
    titulo = models.CharField(max_length=150, verbose_name="Título")
    imagen = models.ImageField(
        upload_to="cuadre_caja/cierres/%Y/%m/",
        verbose_name="Imagen",
    )
    fecha_subida = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de subida")

    class Meta:
        ordering = ["id"]
        verbose_name = "Imagen del cierre"
        verbose_name_plural = "Imágenes del cierre"

    def __str__(self):
        return self.titulo