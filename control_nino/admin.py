from django.contrib import admin
from .models import ControlNino, Fiesta, BrazaleteFiesta, Novedad


class BrazaleteFiestaInline(admin.TabularInline):
    model = BrazaleteFiesta
    extra = 0


@admin.register(ControlNino)
class ControlNinoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tiempo', 'fecha_registro', 'hora_salida')
    search_fields = ('nombre', 'descripcion')
    list_filter = ('tiempo',)


@admin.register(Fiesta)
class FiestaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tiempo', 'cantidad_brazaletes', 'fecha_registro', 'hora_inicio')
    search_fields = ('nombre',)
    inlines = [BrazaleteFiestaInline]


@admin.register(Novedad)
class NovedadAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'tipo', 'usuario', 'fecha_registro', 'fiesta', 'nino')
    list_filter = ('tipo', 'fecha_registro')
    search_fields = ('titulo', 'descripcion')
