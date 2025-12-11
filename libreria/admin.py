from django.contrib import admin
from .models import Cliente,Proveedor,Inventario,HistorialProveedoresNotas,MovimientosInventario
# Register your models here.

admin.site.register(Cliente)

admin.site.register(Proveedor)

admin.site.register(HistorialProveedoresNotas)
class HistorialProveedoresNotasInline(admin.StackedInline):
    model = HistorialProveedoresNotas
    # Campos que se mostrarán en la tabla de notas
    fields = ('fecha_registro', 'detalle_nota',)
    readonly_fields = ('fecha_registro',)  # La fecha se establece automáticamente
    extra = 1  # Muestra una fila vacía adicional para ingresar nuevas notas


@admin.register(Inventario)
class InventarioAdmin(admin.ModelAdmin):
    list_display = ('id_producto', 'codigo_producto','nombre_producto', 'categoria', 'cantidad', 'precio_venta')
    list_filter = ('categoria',)
    search_fields = ('nombre_producto','codigo_producto', 'descripcion')


@admin.register(MovimientosInventario)
class MovimientosInventarioAdmin(admin.ModelAdmin):
    list_display = ('producto', 'tipo_movimiento', 'cantidad', 'fecha_movimiento', 'proveedor')
    list_filter = ('tipo_movimiento', 'fecha_movimiento')
    readonly_fields = ('fecha_movimiento',)



    