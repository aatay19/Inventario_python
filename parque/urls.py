from django.urls import path
from . import views

app_name = 'parque'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Eventos CRUD
    path('eventos/', views.lista_eventos, name='lista_eventos'),
    path('eventos/nuevo/', views.crear_evento, name='crear_evento'),
    path('eventos/editar/<int:pk>/', views.editar_evento, name='editar_evento'),
    path('eventos/eliminar/<int:pk>/', views.eliminar_evento, name='eliminar_evento'),
    path('eventos/finalizar/<int:pk>/', views.finalizar_evento, name='finalizar_evento'),
    path('eventos/detalle/<int:pk>/', views.detalle_evento, name='detalle_evento'),

    # Productos CRUD
    path('productos/', views.lista_productos, name='lista_productos'),
    path('productos/nuevo/', views.crear_producto, name='crear_producto'),
    path('productos/editar/<int:pk>/', views.editar_producto, name='editar_producto'),
    path('productos/eliminar/<int:pk>/', views.eliminar_producto, name='eliminar_producto'),

    # Combos CRUD
    path('combos/', views.lista_combos, name='lista_combos'),
    path('combos/nuevo/', views.crear_combo, name='crear_combo'),
    path('combos/editar/<int:pk>/', views.editar_combo, name='editar_combo'),
    path('combos/eliminar/<int:pk>/', views.eliminar_combo, name='eliminar_combo'),

    # Brazaletes CRUD
    path('brazaletes/', views.lista_brazaletes, name='lista_brazaletes'),
    path('brazaletes/nuevo/', views.crear_brazalete, name='crear_brazalete'),
    path('brazaletes/editar/<int:pk>/', views.editar_brazalete, name='editar_brazalete'),
    path('brazaletes/eliminar/<int:pk>/', views.eliminar_brazalete, name='eliminar_brazalete'),
]
