from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
  
urlpatterns = [

    path('accounts/login/', auth_views.LoginView.as_view(template_name='login.html', redirect_authenticated_user=True), name='login'),
    path('logout/', views.custom_logout, name='logout'),
    path('', views.index, name='index'),
    
    #proveedores urls
    path('proveedores/', views.proveedores_index, name='proveedores.index'),
    path('proveedores/crear', views.proveedores_crear, name='proveedores.crear'),
    path('proveedores/editar<int:id>', views.proveedores_editar, name='proveedores.editar'),
    path('proveedores/eliminar<int:id>', views.proveedores_eliminar, name='proveedores.eliminar'),
    path('proveedores/editar/<int:id>', views.proveedores_editar, name='proveedores.editar'),
    path('proveedores/importar', views.proveedores_importar, name='proveedores.importar'),
    
    # Pedidos / Compras urls
    path('compras/', views.compras_seleccionar_proveedor, name='compras.index'),
    path('compras/nuevo/<int:proveedor_id>', views.compras_form_pedido, name='compras.nuevo'),
    path('compras/confirmar/', views.compras_confirmar, name='compras.confirmar'),
    path('compras/procesar/', views.compras_procesar, name='compras.procesar'),
    path('compras/exportar/pdf', views.exportar_pedido_pdf, name='compras.exportar_pdf'),
    path('compras/pedido/pdf/<int:pedido_id>', views.exportar_pedido_unico_pdf, name='compras.pedido_pdf'),
    path('compras/pedido/editar/<int:pedido_id>', views.compras_editar_pedido, name='compras.editar'),
    path('compras/eliminar_pedido/', views.compras_eliminar_pedido, name='compras.eliminar_pedido'),
    path('compras/historial/eliminar_todo/', views.compras_eliminar_todo_historial, name='compras.eliminar_todo_historial'),

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
    path('inventario/exportar/excel', views.exportar_inventario_excel, name='inventario.exportar_excel'),
    path('inventario/exportar/pdf', views.exportar_inventario_pdf, name='inventario.exportar_pdf'),
    path('inventario/importar', views.inventario_importar, name='inventario.importar'),

    # MovimientosInventario urls
    path('movimientos/', views.movimientos_inventario_index, name='movimientos.index'),
    path('movimientos/crear', views.movimientos_inventario_crear, name='movimientos.crear'),
    path('movimientos/editar<int:id_movimiento>', views.movimientos_inventario_editar, name='movimientos.editar'),
    path('movimientos/eliminar<int:id_movimiento>', views.movimientos_inventario_eliminar, name='movimientos.eliminar'),
    path('movimientos/salida', views.movimientos_salida_form, name='movimientos.salida'),
    path('movimientos/salida/confirmar', views.movimientos_salida_confirmar, name='movimientos.salida_confirmar'),
    path('movimientos/salida/procesar', views.movimientos_salida_procesar, name='movimientos.salida_procesar'),
    path('movimientos/entrada', views.movimientos_entrada_form, name='movimientos.entrada'),
    path('movimientos/entrada/confirmar', views.movimientos_entrada_confirmar, name='movimientos.entrada_confirmar'),
    path('movimientos/entrada/procesar', views.movimientos_entrada_procesar, name='movimientos.entrada_procesar'),
    path('movimientos/historial/pedidos', views.movimientos_historial_pedidos, name='movimientos.historial_pedidos'),
    path('movimientos/historial/salidas', views.movimientos_historial_salidas, name='movimientos.historial_salidas'),
    path('movimientos/historial/entradas', views.movimientos_historial_entradas, name='movimientos.historial_entradas'),
    path('movimientos/historial/exportar/pdf', views.exportar_lote_pdf, name='movimientos.exportar_lote_pdf'),
    path('movimientos/lote/eliminar', views.movimientos_lote_eliminar, name='movimientos.lote_eliminar'),
    path('movimientos/lote/editar/<str:lote_id>', views.movimientos_lote_editar, name='movimientos.lote_editar'),

    #usuarios urls
    path('usuarios/', views.usuarios_index, name='usuarios.index'),
    path('usuarios/crear', views.usuarios_crear, name='usuarios.crear'),
    path('usuarios/editar<int:id>', views.usuarios_editar, name='usuarios.editar'),
    path('usuarios/eliminar<int:id>', views.usuarios_eliminar, name='usuarios.eliminar'),
    path('usuarios/editar/<int:id>', views.usuarios_editar, name='usuarios.editar'),

    # Backup
    path('configuracion/backup', views.realizar_copia_seguridad, name='backup'),
    path('inventario/buscar_ajax/', views.buscar_productos_ajax, name='inventario.buscar_ajax'),
]