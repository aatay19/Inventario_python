from django.urls import path
from . import views

app_name = 'control_nino'

urlpatterns = [
    path('', views.lista_control_ninos, name='lista_control_ninos'),
    path('nuevo/', views.crear_control_nino, name='crear_control_nino'),
    path('eliminar/<int:pk>/', views.eliminar_control_nino, name='eliminar_control_nino'),
    path('salida/<int:pk>/', views.marcar_salida, name='marcar_salida'),
    path('deshacer-salida/<int:pk>/', views.deshacer_salida, name='deshacer_salida'),
    path('reporte/', views.reporte_control_ninos, name='reporte_control_ninos'),
    path('reporte/pdf/', views.reporte_control_ninos_pdf, name='reporte_control_ninos_pdf'),
    path('reporte/nino/<int:pk>/pdf/', views.reporte_control_nino_pdf, name='reporte_control_nino_pdf'),
    path('reporte/fiesta/<int:pk>/pdf/', views.reporte_fiesta_pdf, name='reporte_fiesta_pdf'),
    path('historial/', views.historial_control_ninos, name='historial_control_ninos'),
    path('estadisticas/', views.estadisticas_control_ninos, name='estadisticas_control_ninos'),

    # Fiestas
    path('fiesta/nueva/', views.crear_fiesta, name='crear_fiesta'),
    path('fiesta/<int:pk>/', views.detalle_fiesta, name='detalle_fiesta'),
    path('fiesta/iniciar/<int:pk>/', views.iniciar_fiesta, name='iniciar_fiesta'),
    path('fiesta/salida/<int:pk>/', views.marcar_salida_fiesta, name='marcar_salida_fiesta'),
    path('fiesta/deshacer-salida/<int:pk>/', views.deshacer_salida_fiesta, name='deshacer_salida_fiesta'),
    path('fiesta/agregar-tiempo/<int:pk>/', views.agregar_tiempo_fiesta, name='agregar_tiempo_fiesta'),
    path('fiesta/eliminar/<int:pk>/', views.eliminar_fiesta, name='eliminar_fiesta'),
]
