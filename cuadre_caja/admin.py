from django.contrib import admin

from .models import Caja, CierreCaja, Departamento, DetalleCierre, EgresoCierre, ImagenCierre


class CajaInline(admin.TabularInline):
    model = Caja
    extra = 0


@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "slug", "orden", "activo")
    list_editable = ("orden", "activo")
    prepopulated_fields = {"slug": ("nombre",)}
    inlines = [CajaInline]


@admin.register(Caja)
class CajaAdmin(admin.ModelAdmin):
    list_display = ("departamento", "numero", "nombre", "activo")
    list_filter = ("departamento", "activo")
    ordering = ("departamento__orden", "numero")


class DetalleCierreInline(admin.TabularInline):
    model = DetalleCierre
    extra = 0
    readonly_fields = ("metodo_pago", "monto_bs", "monto_usd")


class EgresoCierreInline(admin.TabularInline):
    model = EgresoCierre
    extra = 0
    fields = ("tipo", "cedula", "telefono", "banco", "moneda", "monto", "referencia")
    readonly_fields = ("tipo", "cedula", "telefono", "banco", "moneda", "monto", "referencia")


class ImagenCierreInline(admin.TabularInline):
    model = ImagenCierre
    extra = 0
    fields = ("titulo", "imagen")


@admin.register(CierreCaja)
class CierreCajaAdmin(admin.ModelAdmin):
    list_display = (
        "fecha",
        "turno",
        "caja",
        "nombre_cajera",
        "total_bs",
        "total_usd",
        "usuario",
        "fecha_registro",
    )
    list_filter = ("fecha", "turno", "caja__departamento")
    search_fields = ("nombre_cajera",)
    date_hierarchy = "fecha"
    inlines = [DetalleCierreInline, EgresoCierreInline, ImagenCierreInline]
