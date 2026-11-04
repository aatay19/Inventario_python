from django.urls import path

from . import views

app_name = "cuadre_caja"

urlpatterns = [
    path("", views.index, name="index"),
    path(
        "departamentos/nuevo/",
        views.departamento_crear,
        name="departamento_crear",
    ),
    path(
        "departamento/<slug:slug>/",
        views.departamento_detalle,
        name="departamento_detalle",
    ),
    path(
        "departamento/<slug:slug>/cajas/nueva/",
        views.caja_crear,
        name="caja_crear",
    ),
    path("caja/<int:caja_id>/cerrar/", views.cerrar_caja, name="cerrar_caja"),
    path("cierre/<int:cierre_id>/", views.cierre_detalle, name="cierre_detalle"),
    path("historial/", views.historial, name="historial"),
    path("reportes/", views.reportes, name="reportes"),
    path("reporte/dia/<str:fecha_str>/", views.reporte_dia, name="reporte_dia"),
    path("reporte/semanal/", views.reporte_semanal, name="reporte_semanal"),
    path("reporte/mensual/", views.reporte_mensual, name="reporte_mensual"),
    path("reporte/anual/", views.reporte_anual, name="reporte_anual"),
]
