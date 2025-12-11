from django.urls import path
from . import views
 
urlpatterns = [
    path('', views.index, name='index'),
    #clientes urls
    path('clientes/', views.clientes_index, name='clientes.index'),
    path('clientes/crear', views.clientes_crear, name='clientes.crear'),
    path('clientes/editar', views.clientes_editar, name='clientes.editar'),
    path('clientes/eliminar<int:id>', views.clientes_eliminar, name='clientes.eliminar'),
    path('clientes/ver', views.clientes_ver, name='clientes.ver'),
    path('clientes/editar/<int:id>', views.clientes_editar, name='clientes.editar'),


    #proveedores urls
    path('proveedores/', views.proveedores_index, name='proveedores.index'),
    path('proveedores/crear', views.proveedores_crear, name='proveedores.crear'),
    path('proveedores/editar<int:id>', views.proveedores_editar, name='proveedores.editar'),
    path('proveedores/eliminar<int:id>', views.proveedores_eliminar, name='proveedores.eliminar'),
    path('proveedores/editar/<int:id>', views.proveedores_editar, name='proveedores.editar'),
    # HistorialProveedoresNotas urls
    path('HistorialProveedoresNotas/', views.historial_proveedores_notas_index, name='HistorialProveedoresNotas.index'),
    path('HistorialProveedoresNotas/crear', views.historial_proveedores_notas_crear, name='HistorialProveedoresNotas.crear'),
    path('HistorialProveedoresNotas/editar<int:id_historialproveedor>', views.historial_proveedores_notas_editar, name='HistorialProveedoresNotas.editar'),
    path('HistorialProveedoresNotas/eliminar<int:id_historialproveedor>', views.historial_proveedores_notas_eliminar, name='HistorialProveedoresNotas.eliminar'),
    


    # inventarios urls
    path('inventario/', views.inventario_index, name='inventario.index'),
    path('inventario/crear', views.inventario_crear, name='inventario.crear'),
    path('inventario/editar<int:id_producto>', views.inventario_editar, name='inventario.editar'),
    path('inventario/eliminar<int:id_producto>', views.inventario_eliminar, name='inventario.eliminar'),
    path('inventario/editar<int:id_producto>', views.inventario_editar, name='inventario.editar'),

    # MovimientosInventario urls
    path('movimientos/', views.movimientos_inventario_index, name='movimientos.index'),
    path('movimientos/crear', views.movimientos_inventario_crear, name='movimientos.crear'),
    path('movimientos/editar<int:id_movimiento>', views.movimientos_inventario_editar, name='movimientos.editar'),
    path('movimientos/eliminar<int:id_movimiento>', views.movimientos_inventario_eliminar, name='movimientos.eliminar'),
    path('movimientos/editar<int:id_movimiento>', views.movimientos_inventario_editar, name='movimientos.editar'),


]